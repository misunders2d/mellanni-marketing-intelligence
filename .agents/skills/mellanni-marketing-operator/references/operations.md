# Content operations

Run commands from repository root unless stated otherwise. Use a unique temporary directory outside repository:

```bash
RUN_DIR="$(mktemp -d /tmp/mellanni-digest.XXXXXX)"
```

Validate `RUN_DIR` points under `/tmp/mellanni-digest.` before deleting it. Keep it only until live write/readback succeeds.

## Environment

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
PYTHONPATH=src python -m mellanni_marketing_intelligence.supabase_content list-sources
```

Include paused sources:

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence.supabase_content list-sources --all
```

Add or update one source from external temporary JSON:

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence.supabase_content \
  upsert-source --input "$RUN_DIR/source.json"
```

Source JSON uses `slug`, `name`, `home_url`, optional `priority`, `why`, `include_patterns`, `allowed_hosts`, `feed_urls`, `max_items`, `max_feed_candidates`, and `enabled`.

Reversible removal or restore:

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence.supabase_content \
  set-source-state --slug SOURCE_SLUG --state paused
PYTHONPATH=src python -m mellanni_marketing_intelligence.supabase_content \
  set-source-state --slug SOURCE_SLUG --state enabled
```

Read back with `list-sources --all` after mutation.

## Digest run

1. Export exact enabled-source snapshot:

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence.supabase_content \
  export-sources --output "$RUN_DIR/sources.json"
```

2. Collect into external temporary journal:

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence \
  --config "$RUN_DIR/sources.json" \
  --journal-root "$RUN_DIR/journal" \
  --since-days 8
```

3. Inspect manifest before synthesis. Record complete failures, partial errors, warnings, undated/noisy content, and source coverage. If collection failed or no digest will be created, record the run once and stop:

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence.supabase_content \
  record-run --manifest "$RUN_DIR/journal/RUN_ID/manifest.json"
```

For a successful run that will produce a digest, skip `record-run`; step 6 records the manifest once and links it to the digest.

4. Read selected journal items. Build one evidence-bounded digest JSON matching `examples/digest.example.json`. Preserve direct source URLs. For YouTube:

```bash
node --env-file=.env scripts/youtube-summary.mjs "YOUTUBE_URL" "FOCUS QUESTION"
```

5. Validate locally without DB write:

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence.supabase_content \
  validate-digest --input "$RUN_DIR/digest.json"
```

6. Push draft and record its manifest once:

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence.supabase_content \
  push-digest --input "$RUN_DIR/digest.json" \
  --manifest "$RUN_DIR/journal/RUN_ID/manifest.json"
```

Same slug updates existing digest. Draft is not public.

7. Read back:

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence.supabase_content \
  list-digests --status draft
```

8. Publish only after explicit approval:

```bash
PYTHONPATH=src python -m mellanni_marketing_intelligence.supabase_content \
  set-digest-state --slug DIGEST_SLUG --state published
```

Verify with `list-digests --status published` and public digest URL. To remove from website without data loss, set state back to `draft` and verify public URL no longer resolves.

9. Delete exact external temporary directory only after verified write/readback. Do not delete broad paths or unresolved variables.

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
