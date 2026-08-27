# Mellanni Marketing Intelligence

This is one repository: Python collection and content tools live at root, the
Next.js publication site lives in `website/`, and Supabase schema/config lives
in `supabase/`.

Agents working in this repository must read `AGENTS.md` and the linked
`mellanni-marketing-operator` project skill before operating live content.

Install the locked Python environment once, then use `uv run` for every Python command:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync --locked
```

Fetch-only pipeline for Plane project `MKT-1`:

1. Collect recent items from the 12-source pilot registry.
2. Normalize fetched page/feed text.
3. Write one Markdown file per item under ignored local `journal/<run>/`.
4. Write a machine-readable manifest with source health and item paths.

The fetch pipeline does not start agents, score content, summarize findings, schedule jobs, or deliver messages. The YouTube helper below runs only when explicitly invoked.

## Manual run

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence --since-days 8
```

Target one source while debugging:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence --source seller-sessions
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

## Supabase content flow

Supabase is the live source of truth for enabled sources, draft/published digests, and run records. The checked-in `config/sources.json` remains an offline fixture.

Runner first reads ignored root `.env` when explicit credentials are supplied:

```dotenv
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_SECRET_KEY=your-secret-key
```

Never put the secret key in `website/`, Vercel, client code, logs, or chat. Website/browser access uses only the publishable key plus Row Level Security.

On the Mellanni workstation, the runner otherwise reads the approved company
Supabase CLI profile at `~/.config/supabase/company` and keeps the retrieved key
in process memory only. Access to that profile is the authorization boundary.

Export enabled sources into the existing fetcher format:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  export-sources --output journal/runtime/sources.json
```

Run collection from that exact snapshot:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence \
  --config journal/runtime/sources.json --since-days 8
```

Validate private evidence packet and digest input before its public/admin projections:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  validate-evidence-packet --input examples/evidence-packet.example.json
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  validate-digest --input examples/digest.example.json \
  --evidence-packet examples/evidence-packet.example.json
```

Push an agent-produced digest as a draft:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  push-digest --input examples/digest.example.json \
  --evidence-packet examples/evidence-packet.example.json
```

Add `--manifest journal/<run>/manifest.json` to attach collection plus private evidence packet to private run record. Public digest receives no exact internal metrics, identifiers, query results, or Professional Memory records. Add `--publish` only for explicitly approved direct publication; normal flow is draft first, then publish from `/admin`.

Record any collection run independently, including failures that never produce a digest:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  record-run --manifest journal/<run>/manifest.json
```

When collection succeeded but synthesis cannot continue, record the actual outcome:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  record-run --manifest journal/<run>/manifest.json \
  --outcome no-digest --reason "missing required Mellanni MCP capability"
```

Use `--digest-id UUID` only when a digest was created separately and should be linked to that run.

The website needs only:

```dotenv
NEXT_PUBLIC_SUPABASE_URL=https://PROJECT_REF.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=your-publishable-key
```

Public pages read published digests dynamically. `/admin` authenticates `sergey@mellanni.com`, manages enabled/paused sources, and promotes drafts to published status without redeploying the site.

## Manifest observability

New runs use additive manifest schema v2. Existing fields keep their original names and meanings. V2 adds:

- exact run parameters and source-config SHA-256;
- per-source warnings, feed candidate totals, actual probe count, and truncation count;
- an explicit HTML fallback reason;
- a run-level warning count.

Feed probing stays sequential and bounded. Explicit `feed_urls` are always eligible to run unless an earlier candidate succeeds. Discovered and common feed candidates share the remaining `max_feed_candidates` budget, which defaults to 8. Any truncation is recorded in source warnings.

## Tests

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest discover -s tests -v
```

Weekly scheduler is not installed yet. Schedule still needs day/time confirmation.
