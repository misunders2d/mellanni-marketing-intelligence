"""Deterministic scaffolds for agent-authored weekly synthesis files.

The runner pre-fills every field that is mechanically derived from the
collection manifest, the prior-digest snapshot, or the completed evidence
packet. The agent fills only fields that need judgment; validation still
checks every copied value, so a scaffold never weakens a gate.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


MEMORY_SKILL_URI = "mellanni://skills/professional-memory-search"


def prior_findings_index(prior_digests: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Every published finding an evidence packet may cite in priorDigestFindings."""
    index: list[dict[str, str]] = []
    for digest in prior_digests:
        slug = str(digest.get("slug", ""))
        body = digest.get("body")
        if not slug or not isinstance(body, dict):
            continue
        for finding in [*(body.get("actions") or []), *(body.get("signals") or [])]:
            if not isinstance(finding, dict):
                continue
            finding_id = str(finding.get("id", ""))
            title = str(finding.get("title", ""))
            if finding_id and title:
                index.append({"digestSlug": slug, "findingId": finding_id, "title": title})
    return index


def previously_published_urls(prior_digests: list[dict[str, Any]]) -> dict[str, str]:
    """Map each source URL cited by a published digest to the newest citing slug."""
    cited: dict[str, str] = {}
    for digest in prior_digests:
        slug = str(digest.get("slug", ""))
        body = digest.get("body")
        if not slug or not isinstance(body, dict):
            continue
        for source in body.get("sources") or []:
            if isinstance(source, dict) and isinstance(source.get("url"), str):
                cited.setdefault(source["url"], slug)
    return cited


def _source_name(item: dict[str, Any]) -> str:
    source_name = str(item.get("source_name") or "").strip()
    title = str(item.get("title") or "").strip()
    if source_name and title:
        return f"{source_name}: {title}"
    return title or source_name or str(item.get("url", ""))


def evidence_packet_scaffold(
    manifest: dict[str, Any],
    *,
    collection_manifest_sha256: str,
    prior_digests: list[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    """Packet skeleton with one review row and one source stub per manifest item.

    Items whose URL was already cited by a published digest are pre-excluded
    with a deterministic reason; the agent may override that decision. Source
    stubs cover every item: keep stubs only for included items and write each
    kept stub's note.
    """
    cited = previously_published_urls(prior_digests)
    reviews: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for item in manifest.get("items") or []:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("item_id", ""))
        url = str(item.get("url", ""))
        prior_slug = cited.get(url)
        reviews.append(
            {
                "itemId": item_id,
                "title": str(item.get("title") or ""),
                "url": url,
                "source": str(item.get("source_name") or item.get("source_slug") or ""),
                "disposition": "excluded" if prior_slug else None,
                "signalIds": [],
                "reason": (
                    f"Previously cited in published digest {prior_slug}; excluded unless "
                    "this item carries a material update."
                    if prior_slug
                    else ""
                ),
            }
        )
        source: dict[str, Any] = {
            "id": item_id,
            "name": _source_name(item),
            "url": url,
            "note": "",
        }
        if item.get("published_at"):
            source["publishedAt"] = str(item["published_at"])
        sources.append(source)
    return {
        "schemaVersion": 2,
        "generatedAt": generated_at,
        "collectionManifestSha256": collection_manifest_sha256,
        "itemReviews": reviews,
        "signals": [],
        "sources": sources,
        "priorDigestFindings": [],
        "memoryBatch": {"skillUri": MEMORY_SKILL_URI, "queries": []},
        "memoryRecords": [],
        "memoryReconciliations": [],
        "mellanniQueries": [],
        "skillInventory": [],
    }


def _joined(values: list[str]) -> str:
    return "; ".join(dict.fromkeys(value for value in values if value))


def digest_scaffold(
    packet: dict[str, Any], *, slug: str, date: str
) -> dict[str, Any]:
    """Digest skeleton that mirrors every packet-bound field.

    Packet signals with Mellanni queries become Actions; the rest become
    External Signals. Blank strings, empty lists, and empty novelty status mark
    the reasoning fields the agent must fill. Drop findings that do not make
    the final selection from both the packet and this digest.
    """
    reconciliations = {
        reconciliation["findingId"]: reconciliation
        for reconciliation in packet.get("memoryReconciliations") or []
    }
    queries_by_finding: dict[str, list[dict[str, Any]]] = {}
    for query in packet.get("mellanniQueries") or []:
        queries_by_finding.setdefault(query["findingId"], []).append(query)

    actions: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    for signal in packet.get("signals") or []:
        reconciliation = reconciliations.get(signal["id"])
        if reconciliation is None:
            memory = {
                "outcome": "",
                "comparison": "",
                "decisionImpact": "",
                "privateEvidenceRefs": [],
            }
        else:
            memory = {
                "outcome": reconciliation["outcome"],
                "comparison": reconciliation["comparison"],
                "decisionImpact": reconciliation["decisionImpact"],
                "privateEvidenceRefs": (
                    []
                    if reconciliation["outcome"] == "no-relevant-record"
                    else [reconciliation["id"]]
                ),
            }
        finding = {
            "id": signal["id"],
            "title": "",
            "externalSignal": signal["statement"],
            "sourceIds": list(signal["sourceIds"]),
            "memory": memory,
        }
        queries = queries_by_finding.get(signal["id"])
        if queries:
            actions.append(
                {
                    **finding,
                    "mellanniEvidence": {
                        "entityScope": "",
                        "conclusion": "",
                        "source": _joined([query.get("source", "") for query in queries]),
                        "window": _joined([query.get("window", "") for query in queries]),
                        "grain": _joined([query.get("grain", "") for query in queries]),
                        "privateQueryRefs": [query["id"] for query in queries],
                        "rawEvidenceWithheld": True,
                    },
                    "privateDecision": {
                        "entityIds": sorted(
                            {
                                entity_id
                                for query in queries
                                for entity_id in query.get("entityIds") or []
                            }
                        ),
                        "baseline": "",
                        "guidance": "",
                        "kpi": "",
                        "successCondition": "",
                        "stopCondition": "",
                    },
                    "guidance": "",
                    "timebox": "",
                    "kpi": "",
                    "successCondition": "",
                    "stopCondition": "",
                    "confidence": "",
                    "limitations": [],
                    "novelty": {"status": ""},
                    "skillReferences": [],
                }
            )
        else:
            signals.append(
                {
                    **finding,
                    "whyItMatters": "",
                    "nextValidation": "",
                    "novelty": {"status": ""},
                    "skillReferences": [],
                }
            )
    return {
        "schemaVersion": 2,
        "slug": slug,
        "date": date,
        "title": "",
        "summary": "",
        "topics": [],
        "actions": actions,
        "signals": signals,
        "sources": deepcopy(packet.get("sources") or []),
    }
