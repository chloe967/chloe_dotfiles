#!/usr/bin/env bash
# Keepalive launcher for the REACTIVE project-manager Slack bot.
#
# This is not a scheduler. The bot reacts to @-mentions in real time, so it must
# stay running to catch them. This wrapper just (re)starts the listener if it
# crashes. Cron is optional and only used to start it at boot, e.g.:
#   @reboot /home/ubuntu/git/chloe_dotfiles/slack-bot/run_pm_bot.sh >> \
#     /home/ubuntu/git/chloe_dotfiles/slack-bot/pm_bot.log 2>&1
# (Start it by hand the first time; the @reboot line just survives reboots.)
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
