# Editorial contract

## Goal

Produce a reliable source of useful ecommerce knowledge for running Mellanni. Include material knowledge across Amazon, DTC, retail, marketplaces, creator commerce, advertising, retention, operations, and adjacent ecommerce channels. Do not discard a strong external signal merely because current Mellanni data cannot validate it.

## Two public item types

### Mellanni Action

Use only when a private Mellanni query supports concrete guidance. Target two to four Actions when evidence supports them; maximum four. Never invent or weaken an Action to fill a quota.

Each Action needs:

- stable ID, title, exact external signal, and direct source IDs;
- Professional Memory outcome and explicit decision impact;
- safe public evidence summary with entity scope, source, Pacific-time window, and grain;
- one or more private Mellanni query references in evidence packet;
- exact private entity IDs, measured baseline, guidance, KPI, numeric success condition, and numeric stop condition for authenticated admin review;
- safe public guidance, timebox, KPI, relative success condition, relative stop condition, confidence, and limitations;
- novelty status: `novel`, or `supersedes` with prior digest/finding and material update;
- applicable installed Mellanni skill references.

Do not assign owner, person, or role. Assignment happens outside digest.

### External Signal

Use for strong ecommerce knowledge that helps Mellanni but does not have enough internal evidence for an Action. No numeric cap. Keep each Signal concise and material.

Each Signal needs:

- stable ID, title, exact external signal, and direct source IDs;
- Professional Memory outcome and explicit decision impact;
- why it matters to Mellanni or ecommerce decisions;
- exact next validation, data need, or test that could promote it to an Action;
- novelty status and applicable installed Mellanni skill references.

## Professional Memory reconciliation

Load `mellanni://skills/professional-memory-search`. After raw deduplication and item selection, run one deduplicated three-to-five-query semantic batch across all included Actions and External Signals. One follow-up batch is allowed only for a material gap. Retrieve selected records once.

Preserve query, record ID, memory timestamp, authority, match rationale, comparison, and decision impact in private evidence packet. Public digest carries only safe comparison and decision impact.

Allowed outcomes:

- `consistent`
- `contradicts`
- `extends`
- `no-relevant-record`

Memory is historical context, not automatic authority. Fresh first-party evidence may change current decision. Any contradiction appears first on public page and states both sides explicitly. Contradiction does not add a publication block beyond normal draft review.

Digest generation is read-only. Never mutate Professional Memory or Mellanni operational systems unless Sergey separately authorizes exact write.

## Mellanni evidence for Actions

Load `mellanni://skills/source-routing`, then exact provider playbook. Use provider-side query or deterministic script for calculations and joins. Never calculate or join business data manually in model context.

Private packet must identify concrete owned entity, provider, metric, exact value, Pacific-time window, grain, and query result. Keepa and Helium 10 may support research but do not replace first-party Mellanni evidence.

Public digest must not expose exact internal values, ASIN/SKU/campaign/portfolio/keyword identifiers, query results, or memory records. It shows only safe entity scope, evidence conclusion, source, window, grain, and relative success/stop conditions. Set both public privacy flags to `false`.

The same validated digest input carries `privateDecision` with exact entity IDs, measured baseline, guidance, KPI, and numeric success/stop conditions. The CLI removes that object from public `body` and stores it in admin-only `private_body`. Raw provider results and memory records remain only in private run record. Anonymous access to `private_body` is prohibited by column grants and RLS.

## Skill references

Capture live installed Mellanni skill inventory before synthesis. Do not invent, auto-install, or discover relay skills. Namespace every reference as `mellanni://skills/NAME`. `memoryBatch.skillUri`, every `mellanniQueries[*].skillUri`, and every finding reference must resolve in captured inventory or validation fails.

Each reference states:

- why applicable;
- required inputs;
- intended next operation.

Common routes include:

- `mellanni://skills/professional-memory-search`
- `mellanni://skills/source-routing`
- `mellanni://skills/helium10-research`
- `mellanni://skills/amazon-ads-reporting`
- `mellanni://skills/amazon-data-analysis`
- `mellanni://skills/bigquery-reporting`
- `mellanni://skills/sp-api-operations`
- `mellanni://skills/keepa-research`
- `mellanni://skills/mcp-tool-operations`

## Validation gates

Private packet follows `schemas/evidence-packet.schema.json`; digest input follows `schemas/digest.schema.json`. Storage projects that validated input into safe public `body` and admin-only `private_body`. Cross-field validator also enforces:

- every included item exists as stable packet signal and preserves exact signal/source IDs;
- every included item resolves to exactly one memory reconciliation;
- every Action resolves to private Mellanni query for same finding;
- every skill URI exists in captured inventory;
- every superseded finding exists in captured prior digests;
- no public sensitive values or identifiers;
- at least one Action or External Signal; at most four Actions;
- pipeline health stays in run record, never masquerades as marketing intelligence.

Today-style generic advice such as “brands should test creator content” without direct evidence, memory reconciliation, and Mellanni relevance fails. Preserve good sourced knowledge as External Signal; promote to Action only after private Mellanni query supports it.
