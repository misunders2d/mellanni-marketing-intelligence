from __future__ import annotations

import json
from copy import deepcopy
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mellanni_marketing_intelligence.supabase_content import (
    build_parser,
    credentials,
    digest_to_row,
    fetch_enabled_sources,
    list_digests,
    list_sources,
    record_run,
    set_digest_state,
    set_source_state,
    source_document_to_row,
    source_rows_to_config,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def example_documents() -> tuple[dict, dict]:
    digest = json.loads(
        (PROJECT_ROOT / "examples" / "digest.example.json").read_text(encoding="utf-8")
    )
    packet = json.loads(
        (PROJECT_ROOT / "examples" / "evidence-packet.example.json").read_text(
            encoding="utf-8"
        )
    )
    return digest, packet


class SupabaseContentTests(unittest.TestCase):
    @patch("mellanni_marketing_intelligence.supabase_content.subprocess.run")
    def test_company_cli_profile_is_fallback_credential_source(self, run) -> None:
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                [{"name": "service_role", "type": "legacy", "api_key": "test-key"}]
            ),
        )
        with tempfile.TemporaryDirectory() as temp:
            url, key = credentials(Path(temp) / ".env", project_ref="example-ref")

        self.assertEqual(url, "https://example-ref.supabase.co")
        self.assertEqual(key, "test-key")
        self.assertEqual(run.call_args.kwargs["capture_output"], True)
        self.assertTrue(run.call_args.kwargs["env"]["SUPABASE_HOME"].endswith("/company"))

    @patch("mellanni_marketing_intelligence.supabase_content._request_json", return_value=[])
    def test_empty_enabled_source_list_is_an_error(self, request_json) -> None:
        with self.assertRaisesRegex(RuntimeError, "no enabled sources"):
            fetch_enabled_sources("https://example.supabase.co", "sb_secret_example")

        request_json.assert_called_once()

    def test_record_run_is_independent_of_digest_push(self) -> None:
        args = build_parser().parse_args(
            ["record-run", "--manifest", "journal/example/manifest.json"]
        )

        self.assertEqual(args.command, "record-run")
        self.assertIsNone(args.digest_id)
        self.assertEqual(args.outcome, "collection")

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_no_digest_outcome_overrides_successful_collection(self, request_json) -> None:
        manifest = {"exit_code": 0, "source_statuses": []}

        record_run(
            "https://example.supabase.co",
            "secret",
            manifest,
            digest_id=None,
            outcome="no-digest",
            reason="missing mellanni_skills_list",
        )

        payload = request_json.call_args.kwargs["payload"]
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["outcome"], "no-digest")
        self.assertEqual(payload["outcome_reason"], "missing mellanni_skills_list")

    def test_no_digest_outcome_requires_reason(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires a reason"):
            record_run(
                "https://example.supabase.co",
                "secret",
                {"exit_code": 0, "source_statuses": []},
                digest_id=None,
                outcome="no-digest",
            )

    def test_source_rows_match_fetcher_config_shape(self) -> None:
        config = source_rows_to_config([
            {
                "slug": "example-source",
                "name": "Example Source",
                "home_url": "https://example.com/",
                "priority": "B",
                "why": "Useful example",
                "include_patterns": ["/news/"],
                "allowed_hosts": [],
                "feed_urls": ["https://example.com/feed.xml"],
                "max_items": 7,
                "max_feed_candidates": 9,
            }
        ])

        self.assertEqual(config["sources"][0]["slug"], "example-source")
        self.assertEqual(config["sources"][0]["max_items"], 7)
        self.assertEqual(config["sources"][0]["feed_urls"], ["https://example.com/feed.xml"])

    def test_source_document_defaults_to_enabled(self) -> None:
        row = source_document_to_row(
            {
                "slug": "example-source",
                "name": "Example Source",
                "home_url": "https://example.com/",
            }
        )

        self.assertTrue(row["enabled"])
        self.assertEqual(row["max_items"], 5)
        self.assertEqual(row["max_feed_candidates"], 8)

    @patch("mellanni_marketing_intelligence.supabase_content._request_json", return_value=[])
    def test_list_sources_defaults_to_enabled_only(self, request_json) -> None:
        self.assertEqual(list_sources("https://example.supabase.co", "secret", include_disabled=False), [])
        self.assertIn("enabled=eq.true", request_json.call_args.args[2])

    @patch(
        "mellanni_marketing_intelligence.supabase_content._request_json",
        return_value=[{"slug": "example-source", "enabled": False}],
    )
    def test_source_can_be_paused_without_deletion(self, request_json) -> None:
        source = set_source_state(
            "https://example.supabase.co", "secret", "example-source", enabled=False
        )

        self.assertFalse(source["enabled"])
        self.assertEqual(request_json.call_args.kwargs["method"], "PATCH")
        self.assertEqual(request_json.call_args.kwargs["payload"], {"enabled": False})

    def test_digest_defaults_to_draft(self) -> None:
        digest, packet = example_documents()
        row = digest_to_row(
            digest,
            publish=False,
            evidence_packet=packet,
        )

        self.assertEqual(row["status"], "draft")
        self.assertIsNone(row["published_at"])
        self.assertEqual(row["body"]["schemaVersion"], 2)
        self.assertEqual(len(row["body"]["actions"]), 1)

    def test_legacy_generic_digest_is_rejected(self) -> None:
        _, packet = example_documents()
        with self.assertRaisesRegex(ValueError, "findings"):
            digest_to_row(
                {
                    "slug": "generic-weekly-brief",
                    "date": "2026-08-27",
                    "title": "Weekly brief",
                    "summary": "A concise summary.",
                    "topics": [],
                    "findings": ["Brands should test creator marketing."],
                    "sources": [],
                },
                publish=False,
                evidence_packet=packet,
            )

    def test_useful_external_signal_needs_no_mellanni_query(self) -> None:
        digest, packet = example_documents()
        digest["actions"] = []
        packet["signals"] = [packet["signals"][1]]
        packet["memoryReconciliations"] = [packet["memoryReconciliations"][1]]
        packet["mellanniQueries"] = []

        row = digest_to_row(digest, publish=False, evidence_packet=packet)

        self.assertEqual(len(row["body"]["signals"]), 1)
        self.assertEqual(row["body"]["actions"], [])

    def test_digest_caps_actions_at_four(self) -> None:
        digest, packet = example_documents()
        action = digest["actions"][0]
        packet_signal = packet["signals"][0]
        reconciliation = packet["memoryReconciliations"][0]
        query = packet["mellanniQueries"][0]
        digest["actions"] = []
        packet["signals"] = [packet["signals"][1]]
        packet["memoryReconciliations"] = [packet["memoryReconciliations"][1]]
        packet["mellanniQueries"] = []
        for index in range(5):
            finding_id = f"action-{index}"
            candidate = deepcopy(action)
            candidate["id"] = finding_id
            candidate["mellanniEvidence"]["privateQueryRefs"] = [f"query-{index}"]
            digest["actions"].append(candidate)
            signal = deepcopy(packet_signal)
            signal["id"] = finding_id
            packet["signals"].append(signal)
            memory = deepcopy(reconciliation)
            memory["id"] = f"memory-{index}"
            memory["findingId"] = finding_id
            packet["memoryReconciliations"].append(memory)
            evidence_query = deepcopy(query)
            evidence_query["id"] = f"query-{index}"
            evidence_query["findingId"] = finding_id
            packet["mellanniQueries"].append(evidence_query)

        with self.assertRaisesRegex(ValueError, "too long"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

    def test_action_requires_matching_private_mellanni_query(self) -> None:
        digest, packet = example_documents()
        digest["actions"][0]["mellanniEvidence"]["privateQueryRefs"] = ["missing-query"]

        with self.assertRaisesRegex(ValueError, "missing Mellanni query"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

    def test_every_included_signal_requires_memory_reconciliation(self) -> None:
        digest, packet = example_documents()
        packet["memoryReconciliations"] = packet["memoryReconciliations"][:1]

        with self.assertRaisesRegex(ValueError, "need memory reconciliation"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

    def test_skill_reference_must_resolve_in_packet_inventory(self) -> None:
        digest, packet = example_documents()
        digest["signals"][0]["skillReferences"][0]["uri"] = (
            "mellanni://skills/unavailable-skill"
        )

        with self.assertRaisesRegex(ValueError, "absent from packet inventory"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

    def test_every_used_mcp_skill_must_resolve_in_packet_inventory(self) -> None:
        digest, packet = example_documents()
        packet["skillInventory"] = [
            skill
            for skill in packet["skillInventory"]
            if skill["uri"] != "mellanni://skills/amazon-data-analysis"
        ]

        with self.assertRaisesRegex(ValueError, "absent from captured inventory"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

    def test_contradiction_is_valid_and_explicit(self) -> None:
        digest, packet = example_documents()
        digest["signals"][0]["memory"]["outcome"] = "contradicts"
        packet["memoryReconciliations"][1]["outcome"] = "contradicts"

        row = digest_to_row(digest, publish=False, evidence_packet=packet)

        self.assertEqual(row["body"]["signals"][0]["memory"]["outcome"], "contradicts")

    def test_private_evidence_is_not_copied_to_public_digest_body(self) -> None:
        digest, packet = example_documents()

        row = digest_to_row(digest, publish=False, evidence_packet=packet)
        public_json = json.dumps(row["body"])

        self.assertNotIn("evidencePacket", row["body"])
        self.assertNotIn("illustrative-private-portfolio", public_json)
        self.assertNotIn("results", public_json)
        self.assertNotIn("privateEvidenceRefs", public_json)
        self.assertNotIn("privateQueryRefs", public_json)
        self.assertNotIn("privateDecision", public_json)
        self.assertEqual(
            row["private_body"]["actions"][0]["privateDecision"],
            digest["actions"][0]["privateDecision"],
        )

    def test_public_digest_rejects_exact_private_values_and_identifiers(self) -> None:
        digest, packet = example_documents()
        digest["actions"][0]["mellanniEvidence"]["entityScope"] = "ASIN B012345678"
        with self.assertRaisesRegex(ValueError, "exact Amazon ASIN"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

        digest, packet = example_documents()
        digest["actions"][0]["kpi"] = "Reduce ACoS from 31%"
        with self.assertRaisesRegex(ValueError, "exact percentage value"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

        digest, packet = example_documents()
        digest["actions"][0]["kpi"] = "Reduce ACoS from 31 percent"
        with self.assertRaisesRegex(ValueError, "word-form percentage value"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

        digest, packet = example_documents()
        digest["actions"][0]["guidance"] = "Scale when return reaches 3.2x"
        with self.assertRaisesRegex(ValueError, "multiplier value"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

        digest, packet = example_documents()
        digest["sources"][0]["note"] = "Private baseline is 31 pct"
        packet["sources"][0]["note"] = "Private baseline is 31 pct"
        with self.assertRaisesRegex(ValueError, "word-form percentage value"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

    def test_private_decision_entities_must_come_from_queried_entities(self) -> None:
        digest, packet = example_documents()
        digest["actions"][0]["privateDecision"]["entityIds"] = ["unqueried-entity"]

        with self.assertRaisesRegex(ValueError, "entity absent"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

    def test_digest_sources_must_match_private_packet(self) -> None:
        digest, packet = example_documents()
        digest["sources"][0]["url"] = "https://example.com/changed"
        with self.assertRaisesRegex(ValueError, "url differs from packet"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

    def test_packet_signals_and_public_findings_must_match(self) -> None:
        digest, packet = example_documents()
        packet["signals"].append(
            {
                "id": "unused-signal",
                "statement": "Useful signal omitted from public digest.",
                "sourceIds": ["creator-source"],
            }
        )
        packet["memoryReconciliations"].append(
            {
                "id": "memory-unused-signal",
                "findingId": "unused-signal",
                "outcome": "no-relevant-record",
                "recordIds": [],
                "matchRationale": "No relevant record.",
                "comparison": "No relevant record.",
                "decisionImpact": "Keep as external signal.",
            }
        )
        with self.assertRaisesRegex(ValueError, "exactly match selected packet signals"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_private_evidence_packet_is_stored_only_with_run_record(self, request_json) -> None:
        _, packet = example_documents()
        manifest = {"exit_code": 0, "source_statuses": []}

        record_run(
            "https://example.supabase.co",
            "secret",
            manifest,
            digest_id="digest-id",
            evidence_packet=packet,
        )

        stored = request_json.call_args.kwargs["payload"]["manifest"]
        self.assertEqual(stored["collection"], manifest)
        self.assertEqual(stored["evidencePacket"], packet)

    @patch("mellanni_marketing_intelligence.supabase_content._request_json", return_value=[])
    def test_list_digests_can_filter_status(self, request_json) -> None:
        self.assertEqual(
            list_digests("https://example.supabase.co", "secret", status="published"), []
        )
        self.assertIn("status=eq.published", request_json.call_args.args[2])

    @patch(
        "mellanni_marketing_intelligence.supabase_content._request_json",
        return_value=[{"slug": "weekly-brief", "status": "draft"}],
    )
    def test_digest_can_be_hidden_without_deletion(self, request_json) -> None:
        digest = set_digest_state(
            "https://example.supabase.co", "secret", "weekly-brief", status="draft"
        )

        self.assertEqual(digest["status"], "draft")
        self.assertEqual(request_json.call_args.kwargs["payload"]["published_at"], None)

    def test_management_commands_are_parseable(self) -> None:
        self.assertEqual(build_parser().parse_args(["list-sources"]).command, "list-sources")
        self.assertEqual(
            build_parser()
            .parse_args(["set-source-state", "--slug", "example", "--state", "paused"])
            .state,
            "paused",
        )
        self.assertEqual(
            build_parser()
            .parse_args(["set-digest-state", "--slug", "weekly", "--state", "published"])
            .state,
            "published",
        )
        self.assertEqual(
            build_parser()
            .parse_args(
                [
                    "validate-evidence-packet",
                    "--input",
                    "evidence-packet.json",
                ]
            )
            .command,
            "validate-evidence-packet",
        )
        self.assertEqual(
            build_parser()
            .parse_args(
                [
                    "validate-digest",
                    "--input",
                    "digest.json",
                    "--evidence-packet",
                    "evidence-packet.json",
                ]
            )
            .command,
            "validate-digest",
        )


if __name__ == "__main__":
    unittest.main()
