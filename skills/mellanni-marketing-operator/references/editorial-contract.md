# Editorial contract

## Goal

Produce a reliable source of useful ecommerce knowledge for running Mellanni. Include material knowledge across Amazon, DTC, retail, marketplaces, creator commerce, advertising, retention, operations, and adjacent ecommerce channels. Do not discard a strong external signal merely because current Mellanni data cannot validate it.

## Two employee-visible item types

### Mellanni Action

Use only when a private Mellanni query supports concrete guidance. Target two to four Actions when evidence supports them; maximum four. Never invent or weaken an Action to fill a quota.

Each Action needs:

- stable ID, title, exact external signal, and direct source IDs;
- Professional Memory outcome and explicit decision impact;
- authenticated member-visible evidence summary with entity scope, source, Pacific-time window, grain, and any exact internal commercial metrics or business entity identifiers needed to support the decision;
- one or more private Mellanni query references in evidence packet;
- full structured admin-only operational detail, including private auth/account/billing identifiers when required for an approved operation;
- member-visible guidance, timebox, KPI, exact or relative success condition, exact or relative stop condition, confidence, and limitations;
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

Preserve query, record ID, memory timestamp, authority, match rationale, comparison, and decision impact in private evidence packet. Member-visible digest may carry decision-useful internal metrics plus the selected comparison and decision impact, but never raw Professional Memory records.

Allowed outcomes:

- `consistent`
- `contradicts`
- `extends`
- `no-relevant-record`

Memory is historical context, not automatic authority. Fresh first-party evidence may change current decision. Any contradiction appears first on the employee-visible page and states both sides explicitly. Contradiction does not add a publication block beyond normal draft review.

Digest generation is read-only. Never mutate Professional Memory or Mellanni operational systems unless Sergey separately authorizes exact write.

## Mellanni evidence for Actions

Load `mellanni://skills/source-routing`, then exact provider playbook. Use provider-side query or deterministic script for calculations and joins. Never calculate or join business data manually in model context.

Private packet must identify concrete owned entity, provider, metric, exact value, Pacific-time window, grain, and query result. Keepa and Helium 10 may support research but do not replace first-party Mellanni evidence.

Member-visible digest is internal company content. It may include exact sales, spend, margin, advertising, conversion, inventory, percentage, unit, and decision-threshold values plus business entity identifiers needed to act, such as ASIN, SKU, campaign, portfolio, or keyword names/IDs. It must not expose secrets, credentials, private auth/account/billing identifiers, customer or employee PII, raw provider rows, or raw Professional Memory records. Set `privacy.exactValuesPublished` and `privacy.businessIdentifiersPublished` to match the member-visible digest; runtime validation derives both provenance-neutral flags and rejects mismatches. `rawEvidenceWithheld: true` means raw provider/query rows and raw memory records remain private, not that decision-useful internal data must be removed.

The same validated digest input carries `privateDecision` with full structured admin-only operational detail. The CLI removes that object from member-visible `body` and stores it in admin-only `digest_private_bodies.private_body`; decision-useful metrics, thresholds, and business entity identifiers may also appear in normal member-visible fields. Raw provider results and memory records remain only in private run record. Reader and anonymous access to private bodies is prohibited by grants and RLS.

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

Private packet follows `schemas/evidence-packet.schema.json`; digest input follows `schemas/digest.schema.json`. Storage projects that validated input into authenticated member-visible `body` and admin-only private body. Cross-field validator also enforces:

- every included item exists as stable packet signal and preserves exact signal/source IDs;
- every included item resolves to exactly one memory reconciliation;
- every Action resolves to private Mellanni query for same finding;
- every skill URI exists in captured inventory;
- every superseded finding exists in captured prior digests;
- member-visible exact business metrics and action-needed business entity identifiers are allowed; runtime scans every projected string plus title and summary for recognizable secrets/credentials, email addresses, phone numbers, labeled personal names, private account/auth/billing identifiers, Amazon order IDs, raw-row markers, and long unformatted digit runs, and derives the privacy flags;
- semantic review still excludes novel or obfuscated PII/secrets and raw provider or memory excerpts that deterministic patterns cannot recognize;
- at least one Action or External Signal; at most four Actions;
- pipeline health stays in run record, never masquerades as marketing intelligence.

Today-style generic advice such as “brands should test creator content” without direct evidence, memory reconciliation, and Mellanni relevance fails. Preserve good sourced knowledge as External Signal; promote to Action only after private Mellanni query supports it.
