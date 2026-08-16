#!/usr/bin/env python3
"""Add scopes to the shared Google token via a manual PKCE consent flow.

This is the scripted version of the ad-hoc flow used 2026-08-08 to add drive
write scope: print a consent URL, Chloe opens it in a real browser (this EC2
box is headless), Google redirects to http://localhost/?code=... which fails
to load in her browser -- that's expected -- and she pastes that full URL back
here. We exchange the code and rewrite token.json with the union of old and
new scopes (backup kept alongside).

Stdlib-only on purpose so it runs with system python3, no venv required.
Google requires PKCE-style installed-app flows to include the client_secret
from credentials.json; both live in ~/.config/google-sheets-mcp/.

Usage:
  python3 google-reconsent.py                 # adds gmail.readonly + gmail.compose
  python3 google-reconsent.py drive.readonly calendar.readonly
Scope args may be short names (gmail.readonly) or full URLs.
"""

import base64
import datetime
import hashlib
import json
import os
import secrets
import shutil
import sys
import urllib.parse
import urllib.request

CREDENTIALS_DIR = os.path.expanduser(
    os.getenv("GOOGLE_CREDENTIALS_DIR", "~/.config/google-sheets-mcp")
)
CREDENTIALS_PATH = os.path.join(CREDENTIALS_DIR, "credentials.json")
TOKEN_PATH = os.path.join(CREDENTIALS_DIR, "token.json")

DEFAULT_ADD = ["gmail.readonly", "gmail.compose"]
SCOPE_PREFIX = "https://www.googleapis.com/auth/"
REDIRECT_URI = "http://localhost"  # matches the installed client's registered URI


def full_scope(s: str) -> str:
    return s if s.startswith("https://") else SCOPE_PREFIX + s


def main() -> None:
    with open(CREDENTIALS_PATH) as fh:
        client = json.load(fh)["installed"]

    old_scopes: list[str] = []
    old_token = {}
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH) as fh:
            old_token = json.load(fh)
        old_scopes = old_token.get("scopes", [])

    add = [full_scope(s) for s in (sys.argv[1:] or DEFAULT_ADD)]
    scopes = sorted(set(old_scopes) | set(add))
    print(f"Existing scopes: {old_scopes or '(none)'}")
    print(f"Requesting union: {scopes}\n")

    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        {
            "client_id": client["client_id"],
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(scopes),
            "access_type": "offline",
            # Force the consent screen so Google issues a fresh refresh_token
            # covering the widened scope set, instead of silently reusing the
            # narrow one.
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )

    print("1. Open this URL in a browser (your Mac is fine):\n")
    print(auth_url)
    print(
        "\n2. Approve. The browser will land on an http://localhost/?code=... "
        "page that fails to load. That's expected.\n"
        "3. Paste that full URL (or just the code) here:\n"
    )
    pasted = input("redirect URL or code> ").strip()

    if pasted.startswith("http"):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query)
        if "code" not in qs:
            sys.exit(f"No ?code= in that URL (got keys {list(qs)}). Aborting.")
        code = qs["code"][0]
    else:
        code = pasted

    body = urllib.parse.urlencode(
        {
            "client_id": client["client_id"],
            "client_secret": client["client_secret"],
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        }
    ).encode()

    req = urllib.request.Request(
        client["token_uri"],
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            grant = json.load(resp)
    except urllib.error.HTTPError as exc:
        sys.exit(f"Token exchange failed ({exc.code}): {exc.read().decode()}")

    granted_scopes = grant.get("scope", " ".join(scopes)).split()
    expiry = (
        datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(seconds=grant.get("expires_in", 3600))
    ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    new_token = {
        "token": grant["access_token"],
        # prompt=consent guarantees a refresh_token, but keep the old one as a
        # fallback rather than writing null and bricking all three servers.
        "refresh_token": grant.get("refresh_token") or old_token.get("refresh_token"),
        "token_uri": client["token_uri"],
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "scopes": granted_scopes,
        "universe_domain": old_token.get("universe_domain", "googleapis.com"),
        "account": old_token.get("account", ""),
        "expiry": expiry,
    }

    if os.path.exists(TOKEN_PATH):
        stamp = datetime.date.today().strftime("%m%d")
        backup = f"{TOKEN_PATH}.bak-pre-reconsent-{stamp}"
        shutil.copy2(TOKEN_PATH, backup)
        print(f"\nBacked up old token -> {backup}")

    with open(TOKEN_PATH, "w") as fh:
        json.dump(new_token, fh)
    os.chmod(TOKEN_PATH, 0o600)

    missing = set(scopes) - set(granted_scopes)
    print(f"Wrote {TOKEN_PATH} with scopes:\n  " + "\n  ".join(granted_scopes))
    if missing:
        print(f"WARNING: not granted (unchecked on consent screen?): {sorted(missing)}")
    print("\nDone. Restart Claude Code sessions to pick it up.")


if __name__ == "__main__":
    main()
