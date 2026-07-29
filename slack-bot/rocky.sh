#!/usr/bin/env bash
# Exec wrapper for Rocky (the project-manager Slack bot), run by rocky.service.
#
# Deliberately has NO restart loop: systemd's Restart=always owns supervision,
# and a loop here would hide crashes from it (systemd would only ever see one
# never-exiting bash). run_pm_bot.sh keeps its own while-loop for ad-hoc manual
# runs when you don't want to touch the service.
#
# Started via systemd rather than an @reboot cron line so that a reboot, a crash,
# and an OOM kill all recover the same way. See PROJECT_MANAGER_BOT.md.
set -euo pipefail

DIR="/home/ubuntu/git/chloe_dotfiles/slack-bot"

# PM_SLACK_BOT_TOKEN / PM_SLACK_APP_TOKEN. Not in the unit's Environment= because
# secrets should not be readable via `systemctl show`.
# shellcheck disable=SC1091
source /home/ubuntu/git/chloe_dotfiles/.secrets

cd "$DIR"

# Call the env's interpreter directly instead of `conda activate`. Under systemd
# there is no interactive shell init, so depending on conda.sh being sourceable
# is an extra failure mode we don't need. slack_bolt lives in deeptune311.
exec /home/ubuntu/miniconda3/envs/deeptune311/bin/python \
  "$DIR/project_manager_bot.py"
