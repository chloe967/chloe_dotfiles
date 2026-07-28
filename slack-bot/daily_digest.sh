#!/usr/bin/env bash
# Daily EOD digest: read #team-code-delivery, summarize with Claude, post to #team-code.
# Run by system cron. Logs to slack-bot/digest.log.
set -euo pipefail

# cron runs with a minimal PATH; ensure claude + user bins are reachable
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_CHANNEL="C0BCYRA8F17"   # team-code-delivery (read)
DEST_CHANNEL="C0APTUQT0AK"     # team-code (post)
LOOKBACK_HOURS="24"
LOG="$SCRIPT_DIR/digest.log"

log() { echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $*" >>"$LOG"; }

# Post a header line, then the report body as a threaded reply beneath it.
# $1 = path to file holding the report body.
post_threaded() {
  local body_file="$1" parent_ts
  parent_ts="$(printf 'delivery daily update' \
    | python3 "$SCRIPT_DIR/post_message.py" "$DEST_CHANNEL" 2>>"$LOG")"
  if [ -z "$parent_ts" ]; then
    log "ERROR: failed to post header message; aborting"
    exit 1
  fi
  python3 "$SCRIPT_DIR/post_message.py" "$DEST_CHANNEL" --thread "$parent_ts" \
    < "$body_file" >>"$LOG" 2>&1
}

# Load Slack token
set -a; source ~/git/chloe_dotfiles/.secrets; set +a

log "=== run start (lookback ${LOOKBACK_HOURS}h) ==="

TRANSCRIPT="$(python3 "$SCRIPT_DIR/fetch_channel.py" "$SOURCE_CHANNEL" "$LOOKBACK_HOURS")"

# Detect an empty window (header line reports "0 top-level messages")
if echo "$TRANSCRIPT" | grep -q "0 top-level messages"; then
  log "no activity in window; posting short note"
  printf '*EOD — #team-code-delivery*\nNo notable activity today.' > /tmp/eod_report.txt
  post_threaded /tmp/eod_report.txt
  log "=== run done (empty) ==="
  exit 0
fi

PROMPT='You are writing an executive end-of-day Slack digest for an engineering channel. The user message is a raw transcript of the last 24h of #team-code-delivery. Write for a busy leader: short, high-signal, decisions and outcomes only, no play-by-play.

Format (Slack mrkdwn: *bold* not **bold**, - bullets):
- First line: *EOD — #team-code-delivery — <weekday Mon DD>* (infer date; omit if unknown).
- One bold *TL;DR:* sentence capturing the single most important thing.
- *Decisions & progress* — 3-5 bullets max. Each bullet is one tight line: what was decided or shipped, and the owner if clear. Aggregate related chatter into a single bullet; cut the back-and-forth.
- *PRs* — only if notable; one line each: `#NUM — what it does`.
- *Needs a decision* — only genuinely open, important asks; one line each. Omit the section if none.

Hard rules: Output ONLY the report. Aim for under ~120 words total. Favor cutting over including. NEVER include secrets, API keys, tokens, or credentials from the transcript, even if quoted.'

REPORT="$(printf '%s' "$TRANSCRIPT" | timeout 240 claude -p "$PROMPT" 2>>"$LOG")"

if [ -z "${REPORT// /}" ]; then
  log "ERROR: empty report from claude; aborting (not posting)"
  exit 1
fi

printf '%s' "$REPORT" > /tmp/eod_report.txt
post_threaded /tmp/eod_report.txt
log "=== run done (posted) ==="
