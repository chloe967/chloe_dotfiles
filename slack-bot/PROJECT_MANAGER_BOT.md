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

```bash
bash ~/git/chloe_dotfiles/slack-bot/run_pm_bot.sh   # foreground; Ctrl-C to stop
# or detached:
nohup bash ~/git/chloe_dotfiles/slack-bot/run_pm_bot.sh \
  >> ~/git/chloe_dotfiles/slack-bot/pm_bot.log 2>&1 &
# survive reboots (optional): add the @reboot line from run_pm_bot.sh via `crontab -e`
```

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
