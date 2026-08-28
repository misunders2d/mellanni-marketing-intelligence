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

7. Build digest input matching `examples/digest.example.json` only from validated packet. Use zero to four data-backed Mellanni Actions plus every material External Signal. Each Action includes exact `privateDecision` for admin and a safe employee-visible summary; never copy raw query results or memory records. Validator/storage split removes `privateDecision` from the employee-visible body. Validate cross-references locally without DB write:

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

Same slug updates existing digest. Draft is not employee-visible.

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

Verify with `list-digests --status published` and an authenticated reader request to the digest URL. To remove from the website without data loss, set state back to `draft` and verify the authenticated URL no longer resolves.

11. Delete exact external temporary directory only after verified write/readback. Private packet is retained only inside private run record; never publish or commit it. Do not delete broad paths or unresolved variables.

## Membership and offboarding

List active members, or include inactive rows:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content list-members
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content list-members --all
```

Deactivate by exact auth user ID, never by email. More than one auth identity may carry the same email:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  set-member-state --user-id USER_UUID --state inactive
```

Read back with `list-members --all`, then verify that user's authenticated page and direct Data API requests return no content. The membership gate blocks access immediately even while an old refresh token exists. After that denial is proven, revoke the user's Auth sessions or delete the Auth user through the Supabase Auth admin surface. Reactivation uses the same command with `--state active` and requires explicit approval.

## Website and deployment

Website reads published rows dynamically for active company readers; content changes do not require redeploy. Supabase RLS is the security boundary. Next.js `proxy.ts` supplies session refresh and redirects but does not replace direct Data API checks.

From `website/`:

```bash
npm run typecheck
npm run lint
npm run build
```

For UI changes, inspect real desktop/mobile pages, focus states, overflow, and browser console before completion.

### Authentication configuration

Local Google OAuth needs these ignored environment values; never commit or print them:

```dotenv
SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID=google-web-client-id
SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_SECRET=google-web-client-secret
```

Google Auth Platform must allow the site origin and the Supabase Auth callback shown by the project provider settings. Supabase redirect allowlists must include `/auth/callback/` for production and local development.

Production cutover order is fail-closed:

1. Configure Google provider and redirect URLs while global signup remains disabled.
2. Apply the reviewed migration. It creates membership/hook functions, moves private bodies, removes anonymous reads, and seeds eligible existing Mellanni users.
3. Configure the production Before User Created hook and verify its grants. Local auth tests must already prove non-Mellanni and non-Google rejection. Inject one hook error and record both outcomes in the release log: whether GoTrue created an auth user, and that the independent provisioning trigger created no active member so page and Data API access remained denied.
4. Deploy the reviewed website and verify `/login/`, callback routing, and anonymous redirect while content stays inaccessible.
5. Enable global signup. Keep email signup disabled. Immediately verify a non-Mellanni Google attempt creates no auth user or member, then verify a Mellanni Google reader.
6. Verify direct Data API boundaries: anonymous gets no digest rows; reader gets published `body` only; reader cannot read `digest_private_bodies`, sources, runs, drafts, or writes; admin retains controls; inactive reader gets no content.

Never reverse steps 3 and 5. The signup hook must be configured before internet-wide signup opens. Do not apply migrations, change live Auth settings, or deploy without explicit release approval.

Production site: `https://mellanni-marketing-insights.vercel.app`.

Code deployment uses company Vercel project `marketing-insights`. GitHub auto-deploy remains unavailable until company Vercel account has GitHub Login Connection; use approved company CLI profile for manual deployment meanwhile. Database migrations require separate explicit approval and company Supabase CLI profile.
