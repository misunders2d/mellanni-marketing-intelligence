---
name: mellanni-marketing-operator
description: Operate and maintain the Mellanni Marketing Intelligence repository, including private company authentication and access control, live Supabase sources, command-run collection and digest creation, publication state, YouTube summaries, website checks, and deployment. Use only inside this repository.
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
- Default to draft. Publish only on explicit user instruction.
- Prefer reversible removal: pause source; return digest to draft. Hard delete requires explicit approval and a separate reviewed action.
- Main editorial goal: retain strong, useful ecommerce knowledge across Amazon, DTC, retail, marketplaces, creator commerce, advertising, retention, operations, and adjacent channels. Do not narrow the digest to Amazon.
- Every included Action or External Signal must reconcile against Professional Memory. Do not mutate Professional Memory during digest generation.
- If Mellanni skill inventory/load or Professional Memory search/get capability is absent, stop synthesis, record the manifest with `record-run --outcome no-digest --reason ...`, and report the missing capability. Never substitute general knowledge.
- Actions are Mellanni-specific and backed by private queried Mellanni evidence. External Signals remain included when useful even if no Mellanni evidence exists.
- Employee-visible digest `body` must contain no private values, account identifiers, query results, or Professional Memory records. Exact decision values go to admin-only `digest_private_bodies`; raw evidence stays only in private run packet.
- Website access requires active `@mellanni.com` membership plus Google OAuth. Anonymous and non-OAuth sessions receive no content. Reader and admin database access stays enforced by RLS, not redirect logic.
- Use direct evidence URLs in digest snapshot. Do not present external claims as Mellanni results.
- Use external temporary directory for every run. Never place fetched source text or generated digest artifacts in Git.

## Routing

- Source list/add/edit/pause/enable: follow **Source operations** in operations reference.
- Weekly/manual digest: follow **Digest run** end to end and satisfy editorial contract.
- YouTube evidence: use `scripts/youtube-summary.mjs`; preserve URL and summary limitations.
- Website/repo maintenance: follow **Website and deployment** plus repository `AGENTS.md` verification.

## Completion evidence

Report exact source count, manifest status/counts, digest slug/status, authenticated reader readback when published, checks run, and any skipped live step. Never report success from a write response alone; read back resulting source/digest state.
