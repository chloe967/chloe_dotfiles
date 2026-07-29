#!/usr/bin/env python3
"""Reactive Slack bot: tag it, and it runs the project-manager agent.

This is NOT a cron job. It is a long-running listener that reacts when a user
@-mentions the bot in a channel. Socket Mode is used so the box needs no public
URL or open ports — the script opens an outbound WebSocket to Slack.

Flow for `@project-manager <request>` in a channel the bot is in:
  1. app_mention event arrives over the socket (Bolt auto-acks it).
  2. React with 👀 (eyes) on the mention so the user sees it landed.
  3. A background thread runs the agent headless via `claude -p --agent` and posts the
     result back as a threaded reply. The work runs off the event path because
     it takes minutes.

Requires in the environment (sourced from ~/git/chloe_dotfiles/.secrets):
  PM_SLACK_BOT_TOKEN   xoxb-...  bot token; scopes: app_mentions:read, chat:write,
                                 reactions:write
  PM_SLACK_APP_TOKEN   xapp-...  app-level token; scope: connections:write
These are dedicated to the `codingprojectmanager` app and kept separate from the
global SLACK_BOT_TOKEN (the digest bot + Slack MCP) so those keep their identity
and read scopes. Falls back to SLACK_BOT_TOKEN/SLACK_APP_TOKEN if PM_* are unset.
Install deps once:  pip install slack_bolt

The project-manager agent (.claude/agents/project-manager.md) owns all PM
behavior and knows which MCPs it needs; this file is only the Slack<->agent glue.
Single source of truth stays in the agent, not here.
"""
import os
import re
import subprocess
import threading

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

BOT_TOKEN = os.environ.get("PM_SLACK_BOT_TOKEN") or os.environ["SLACK_BOT_TOKEN"]
APP_TOKEN = os.environ.get("PM_SLACK_APP_TOKEN") or os.environ["SLACK_APP_TOKEN"]
# Absolute path so we don't depend on the launcher's PATH.
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "/home/ubuntu/.local/bin/claude")
RUN_TIMEOUT = int(os.environ.get("PM_BOT_TIMEOUT", "1800"))  # 30 min ceiling
SLACK_MAX = 39000  # Slack hard-caps a message near 40k chars; leave headroom.

app = App(token=BOT_TOKEN)
MENTION_RE = re.compile(r"<@[A-Z0-9]+>")  # strip @-mentions from the request text


def run_agent(request_text, channel, user, thread_ts, client):
    """Run the project-manager agent headless and post the result to the thread."""
    # The request text is the user prompt; the PM behavior lives in the
    # `project-manager` agent (.claude/agents/project-manager.md), loaded via
    # --agent below. The parenthetical is per-invocation context.
    #
    # IMPORTANT: tell the agent NOT to post to Slack itself. Its Slack MCP is
    # authed with the *global* SLACK_BOT_TOKEN (the chloe_daily_digest bot), so
    # anything it posts shows up under that identity. Reading Slack for context
    # is fine; sending is the bot's job so the reply comes from us.
    prompt = (
        f"{request_text}\n\n"
        f"(You are running headless as the backend of a Slack bot, invoked by "
        f"<@{user}> in channel {channel}. Do NOT post to Slack or send any Slack "
        f"message yourself — reading Slack for context is fine, but return your "
        f"report as your final text output only; the bot posts it as itself. "
        f"Keep it concise and formatted for a Slack message.)"
    )
    try:
        # --agent project-manager: run the whole headless session AS the PM
        # agent (its system prompt + Voice). bypassPermissions: no human is here
        # to approve tool calls, and the agent runs gh/Linear/Slack MCP tools.
        # Harden with an --allowedTools allowlist to bound it (see
        # PROJECT_MANAGER_BOT.md).
        proc = subprocess.run(
            [CLAUDE_BIN, "-p", prompt, "--agent", "project-manager",
             "--permission-mode", "bypassPermissions"],
            capture_output=True, text=True, timeout=RUN_TIMEOUT,
        )
        out = proc.stdout.strip() or proc.stderr.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        out = f":warning: project-manager run timed out after {RUN_TIMEOUT}s."
    except Exception as e:  # surface the real error rather than swallowing it
        out = f":warning: project-manager run failed: {e}"

    client.chat_postMessage(
        channel=channel, thread_ts=thread_ts,
        text=out[:SLACK_MAX], mrkdwn=True, unfurl_links=False,
    )


@app.event("app_mention")
def handle_mention(event):
    # Strip the bot's own @-mention; the rest is the request/scope.
    request_text = MENTION_RE.sub("", event.get("text", "")).strip()
    channel = event["channel"]
    user = event.get("user", "")
    # Thread under the mention if it's already in a thread, else start one on it.
    thread_ts = event.get("thread_ts") or event["ts"]

    # Acknowledge with a 👀 reaction on the mention itself instead of a message.
    # Needs the reactions:write scope. Don't let an ack failure kill the run.
    try:
        app.client.reactions_add(channel=channel, timestamp=event["ts"], name="eyes")
    except Exception as e:
        print(f"[pm-bot] reactions_add failed: {e}", flush=True)

    threading.Thread(
        target=run_agent,
        args=(request_text, channel, user, thread_ts, app.client),
        daemon=True,
    ).start()


if __name__ == "__main__":
    print("[pm-bot] connecting to Slack via Socket Mode...", flush=True)
    SocketModeHandler(app, APP_TOKEN).start()
