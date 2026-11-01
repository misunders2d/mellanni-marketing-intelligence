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

Migrations `20260907180000_content_bound_digest_publication.sql`, `20260910120000_restore_preproof_publications.sql`, and `20260914120000_close_legacy_publication_path.sql` are historical production incident migrations, not a reusable publication shortcut. The restoration selected three reviewed rows by exact slug, draft state, null stored hash, and expected update timestamp, then recorded their reviewed hashes. Production readback separately confirmed those hashes matched the current public and private content. The closure migration leaves those records as audit evidence only; legacy records cannot authorize any future publication. Never apply or reuse the restoration without the closure in the same controlled maintenance window, and do not reopen application access between them. All future publication, including any changed restored digest, requires normal schema-2 verified proof. Applying any migration is a separate live mutation and needs explicit release approval.

Current live authority contains 13 enabled sources. Start or resume the workflow
with the same command every time:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run mellanni-weekly
```

Runner creates a private `0700` `/tmp/mellanni-marketing-weekly/<run_id>/`
workspace; runner-written sensitive files are `0600`. It owns these stages:

- exact enabled-source snapshot and SHA-256;
- bounded collection with fatal source errors separate from warnings;
- agentic YouTube batch with concurrency 2, 600-second item timeout,
  3,600-second whole-batch deadline, and 25-video preflight cap;
- immutable manifest v3 with SHA-256 for every collected artifact, plus a cryptographically bound YouTube sidecar with separate Markdown and JSON hashes;
- prior-published-digest snapshot;
- manifest-bound evidence packet with one included/excluded `itemReviews` decision per collected item;
- evidence/digest schema, prior-finding, and cross-reference validation;
- draft write, full public/private content-hash readback, linked content-bound run proof, and one final immutable `run-receipt.json`.

At `status: awaiting_synthesis`, use paths printed by runner. Read
`references/editorial-contract.md`, collected item files, every YouTube artifact,
and `prior-digests.json`. Never select one representative episode or compress a
multi-episode source before episode review. Shallow podcast notes are insufficient
evidence; record a no-digest outcome instead of inventing episode knowledge.

Use this exact agent-only handoff:

1. Call `mellanni_skills_list`; require `professional-memory-search` and
   `source-routing`. Load both plus each provider playbook selected by routing.
2. Call `mellanni_memory_advanced_search` once with one deduplicated three-to-five
   query batch. Fetch selected records by ID. Never write Professional Memory.
3. Call only provider read tools named by loaded playbooks. Provider tools/scripts
   own calculations and joins. Preserve exact tool, inputs, window, grain, entity
   IDs, and returned values.
4. Write the printed `evidence-packet.json` path using the example contract. Set `collectionManifestSha256` to the exact `collection_manifest_sha256` returned by runner. Add exactly one `itemReviews` row for every manifest item: `included` with all supported Signal IDs, or `excluded` with no Signal IDs and a concrete item-specific reason. Preserve machine values; do not manually join or recalculate them.
5. Write the printed `digest.json` path using the example contract. Select and consolidate the most important findings under the editorial contract: at most 10 employee-visible items total (validation rejects more), including zero to four data-backed Mellanni Actions and the selected External Signals. Keep complete per-item and per-episode review evidence even when fewer findings are selected.

If required skill, memory, or provider capability is absent, terminate the run
through the same runner so it records a no-digest receipt and database run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run mellanni-weekly \
  --fail-reason "missing required Mellanni MCP capability"
```

After both fixed files exist, run the unchanged command again:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run mellanni-weekly
```

Success is `outcome: draft` plus `readback_verified: true` in immutable receipt. Readback means slug, ID, status, title, summary, member body, admin-only private body, and canonical content hash all match validated input. Same slug updates an existing draft. A slug that is currently published is refused, because the write would return the live digest to draft; `push-digest --replace-published` is the explicit override. Draft remains invisible to employee readers.

After full readiness validation, draft write, readback, and run linkage, database
`runs.manifest` retains only compact non-raw proof: run ID; collection-manifest, YouTube-sidecar, evidence-packet, and canonical digest-content SHA-256 hashes; source/item/video counts; and `agentic_verified`.
Retain compact `run-receipt.json` (and `run-state.json` when resume history is
needed) locally. Collected pages, manifest, YouTube sidecar, per-episode
JSON/Markdown, evidence packet, and digest input are disposable raw artifacts;
never upload or publish them. Delete those raw files after verifying the draft
receipt and linked run. Compact database proof remains publication gate.

Publish only after explicit approval:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence.supabase_content \
  set-digest-state --slug DIGEST_SLUG --state published
```

CLI requires a successful digest run linked to the exact current public/private content hash. Publication runs through the atomic `publish_digest_with_verified_run` database function; a proof for older content cannot authorize a changed draft. Missing, obsolete, content-mismatched, or unverified proof blocks. Raw local artifacts need not exist. If they still exist, `--manifest PATH` is an optional extra collection-proof match, never primary publication authority. Verify published readback and authenticated reader URL. Returning digest to draft remains reversible and needs no manifest.

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
