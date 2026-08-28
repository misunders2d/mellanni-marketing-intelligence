# Mellanni Marketing Intelligence Agent Guide

This is one unified repository. Do not create another clone or worktree for project work.

Before collecting sources, changing live content, deploying, or maintaining this repo, read:

`./.agents/skills/mellanni-marketing-operator/SKILL.md`

## Repository map

- `src/mellanni_marketing_intelligence/`: deterministic collection and Supabase content CLI.
- `scripts/`: standalone helpers, including Gemini YouTube summary.
- `website/`: Next.js private company site with reader and admin tiers.
- `supabase/`: schema, RLS, grants, and local CLI config.
- `config/sources.json`: offline test fixture only. Supabase is live source authority.
- `schemas/`: private evidence-packet and validated digest-input JSON Schemas.
- `examples/`: non-sensitive example packet and digest contracts.

## Python environment

Install the locked project environment once, then run every Python command through `uv`:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync --locked
```

Do not use bare system `python`; digest validation depends on locked packages including `jsonschema`.

## Non-negotiable boundaries

- Explicit secrets may stay in ignored root `.env`; browser/Vercel receives publishable key only.
- On the Mellanni workstation, live CLI falls back to approved company Supabase profile at `~/.config/supabase/company`; profile access is the authority boundary and retrieved keys must never be printed.
- Script-directory access does not grant database authority. Live mutations require approved runner credentials and user authorization.
- Use project CLI for source/digest mutations. Do not improvise raw SQL or REST writes.
- Source removal means pause. Published digest removal means return to draft. Hard deletion needs explicit user approval and is not exposed by normal CLI.
- New or updated digest defaults to draft. Publish only when user explicitly requests publication.
- Put fetched pages, manifests, draft JSON, screenshots, and other run artifacts in a unique external temporary directory. Never commit or publish them. Delete them after verified DB write/readback.
- Anonymous users receive no site or database content. Active Google-authenticated `@mellanni.com` readers receive published safe `body` columns only. Admins may also read the separate `digest_private_bodies` table and operate sources, drafts, and runs.
- Preserve existing unrelated working-tree changes. Do not create extra repos or worktrees.

## Verification

- Python: `UV_CACHE_DIR=/tmp/uv-cache uv run python -m unittest discover -s tests -v`
- Website: from `website/`, run `npm run typecheck`, `npm run lint`, and `npm run build`.
- Auth boundary: verify anonymous page redirect plus anonymous REST denial, reader denial for private/admin tables, admin access, and inactive-member denial.
- Offboarding: use `supabase_content list-members --all` and `set-member-state --user-id ... --state inactive`; never mutate membership with raw SQL or target email alone. Prove denial before Auth session/account cleanup.
- User-visible changes also need rendered desktop/mobile checks before completion.
- Do not commit or push until requested review/approval gate is satisfied.
