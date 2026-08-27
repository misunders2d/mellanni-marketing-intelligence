# Content operations

Run commands from repository root unless stated otherwise. Use a unique temporary directory outside repository:

```bash
RUN_DIR="$(mktemp -d /tmp/mellanni-digest.XXXXXX)"
```

Validate `RUN_DIR` points under `/tmp/mellanni-digest.` before deleting it. Keep it only until live write/readback succeeds.

## Environment

Install the locked Python environment before first use or after dependency changes:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync --locked
```

Run every Python command below through `uv run`; bare system Python is unsupported.

On Mellanni workstation, source/digest CLI automatically uses approved company
Supabase profile at `~/.config/supabase/company`. Access to that profile grants
runner authority. Retrieved key stays in process memory and must never be printed.

Ignored root `.env` may override with explicit credentials:

```dotenv
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_SECRET_KEY=approved-runner-key
GOOGLE_API_KEY=gemini-key
```

Never print values. Website uses separate publishable environment variables only.

## Source operations

Show enabled live sources:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content list-sources
```

Include paused sources:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content list-sources --all
```

Add or update one source from external temporary JSON:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  upsert-source --input "$RUN_DIR/source.json"
```

Source JSON uses `slug`, `name`, `home_url`, optional `priority`, `why`, `include_patterns`, `allowed_hosts`, `feed_urls`, `max_items`, `max_feed_candidates`, and `enabled`.

Reversible removal or restore:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  set-source-state --slug SOURCE_SLUG --state paused
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  set-source-state --slug SOURCE_SLUG --state enabled
```

Read back with `list-sources --all` after mutation.

## Digest run

1. Export exact enabled-source snapshot:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  export-sources --output "$RUN_DIR/sources.json"
```

2. Collect into external temporary journal:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence \
  --config "$RUN_DIR/sources.json" \
  --journal-root "$RUN_DIR/journal" \
  --since-days 8
```

3. Inspect manifest before synthesis. Record complete failures, partial errors, warnings, undated/noisy content, and source coverage.

If collection failed, record the collection result once and stop:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  record-run --manifest "$RUN_DIR/journal/RUN_ID/manifest.json"
```

If collection succeeded but no digest will be created, record the actual no-digest outcome and a concrete reason, then stop:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  record-run --manifest "$RUN_DIR/journal/RUN_ID/manifest.json" \
  --outcome no-digest --reason "REASON"
```

For a successful run that will produce a digest, skip `record-run`; step 8 records the manifest once and links it to the digest.

4. Read `references/editorial-contract.md`. List prior digests with bodies before novelty classification:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  list-digests --status published
```

Select and deduplicate material ecommerce signals. Use stable IDs. Useful external knowledge remains eligible even when no Mellanni data exists.

5. Use this exact MCP handoff; do not synthesize around a missing capability:

   1. Call `mellanni_skills_list` and save its machine-readable result as `$RUN_DIR/mcp-skill-inventory.json`.
   2. Require `professional-memory-search` and `source-routing` in that result. Call `mellanni_skills_get` for both, then for every provider playbook selected by source routing. If list/get/search tools or a required playbook are absent, run the command below and stop:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  record-run --manifest "$RUN_DIR/journal/RUN_ID/manifest.json" \
  --outcome no-digest --reason "missing required Mellanni MCP capability"
```
   3. Call `mellanni_memory_advanced_search` once with one deduplicated three-to-five-query batch across all included signals. For selected matches, call `mellanni_memory_get` once per record ID. Never call memory write tools.
   4. Call only read tools named by loaded provider playbooks. Save exact tool name, inputs, window/grain, entity IDs, and returned result under the matching `mellanniQueries` row. Provider tools/scripts own calculations and joins.
   5. Build `$RUN_DIR/evidence-packet.json` from those machine-readable results. Preserve returned IDs and values; do not recalculate or manually join them. Validation fails when any used skill URI is absent from captured inventory.

For YouTube evidence:

```bash
node --env-file=.env scripts/youtube-summary.mjs "YOUTUBE_URL" "FOCUS QUESTION"
```

Preserve video URL, summary limitations, useful tactic, and exact applicable skill reference.

6. Build private packet matching `examples/evidence-packet.example.json`. It contains exact source, memory, query, prior-digest, and skill evidence. Validate before synthesis:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  validate-evidence-packet --input "$RUN_DIR/evidence-packet.json"
```

7. Build digest input matching `examples/digest.example.json` only from validated packet. Use zero to four data-backed Mellanni Actions plus every material External Signal. Each Action includes exact `privateDecision` for admin and a safe public summary; never copy raw query results or memory records. Validator/storage split removes `privateDecision` from public body. Validate cross-references locally without DB write:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  validate-digest --input "$RUN_DIR/digest.json" \
  --evidence-packet "$RUN_DIR/evidence-packet.json"
```

8. Push draft and record collection plus private evidence packet once:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  push-digest --input "$RUN_DIR/digest.json" \
  --evidence-packet "$RUN_DIR/evidence-packet.json" \
  --manifest "$RUN_DIR/journal/RUN_ID/manifest.json"
```

Same slug updates existing digest. Draft is not public.

9. Read back:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  list-digests --status draft
```

10. Publish only after explicit approval:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  set-digest-state --slug DIGEST_SLUG --state published
```

Verify with `list-digests --status published` and public digest URL. To remove from website without data loss, set state back to `draft` and verify public URL no longer resolves.

11. Delete exact external temporary directory only after verified write/readback. Private packet is retained only inside private run record; never publish or commit it. Do not delete broad paths or unresolved variables.

## Website and deployment

Website reads published rows dynamically; content changes do not require redeploy.

From `website/`:

```bash
npm run typecheck
npm run lint
npm run build
```

For UI changes, inspect real desktop/mobile pages, focus states, overflow, and browser console before completion.

Production site: `https://mellanni-marketing-insights.vercel.app`.

Code deployment uses company Vercel project `marketing-insights`. GitHub auto-deploy remains unavailable until company Vercel account has GitHub Login Connection; use approved company CLI profile for manual deployment meanwhile. Database migrations require separate explicit approval and company Supabase CLI profile.
