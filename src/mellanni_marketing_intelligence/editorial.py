from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DIGEST_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "digest.schema.json"
EVIDENCE_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "evidence-packet.schema.json"
MEMBER_VISIBLE_RESTRICTED_PATTERNS = (
    (
        "secret or credential",
        re.compile(
            r"\b(?:(?:api|oauth|client|access|refresh|private)[\s_-]*)?"
            r"(?:secret|password|token|credential|private\s+key)\s*[:=]\s*\S{6,}",
            re.IGNORECASE,
        ),
    ),
    (
        "email address",
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    ),
    (
        "phone number",
        re.compile(
            r"\b(?:(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}|"
            r"(?:phone|tel(?:ephone)?|mobile|contact|callback)\s*[:=]?\s*"
            r"(?:\+?1[\s.-]?)?(?:\d{10}|\d{3}[\s.-]\d{4}))\b",
            re.IGNORECASE,
        ),
    ),
    (
        "labeled personal name",
        re.compile(
            r"\b(?i:customer|employee|member)(?:\s+name)?\s*[:=]?\s+"
            r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"
        ),
    ),
    ("Amazon order ID", re.compile(r"\b\d{3}-\d{7}-\d{7}\b")),
    ("unformatted long digit run", re.compile(r"\b\d{12,}\b")),
    (
        "raw provider row",
        re.compile(r"\b(?:raw\s+)?(?:provider\s+)?row\s*[:=]\s*\{", re.IGNORECASE),
    ),
    (
        "account or identity identifier",
        re.compile(
            r"\b(?:account|auth(?:entication)?(?:[\s_-]+user)?|billing(?:[\s_-]+profile)?|"
            r"payment|customer|employee|member)[\s_-]+(?:ID|identifier|number|UUID)\s*"
            r"[:#=]?\s*[A-Z0-9][A-Z0-9_-]{4,}\b",
            re.IGNORECASE,
        ),
    ),
)
MEMBER_VISIBLE_VALUE_PATTERNS = (
    re.compile(r"(?:[$€£]\s?\d|\b(?:USD|EUR|GBP)\s+\d)", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+)?\s?%"),
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:percent|pct)\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+)?\s*[x×](?!\w)", re.IGNORECASE),
    re.compile(
        r"\b\d+(?:,\d{3})*(?:\.\d+)?\s+"
        r"(?:units?|orders?|clicks?|impressions?|sessions?|sales)\b",
        re.IGNORECASE,
    ),
)
MEMBER_VISIBLE_BUSINESS_IDENTIFIER_PATTERNS = (
    re.compile(r"\bB0[A-Z0-9]{8}\b", re.IGNORECASE),
    re.compile(
        r"\bSKU(?:\s+(?:ID|name))?\s*(?:[:#=]\s*|\s+)"
        r"[A-Z0-9][A-Z0-9_-]{2,}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:campaign|portfolio|keyword|search\s+term)\s+(?:ID|name)\s*"
        r"[:#=]?\s*[A-Z0-9][A-Z0-9_-]{2,}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:campaign|portfolio|keyword|search\s+term)\s+"
        r"(?=[A-Z0-9_-]*[-_])[A-Z0-9][A-Z0-9_-]{2,}\b",
        re.IGNORECASE,
    ),
)


def _load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_schema(document: dict[str, Any], path: Path, label: str) -> None:
    validator = Draft202012Validator(_load_schema(path), format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if not errors:
        return
    error = errors[0]
    location = ".".join(str(part) for part in error.absolute_path) or "<root>"
    raise ValueError(f"{label} schema error at {location}: {error.message}")


def validate_evidence_packet(packet: dict[str, Any]) -> None:
    _validate_schema(packet, EVIDENCE_SCHEMA_PATH, "evidence packet")

    signal_ids = [signal["id"] for signal in packet["signals"]]
    if len(signal_ids) != len(set(signal_ids)):
        raise ValueError("evidence packet signal IDs must be unique")

    source_ids = {source["id"] for source in packet["sources"]}
    if len(source_ids) != len(packet["sources"]):
        raise ValueError("evidence packet source IDs must be unique")
    for signal in packet["signals"]:
        missing = set(signal["sourceIds"]) - source_ids
        if missing:
            raise ValueError(
                f"evidence packet signal {signal['id']!r} references missing sources: "
                + ", ".join(sorted(missing))
            )

    record_ids = {record["id"] for record in packet["memoryRecords"]}
    reconciliation_ids: set[str] = set()
    reconciled_findings: set[str] = set()
    for reconciliation in packet["memoryReconciliations"]:
        reconciliation_id = reconciliation["id"]
        finding_id = reconciliation["findingId"]
        if reconciliation_id in reconciliation_ids:
            raise ValueError("evidence packet memory reconciliation IDs must be unique")
        if finding_id in reconciled_findings:
            raise ValueError(
                f"evidence packet finding {finding_id!r} has multiple memory reconciliations"
            )
        reconciliation_ids.add(reconciliation_id)
        reconciled_findings.add(finding_id)
        if finding_id not in signal_ids:
            raise ValueError(
                f"memory reconciliation {reconciliation_id!r} references a missing signal"
            )
        missing = set(reconciliation["recordIds"]) - record_ids
        if missing:
            raise ValueError(
                f"memory reconciliation {reconciliation_id!r} references missing records: "
                + ", ".join(sorted(missing))
            )
        has_records = bool(reconciliation["recordIds"])
        if reconciliation["outcome"] == "no-relevant-record" and has_records:
            raise ValueError("no-relevant-record reconciliation cannot cite memory records")
        if reconciliation["outcome"] != "no-relevant-record" and not has_records:
            raise ValueError(
                f"memory reconciliation {reconciliation_id!r} needs at least one record"
            )

    missing_reconciliations = set(signal_ids) - reconciled_findings
    if missing_reconciliations:
        raise ValueError(
            "evidence packet signals need memory reconciliation: "
            + ", ".join(sorted(missing_reconciliations))
        )

    query_ids: set[str] = set()
    for query in packet["mellanniQueries"]:
        if query["id"] in query_ids:
            raise ValueError("evidence packet Mellanni query IDs must be unique")
        query_ids.add(query["id"])
        if query["findingId"] not in signal_ids:
            raise ValueError(
                f"Mellanni query {query['id']!r} references a missing signal"
            )

    skill_uris = [skill["uri"] for skill in packet["skillInventory"]]
    if len(skill_uris) != len(set(skill_uris)):
        raise ValueError("evidence packet skill inventory URIs must be unique")
    skill_inventory = set(skill_uris)
    used_skill_uris = {
        packet["memoryBatch"]["skillUri"],
        *(query["skillUri"] for query in packet["mellanniQueries"]),
    }
    missing_skills = used_skill_uris - skill_inventory
    if missing_skills:
        raise ValueError(
            "evidence packet uses skills absent from captured inventory: "
            + ", ".join(sorted(missing_skills))
        )


def _string_fields(value: Any, path: str = "body") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, list):
        return [
            field
            for index, item in enumerate(value)
            for field in _string_fields(item, f"{path}[{index}]")
        ]
    if isinstance(value, dict):
        return [
            field
            for key, item in value.items()
            for field in _string_fields(item, f"{path}.{key}")
        ]
    return []


def _member_visible_text(document: dict[str, Any]) -> list[tuple[str, str]]:
    projected = _project_member_visible_body(document, privacy={})
    return [
        ("title", document["title"]),
        ("summary", document["summary"]),
        *_string_fields(projected),
    ]


def _derived_member_visible_privacy(document: dict[str, Any]) -> dict[str, bool]:
    values = [value for _, value in _member_visible_text(document)]
    return {
        "exactValuesPublished": any(
            pattern.search(value)
            for value in values
            for pattern in MEMBER_VISIBLE_VALUE_PATTERNS
        ),
        "businessIdentifiersPublished": any(
            pattern.search(value)
            for value in values
            for pattern in MEMBER_VISIBLE_BUSINESS_IDENTIFIER_PATTERNS
        ),
    }


def _mask_business_identifiers(value: str) -> str:
    for pattern in MEMBER_VISIBLE_BUSINESS_IDENTIFIER_PATTERNS:
        value = pattern.sub("<business-identifier>", value)
    return value


def _validate_member_visible_content(document: dict[str, Any]) -> None:
    for location, value in _member_visible_text(document):
        for label, pattern in MEMBER_VISIBLE_RESTRICTED_PATTERNS:
            candidate = (
                _mask_business_identifiers(value)
                if label == "unformatted long digit run"
                else value
            )
            if pattern.search(candidate):
                raise ValueError(
                    f"authenticated digest {location} contains a restricted {label}"
                )
    expected_privacy = _derived_member_visible_privacy(document)
    if document["privacy"] != expected_privacy:
        raise ValueError(
            "digest privacy flags do not match member-visible content: "
            + json.dumps(expected_privacy, sort_keys=True)
        )


def validate_digest(document: dict[str, Any], packet: dict[str, Any]) -> None:
    _validate_schema(document, DIGEST_SCHEMA_PATH, "digest")
    validate_evidence_packet(packet)
    date.fromisoformat(document["date"])
    _validate_member_visible_content(document)

    findings = [*document["actions"], *document["signals"]]
    if not findings:
        raise ValueError("digest needs at least one Action or External Signal")

    finding_ids = [finding["id"] for finding in findings]
    if len(finding_ids) != len(set(finding_ids)):
        raise ValueError("digest Action and External Signal IDs must be unique")

    packet_signals = {signal["id"]: signal for signal in packet["signals"]}
    digest_sources = {source["id"] for source in document["sources"]}
    packet_sources = {source["id"] for source in packet["sources"]}
    reconciliation_by_id = {
        reconciliation["id"]: reconciliation
        for reconciliation in packet["memoryReconciliations"]
    }
    queries_by_id = {query["id"]: query for query in packet["mellanniQueries"]}
    skill_inventory = {skill["uri"] for skill in packet["skillInventory"]}
    prior_references = {
        prior["digestSlug"] + "#" + prior["findingId"]
        for prior in packet["priorDigestFindings"]
    }

    if digest_sources - packet_sources:
        raise ValueError("digest sources must exist in private evidence packet")
    if len(digest_sources) != len(document["sources"]):
        raise ValueError("digest source IDs must be unique")
    if set(finding_ids) != set(packet_signals):
        raise ValueError("digest findings must exactly match selected packet signals")

    packet_source_rows = {source["id"]: source for source in packet["sources"]}
    for source in document["sources"]:
        packet_source = packet_source_rows[source["id"]]
        for field in ("name", "url", "note", "publishedAt"):
            if source.get(field) != packet_source.get(field):
                raise ValueError(
                    f"digest source {source['id']!r} {field} differs from packet"
                )

    for finding in findings:
        finding_id = finding["id"]
        packet_signal = packet_signals.get(finding_id)
        if packet_signal is None:
            raise ValueError(f"digest finding {finding_id!r} has no packet signal")
        if finding["externalSignal"] != packet_signal["statement"]:
            raise ValueError(
                f"digest finding {finding_id!r} changes packet external signal text"
            )
        if set(finding["sourceIds"]) != set(packet_signal["sourceIds"]):
            raise ValueError(
                f"digest finding {finding_id!r} source IDs differ from packet signal"
            )
        if set(finding["sourceIds"]) - digest_sources:
            raise ValueError(f"digest finding {finding_id!r} references a missing public source")

        memory_refs = finding["memory"]["privateEvidenceRefs"]
        if finding["memory"]["outcome"] == "no-relevant-record":
            matching_reconciliations = [
                reconciliation
                for reconciliation in packet["memoryReconciliations"]
                if reconciliation["findingId"] == finding_id
            ]
        else:
            matching_reconciliations = [
                reconciliation_by_id[reference]
                for reference in memory_refs
                if reference in reconciliation_by_id
            ]
        if len(matching_reconciliations) != 1:
            raise ValueError(
                f"digest finding {finding_id!r} must resolve to one memory reconciliation"
            )
        reconciliation = matching_reconciliations[0]
        if reconciliation["findingId"] != finding_id:
            raise ValueError(
                f"digest finding {finding_id!r} cites another finding's memory reconciliation"
            )
        for field in ("outcome", "comparison", "decisionImpact"):
            if finding["memory"][field] != reconciliation[field]:
                raise ValueError(
                    f"digest finding {finding_id!r} memory {field} differs from packet"
                )

        novelty = finding["novelty"]
        if novelty["status"] == "supersedes" and novelty["reference"] not in prior_references:
            raise ValueError(
                f"digest finding {finding_id!r} supersedes an unknown prior finding"
            )

        for skill in finding["skillReferences"]:
            if skill["uri"] not in skill_inventory:
                raise ValueError(
                    f"digest finding {finding_id!r} cites skill absent from packet inventory: "
                    + skill["uri"]
                )

    for action in document["actions"]:
        query_refs = action["mellanniEvidence"]["privateQueryRefs"]
        if any(reference not in queries_by_id for reference in query_refs):
            raise ValueError(f"Action {action['id']!r} references a missing Mellanni query")
        if any(queries_by_id[reference]["findingId"] != action["id"] for reference in query_refs):
            raise ValueError(f"Action {action['id']!r} cites another finding's Mellanni query")
        queried_entity_ids = {
            entity_id
            for reference in query_refs
            for entity_id in queries_by_id[reference]["entityIds"]
        }
        private_entity_ids = set(action["privateDecision"]["entityIds"])
        if private_entity_ids - queried_entity_ids:
            raise ValueError(
                f"Action {action['id']!r} private decision cites an entity absent from "
                "its Mellanni queries"
            )


def _project_member_visible_body(
    document: dict[str, Any],
    *,
    privacy: dict[str, bool],
) -> dict[str, Any]:
    actions = []
    for action in document["actions"]:
        public_action = {
            key: value
            for key, value in action.items()
            if key not in {"memory", "mellanniEvidence", "privateDecision"}
        }
        public_action["memory"] = {
            key: value
            for key, value in action["memory"].items()
            if key != "privateEvidenceRefs"
        }
        public_action["mellanniEvidence"] = {
            key: value
            for key, value in action["mellanniEvidence"].items()
            if key != "privateQueryRefs"
        }
        actions.append(public_action)

    signals = []
    for signal in document["signals"]:
        public_signal = {key: value for key, value in signal.items() if key != "memory"}
        public_signal["memory"] = {
            key: value
            for key, value in signal["memory"].items()
            if key != "privateEvidenceRefs"
        }
        signals.append(public_signal)

    return {
        "schemaVersion": 2,
        "topics": document["topics"],
        "privacy": privacy,
        "actions": actions,
        "signals": signals,
        "sources": document["sources"],
        "isSample": document.get("isSample") is True,
    }


def public_digest_body(document: dict[str, Any]) -> dict[str, Any]:
    return _project_member_visible_body(
        document,
        privacy=_derived_member_visible_privacy(document),
    )


def private_digest_body(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "actions": [
            {
                "id": action["id"],
                "title": action["title"],
                "privateDecision": action["privateDecision"],
            }
            for action in document["actions"]
        ],
    }
