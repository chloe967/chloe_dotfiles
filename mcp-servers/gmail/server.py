"""Read + draft-only Gmail MCP server.

Sibling of the google-drive server: same design, same shared token
(~/.config/google-sheets-mcp/token.json), no OAuth flow of its own. If the
token is missing or lacks Gmail scopes, we fail loudly at startup with a
pointer to the re-consent helper instead of starting a second, divergent
OAuth flow.

Send policy, per CLAUDE.md: NEVER send email. Only search/read and create
drafts. Two layers of enforcement:
  1. No tool here calls users.messages.send or users.drafts.send. There is
     no code path to send.
  2. The only write scope requested is gmail.compose. Note that Google's
     gmail.compose scope technically permits drafts.send at the API level
     (there is no draft-only scope), so layer 1 is the one that matters --
     do not add a send handler to this file.
"""

import asyncio
import base64
import html
import json
import logging
import os
import re
import sys
from email.message import EmailMessage
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# stdout is the MCP transport, so logs MUST go to stderr.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("gmail-mcp")

# Shared with claude-google-sheets-mcp and google-drive-mcp on purpose.
CREDENTIALS_DIR = os.path.expanduser(
    os.getenv("GOOGLE_CREDENTIALS_DIR", "~/.config/google-sheets-mcp")
)
TOKEN_PATH = os.path.join(CREDENTIALS_DIR, "token.json")

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

RECONSENT_HINT = (
    "The shared Google token is missing Gmail scopes. Re-consent once with:\n"
    "  python3 ~/git/chloe_dotfiles/mcp-servers/google-reconsent.py\n"
    "(prints a URL to open in a browser; paste the localhost redirect back)"
)

DEFAULT_RESULTS = 20
MAX_RESULTS = 100
DEFAULT_MAX_CHARS = 20_000

app = Server("gmail-mcp")
_credentials: Credentials | None = None
_gmail = None


def _get_gmail():
    """Build (and memoize) the Gmail client, refreshing the token if stale."""
    global _credentials, _gmail

    if _gmail is not None and _credentials and _credentials.valid:
        return _gmail

    if not os.path.exists(TOKEN_PATH):
        raise RuntimeError(f"No Google token at {TOKEN_PATH}.\n{RECONSENT_HINT}")

    # Check GRANTED scopes from the file itself. Passing wanted scopes to
    # from_authorized_user_file makes creds.scopes echo the request back, so a
    # check against creds.scopes passes trivially and the failure surfaces
    # later as an opaque invalid_scope error on token refresh.
    with open(TOKEN_PATH) as fh:
        granted = set(json.load(fh).get("scopes") or [])
    if not set(GMAIL_SCOPES) <= granted:
        raise RuntimeError(
            f"Token at {TOKEN_PATH} has scopes {sorted(granted)}.\n{RECONSENT_HINT}"
        )

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, GMAIL_SCOPES)

    if not creds.valid:
        if not (creds.expired and creds.refresh_token):
            raise RuntimeError(
                f"Token at {TOKEN_PATH} is invalid and has no refresh token.\n"
                f"{RECONSENT_HINT}"
            )
        creds.refresh(Request())
        # Persist so the sibling servers benefit too. Best-effort.
        try:
            with open(TOKEN_PATH, "w") as fh:
                fh.write(creds.to_json())
        except OSError as exc:
            logger.warning("Could not persist refreshed token: %s", exc)

    _credentials = creds
    _gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    return _gmail


def _clamp(raw: Any, default: int, ceiling: int) -> int:
    try:
        return max(1, min(int(raw), ceiling))
    except (TypeError, ValueError):
        return default


def _headers(payload: dict) -> dict[str, str]:
    """Lower-cased header name -> value for one message payload."""
    return {
        h["name"].lower(): h.get("value", "")
        for h in payload.get("headers", [])
    }


_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_ANY_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(raw: str) -> str:
    text = _TAG_RE.sub("", raw)
    text = re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", text, flags=re.I)
    text = _ANY_TAG_RE.sub("", text)
    text = html.unescape(text)
    # Marketing mail loves 40 consecutive blank lines.
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _b64_part(part: dict) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data.encode()).decode("utf-8", "replace")


def _walk_body(payload: dict) -> tuple[str, list[str]]:
    """Decode a message payload -> (text, attachment filenames).

    Prefers text/plain parts; falls back to tag-stripped text/html. Attachments
    are reported by name only -- this server deliberately ships no binary
    handling.
    """
    plains: list[str] = []
    htmls: list[str] = []
    attachments: list[str] = []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        if part.get("filename"):
            attachments.append(part["filename"])
            return
        if mime == "text/plain":
            plains.append(_b64_part(part))
        elif mime == "text/html":
            htmls.append(_b64_part(part))
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    if plains:
        return "\n".join(p for p in plains if p), attachments
    if htmls:
        return _strip_html("\n".join(htmls)), attachments
    return "(no text body)", attachments


def _summary_line(msg: dict) -> str:
    h = _headers(msg.get("payload", {}))
    date = h.get("date", "?")
    return (
        f"- id={msg['id']}  thread={msg.get('threadId')}\n"
        f"    from: {h.get('from', '?')}\n"
        f"    to: {h.get('to', '?')}\n"
        f"    date: {date}\n"
        f"    subject: {h.get('subject', '(no subject)')}\n"
        f"    snippet: {msg.get('snippet', '').strip()}"
    )


def _page(text: str, args: dict, header: str) -> str:
    total = len(text)
    offset = max(0, _clamp(args.get("offset") or 0, 0, total or 1) if args.get("offset") else 0)
    limit = _clamp(args.get("max_chars") or DEFAULT_MAX_CHARS, DEFAULT_MAX_CHARS, 200_000)
    chunk = text[offset : offset + limit]
    if offset or total > offset + limit:
        end = offset + len(chunk)
        header += f" - {total} chars total, showing {offset}-{end}"
        if end < total:
            header += f". Next: offset={end}"
    return f"{header}\n\n{chunk}"


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

TOOLS = [
    Tool(
        name="gmail_search_messages",
        description=(
            "Search Gmail with standard Gmail query syntax (from:, to:, "
            "subject:, label:, after:2026/07/01, has:attachment, etc). Returns "
            "message summaries with ids for gmail_get_message/gmail_get_thread."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Gmail search query."},
                "max_results": {
                    "type": "integer",
                    "description": f"1-{MAX_RESULTS}. Default {DEFAULT_RESULTS}.",
                },
                "include_spam_trash": {
                    "type": "boolean",
                    "description": "Also search SPAM and TRASH. Default false.",
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="gmail_get_message",
        description=(
            "Read one email by message id: headers, decoded text body, and "
            "attachment filenames. Long bodies are paged."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "message_id": {"type": "string"},
                "max_chars": {
                    "type": "integer",
                    "description": f"Chars to return. Default {DEFAULT_MAX_CHARS}.",
                },
                "offset": {"type": "integer", "description": "Char offset for paging."},
            },
            "required": ["message_id"],
        },
    ),
    Tool(
        name="gmail_get_thread",
        description=(
            "Read a whole conversation by thread id: every message's headers "
            "and decoded body, oldest first."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "thread_id": {"type": "string"},
                "max_chars": {
                    "type": "integer",
                    "description": f"Chars to return. Default {DEFAULT_MAX_CHARS}.",
                },
                "offset": {"type": "integer", "description": "Char offset for paging."},
            },
            "required": ["thread_id"],
        },
    ),
    Tool(
        name="gmail_list_labels",
        description="List Gmail labels (system + user) with message counts.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="gmail_list_drafts",
        description="List existing drafts with their subjects and recipients.",
        inputSchema={
            "type": "object",
            "properties": {
                "max_results": {
                    "type": "integer",
                    "description": f"1-{MAX_RESULTS}. Default {DEFAULT_RESULTS}.",
                },
            },
        },
    ),
    Tool(
        name="gmail_create_draft",
        description=(
            "Create a DRAFT email (never sends -- this server has no send "
            "capability). To draft a reply, pass reply_to_message_id and the "
            "draft is threaded onto that conversation with proper In-Reply-To "
            "headers; subject is derived from the original unless given."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Comma-separated recipients."},
                "subject": {"type": "string"},
                "body": {"type": "string", "description": "Plain-text body."},
                "cc": {"type": "string", "description": "Comma-separated CC."},
                "bcc": {"type": "string", "description": "Comma-separated BCC."},
                "reply_to_message_id": {
                    "type": "string",
                    "description": "Gmail message id being replied to.",
                },
            },
            "required": ["to", "body"],
        },
    ),
]


def _tool_search(args: dict) -> str:
    gmail = _get_gmail()
    resp = (
        gmail.users()
        .messages()
        .list(
            userId="me",
            q=args["query"],
            maxResults=_clamp(args.get("max_results"), DEFAULT_RESULTS, MAX_RESULTS),
            includeSpamTrash=bool(args.get("include_spam_trash", False)),
        )
        .execute()
    )
    refs = resp.get("messages", [])
    if not refs:
        return f"No messages matching: {args['query']}"

    lines = [f"{len(refs)} message(s) matching: {args['query']}", ""]
    for ref in refs:
        msg = (
            gmail.users()
            .messages()
            .get(
                userId="me",
                id=ref["id"],
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            )
            .execute()
        )
        lines.append(_summary_line(msg))
    if resp.get("resultSizeEstimate", 0) > len(refs):
        lines.append(f"\n(~{resp['resultSizeEstimate']} total; narrow the query or raise max_results)")
    return "\n".join(lines)


def _render_message(msg: dict) -> str:
    h = _headers(msg.get("payload", {}))
    body, attachments = _walk_body(msg.get("payload", {}))
    lines = [
        f"from: {h.get('from', '?')}",
        f"to: {h.get('to', '?')}",
    ]
    if h.get("cc"):
        lines.append(f"cc: {h['cc']}")
    lines += [
        f"date: {h.get('date', '?')}",
        f"subject: {h.get('subject', '(no subject)')}",
        f"labels: {', '.join(msg.get('labelIds', []))}",
    ]
    if attachments:
        lines.append(f"attachments (names only, not downloadable here): {', '.join(attachments)}")
    lines += ["", body]
    return "\n".join(lines)


def _tool_get_message(args: dict) -> str:
    gmail = _get_gmail()
    msg = (
        gmail.users()
        .messages()
        .get(userId="me", id=args["message_id"], format="full")
        .execute()
    )
    header = f"message {msg['id']} (thread {msg.get('threadId')})"
    return _page(_render_message(msg), args, header)


def _tool_get_thread(args: dict) -> str:
    gmail = _get_gmail()
    thread = (
        gmail.users()
        .threads()
        .get(userId="me", id=args["thread_id"], format="full")
        .execute()
    )
    msgs = thread.get("messages", [])
    parts = []
    for i, msg in enumerate(msgs, 1):
        parts.append(f"--- message {i}/{len(msgs)} (id={msg['id']}) ---")
        parts.append(_render_message(msg))
        parts.append("")
    return _page("\n".join(parts), args, f"thread {args['thread_id']}, {len(msgs)} message(s)")


def _tool_list_labels(args: dict) -> str:
    gmail = _get_gmail()
    labels = gmail.users().labels().list(userId="me").execute().get("labels", [])
    labels.sort(key=lambda l: (l.get("type") != "system", l.get("name", "").lower()))
    lines = [f"{len(labels)} label(s)", ""]
    for l in labels:
        lines.append(f"- {l.get('name')}  (id={l.get('id')}, type={l.get('type')})")
    return "\n".join(lines)


def _tool_list_drafts(args: dict) -> str:
    gmail = _get_gmail()
    resp = (
        gmail.users()
        .drafts()
        .list(userId="me", maxResults=_clamp(args.get("max_results"), DEFAULT_RESULTS, MAX_RESULTS))
        .execute()
    )
    drafts = resp.get("drafts", [])
    if not drafts:
        return "No drafts."
    lines = [f"{len(drafts)} draft(s)", ""]
    for d in drafts:
        msg = (
            gmail.users()
            .drafts()
            .get(userId="me", id=d["id"], format="metadata")
            .execute()
            .get("message", {})
        )
        h = _headers(msg.get("payload", {}))
        lines.append(
            f"- draft id={d['id']}  to: {h.get('to', '?')}  "
            f"subject: {h.get('subject', '(no subject)')}"
        )
    return "\n".join(lines)


def _tool_create_draft(args: dict) -> str:
    gmail = _get_gmail()

    mime = EmailMessage()
    mime["To"] = args["to"]
    if args.get("cc"):
        mime["Cc"] = args["cc"]
    if args.get("bcc"):
        mime["Bcc"] = args["bcc"]
    mime.set_content(args["body"])

    thread_id = None
    if args.get("reply_to_message_id"):
        orig = (
            gmail.users()
            .messages()
            .get(
                userId="me",
                id=args["reply_to_message_id"],
                format="metadata",
                metadataHeaders=["Subject", "Message-ID", "References"],
            )
            .execute()
        )
        oh = _headers(orig.get("payload", {}))
        thread_id = orig.get("threadId")
        rfc_id = oh.get("message-id", "")
        if rfc_id:
            mime["In-Reply-To"] = rfc_id
            mime["References"] = f"{oh.get('references', '')} {rfc_id}".strip()
        if not args.get("subject"):
            orig_subject = oh.get("subject", "")
            mime["Subject"] = (
                orig_subject if orig_subject.lower().startswith("re:") else f"Re: {orig_subject}"
            )
    if "Subject" not in mime:
        mime["Subject"] = args.get("subject", "(no subject)")

    payload: dict[str, Any] = {
        "message": {"raw": base64.urlsafe_b64encode(mime.as_bytes()).decode()}
    }
    if thread_id:
        payload["message"]["threadId"] = thread_id

    draft = gmail.users().drafts().create(userId="me", body=payload).execute()
    return (
        f"Draft created (NOT sent): id={draft['id']}\n"
        f"to: {args['to']}\nsubject: {mime['Subject']}\n"
        "Review and send it from the Gmail UI."
    )


HANDLERS = {
    "gmail_search_messages": _tool_search,
    "gmail_get_message": _tool_get_message,
    "gmail_get_thread": _tool_get_thread,
    "gmail_list_labels": _tool_list_labels,
    "gmail_list_drafts": _tool_list_drafts,
    "gmail_create_draft": _tool_create_draft,
}


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    handler = HANDLERS.get(name)
    if handler is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    try:
        # googleapiclient is blocking; keep the event loop free.
        result = await asyncio.to_thread(handler, arguments or {})
        return [TextContent(type="text", text=result)]
    except HttpError as exc:
        # Surface Google's own message: "API not enabled" (accessNotConfigured)
        # includes the exact console URL to click, so pass reason through.
        logger.error("Gmail API error in %s: %s", name, exc)
        return [
            TextContent(
                type="text",
                text=f"Gmail API error ({exc.status_code}) in {name}: {exc.reason}",
            )
        ]
    except RuntimeError as exc:
        logger.error("Config error in %s: %s", name, exc)
        return [TextContent(type="text", text=str(exc))]


async def main() -> None:
    # Fail fast and loudly at startup if creds are unusable.
    _get_gmail()
    logger.info("gmail-mcp ready (read + draft only, token=%s)", TOKEN_PATH)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        logger.error("Server failed: %s", exc)
        sys.exit(1)
