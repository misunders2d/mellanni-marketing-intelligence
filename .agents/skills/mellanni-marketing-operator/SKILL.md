---
name: mellanni-marketing-operator
description: Operate and maintain the Mellanni Marketing Intelligence repository, including live Supabase sources, command-run collection and digest creation, publication state, YouTube summaries, website checks, and deployment. Use only inside this repository.
---

# Mellanni Marketing Operator

Operate one system: Supabase source authority -> local deterministic collection -> evidence-bounded digest -> Supabase draft/publish -> dynamic Next.js website.

Read [references/operations.md](references/operations.md) before live source, digest, database, or deployment work.

## Core rules

- Work in current repository. Never create another clone or worktree.
- Treat Supabase as live authority. `config/sources.json` is offline fixture only.
- Use explicit ignored root `.env` credentials when provided; otherwise live CLI uses approved company Supabase profile. Never copy or print retrieved keys.
- Use `mellanni_marketing_intelligence.supabase_content` for DB operations. Avoid raw SQL/REST mutations.
- Keep collection deterministic. Agent work starts after manifest exists and is limited to evidence selection and synthesis.
- Default to draft. Publish only on explicit user instruction.
- Prefer reversible removal: pause source; return digest to draft. Hard delete requires explicit approval and a separate reviewed action.
- Use direct evidence URLs in digest snapshot. Do not present external claims as Mellanni results.
- Use external temporary directory for every run. Never place fetched source text or generated digest artifacts in Git.

## Routing

- Source list/add/edit/pause/enable: follow **Source operations** in operations reference.
- Weekly/manual digest: follow **Digest run** end to end.
- YouTube evidence: use `scripts/youtube-summary.mjs`; preserve URL and summary limitations.
- Website/repo maintenance: follow **Website and deployment** plus repository `AGENTS.md` verification.

## Completion evidence

Report exact source count, manifest status/counts, digest slug/status, public readback when published, checks run, and any skipped live step. Never report success from a write response alone; read back resulting source/digest state.
