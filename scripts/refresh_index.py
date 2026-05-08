#!/usr/bin/env python3
"""
refresh_index.py — Scan GitHub org for SKILL.md files and rebuild the skill index.

Each individual SKILL.md found is indexed as its own skill entry, so a repo with
multiple skills will produce multiple index entries.

Requires:
  GITHUB_TOKEN         Personal access token with repo and read:org scope
  GITHUB_ORG           GitHub org name
  INDEX_REPO           Repo that holds the index (e.g. "my-org/skill-index")
  GITHUB_BASE_URL      Base URL for GitHub (default: https://github.com)
                       For GitHub Enterprise: https://github.example.com

Outputs updated index/skills.json and index/timestamp.txt to INDEX_REPO via git commit.
"""

import os
import sys
import json
import datetime
import subprocess
import tempfile
import urllib.request
import urllib.error
import re

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_ORG = os.environ.get("GITHUB_ORG", "")
INDEX_REPO = os.environ.get("INDEX_REPO", "")
GITHUB_BASE_URL = os.environ.get("GITHUB_BASE_URL", "https://github.com").rstrip("/")

# Derive API and raw content base URLs from GITHUB_BASE_URL
if GITHUB_BASE_URL == "https://github.com":
    GITHUB_API_URL = "https://api.github.com"
    GITHUB_RAW_URL = "https://raw.githubusercontent.com"
else:
    # GitHub Enterprise Server layout
    GITHUB_API_URL = f"{GITHUB_BASE_URL}/api/v3"
    GITHUB_RAW_URL = f"{GITHUB_BASE_URL}/raw"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

_default_branch_cache: dict[str, str] = {}


def gh_get(url: str) -> dict | list | None:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {url}", file=sys.stderr)
        return None


def get_default_branch(repo_full_name: str, repo_obj: dict) -> str:
    """Return the default branch for a repo.

    Uses the branch already present in the code-search result object when available,
    falling back to a dedicated API call so repos not on 'main' are handled correctly.
    """
    if repo_full_name in _default_branch_cache:
        return _default_branch_cache[repo_full_name]

    branch = repo_obj.get("default_branch")
    if not branch:
        data = gh_get(f"{GITHUB_API_URL}/repos/{repo_full_name}")
        branch = (data or {}).get("default_branch", "main")

    _default_branch_cache[repo_full_name] = branch
    return branch


def find_all_skill_files() -> list[dict]:
    """
    Search the org for all files named SKILL.md.
    Returns one item per SKILL.md file found — a repo with multiple SKILL.md files
    (e.g. in subdirectories) will produce multiple items.
    """
    items = []
    page = 1
    while True:
        url = (
            f"{GITHUB_API_URL}/search/code"
            f"?q=filename:SKILL.md+org:{GITHUB_ORG}&per_page=100&page={page}"
        )
        data = gh_get(url)
        if not data or not data.get("items"):
            break
        items.extend(data["items"])
        if len(data["items"]) < 100:
            break
        page += 1

    return items


def fetch_raw_file(repo_full_name: str, file_path: str, branch: str) -> str | None:
    """Fetch raw file content from GitHub."""
    url = f"{GITHUB_RAW_URL}/{repo_full_name}/{branch}/{file_path}"
    req = urllib.request.Request(url, headers={"Authorization": f"token {GITHUB_TOKEN}"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode()
    except urllib.error.HTTPError:
        return None


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from SKILL.md."""
    if not content.startswith("---"):
        return {}, content

    # Match \n--- so that --- appearing inside a quoted value doesn't end the block early
    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    frontmatter_str = content[3:end].strip()
    body = content[end + 4:].strip()

    meta = {}
    lines = frontmatter_str.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line:
            key, _, val = line.partition(":")
            val = val.strip().strip('"').strip("'")
            if val in (">", "|", ">-", "|-", ">+", "|+"):
                # Block scalar: collect subsequent indented lines as the value
                block_lines = []
                i += 1
                while i < len(lines) and (not lines[i] or lines[i][0] in (" ", "\t")):
                    block_lines.append(lines[i].strip())
                    i += 1
                meta[key.strip()] = " ".join(filter(None, block_lines))
                continue
            meta[key.strip()] = val
        i += 1

    return meta, body


def extract_tags(meta: dict, body: str) -> list[str]:
    """Extract tags from frontmatter or body."""
    raw = meta.get("tags", meta.get("tag", ""))
    if raw:
        raw = raw.strip("[]")
        return [t.strip() for t in raw.split(",") if t.strip()]

    match = re.search(r"(?i)^tags?:\s*(.+)$", body, re.MULTILINE)
    if match:
        return [t.strip() for t in match.group(1).split(",") if t.strip()]

    return []


def make_summary(body: str, max_lines: int = 3) -> str:
    """Return first few non-empty, non-heading lines of the body."""
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
            lines.append(stripped)
        if len(lines) >= max_lines:
            break
    return " ".join(lines)


def build_index(skill_files: list[dict]) -> list[dict]:
    """
    Build one index entry per SKILL.md file found.
    A repo with skills/foo/SKILL.md and skills/bar/SKILL.md gets two entries.
    """
    skills = []
    skipped = []
    now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    for item in skill_files:
        repo = item["repository"]
        full_name = repo["full_name"]
        file_path = item["path"]  # e.g. "SKILL.md" or "skills/unit-test/SKILL.md"
        branch = get_default_branch(full_name, repo)

        print(f"  Indexing {full_name}/{file_path} (branch: {branch})...", file=sys.stderr)

        content = fetch_raw_file(full_name, file_path, branch)
        if not content:
            print(f"    Could not fetch, skipping", file=sys.stderr)
            skipped.append(f"{full_name}/{file_path}")
            continue

        meta, body = parse_frontmatter(content)

        # Derive a fallback name from the directory containing the SKILL.md,
        # or from the repo name if the file is at the root
        path_dir = os.path.dirname(file_path).strip("/")
        path_name = path_dir.split("/")[-1] if path_dir else repo["name"]

        name = meta.get("name", path_name)
        description = meta.get("description", repo.get("description", ""))
        tags = extract_tags(meta, body)
        summary = make_summary(body)

        skills.append({
            "name": name,
            "repo": full_name,
            "skill_path": file_path,
            "description": description,
            "tags": tags,
            "summary": summary,
            "raw_url": f"{GITHUB_RAW_URL}/{full_name}/{branch}/{file_path}",
            "html_url": f"{GITHUB_BASE_URL}/{full_name}/blob/{branch}/{file_path}",
            "last_indexed": now,
        })

    if skipped:
        print(f"\n  Skipped {len(skipped)} files: {', '.join(skipped)}", file=sys.stderr)

    return skills


def commit_index(skills: list[dict]):
    """Clone index repo, write updated files, and push."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    index_data = {
        "generated_at": now,
        "org": GITHUB_ORG,
        "base_url": GITHUB_BASE_URL,
        "skill_count": len(skills),
        "skills": skills,
    }

    hostname = GITHUB_BASE_URL.replace("https://", "").replace("http://", "")
    # Token is supplied via GIT_ASKPASS to keep it out of the clone URL and process args
    clone_url = f"https://x-access-token@{hostname}/{INDEX_REPO}.git"

    # Write askpass script to a separate temp file so the clone target dir stays empty
    askpass_fd, askpass_path = tempfile.mkstemp(prefix="git_askpass_")
    try:
        os.write(askpass_fd, b"#!/bin/sh\necho \"$_GIT_TOKEN\"\n")
        os.close(askpass_fd)
        os.chmod(askpass_path, 0o700)
        git_env = {**os.environ, "GIT_ASKPASS": askpass_path, "_GIT_TOKEN": GITHUB_TOKEN}

        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(
                ["git", "clone", "--depth=1", clone_url, tmpdir],
                check=True, capture_output=True, env=git_env,
            )

            index_dir = os.path.join(tmpdir, "index")
            os.makedirs(index_dir, exist_ok=True)

            with open(os.path.join(index_dir, "skills.json"), "w") as f:
                json.dump(index_data, f, indent=2)

            with open(os.path.join(index_dir, "timestamp.txt"), "w") as f:
                f.write(now + "\n")

            subprocess.run(
                ["git", "-C", tmpdir, "add", "index/"],
                check=True, env=git_env,
            )

            result = subprocess.run(
                ["git", "-C", tmpdir, "commit", "-m", "chore: refresh skill index [skip ci]"],
                capture_output=True, env=git_env,
            )
            if result.returncode != 0:
                if b"nothing to commit" in result.stdout + result.stderr:
                    print("Index unchanged, nothing to commit.")
                    return
                raise subprocess.CalledProcessError(result.returncode, result.args)

            push_result = subprocess.run(
                ["git", "-C", tmpdir, "push"],
                capture_output=True, env=git_env,
            )
            if push_result.returncode != 0:
                print(
                    f"WARNING: git push failed. Copy the following JSON to "
                    f"index/skills.json in {INDEX_REPO} and commit manually "
                    f"with message: chore: refresh skill index [skip ci]",
                    file=sys.stderr,
                )
                print(json.dumps(index_data, indent=2))
                return

    finally:
        os.unlink(askpass_path)

    print(f"Index updated: {len(skills)} skills indexed at {now}")


def main():
    missing = [v for v in ["GITHUB_TOKEN", "GITHUB_ORG", "INDEX_REPO"] if not os.environ.get(v)]
    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    print(f"Base URL: {GITHUB_BASE_URL}", file=sys.stderr)
    print(f"API URL:  {GITHUB_API_URL}", file=sys.stderr)
    print(f"Scanning org '{GITHUB_ORG}' for SKILL.md files...", file=sys.stderr)

    skill_files = find_all_skill_files()
    print(f"Found {len(skill_files)} SKILL.md files.", file=sys.stderr)

    skills = build_index(skill_files)
    commit_index(skills)


if __name__ == "__main__":
    main()
