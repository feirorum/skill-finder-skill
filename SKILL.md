---
name: skill-finder
description: >
  Discover, search, and browse available GitHub Copilot skills across your GitHub org.
  Use this skill whenever a user wants to find a skill, browse available skills, search
  for skills by keyword or topic, or wants to know "what skills do we have for X".
  Also use when the user wants to update or refresh the skill index. This skill maintains
  a cached index of all skills in the org and can do fast keyword searches or deeper
  full-file lookups for best matches.
---

# Skill Finder

Helps users discover available skills across the GitHub org by maintaining and querying
a cached skill index. The index lives in a dedicated GitHub repo and is refreshed
automatically when stale.

---

## Configuration

Read from environment or ask the user if missing:

```
GITHUB_TOKEN          # Personal access token with repo and read:org scope
GITHUB_ORG            # GitHub org name (e.g. "my-org")
INDEX_REPO            # Repo that holds the index (e.g. "my-org/skill-index")
GITHUB_BASE_URL       # Base URL (default: https://github.com). For GHE: https://github.example.com
INDEX_MAX_AGE_SECONDS # How old the index can be before refresh (default: 3600)
```

---

## User Flows

### Flow 1: Search for skills
User says something like: "find a skill for writing unit tests" or "what skills do we have?"

→ See [Search Flow](#search-flow)

### Flow 2: Force refresh
User says: "refresh the skill index" or "update skills"

→ Skip cache check, go straight to [Index Refresh](#index-refresh)

---

## Search Flow

```
1. Check index freshness   →  [scripts/check_index.py]
2a. If fresh: search index →  [scripts/search_index.py]
2b. If stale: refresh first → [Index Refresh], then search
3. If top matches found: fetch full skill files from GitHub
4. Re-rank and return best matches
```

### Step 1 – Check index freshness

Run `scripts/check_index.py`. It fetches `index/timestamp.txt` from INDEX_REPO
and returns how many seconds old the index is.

- If age < INDEX_MAX_AGE_SECONDS → index is fresh, skip to Step 2a
- If age ≥ INDEX_MAX_AGE_SECONDS or timestamp missing → run Index Refresh first

### Step 2a – Search the index

Run `scripts/search_index.py --query "<user query>"`.

Returns a ranked list of skill matches from `index/skills.json` based on keyword
overlap against: name, description, tags, and summary fields.

Return **top 5** candidates.

### Step 3 – Deep fetch for top matches

For the top 3 matches (or fewer if less found), fetch the full SKILL.md directly
from the skill's source repo on GitHub using the GitHub raw content URL.

Compare the full file content against the user's query and re-rank if needed.

### Step 4 – Present results

Show results like this:

```
## Found 3 matching skills

### 1. unit-test-writer
📁 my-org/unit-test-writer-skill
> Generates unit tests for Python and TypeScript using pytest and Jest.
Tags: testing, python, typescript
[View full skill](https://github.com/my-org/unit-test-writer-skill/blob/main/SKILL.md)

### 2. ...
```

If no matches: say so clearly and suggest the user browse all skills or refresh.

---

## Index Refresh

Run `scripts/refresh_index.py`. This script:

1. Lists all repos in the org with the configured GitHub topic
2. For each repo, fetches `SKILL.md` (or `skill/SKILL.md`)
3. Extracts: name, description, tags (from YAML frontmatter), and generates a
   short summary (first 3 non-frontmatter lines of body)
4. Builds `index/skills.json` and updates `index/timestamp.txt`
5. Commits and pushes to INDEX_REPO

See [references/index-format.md] for the JSON schema.

---

## Notes

- If GitHub API rate limit is hit during refresh, skip remaining repos and note
  which were skipped. Proceed with what was indexed.
- If a repo has no SKILL.md, skip it silently.
- The index commit message should be: `chore: refresh skill index [skip ci]`
- If run in a context without git push access, print the updated JSON and ask
  the user to commit manually.

---

## Reference Files

- `references/index-format.md` — Schema for skills.json
- `scripts/check_index.py` — Checks index freshness
- `scripts/search_index.py` — Searches the local index
- `scripts/refresh_index.py` — Scans org and rebuilds index
