# slack-bot — daily EOD digest

Reads a Slack channel, summarizes the last 24h with Claude, posts the digest to another channel. Runs via system cron.

## Current configuration

- **Source (read):** `#team-code-delivery` (`C0BCYRA8F17`)
- **Destination (post):** `#team-code` (`C0APTUQT0AK`)
- **Schedule:** daily at `3 23 * * *` UTC = **7:03pm US Eastern (EDT)**
- **Bot identity:** `chloe_daily_digest` (Deeptune workspace, `T03DY614WAU`)

## Files

- `fetch_channel.py <channel_id> [hours]` — prints a readable transcript (resolves usernames, includes threads, paginates). Reads `SLACK_BOT_TOKEN` from env.
- `post_message.py <channel_id> [--thread <parent_ts>]` — posts stdin to a channel as Slack mrkdwn. Prints the posted message's `ts` to stdout (for threading); diagnostics to stderr.
- `daily_digest.sh` — the cron entrypoint: fetch → `claude -p` summarize → post. Logs to `digest.log`; cron stdout/stderr go to `cron.log`.

## Post format

Each run posts a one-line header **`delivery daily update`** to `#team-code`,
then the full digest as a **threaded reply** beneath it (keeps the channel
clean). Handled by the `post_threaded` helper in `daily_digest.sh`.

## Token

`SLACK_BOT_TOKEN` (a `xoxb-` bot token) lives in `~/git/chloe_dotfiles/.secrets`.
Required bot scopes: `channels:history`, `channels:read`, `groups:history`,
`groups:read`, `users:read`, `chat:write`. The bot must be **invited to both
channels** (they're private). Add via the channel's Integrations → Add an App.

## Operating notes

- **Run manually:** `bash ~/git/chloe_dotfiles/slack-bot/daily_digest.sh`
- **Dry run (no post):** run `fetch_channel.py` and pipe to `claude -p` yourself.
- **DST caveat:** the cron is pinned to 23:03 UTC. That's 7:03pm Eastern during
  daylight time (EDT). When US DST ends (~Nov 2), 7pm Eastern becomes 00:03 UTC;
  shift the crontab hour to `3 0 * * *` to keep it at 7pm local, or switch to
  `CRON_TZ=America/New_York` if the cron daemon supports it.
- **Slack `oldest` gotcha:** `conversations.history` returns 0 messages if
  `oldest` is a float with decimals — it must be an integer (handled in
  `fetch_channel.py`).
- **Secrets safety:** `daily_digest.sh` instructs Claude to never echo API keys
  or tokens found in the transcript into the digest.

## Change the channels / schedule

Edit the channel IDs at the top of `daily_digest.sh`, and the cron line via
`crontab -e`.
