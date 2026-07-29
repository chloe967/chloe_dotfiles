# project-manager Slack bot

Tag the bot in a channel and it runs the `project-manager` agent, then posts the
result back in-thread. Reactive (Socket Mode), not a cron.

- `project_manager_bot.py` — the reactive listener (`app_mention` → `claude -p`).
- `run_pm_bot.sh` — keepalive launcher (sources secrets, activates env, restarts
  on crash). This is the process you keep running.

## Architecture in one line

`@bot ...` → `app_mention` over Socket Mode → background `claude -p "..." --agent project-manager` → reply in thread.
Socket Mode = outbound WebSocket, so this box needs no public URL or open port.

## Slack app setup (one-time, in the browser)

1. **Create the app** at <https://api.slack.com/apps> → *Create New App* → *From
   scratch* → pick the Deeptune workspace (`T03DY614WAU`).
2. **Enable Socket Mode**: *Settings → Socket Mode → Enable*. This generates an
   **app-level token** (`xapp-...`) with scope `connections:write`. Copy it.
3. **Bot scopes**: *Features → OAuth & Permissions → Scopes → Bot Token Scopes*,
   add: `app_mentions:read`, `chat:write`, `reactions:write` (and `channels:history`,
   `groups:history` if you also want the earlier slash-command/digest flows).
4. **Event Subscriptions**: *Features → Event Subscriptions → Enable*. Under
   *Subscribe to bot events* add **`app_mention`**. (No Request URL needed —
   Socket Mode delivers events.)
5. **Install** to the workspace: *OAuth & Permissions → Install to Workspace*.
   Copy the **bot token** (`xoxb-...`).
6. **Invite the bot** to each channel you'll tag it in: `/invite @your-bot-name`.

## Machine setup (one-time, here)

```bash
pip install slack_bolt          # into the deeptune311 env
# The codingprojectmanager app's tokens live in .secrets as dedicated vars,
# kept separate from the global SLACK_BOT_TOKEN (digest bot + Slack MCP):
#   export PM_SLACK_BOT_TOKEN=xoxb-...   (app_mentions:read, chat:write)
#   export PM_SLACK_APP_TOKEN=xapp-...   (connections:write)
```

## Run it

Rocky runs as a systemd **user** service (`rocky.service`, installed by
`install.sh`). Being a resident listener, it needs supervision that survives
reboots, crashes and OOM kills, which an `@reboot` cron line does not give you.

```bash
systemctl --user status rocky      # is he up?
systemctl --user restart rocky     # bounce after editing the bot or the agent
journalctl --user -u rocky -f      # live logs (the log of record)
```

Requires lingering (`loginctl enable-linger $USER`, done by `install.sh`).
Without it the user manager dies with your last SSH session and nothing comes
back at boot. Check with `loginctl show-user $USER -p Linger`.

For an ad-hoc run without touching the service, `run_pm_bot.sh` still works
(foreground, own restart loop, logs to `pm_bot.log`). Stop the service first or
you get two listeners double-replying to every mention.

Then in Slack: `@your-bot check acme/api and the Platform team for the last week`.

## Notes / tradeoffs

- **Permissions**: the headless run uses `--permission-mode bypassPermissions`
  because no human is present to approve tool calls. To bound what the bot can
  do, replace it with an allowlist, e.g.
  `--allowedTools "Bash(gh:*)" "mcp__linear__*" "mcp__slack__*" Read`.
- **The bot posts as itself** (an AI assistant), never as the person who tagged
  it — matches the identity rule in the agent.
- **Long runs**: work happens in a background thread with a 30-min ceiling
  (`PM_BOT_TIMEOUT`); the result is a threaded reply so channels stay clean.
- **Slash command instead of a tag?** Same backend — swap the `@app.event
  ("app_mention")` handler for `@app.command("/project-manager")` (add a
  *Slash Commands* entry + the `commands` scope in the app config).
