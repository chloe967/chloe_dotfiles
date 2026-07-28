#!/usr/bin/env python3
"""Post a message to a Slack channel, optionally as a threaded reply.

Usage:
    python3 post_message.py <channel_id> < message.txt
    python3 post_message.py <channel_id> --thread <parent_ts> < reply.txt
    echo "hi" | python3 post_message.py <channel_id>

Reads SLACK_BOT_TOKEN from the environment and the message body from stdin.
On success, prints the posted message's ts to stdout (nothing else), so callers
can capture it to thread replies. Diagnostics go to stderr.
"""
import os
import sys
import json
import urllib.request
import urllib.parse

API = "https://slack.com/api/chat.postMessage"
TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")


def main():
    if not TOKEN:
        sys.exit("SLACK_BOT_TOKEN not set in environment")
    if len(sys.argv) < 2:
        sys.exit("usage: post_message.py <channel_id> [--thread <parent_ts>] < message.txt")
    channel = sys.argv[1]

    thread_ts = None
    if len(sys.argv) >= 4 and sys.argv[2] == "--thread":
        thread_ts = sys.argv[3]

    text = sys.stdin.read().strip()
    if not text:
        sys.exit("refusing to post: empty message body on stdin")

    fields = {
        "channel": channel,
        "text": text,
        "unfurl_links": "false",
        "mrkdwn": "true",
    }
    if thread_ts:
        fields["thread_ts"] = thread_ts

    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        API, data=data,
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as r:
        d = json.load(r)
    if not d.get("ok"):
        sys.exit(f"chat.postMessage error: {d.get('error')}")
    print(f"posted ok: channel={d.get('channel')} ts={d.get('ts')}", file=sys.stderr)
    # stdout = just the ts, for capture
    print(d.get("ts"))


if __name__ == "__main__":
    main()
