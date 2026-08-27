# Mellanni Marketing Intelligence

Fetch-only pipeline for Plane project `MKT-1`:

1. Collect recent items from the 12-source pilot registry.
2. Normalize fetched page/feed text.
3. Write one Markdown file per item under ignored local `journal/<run>/`.
4. Write a machine-readable manifest with source health and item paths.

The fetch pipeline does not start agents, score content, summarize findings, schedule jobs, or deliver messages. The YouTube helper below runs only when explicitly invoked.

## Manual run

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence --since-days 8
```

Target one source while debugging:

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence --source seller-sessions
```

Default output lives under ignored `journal/`. Source extracts are local artifacts and remain untracked.

## YouTube summarizer

The standalone helper preserves the existing Pi Gemini YouTube summarizer's model defaults, fallback, URL validation, prompt, and multimodal request.

Put the API key in local ignored `.env`:

```dotenv
GOOGLE_API_KEY=your-key
```

Run:

```bash
node --env-file=.env scripts/youtube-summary.mjs "https://www.youtube.com/watch?v=VIDEO_ID"
```

Optional focus question follows the URL. Model overrides use `YOUTUBE_SUMMARIZER_MODEL` and `YOUTUBE_SUMMARIZER_FALLBACK_MODEL`.

## Manifest observability

New runs use additive manifest schema v2. Existing fields keep their original names and meanings. V2 adds:

- exact run parameters and source-config SHA-256;
- per-source warnings, feed candidate totals, actual probe count, and truncation count;
- an explicit HTML fallback reason;
- a run-level warning count.

Feed probing stays sequential and bounded. Explicit `feed_urls` are always eligible to run unless an earlier candidate succeeds. Discovered and common feed candidates share the remaining `max_feed_candidates` budget, which defaults to 8. Any truncation is recorded in source warnings.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Weekly scheduler is not installed yet. Schedule still needs day/time confirmation.
