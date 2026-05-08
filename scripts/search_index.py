#!/usr/bin/env python3
"""
search_index.py — Search the cached skill index by keyword query.

Usage:
  python search_index.py --query "unit testing python" [--top 5]
  python search_index.py --list-all

Prints JSON array of top matching skills to stdout.
Prints an empty array if no skills match; use --list-all to browse all skills.
"""

import os
import sys
import json
import argparse
import urllib.request
import urllib.error

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
INDEX_REPO = os.environ.get("INDEX_REPO", "")
GITHUB_BASE_URL = os.environ.get("GITHUB_BASE_URL", "https://github.com").rstrip("/")

if GITHUB_BASE_URL == "https://github.com":
    GITHUB_RAW_URL = "https://raw.githubusercontent.com"
else:
    GITHUB_RAW_URL = f"{GITHUB_BASE_URL}/raw"


def fetch_index() -> dict | None:
    url = f"{GITHUB_RAW_URL}/{INDEX_REPO}/main/index/skills.json"
    req = urllib.request.Request(url, headers={"Authorization": f"token {GITHUB_TOKEN}"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.HTTPError, json.JSONDecodeError):
        return None


def score_skill(skill: dict, keywords: list[str]) -> int:
    """Simple keyword overlap score against searchable fields."""
    text = " ".join([
        skill.get("name", ""),
        skill.get("description", ""),
        skill.get("summary", ""),
        " ".join(skill.get("tags", [])),
    ]).lower()

    return sum(1 for kw in keywords if kw in text)


def main():
    if not GITHUB_TOKEN:
        print("WARNING: GITHUB_TOKEN is not set; using unauthenticated access (strict rate limits)", file=sys.stderr)

    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=False, default="", help="Search query")
    parser.add_argument("--top", type=int, default=5, help="Number of results")
    parser.add_argument("--list-all", action="store_true", help="List all skills, no filtering")
    args = parser.parse_args()

    index = fetch_index()
    if not index:
        print(json.dumps({"error": "Could not fetch index", "skills": []}))
        sys.exit(1)

    skills = index.get("skills", [])

    if args.list_all or not args.query.strip():
        # Return all skills sorted alphabetically
        result = sorted(skills, key=lambda s: s.get("name", ""))
        print(json.dumps(result[:50]))  # Cap at 50
        return

    keywords = args.query.lower().split()
    scored = [(score_skill(s, keywords), s) for s in skills]
    scored.sort(key=lambda x: x[0], reverse=True)

    matched = [s for score, s in scored if score > 0]
    # No fallback to all-skills: an empty result means nothing matched.
    # The caller should report this and offer --list-all or a refresh.
    print(json.dumps(matched[:args.top]))


if __name__ == "__main__":
    main()
