#!/usr/bin/env python3
"""Fetch recent messages from a Slack channel as readable text.

Usage:
    python3 fetch_channel.py <channel_id> [hours_back]

Reads SLACK_BOT_TOKEN from the environment. Resolves user IDs to display
names, includes threaded replies, and handles pagination. Prints a plain-text
transcript to stdout for a Claude session to summarize.
"""
import os
import sys
import json
import time
import urllib.request
import urllib.parse

API = "https://slack.com/api/"
TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
_user_cache = {}


def call(method, params):
    url = API + method + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def user_name(uid):
    if not uid:
        return "unknown"
    if uid in _user_cache:
        return _user_cache[uid]
    d = call("users.info", {"user": uid})
    if d.get("ok"):
        u = d["user"]
        name = u.get("profile", {}).get("display_name") or u.get("real_name") or u.get("name") or uid
    else:
        name = uid
    _user_cache[uid] = name
    return name


def history(channel, oldest):
    msgs, cursor = [], None
    while True:
        # Slack's `oldest` filter misbehaves with fractional floats; floor to int seconds.
        params = {"channel": channel, "oldest": int(oldest), "limit": 200}
        if cursor:
            params["cursor"] = cursor
        d = call("conversations.history", params)
        if not d.get("ok"):
            sys.exit(f"conversations.history error: {d.get('error')}")
        msgs.extend(d.get("messages", []))
        cursor = d.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.5)
    return msgs


def replies(channel, ts):
    d = call("conversations.replies", {"channel": channel, "ts": ts, "limit": 200})
    if not d.get("ok"):
        return []
    return d.get("messages", [])[1:]  # skip the parent


def fmt(m, indent=""):
    who = user_name(m.get("user") or m.get("bot_id"))
    text = (m.get("text") or "").replace("\n", "\n" + indent + "    ")
    return f"{indent}- {who}: {text}"


def main():
    if not TOKEN:
        sys.exit("SLACK_BOT_TOKEN not set in environment")
    if len(sys.argv) < 2:
        sys.exit("usage: fetch_channel.py <channel_id> [hours_back]")
    channel = sys.argv[1]
    hours = float(sys.argv[2]) if len(sys.argv) > 2 else 24.0
    oldest = time.time() - hours * 3600

    msgs = history(channel, oldest)
    msgs.sort(key=lambda m: float(m.get("ts", 0)))

    lines = []
    for m in msgs:
        if m.get("subtype") in ("channel_join", "channel_leave"):
            continue
        lines.append(fmt(m))
        if int(m.get("reply_count", 0)) > 0:
            for r in replies(channel, m["ts"]):
                lines.append(fmt(r, indent="  "))
            time.sleep(0.5)

    print(f"# Transcript: channel {channel}, last {hours:g}h ({len(msgs)} top-level messages)")
    print("\n".join(lines) if lines else "(no messages in window)")


if __name__ == "__main__":
    main()
