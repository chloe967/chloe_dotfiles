# gmail-mcp

Read + draft-only Gmail MCP server. Sibling of `../google-drive` — same shared
token (`~/.config/google-sheets-mcp/token.json`), same "no OAuth flow of its
own" rule, same venv-per-server layout built by `install.sh`.

## Send policy

Per CLAUDE.md: **never send email, only create drafts.** Enforced by never
calling `messages.send`/`drafts.send` anywhere in `server.py`. The
`gmail.compose` scope technically allows sending (Google ships no draft-only
scope), so the no-send guarantee lives in this code — do not add a send tool.

## Tools

- `gmail_search_messages` — Gmail query syntax (`from:`, `after:2026/07/01`, …)
- `gmail_get_message` / `gmail_get_thread` — decoded text bodies, paged
- `gmail_list_labels`, `gmail_list_drafts`
- `gmail_create_draft` — supports threaded replies via `reply_to_message_id`

## Auth

Token must carry `gmail.readonly` + `gmail.compose` on top of the existing
`drive` + `spreadsheets`. If it doesn't, the server fails at startup with a
pointer to:

```bash
python3 ~/git/chloe_dotfiles/mcp-servers/google-reconsent.py
```

That script prints a consent URL (open on any browser, e.g. the Mac), and you
paste the resulting `http://localhost/?code=...` redirect URL back into it.
It merges the new scopes into token.json (backing up the old one first).

The Gmail API must also be enabled in the OAuth client's GCP project
(`trusty-wares-494715-t5`): https://console.cloud.google.com/apis/library/gmail.googleapis.com?project=trusty-wares-494715-t5
If it isn't, the first tool call returns Google's accessNotConfigured error
with the same link.
