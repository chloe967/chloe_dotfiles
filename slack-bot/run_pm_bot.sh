#!/usr/bin/env bash
# Keepalive launcher for the REACTIVE project-manager Slack bot.
#
# This is not a scheduler. The bot reacts to @-mentions in real time, so it must
# stay running to catch them. This wrapper just (re)starts the listener if it
# crashes.
#
# NOT the normal way to run Rocky anymore: rocky.service (systemd user unit)
# supervises him and survives reboots, which this wrapper cannot do on its own.
# Keep this for ad-hoc foreground runs only, and stop the service first
# (`systemctl --user stop rocky`) or two listeners will double-reply to mentions.
set -uo pipefail

DIR="/home/ubuntu/git/chloe_dotfiles/slack-bot"

# SLACK_BOT_TOKEN (xoxb), SLACK_APP_TOKEN (xapp), NOTION_* for the MCPs the
# headless skill invokes.
source /home/ubuntu/git/chloe_dotfiles/.secrets

# Activate the env that has slack_bolt + the claude CLI on PATH.
source /home/ubuntu/miniconda3/etc/profile.d/conda.sh
conda activate deeptune311

cd "$DIR"
while true; do
  echo "[pm-bot] starting $(date -u +%FT%TZ)"
  python project_manager_bot.py
  echo "[pm-bot] exited $? — restarting in 5s"
  sleep 5
done
