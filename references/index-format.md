# Index Format Reference

## skills.json

```json
{
  "generated_at": "2026-05-08T10:00:00Z",
  "org": "my-org",
  "skills": [
    {
      "name": "unit-test-writer",
      "repo": "my-org/unit-test-writer-skill",
      "skill_path": "SKILL.md",
      "description": "Generates unit tests for Python and TypeScript.",
      "tags": ["testing", "python", "typescript"],
      "summary": "First few lines of skill body giving more context.",
      "raw_url": "https://raw.githubusercontent.com/my-org/unit-test-writer-skill/main/SKILL.md",
      "html_url": "https://github.com/my-org/unit-test-writer-skill/blob/main/SKILL.md",
      "last_indexed": "2026-05-08T10:00:00Z"
    }
  ]
}
```

## timestamp.txt

Plain text file containing a single ISO 8601 datetime string:

```
2026-05-08T10:00:00Z
```

## Index repo layout

```
skill-index/
├── index/
│   ├── skills.json
│   └── timestamp.txt
└── README.md
```
