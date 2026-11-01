# Handoff: Repository Review Findings

- **Date:** 2026-10-30
- **Base commit:** `97ff014` (`main`)
- **Scope:** read-only review of frontend design, code logic, and agent operability. No code was changed.
- **Pre-existing uncommitted work at review time (not part of this review):** `skills/mellanni-marketing-operator/SKILL.md`, `evals/evals.json`, `references/editorial-contract.md`.

## Goal

A fresh agent with no prior context should be able to run the weekly marketing research end to end with as many pre-built deterministic tools as possible. LLM reasoning should be limited to work that actually needs judgment.

## Verdict

- **Code:** no security blockers. Main gap is operability: the agent still performs mechanical work by hand, and one class of agent mistake ends a run terminally and expensively.
- **Frontend:** approve with follow-ups. One P1 content-truth bug, plus P1 density and navigation problems on the digest page.

## Resolution status (2026-11-01, branch `fix/review-handoff-findings`)

Every item below is resolved except AR-9. The original findings stay unchanged further down for reference.

| ID | Status | Resolution |
|---|---|---|
| AR-1 | Fixed | Packet/digest validation errors (malformed JSON and wrong slug too) return `status: validation_failed`, keep the same `run_id` at `awaiting_synthesis`, and record no DB row. Only a broken runner-owned invariant or `--fail-reason` is terminal. |
| AR-2 | Fixed | `mellanni-weekly --check` runs the full readiness chain offline, with no credentials, DB writes, or state change. |
| AR-3 | Fixed | All schema errors (capped at 50, array dumps shortened) plus all cross-field errors per pass. |
| AR-4 | Fixed | Privacy flags are derived; agent `privacy` input is optional and ignored. Restricted-content checks stay hard failures. |
| AR-5 | Fixed | `validate_digest` enforces at most 10 Actions plus Signals combined; the schema caps Signals at 10. |
| AR-6 | Fixed | Runner writes `evidence-packet.scaffold.json` and the prior-findings index at `awaiting_synthesis`. `--scaffold-digest` builds `digest.scaffold.json` from the finished packet with every mirrored field copied. |
| AR-7 | Fixed, different ledger | No new table: `runs.manifest` holds compact proof only, so the scaffold pre-excludes items whose URL a published digest already cited. Locale/query variants are deduped. Undated html-index items are rejected unless the source is `evergreen`. `evergreen` is a config-level flag only; no DB column was added. |
| AR-8 | Fixed | Collector prefers `<article>`/`<main>` text, keeps paragraph breaks, drops nav/footer/aside/form chrome, and reads page publish dates from meta, `<time>`, and JSON-LD. |
| AR-9 | Open | Needs Sergey's decision on cost, provider, and episode cap. |
| AR-10 | Fixed | Runner generates the slug from the Pacific `week_start`. `push-digest` refuses a currently published slug unless `--replace-published` is passed. |
| CL-1 | Fixed | Proxy adds `?next=`; login form and callback pass it through `safeNextPath`. |
| CL-2 | Fixed | `week_start` uses `America/Los_Angeles`. |
| CL-3 | Fixed | Reads throw `DigestLoadError`; `app/error.tsx` renders a real error state. |
| CL-4 | Fixed | Admin console shows proof status, disables Publish without a verified proof for the current content hash, asks for inline confirmation, links a preview, and maps errors to readable text. Migration `20261101120000` makes the guard trigger stamp `published_at` from the database clock and ignore client values. |
| CL-5 | Fixed | JSON mode renders the member-visible projection through `public_digest_body`. |
| CL-6 | Fixed | Tests use dates relative to now. |
| CL-7 | Fixed | Standalone output defaults to `/tmp/mellanni-marketing-journal` (`MELLANNI_JOURNAL_ROOT` overrides); duplicate pip block removed. |
| CL-8 | Approved | Local ignored `journal/` and `website/out/` deleted with Sergey's approval. |
| CL-9 | Documented | Decision: keep admin `DELETE` and document it in `references/operations.md` as an admin capability. Normal removal stays return-to-draft. |
| CL-10 | Fixed | `list_digests` filters private bodies by the returned digest IDs. |
| CL-11 | Fixed | `sampleDigest` removed. |
| CL-12 | Fixed | Example uses contribution margin, higher is better, with consistent success/stop thresholds. |
| FE-1 | Fixed | "Mellanni evidence" label; new sample-notice copy. |
| FE-2 | Fixed | Numbered overview (kind, title, KPI/timebox/confidence or next validation, contradiction flag) with `#id` links. Scope, limits, and playbooks collapse into `<details>`. A comparable 10-item fixture now measures 10,427px desktop and 14,286px mobile with details closed; the fixture differs slightly from the review's, so treat the delta as indicative. |
| FE-3 | Fixed | Evidence links go straight to the external source. Source notes list "Cited in Action N / Signal N" back-links; every finding has "Back to overview". |
| FE-4 | Fixed | Skill URIs hidden; playbooks sit inside `<details>`. Memory notes render only for `contradicts`/`extends`. |
| FE-5 | Fixed | Finding-level hits with deep links; query persists in `?q=`. |
| FE-6 | Fixed | Home leads with the latest digest (contradictions, items, links), then earlier digests. Brochure sections removed; metadata copy updated. |
| FE-7 | Fixed | Digest title capped at `clamp(2.25rem, 4.5vw, 3rem)`. |
| FE-8 | Fixed | Nav only for members, Admin only for admins, `aria-current="page"`, "Calendar" renamed "Archive". |
| FE-9 | Fixed | Admin-only `/admin/preview/SLUG/`, noindex, with a draft/published banner. |
| FE-10 | Fixed | Source Serif 4 and Source Sans 3 self-hosted through `next/font`. |
| FE-11 | Fixed | Contradiction colors tokenized; link underline token `#767d71` (3.67:1 on canvas). |
| FE-12 | Fixed | Month-grouped list replaces the calendar grid. |

**Observations found while fixing (not changed):**

- Live Supabase source `sell-on-amazon` still uses `include_patterns: ["/blog/"]`. The collector now drops its locale and navigation noise. Narrowing it (for example to `/blog/announcements/`) is a live source mutation and needs approval.
- RLS lets admins `INSERT`/`UPDATE` `runs`, so an admin could write a run row that satisfies the publication proof gate. That is within the admin trust boundary today. Tighten it if admins should not be able to self-attest proof.

**Verification for this branch:** 129 Python tests and 19 Node tests pass. Website typecheck, lint, and build pass. Fixture-rendered Playwright checks at 1440×900 and 390×844 covered home, digest (10-item stress and example), search, archive, login, admin preview, admin, and 404. No horizontal overflow; console errors only on the expected 404. Authenticated reader/admin behavior on production needs a Google-login check by Sergey.

## Responsibility split

**Already deterministic and well built — keep:** source snapshot, hash-bound collection, resumable YouTube batch and sidecar, manifest/packet/prior-findings binding, draft write, content-hash readback, run proof, immutable receipt, and the database publication gate (trigger plus `publish_digest_with_verified_run`).

**Genuinely LLM work — keep with the agent:** item selection, signal synthesis, Mellanni MCP evidence capture, Professional Memory reconciliation, and skill inventory capture (MCP-only).

**Mechanical work still pushed to the LLM:** tracked below as AR-1 to AR-10.

## Recommended order

1. AR-1, AR-2, AR-3: the run should stop dying on fixable agent mistakes.
2. AR-6, then AR-4, AR-5, AR-10: scaffold and derive mechanical fields.
3. AR-7, AR-8: cut weekly review noise.
4. FE-1 to FE-4 and CL-1: user-visible truth and navigation.
5. AR-9: podcast audio tool, after a design decision.
6. Remaining P2/P3 items.

---

## A. Agent operability (priority)

### AR-1 (P1): Validation errors in agent-authored files end the run terminally

- **Location:** `src/mellanni_marketing_intelligence/weekly.py:501-533`
- **Problem:** Any schema or cross-field error in `evidence-packet.json` or `digest.json` calls `_fail`, which writes an immutable no-digest receipt and records a `no-digest` row in `runs`. On the next invocation, `_active_run` (`weekly.py:115`) skips the failed run and starts a new one. That means full re-collection, a new YouTube batch (up to 1h of Gemini), and another DB row.
- **Contrast:** malformed JSON at `weekly.py:499-500` is read outside that `try`, so it lands in the outer `except` and stays resumable. A typo is terminal; a syntax error is not.
- **Tests:** `tests/test_weekly.py` has no test pinning this behavior as intentional.
- **Fix:** treat validation failures of agent-authored files as resumable (`last_error`, status stays `running` or `awaiting_synthesis`). End a run terminally only through an explicit `--fail-reason`.
- **Acceptance:** a broken digest field followed by a corrected rerun completes in the same `run_id`, with no new collection, no YouTube calls, and no `no-digest` row.

### AR-2 (P1): No full dry-run check

- **Location:** `supabase_content.py:592-597` (`validate-digest`, `validate-evidence-packet`)
- **Problem:** Neither command checks manifest hash binding, `itemReviews` coverage, prior-digest finding binding, or YouTube readiness. The agent cannot know its files pass until the real run, which then hits AR-1.
- **Fix:** add `mellanni-weekly --check`. It runs the full readiness chain against the active run (`require_digest_ready_manifest`, `require_evidence_packet_bound_to_manifest`, `require_prior_digest_findings_bound`, `digest_to_row`, `build_run_proof`). It must not write to the DB or change run state.
- **Acceptance:** `--check` exits 0 only when the subsequent real run would pass validation.

### AR-3 (P1): Validation reports only the first error

- **Location:** `src/mellanni_marketing_intelligence/editorial.py:108-115` (`errors[0]`)
- **Fix:** report all schema errors (capped, for example the first 50) plus all cross-field errors per pass.
- **Acceptance:** a file with three independent errors reports all three in one run.

### AR-4 (P2): Agent must guess regex-derived privacy flags

- **Location:** `editorial.py:294-299`
- **Problem:** `privacy.exactValuesPublished` and `businessIdentifiersPublished` must exactly equal regex-derived values, otherwise validation fails (and under AR-1 the whole run dies). The public body already uses the derived values.
- **Fix:** derive the flags in the tool. Either drop them from agent input, or have scaffold/`--check` write the derived values. Restricted-content checks (secrets, PII, and the rest) stay hard failures.

### AR-5 (P2): 10-item cap not enforced

- **Location:** `schemas/digest.schema.json:47` caps actions at 4 only. `validate_digest` has no total check.
- **Context:** the editorial contract and commit `97ff014` set at most 10 Actions plus Signals combined, but this exists only in prose.
- **Fix:** enforce `len(actions) + len(signals) <= 10` in `validate_digest`, with a test.

### AR-6 (P1): No scaffold, so the agent hand-copies mechanical fields

**Fields copied by hand today:**
- `collectionManifestSha256`.
- One `itemReviews` row per manifest item (45 items in the Aug sample).
- `sources[]` id/name/url/publishedAt from the manifest.
- Digest `externalSignal` equal to packet `statement`.
- `sourceIds`.
- `memory.outcome` / `comparison` / `decisionImpact`.
- Digest `sources` equal to packet sources.

These are equality-checked at `editorial.py:337-394`.

**Fix:**
- At `awaiting_synthesis`, the runner writes `evidence-packet.scaffold.json`. It is pre-filled with schema version, manifest SHA, one `itemReviews` row per item (itemId, title, url, source, `disposition: null`), and source stubs. A prior-findings index from `prior-digests.json` is attached as reference.
- A second command builds `digest.scaffold.json` from the completed packet, copying every mirrored field. Only reasoning fields remain blank: titles, guidance, whyItMatters, nextValidation, timebox, KPI, conditions, confidence, limitations.

**Acceptance:** scaffolded files plus filled reasoning fields pass `--check` with no hand-copied values.

### AR-7 (P2): Undated and nav-junk items recur every week

- **Location:**
  - `collector.py:328` — `_within_window` returns True for undated items.
  - `collector.py:26` — `canonical_url` keeps non-UTM query parameters.
  - `collector.py:277` — `_looks_like_article` accepts a title of exactly 12 characters.
- **Evidence:** in local `journal/20260826T…` runs:
  - 5 of 5 `sell-on-amazon` items were navigation or locale variants, for example `https://sell.amazon.com/blog/announcements?mons_sel_locale=en_US` titled "English - US", "Español - US", "List products".
  - 26 of 45 items were undated.
  - The fixture `config/sources.json` has `include_patterns: ["/blog/"]` for that source, which the locale URL matches. Live Supabase source config was **not** checked.
- **Fix:**
  - Keep a cross-run seen ledger (url plus content hash) from the previous successful run or the DB, and mark unchanged repeats `previously_seen`. A deterministic exclusion reason can then be pre-filled in the scaffold.
  - Drop locale/query variants of the same path.
  - Reject undated html-index items unless the source is flagged evergreen.
  - Review live `include_patterns` for html-index sources.

### AR-8 (P2): Whole-page text, structure flattened

- **Location:** `collector.py:164-170` (`_clean_text` collapses all whitespace), `collector.py:483` (longest of summary, page, or title, up to 30k characters).
- **Problem:** the LLM reads navigation, footer, and cookie text with no paragraph breaks.
- **Fix:** prefer `<article>` or `<main>` content when present and keep paragraph breaks.

### AR-9 (P2, needs design decision): No podcast audio tooling

- **Evidence:** no enclosure, audio, or transcription handling anywhere in `src/` or `scripts/`. Four sources are podcast RSS feeds: `limited-supply`, `seller-sessions`, `ppc-den`, `smartest-amazon-seller`.
- **Conflict:** `references/operations.md` says shallow podcast notes are insufficient evidence and to record no-digest instead. The pipeline only ever has show notes for these sources.
- **Fix:**
  - Capture the RSS `<enclosure>` URL in the manifest.
  - Extend `scripts/youtube-summary.mjs`, or add a sibling, to process episode audio into the same hash-bound sidecar.
- **Open questions:** cost, provider, and episode cap need a decision from Sergey.

### AR-10 (P2): Agent-chosen slug can silently unpublish a live digest

- **Location:** `supabase/migrations/20260907180000_content_bound_digest_publication.sql:140` (`on conflict (slug) do update … status = 'draft'`)
- **Problem:** reusing an existing published slug overwrites that digest and returns it to draft.
- **Fix:** the runner generates the slug from `week_start`. `push_digest` refuses to target a slug that is currently published unless an explicit flag is passed.

---

## B. Other code logic

| ID | Pri | Location | Finding | Fix |
|---|---|---|---|---|
| CL-1 | P1 | `website/lib/supabase-proxy.ts:53`, `website/components/login-form.tsx:26` | Deep links are lost on login: the redirect drops the path, and the form hard-codes `next=/`. A shared digest link lands on Home. | Add `?next=<path>` in the proxy and pass it through the form. The callback's `safeNext` already validates it. |
| CL-2 | P2 | `weekly.py:83-85` | `week_start` uses the UTC Monday, while operations use Pacific time. A Sunday-evening PT resume becomes a "different week" refusal. | Compute the week in `America/Los_Angeles`. |
| CL-3 | P2 | `website/lib/supabase-public.ts:19,37` | DB errors return `[]` or `undefined`, so outages render as "first briefing is being prepared" or a 404. | Throw, and render a real error state. |
| CL-4 | P2 | `website/components/admin-console.tsx:227-245` | Publish button: no confirmation, no draft preview, no proof status, shows the raw Postgres exception, and sets `published_at` from the client clock. The DB trigger still enforces the proof gate; reasoned from migrations, not executed. | Call `publish_digest_with_verified_run` (or a reader-safe equivalent), show proof state, add confirm and preview. |
| CL-5 | P2 | `scripts/generate_html_report.py:351` | JSON mode reads `data["body"]`. Schema digests have none, so the output is empty; a dict body gets dumped as raw JSON text. STANDALONE.md §7 claims JSON input works. | Render validated `digest.json` through the same projection as the website. This can double as the admin preview. |
| CL-6 | P2 | `tests/test_pipeline.py:136,482` | Hard-coded `2026-09-07` with an 8-day window. The test at line 482 now fails (`0 != 1`). Pre-existing time-rot, not a code regression. | Use dates relative to `datetime.now(UTC)`. |
| CL-7 | P3 | `STANDALONE.md:138` | "Or using standard pip" shows the same `uv` command. The standalone path writes to the repo's `journal/`, contradicting AGENTS.md's external temp-dir rule. | Fix the command; default the standalone output to a temp dir. |
| CL-8 | P3 | local ignored `journal/`, `website/out/` | Stale Aug 26 raw collection artifacts and an old static export exist locally, against the repo's own artifact rule. | Delete after confirming nothing needs them. Requires approval. |
| CL-9 | P3 | `supabase/migrations/20260828160000_private_company_auth.sql:290,362` | Admins have DELETE on `digests` through RLS, while the docs say hard delete is not exposed. | Decide: revoke, or document it as an admin capability. |
| CL-10 | P3 | `supabase_content.py:352` | `list_digests` fetches every private body without a filter. | Filter by the returned digest IDs. |
| CL-11 | P3 | `website/lib/digests.ts:82` | `sampleDigest` (~90 lines) is unused. | Remove. |
| CL-12 | P3 | `examples/digest.example.json` | Metric direction is ambiguous ("31% or better", success "26%", stop "34%"), and agents copy this example. | Make the direction explicit (lower is better, or use a different metric). |

---

## C. Frontend

**Evidence method:** the website was copied to a scratch directory with `npm ci`. Supabase reads were replaced by fixture rows built from `examples/digest.example.json` through `public_digest_body`, plus a 10-item stress digest (4 Actions, 6 Signals, one `contradicts`). It was rendered with Playwright at 1440×900 and 390×844.

| ID | Pri | Location | Finding (evidence) | Fix |
|---|---|---|---|---|
| FE-1 | P1 | `website/app/digests/[slug]/page.tsx:174`, `:120-128` | Label "Private Mellanni evidence · values withheld" renders directly above "$1.25M in sales and 31% contribution efficiency… ASIN B012345678". Stale since commit `e948cfc` allowed member-visible metrics. The sample-notice copy has the same problem ("no… performance metrics"). | Relabel as "Mellanni evidence" and update the sample copy. |
| FE-2 | P1 | digest page | 10-item digest measured **12,403px** on desktop and **16,433px** on mobile. First finding at 1,514px; each Action about 1,300px, each Signal about 835px. No overview or jump list. | Add a top summary table (type, title, KPI, timebox, confidence, `#id` link) and collapse secondary detail per item. |
| FE-3 | P1 | digest page, `.source-notes` | On mobile, sources start at 15,491px. Every inline "Evidence" link jumps there with no way back. | Render sources inline per finding, or add "back to finding" links. |
| FE-4 | P1 | `page.tsx:171,199,230,235` | Agent plumbing shown to employees: `mellanni://skills/...` blocks with "Needs:/Next:" (174px each), and a Professional Memory note on every item, including `no-relevant-record`. | Hide skill references or put them in `<details>`. Show memory only for `contradicts`/`extends`. |
| FE-5 | P1 | `website/components/search-explorer.tsx`, `website/lib/search.ts` | Results are whole digest cards, not the matching finding. Query is not in the URL. | Return finding-level hits with `#id` deep links; persist `?q=`. |
| FE-6 | P2 | `website/app/page.tsx` | At 1440×900 the first screen is entirely hero (96px h1); latest digest content starts about 1,500px down. Copy describes a different product ("sales economics, inventory, search behavior", "four disconnected reports"). `:30-33` "Editorial note / 01" references a "sample edition… without reporting account performance". `:41` "Latest briefing" eyebrow sits over a slogan. Three static brochure sections. | Lead with the latest digest: its contradictions and top items, then the archive. Remove the brochure sections. |
| FE-7 | P2 | `website/app/globals.css:41`, `.digest-header h1` | A realistic digest title at `clamp(3rem, 7vw, 6rem)` fills the entire first viewport on desktop and mobile. | Cap at about 3rem for digest titles. |
| FE-8 | P2 | `website/components/site-header.tsx:8` | "Admin" is shown to readers; the proxy silently redirects them. No `aria-current`. | Show it only for the admin role; add `aria-current`. |
| FE-9 | P2 | admin console | No draft preview, so admins publish without seeing the rendered page. | Add an admin-only draft preview route (RLS already allows admin reads). |
| FE-10 | P3 | `globals.css:12-13` | Mac-only font stack (Iowan Old Style, Avenir Next); Windows and Linux employees get fallbacks. | Self-host with `next/font`. |
| FE-11 | P3 | `globals.css` | Contradiction colors (`#ead8d1`, `#6d2d1f`, `#59271c`, `#c69688`) hard-coded outside the tokens. Link underline `--color-rule` is 2.1:1 on canvas. | Tokenize; strengthen the underline. |
| FE-12 | P3 | calendar page | A month grid for one digest a week adds little; mobile hides titles. | Replace with a month-grouped list. |

**Measured contrast (passes):** muted on canvas 5.47:1, muted on strong surface 4.83:1, contradiction text 8.8:1, accent-dark on soft 8.25:1, focus ring 6.43:1. No horizontal overflow at 390px.

**Keep:** contradictions-first panel, semantic structure, skip link, reduced-motion handling, token discipline, clean mobile reflow.

---

## Checks run

- **Python:** `UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest discover -s tests` ran 109 tests with 1 failure (CL-6, time-rot).
- **Node:** `node --test tests/test_youtube_summary.mjs` passed 19/19.
- **Website:** typecheck, lint, and build all passed. They ran in a scratch copy because the repo has no `website/node_modules`; the scratch copy was deleted afterwards.

## Not tested

- **Pages:** search, calendar, login, admin, and 404 were not rendered. Only home and digest pages were checked, on desktop and mobile.
- **Accessibility:** no keyboard/focus pass and no 200% zoom pass.
- **Live/auth:** live Supabase source config, the auth boundary, RLS behavior, and the admin publish path were not executed (no credentials used).

## Constraints for whoever picks this up

- Follow `AGENTS.md` and `skills/mellanni-marketing-operator/SKILL.md`. Use `uv run` only.
- No live DB mutations, migrations, Auth changes, or deploys without explicit approval.
- AR-1, AR-4, AR-5, and AR-10 change validation contracts. Update `references/operations.md`, `references/editorial-contract.md`, and the tests in the same change.
- User-visible changes need rendered desktop and mobile checks before completion.
- Do not commit or push until the requested review/approval gate is satisfied.
