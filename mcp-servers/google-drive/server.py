"""Read-only Google Drive + Docs MCP server.

Why this exists as a separate server instead of tools bolted onto
claude-google-sheets-mcp: that repo is a third-party clone
(github.com/ringo380/claude-google-sheets-mcp). Editing it in place means every
`git pull` is a merge conflict, and its Drive tools are deliberately hard-filtered
to `mimeType='application/vnd.google-apps.spreadsheet'`. Keeping Drive/Docs
concerns here means upstream stays pristine and pullable.

Auth is intentionally NOT bootstrapped here. We only *consume* the token that
claude-google-sheets-mcp's `--setup` wizard produces, so there is exactly one
place that runs an OAuth flow and one token on disk. If the token is missing,
we fail loudly with a pointer rather than silently starting a second, divergent
OAuth flow.

Read-only by construction, two independent ways:
  1. The token carries only `drive.readonly` (someone deliberately narrowed the
     sheets server's scopes to drop full `drive` and `drive.file` -- respected here).
  2. We never call a mutating Drive method. There is no code path to write.
Writes to Sheets remain the sheets server's job.
"""

import asyncio
import logging
import os
import sys
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# stdout is the MCP transport, so logs MUST go to stderr. basicConfig defaults
# to stderr; being explicit so a future edit doesn't accidentally corrupt the
# protocol stream with log lines.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("google-drive-mcp")

# Shared with claude-google-sheets-mcp on purpose (see module docstring).
CREDENTIALS_DIR = os.path.expanduser(
    os.getenv("GOOGLE_CREDENTIALS_DIR", "~/.config/google-sheets-mcp")
)
TOKEN_PATH = os.path.join(CREDENTIALS_DIR, "token.json")

# Must be a subset of what token.json was granted, or from_authorized_user_file
# rejects it. `spreadsheets` is present in the token but deliberately omitted
# here: this server has no business writing cells.
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

# Google-native types have no bytes to download; they must be exported to a
# concrete format. Maps native mimeType -> {requested format: export mimeType}.
# Sheets deliberately exports CSV of the FIRST TAB ONLY -- a real limitation of
# Drive's export endpoint, not something we can page around. Use the sheets
# server's read_range for anything multi-tab.
NATIVE_EXPORTS = {
    "application/vnd.google-apps.document": {
        "markdown": "text/markdown",
        "plain": "text/plain",
        "html": "text/html",
    },
    "application/vnd.google-apps.presentation": {
        "markdown": "text/plain",
        "plain": "text/plain",
        "html": "text/html",
    },
    "application/vnd.google-apps.spreadsheet": {
        "markdown": "text/csv",
        "plain": "text/csv",
        "html": "text/html",
    },
}

# Non-native files we're willing to decode as text. Anything else (pdf, images,
# video, office binaries) needs a parser we deliberately don't ship, so we say
# so instead of returning mojibake.
TEXT_PREFIXES = ("text/",)
TEXT_EXACT = {
    "application/json",
    "application/xml",
    "application/x-yaml",
    "application/yaml",
    "application/javascript",
    "application/x-sh",
}

# Drive returns 100 max per page for most queries; keep a sane ceiling so a
# stray page_size=5000 doesn't stall a tool call.
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25

# Docs get big: the Deeptune master guide is ~276k chars as markdown, which
# would swamp a context window in one tool result. Page it instead.
DEFAULT_MAX_CHARS = 40_000
FILE_FIELDS = "id,name,mimeType,modifiedTime,size,webViewLink,parents,owners(displayName,emailAddress),driveId"

app = Server("google-drive-mcp")
_credentials: Credentials | None = None
_drive = None


def _escape(value: str) -> str:
    r"""Escape a user string for embedding in a Drive `q` clause.

    Drive's query language quotes literals with single quotes and escapes with
    backslash. Without this, a file named "Chloe's Notes" turns into a syntax
    error -- or worse, lets a caller inject arbitrary query clauses.
    """
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _get_drive():
    """Build (and memoize) the Drive client, refreshing the token if stale."""
    global _credentials, _drive

    if _drive is not None and _credentials and _credentials.valid:
        return _drive

    if not os.path.exists(TOKEN_PATH):
        raise RuntimeError(
            f"No Google token at {TOKEN_PATH}. This server does not run its own "
            "OAuth flow on purpose. Bootstrap it once with:\n"
            "  ~/git/claude-google-sheets-mcp/venv/bin/python -m "
            "claude_google_sheets.server --setup"
        )

    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds.valid:
        if not (creds.expired and creds.refresh_token):
            raise RuntimeError(
                f"Token at {TOKEN_PATH} is invalid and has no refresh token. "
                "Re-run the sheets server's --setup wizard."
            )
        creds.refresh(Request())
        # Persist the refreshed access token so the sibling sheets server
        # benefits too, and we don't burn a refresh call on every start.
        # Best-effort: a read-only mount shouldn't take the server down.
        try:
            with open(TOKEN_PATH, "w") as fh:
                fh.write(creds.to_json())
        except OSError as exc:
            logger.warning("Could not persist refreshed token: %s", exc)

    _credentials = creds
    _drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return _drive


def _list_kwargs(all_drives: bool) -> dict[str, Any]:
    """Shared-drive plumbing for files().list.

    Chloe's account has real shared drives ('Deeptune Data Operations',
    '[External] Deeptune Customers'). Without these three flags Drive silently
    returns only My Drive, so a search would come back empty for anything that
    lives on a team drive. Defaulting to all drives is the non-surprising choice.
    """
    if not all_drives:
        return {}
    return {
        "includeItemsFromAllDrives": True,
        "supportsAllDrives": True,
        "corpora": "allDrives",
    }


def _fmt_size(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return ""


def _render_files(files: list[dict], header: str) -> str:
    if not files:
        return f"{header}\n\n(no matching files)"
    lines = [header, ""]
    for f in files:
        kind = f.get("mimeType", "").rsplit(".", 1)[-1]
        bits = [f"{f.get('name', '<unnamed>')}"]
        meta = [f"id={f.get('id')}", f"type={kind}"]
        if f.get("modifiedTime"):
            meta.append(f"modified={f['modifiedTime'][:10]}")
        size = _fmt_size(f.get("size"))
        if size:
            meta.append(f"size={size}")
        if f.get("driveId"):
            meta.append("shared_drive=yes")
        owners = f.get("owners") or []
        if owners:
            meta.append(f"owner={owners[0].get('emailAddress', '?')}")
        bits.append("    " + "  ".join(meta))
        lines.append("- " + "\n".join(bits))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------

TOOLS = [
    Tool(
        name="drive_list_files",
        description=(
            "List files in Google Drive with optional filters. Covers all file "
            "types (Docs, Sheets, Slides, PDFs, folders, video) and searches "
            "shared drives by default. Use drive_search for content search."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "name_contains": {
                    "type": "string",
                    "description": "Match files whose name contains this substring.",
                },
                "file_type": {
                    "type": "string",
                    "enum": ["document", "spreadsheet", "presentation", "folder", "pdf", "any"],
                    "description": "Shorthand file-type filter. Default 'any'.",
                },
                "mime_type": {
                    "type": "string",
                    "description": "Exact mimeType filter. Overrides file_type if both given.",
                },
                "folder_id": {
                    "type": "string",
                    "description": "Only list direct children of this folder id.",
                },
                "modified_after": {
                    "type": "string",
                    "description": "RFC3339 date, e.g. 2026-07-01 or 2026-07-01T00:00:00Z.",
                },
                "page_size": {
                    "type": "integer",
                    "description": f"Max results, 1-{MAX_PAGE_SIZE}. Default {DEFAULT_PAGE_SIZE}.",
                },
                "order_by": {
                    "type": "string",
                    "description": "Drive orderBy, e.g. 'modifiedTime desc' (default) or 'name'.",
                },
                "include_shared_drives": {
                    "type": "boolean",
                    "description": "Search shared drives too. Default true.",
                },
            },
        },
    ),
    Tool(
        name="drive_search",
        description=(
            "Full-text search across Google Drive file CONTENTS and names, "
            "including shared drives. Use this when you don't know the filename."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to search for."},
                "file_type": {
                    "type": "string",
                    "enum": ["document", "spreadsheet", "presentation", "folder", "pdf", "any"],
                    "description": "Restrict to a file type. Default 'any'.",
                },
                "page_size": {
                    "type": "integer",
                    "description": f"Max results, 1-{MAX_PAGE_SIZE}. Default {DEFAULT_PAGE_SIZE}.",
                },
                "include_shared_drives": {
                    "type": "boolean",
                    "description": "Search shared drives too. Default true.",
                },
            },
            "required": ["text"],
        },
    ),
    Tool(
        name="drive_get_file",
        description=(
            "Get metadata for one Drive file by id, including its parent folder "
            "names and a web link. Use before reading to check type and size."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "Drive file id."},
            },
            "required": ["file_id"],
        },
    ),
    Tool(
        name="drive_read_file",
        description=(
            "Read a file's text. Google Docs/Slides are exported as markdown or "
            "plain text; Google Sheets export as CSV of the FIRST TAB ONLY (use "
            "the sheets server's read_range for real spreadsheet work). Plain "
            "text/json/yaml/csv files are read directly. Large files are paged: "
            "the result reports total length and how to fetch the next chunk."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "Drive file id."},
                "format": {
                    "type": "string",
                    "enum": ["markdown", "plain", "html"],
                    "description": (
                        "Export format for Google-native files. Default markdown, "
                        "which preserves headings/tables but runs several times "
                        "longer than plain for the same doc."
                    ),
                },
                "max_chars": {
                    "type": "integer",
                    "description": f"Chars to return. Default {DEFAULT_MAX_CHARS}.",
                },
                "offset": {
                    "type": "integer",
                    "description": "Char offset to start from, for paging. Default 0.",
                },
            },
            "required": ["file_id"],
        },
    ),
]

_TYPE_MIMES = {
    "document": "application/vnd.google-apps.document",
    "spreadsheet": "application/vnd.google-apps.spreadsheet",
    "presentation": "application/vnd.google-apps.presentation",
    "folder": "application/vnd.google-apps.folder",
    "pdf": "application/pdf",
}


def _resolve_mime(args: dict) -> str | None:
    if args.get("mime_type"):
        return args["mime_type"]
    return _TYPE_MIMES.get(args.get("file_type") or "any")


def _clamp_page_size(args: dict) -> int:
    raw = args.get("page_size") or DEFAULT_PAGE_SIZE
    try:
        return max(1, min(int(raw), MAX_PAGE_SIZE))
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE


def _tool_list_files(args: dict) -> str:
    drive = _get_drive()
    clauses = ["trashed = false"]

    if args.get("name_contains"):
        clauses.append(f"name contains '{_escape(args['name_contains'])}'")
    mime = _resolve_mime(args)
    if mime:
        clauses.append(f"mimeType = '{_escape(mime)}'")
    if args.get("folder_id"):
        clauses.append(f"'{_escape(args['folder_id'])}' in parents")
    if args.get("modified_after"):
        raw = args["modified_after"].strip()
        # Drive wants full RFC3339; accept a bare date for convenience.
        stamp = f"{raw}T00:00:00Z" if len(raw) == 10 else raw
        clauses.append(f"modifiedTime > '{_escape(stamp)}'")

    query = " and ".join(clauses)
    resp = (
        drive.files()
        .list(
            q=query,
            pageSize=_clamp_page_size(args),
            orderBy=args.get("order_by") or "modifiedTime desc",
            fields=f"files({FILE_FIELDS})",
            **_list_kwargs(args.get("include_shared_drives", True)),
        )
        .execute()
    )
    files = resp.get("files", [])
    return _render_files(files, f"{len(files)} file(s) matching: {query}")


def _tool_search(args: dict) -> str:
    drive = _get_drive()
    text = _escape(args["text"])
    # `fullText contains` covers body content, title, and (for some types)
    # description + OCR'd text, which is why we don't also OR in `name contains`.
    clauses = [f"fullText contains '{text}'", "trashed = false"]
    mime = _resolve_mime(args)
    if mime:
        clauses.append(f"mimeType = '{_escape(mime)}'")

    query = " and ".join(clauses)
    resp = (
        drive.files()
        .list(
            q=query,
            pageSize=_clamp_page_size(args),
            orderBy="modifiedTime desc",
            fields=f"files({FILE_FIELDS})",
            **_list_kwargs(args.get("include_shared_drives", True)),
        )
        .execute()
    )
    files = resp.get("files", [])
    return _render_files(files, f"{len(files)} file(s) containing '{args['text']}'")


def _tool_get_file(args: dict) -> str:
    drive = _get_drive()
    f = (
        drive.files()
        .get(fileId=args["file_id"], fields=FILE_FIELDS, supportsAllDrives=True)
        .execute()
    )

    lines = [
        f"name: {f.get('name')}",
        f"id: {f.get('id')}",
        f"mimeType: {f.get('mimeType')}",
        f"modified: {f.get('modifiedTime')}",
    ]
    size = _fmt_size(f.get("size"))
    if size:
        lines.append(f"size: {size}")
    owners = f.get("owners") or []
    if owners:
        lines.append(f"owner: {owners[0].get('emailAddress')}")
    if f.get("driveId"):
        lines.append("location: shared drive")
    if f.get("webViewLink"):
        lines.append(f"link: {f['webViewLink']}")

    # Resolve parent folder names so results are humanly locatable, not just ids.
    for parent_id in f.get("parents") or []:
        try:
            p = (
                drive.files()
                .get(fileId=parent_id, fields="id,name", supportsAllDrives=True)
                .execute()
            )
            lines.append(f"parent folder: {p.get('name')} (id={p.get('id')})")
        except HttpError as exc:
            # A parent can live in a drive we can't read; that's informative, not fatal.
            lines.append(f"parent folder: <unreadable {parent_id}> ({exc.status_code})")

    mime = f.get("mimeType", "")
    if mime in NATIVE_EXPORTS or mime.startswith(TEXT_PREFIXES) or mime in TEXT_EXACT:
        lines.append("readable: yes, via drive_read_file")
    else:
        lines.append("readable: no text extractor for this type")
    return "\n".join(lines)


def _tool_read_file(args: dict) -> str:
    drive = _get_drive()
    file_id = args["file_id"]
    fmt = args.get("format") or "markdown"

    meta = (
        drive.files()
        .get(fileId=file_id, fields="id,name,mimeType,size", supportsAllDrives=True)
        .execute()
    )
    mime = meta.get("mimeType", "")
    name = meta.get("name", "<unnamed>")

    if mime in NATIVE_EXPORTS:
        export_mime = NATIVE_EXPORTS[mime].get(fmt) or NATIVE_EXPORTS[mime]["plain"]
        raw = drive.files().export(fileId=file_id, mimeType=export_mime).execute()
        note = f"exported as {export_mime}"
    elif mime.startswith(TEXT_PREFIXES) or mime in TEXT_EXACT:
        raw = drive.files().get_media(fileId=file_id, supportsAllDrives=True).execute()
        note = f"raw {mime}"
    else:
        return (
            f"Cannot extract text from '{name}' (mimeType={mime}). This server "
            "ships no parser for binary types like PDF, images, video, or Office "
            "files. Google Docs/Slides/Sheets and plain text formats work."
        )

    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)

    total = len(text)
    try:
        offset = max(0, int(args.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = max(1, int(args.get("max_chars") or DEFAULT_MAX_CHARS))
    except (TypeError, ValueError):
        limit = DEFAULT_MAX_CHARS

    chunk = text[offset : offset + limit]
    header = f"{name} ({note}) - {total} chars total"
    if offset or total > offset + limit:
        end = offset + len(chunk)
        header += f", showing {offset}-{end}"
        if end < total:
            header += f". Next: offset={end}"
    return f"{header}\n\n{chunk}"


HANDLERS = {
    "drive_list_files": _tool_list_files,
    "drive_search": _tool_search,
    "drive_get_file": _tool_get_file,
    "drive_read_file": _tool_read_file,
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
        # googleapiclient is blocking; keep the event loop free so the server
        # stays responsive while a big Doc export is in flight.
        result = await asyncio.to_thread(handler, arguments or {})
        return [TextContent(type="text", text=result)]
    except HttpError as exc:
        # Surface Google's own message: "API not enabled", "insufficient
        # permissions" and "file not found" are all actionable, and collapsing
        # them into a generic failure is what makes these servers hard to debug.
        logger.error("Drive API error in %s: %s", name, exc)
        return [
            TextContent(
                type="text",
                text=f"Drive API error ({exc.status_code}) in {name}: {exc.reason}",
            )
        ]
    except RuntimeError as exc:
        # Auth/config problems we raised ourselves, already phrased for a human.
        logger.error("Config error in %s: %s", name, exc)
        return [TextContent(type="text", text=str(exc))]


async def main() -> None:
    # Fail fast and loudly at startup if creds are unusable, rather than letting
    # every tool call fail one at a time with the same error.
    _get_drive()
    logger.info("google-drive-mcp ready (read-only, token=%s)", TOKEN_PATH)
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
