#!/bin/bash
# reflection-watcher.sh — Background agent that watches Chloe's Obsidian
# reflections and improves Claude's skills/config based on what it finds.
#
# Usage: runs in a tmux session. Launch with:
#   tmux new-session -d -s watcher 'bash ~/git/chloe_dotfiles/reflection-watcher.sh'
# Attach with:
#   tmux attach -t watcher

set -uo pipefail

WATCH_DIR="$HOME/git/obsidian/chloe"
CLAUDE_NOTES="$HOME/git/obsidian/claude"
LOG="$CLAUDE_NOTES/improvement_notes/watcher_log.md"
POLL_INTERVAL=120   # seconds between checks
DEBOUNCE=30         # seconds to wait after detecting changes before acting
LAST_CHECK="/tmp/.reflection-watcher-ts"

mkdir -p "$(dirname "$LOG")"
touch "$LAST_CHECK"

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" >> "$LOG"
    echo "$msg"
}

log "--- Reflection watcher started ---"
log "Watching: $WATCH_DIR"
log "Poll interval: ${POLL_INTERVAL}s | Debounce: ${DEBOUNCE}s"
log "Model: sonnet | Log: $LOG"

while true; do
    sleep "$POLL_INTERVAL"

    # Find .md files modified since last check
    changed=$(find "$WATCH_DIR" -name "*.md" -newer "$LAST_CHECK" -type f 2>/dev/null || true)
    touch "$LAST_CHECK"

    [ -z "$changed" ] && continue

    # Debounce: wait, then scoop up any additional changes
    log "Changes detected, debouncing ${DEBOUNCE}s..."
    sleep "$DEBOUNCE"
    more=$(find "$WATCH_DIR" -name "*.md" -newer "$LAST_CHECK" -type f 2>/dev/null || true)
    if [ -n "$more" ]; then
        changed="$changed"$'\n'"$more"
        touch "$LAST_CHECK"
    fi

    files=$(echo "$changed" | sort -u | head -10)
    count=$(echo "$files" | wc -l | tr -d ' ')
    log "Processing $count changed file(s):"
    echo "$files" | while read -r f; do log "  $(basename "$f")"; done

    prompt="You are a background reflection watcher for Chloe Loughridge's Claude Code setup.
Working directory: $HOME/git/chloe_dotfiles

These Obsidian files were just modified:
$(echo "$files" | sed 's/^/- /')

Your job:
1. Read each changed file.
2. Look for: ideas for improving skills or tools, feedback on what's working or not, process insights, things that feel stale in CLAUDE.md, workflow observations.
3. If you find something clearly actionable with strong evidence, make a targeted update. Be very selective — most of the time the right action is to just take notes.
4. Append a brief entry to ~/git/obsidian/claude/improvement_notes/watcher_log.md summarizing what you found and what (if anything) you changed.

Selectivity hierarchy:
- Freely: update your own notes in ~/git/obsidian/claude/ (daily_logs, improvement_notes, mcp_notes)
- High bar + explain why: modify skills in ~/git/chloe_dotfiles/.claude/skills/
- Highest bar: modify ~/git/chloe_dotfiles/.claude/CLAUDE.md (only clearly stale info)

Rules:
- Do NOT create new skills or MCPs unless there is evidence of repeated need across multiple days.
- Do NOT touch work repos (gym, etc).
- Do NOT post to Slack, send emails, or take any externally-visible action.
- Keep changes minimal and targeted. When in doubt, just take notes.
- Be concise. Act, then exit."

    log "Invoking Claude (sonnet)..."
    if env -u CLAUDECODE claude --model sonnet --dangerously-skip-permissions -p "$prompt" >> "$LOG" 2>&1; then
        log "Cycle complete."
    else
        log "Claude exited with error (code $?)."
    fi

    log "---"
done
