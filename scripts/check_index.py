#!/usr/bin/env python3
"""
check_index.py — Check how old the skill index is.

Exits with:
  0  if index is fresh (age < INDEX_MAX_AGE_SECONDS)
  1  if index is stale or missing

Prints age in seconds to stdout.
"""

import os
import sys
import datetime
import urllib.request
import urllib.error
import json

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
INDEX_REPO = os.environ.get("INDEX_REPO", "")  # e.g. "my-org/skill-index"
INDEX_MAX_AGE = int(os.environ.get("INDEX_MAX_AGE_SECONDS", "3600"))


def get_timestamp() -> str | None:
    url = f"https://raw.githubusercontent.com/{INDEX_REPO}/main/index/timestamp.txt"
    req = urllib.request.Request(url, headers={"Authorization": f"token {GITHUB_TOKEN}"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode().strip()
    except urllib.error.HTTPError:
        return None


def main():
    if not INDEX_REPO:
        print("ERROR: INDEX_REPO not set", file=sys.stderr)
        sys.exit(1)

    ts_str = get_timestamp()
    if not ts_str:
        print("0")  # No timestamp → treat as maximally stale
        sys.exit(1)

    try:
        ts = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        print("0")
        sys.exit(1)

    now = datetime.datetime.now(datetime.timezone.utc)
    age_seconds = int((now - ts).total_seconds())
    print(age_seconds)

    if age_seconds >= INDEX_MAX_AGE:
        sys.exit(1)  # Stale
    sys.exit(0)  # Fresh


if __name__ == "__main__":
    main()
