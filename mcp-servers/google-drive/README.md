# google-drive-mcp

Read-only Google Drive + Docs access for Claude Code.

## Why this is separate from the Sheets server

`~/git/claude-google-sheets-mcp` is a clone of a third-party repo
(github.com/ringo380/claude-google-sheets-mcp). Its Drive tools are hard-filtered
to `mimeType='application/vnd.google-apps.spreadsheet'`, so they can't see Docs,
folders, or PDFs. Adding tools there would mean carrying a permanent local diff
and hitting a merge conflict on every upstream pull, so Drive/Docs live here
instead and that clone stays pristine.

## Tools

| Tool | Purpose |
| --- | --- |
| `drive_list_files` | List files by name / type / folder / modified date |
| `drive_search` | Full-text search across file **contents**, not just names |
| `drive_get_file` | Metadata for one file: type, size, owner, parent folder, link |
| `drive_read_file` | Read text. Docs/Slides export to markdown or plain; Sheets to CSV; text files read directly |

Shared drives (`Deeptune Data Operations`, `[External] Deeptune Customers`) are
included by default. Without Drive's `includeItemsFromAllDrives`/`corpora=allDrives`
flags the API silently returns My Drive only, which reads as "no results" rather
than as an error.

## Auth

There is no OAuth flow here on purpose. This server only reads the token that
`claude-google-sheets-mcp`'s setup wizard produces, so exactly one component
owns credential bootstrap and there is one token on disk:

```
~/.config/google-sheets-mcp/token.json      # override with GOOGLE_CREDENTIALS_DIR
```

If that token is missing, re-create it once with:

```bash
~/git/claude-google-sheets-mcp/venv/bin/python -m claude_google_sheets.server --setup
```

The token already carries `drive.readonly`, so **no new consent is needed** to
use this server. Refresh happens automatically and the refreshed token is
written back for the sheets server to reuse.

## Read-only guarantee

Two independent reasons this cannot modify Drive:

1. It requests only the `drive.readonly` scope. (The sheets server's scope list
   was deliberately narrowed to drop full `drive` and `drive.file`; that intent
   is preserved here.)
2. No mutating Drive API method is called anywhere in `server.py`.

Sheet **writes** are still possible, but only through the separate
`google-sheets-mcp` server, which holds the `spreadsheets` scope.

## Known limits

- Google Sheets export as CSV of the **first tab only**. That's a Drive export
  limitation. Use `google-sheets-mcp`'s `read_range` for real spreadsheet work.
- No text extraction from PDFs, images, video, or Office binaries. The server
  says so explicitly rather than returning garbage.
- Markdown export runs several times longer than plain text for the same doc
  (the Deeptune master guide is 276k chars as markdown vs 51k as plain), so
  `drive_read_file` pages by default and reports the next offset.

## Install

Handled by `install.sh`, which builds the venv from `requirements.txt` and then
registers `.claude/mcp/google-drive-mcp.json`.
