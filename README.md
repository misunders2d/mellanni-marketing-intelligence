# Mellanni Marketing Intelligence

Fetch-only pipeline for Plane project `MKT-1`:

1. Collect recent items from the 12-source pilot registry.
2. Normalize fetched page/feed text.
3. Write one Markdown file per item under ignored local `journal/<run>/`.
4. Write a machine-readable manifest with source health and item paths.

This repo does not start agents, score content, summarize findings, render HTML, schedule jobs, or deliver messages. Sergey asks Codex to analyze a journal run separately.

## Manual run

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence --since-days 8
```

Target one source while debugging:

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence --source seller-sessions
```

Default output lives under ignored `journal/`. Source extracts are local artifacts and remain untracked.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Weekly scheduler is not installed yet. Schedule still needs day/time confirmation.
