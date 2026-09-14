---
name: mellanni-marketing-operator
description: Operate and maintain the Mellanni Marketing Intelligence repository, including its resumable weekly runner, private company authentication and access control, live Supabase sources, deterministic collection and digest creation, publication state, YouTube evidence, website checks, and deployment. Use only inside this repository.
---

# Mellanni Marketing Operator

Operate one system: Supabase source authority -> local deterministic collection -> private evidence packet -> useful ecommerce intelligence -> Supabase draft/publish -> dynamic Next.js website.

Read [references/operations.md](references/operations.md) before live source, digest, database, or deployment work.
Read [references/editorial-contract.md](references/editorial-contract.md) before selecting signals or writing a digest.

## Core rules

- Work in current repository. Never create another clone or worktree.
- Before Python work, run `UV_CACHE_DIR=/tmp/uv-cache uv sync --locked`; use `uv run python`, never bare system `python`.
- Treat Supabase as live authority. `config/sources.json` is offline fixture only.
- Use explicit ignored root `.env` credentials when provided; otherwise live CLI uses approved company Supabase profile. Never copy or print retrieved keys.
- Use `mellanni_marketing_intelligence.supabase_content` for DB operations. Avoid raw SQL/REST mutations.
- Keep collection deterministic. Agent work starts after manifest exists and is limited to evidence selection, exact MCP evidence capture, and synthesis from the validated packet.
- Collection fails closed on fatal source acquisition/parsing errors. Recoverable item failures and truncation remain warnings. Never replace a fatally failed source with one manually selected item.
- Run the repo-owned `mellanni-weekly` command for the current 13-source workflow. It owns snapshot, hash-bound collection, bounded YouTube processing, validation, draft write, exact readback, run link, and immutable receipt.
- Every collected item needs a hash-verified local artifact. Every collected video also needs hash-verified agentic Markdown and JSON artifacts bound to the immutable manifest; one missing or changed artifact stops the digest.
- Review every collected item once in `itemReviews`: included items name their Signal IDs; excluded items give a concrete reason. Keep podcast and YouTube findings episode-specific; never collapse a multi-episode week into one source-level sentence.
- Default to draft. Publish only on explicit user instruction.
- Prefer reversible removal: pause source; return digest to draft. Hard delete requires explicit approval and a separate reviewed action.
- Main editorial goal: retain strong, useful ecommerce knowledge across Amazon, DTC, retail, marketplaces, creator commerce, advertising, retention, operations, and adjacent channels. Do not narrow the digest to Amazon.
- Every included Action or External Signal must reconcile against Professional Memory. Do not mutate Professional Memory during digest generation.
- If Mellanni skill inventory/load or Professional Memory search/get capability is absent, stop synthesis and rerun the same `mellanni-weekly` command with `--fail-reason "<exact missing capability>"`; require its immutable no-digest receipt. Never call `record-run` directly or substitute general knowledge.
- Actions are Mellanni-specific and backed by private queried Mellanni evidence. External Signals remain included when useful even if no Mellanni evidence exists.
- Authenticated member-visible digest `body` may include exact sales, spend, conversion, profit, inventory, percentage, unit, and decision-threshold values plus business entity identifiers needed to act, such as ASIN, SKU, campaign, portfolio, or keyword names/IDs.
- Never put secrets, credentials, private auth/account/billing identifiers, customer or employee PII, raw provider query results, or raw Professional Memory records in member-visible `body`. Keep full structured admin detail in `privateDecision`/`digest_private_bodies`; raw evidence stays in the private run packet.
- Website access requires active `@mellanni.com` membership plus Google OAuth. Anonymous, inactive, and non-OAuth sessions receive no content. Reader and admin database access stays enforced by RLS, not redirect logic.
- Use direct evidence URLs in digest snapshot. Do not present external claims as Mellanni results.
- Publication requires an atomic database gate whose linked proof matches the current public and private digest content hash; old proof can never publish changed content.
- Use external temporary directory for every run. Never place fetched source text or generated digest artifacts in Git.

## Routing

- Source list/add/edit/pause/enable: follow **Source operations** in operations reference.
- Weekly/manual digest: follow **Digest run** end to end and satisfy editorial contract; use the same `mellanni-weekly` command to start and resume.
- YouTube evidence: let the weekly runner invoke `scripts/youtube-summary.mjs`; preserve every episode URL, result, and limitation.
- Website/repo maintenance: follow **Website and deployment** plus repository `AGENTS.md` verification.

## Completion evidence

Report exact source count, manifest status/counts, digest slug/status, content-hash-matched readback, authenticated reader readback when published, checks run, and any skipped live step. Never report success from a write response alone.
