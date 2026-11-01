from __future__ import annotations

import json
import hashlib
from copy import deepcopy
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mellanni_marketing_intelligence.supabase_content import (
    build_collection_proof,
    build_parser,
    build_run_proof,
    credentials,
    digest_content_sha256,
    digest_to_row,
    fetch_enabled_sources,
    list_digests,
    list_members,
    list_sources,
    main as supabase_main,
    push_digest,
    record_run,
    require_digest_readback,
    require_digest_ready_manifest,
    require_evidence_packet_bound_to_manifest,
    require_linked_digest_run,
    require_prior_digest_findings_bound,
    set_digest_state,
    set_member_state,
    set_source_state,
    source_document_to_row,
    source_rows_to_config,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def collection_items(root: Path, rows: list[tuple[str, str]]) -> list[dict]:
    item_dir = root / "items"
    item_dir.mkdir()
    items = []
    for index, (item_id, url) in enumerate(rows):
        artifact = item_dir / f"item-{index}.md"
        artifact.write_text(f"Evidence for {url}", encoding="utf-8")
        items.append(
            {
                "item_id": item_id,
                "url": url,
                "journal_path": f"items/item-{index}.md",
                "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            }
        )
    return items


def ready_youtube_manifest(root: Path, urls: list[str]) -> tuple[dict, Path, Path]:
    manifest_path = root / "manifest.json"
    manifest = {
        "schema_version": 3,
        "run_id": "test-run",
        "exit_code": 0,
        "source_failures": 0,
        "source_count": 1,
        "source_statuses": [{"slug": "source", "errors": []}],
        "items": collection_items(
            root,
            [(f"item-{index}", url) for index, url in enumerate(urls)],
        ),
        "item_count": len(urls),
        "manifest_path": str(manifest_path),
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    youtube_dir = root / "youtube"
    youtube_dir.mkdir()
    results = []
    for index, url in enumerate(urls):
        artifact = youtube_dir / f"item-{index}.md"
        details = youtube_dir / f"item-{index}.json"
        artifact.write_text(f"Evidence for {url}", encoding="utf-8")
        details.write_text("{}", encoding="utf-8")
        results.append(
            {
                "index": index,
                "item_id": f"item-{index}",
                "url": url,
                "model": "gemini-3.8-flash",
                "processing": "agentic",
                "processing_evidence": {
                    "processingCall": True,
                    "processingResult": True,
                    "agenticProcessingUsed": True,
                },
                "artifact_path": f"youtube/item-{index}.md",
                "details_path": f"youtube/item-{index}.json",
                "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                "details_sha256": hashlib.sha256(details.read_bytes()).hexdigest(),
            }
        )
    sidecar = {
        "schema_version": 2,
        "run_id": "test-run",
        "collection_manifest_sha256": manifest_hash,
        "status": "succeeded",
        "processing": "agentic",
        "expected": len(urls),
        "expected_urls": urls,
        "succeeded": len(urls),
        "failed": 0,
        "results": results,
        "failures": [],
    }
    sidecar_path = youtube_dir / "youtube-summary-manifest.json"
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    return manifest, manifest_path, sidecar_path


def ready_packet_manifest(
    root: Path, packet: dict
) -> tuple[dict, Path, Path]:
    manifest_path = root / "manifest.json"
    items = collection_items(
        root,
        [(source["id"], source["url"]) for source in packet["sources"]],
    )
    manifest = {
        "schema_version": 3,
        "run_id": "test-run",
        "exit_code": 0,
        "source_failures": 0,
        "source_count": 1,
        "source_statuses": [{"slug": "source", "errors": []}],
        "item_count": len(items),
        "items": items,
        "manifest_path": str(manifest_path),
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    packet["collectionManifestSha256"] = hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()
    youtube_dir = root / "youtube"
    youtube_dir.mkdir()
    sidecar = {
        "schema_version": 2,
        "run_id": "test-run",
        "collection_manifest_sha256": hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest(),
        "status": "not-required",
        "processing": "agentic",
        "expected": 0,
        "expected_urls": [],
        "succeeded": 0,
        "failed": 0,
        "results": [],
        "failures": [],
    }
    sidecar_path = youtube_dir / "youtube-summary-manifest.json"
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
    return manifest, manifest_path, sidecar_path


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


def stored_digest_row(digest: dict, packet: dict, digest_id: str = "digest-id") -> dict:
    row = digest_to_row(digest, publish=False, evidence_packet=packet)
    return {"id": digest_id, **row}


def keep_packet_signals(digest: dict, packet: dict, signal_ids: set[str]) -> None:
    packet["signals"] = [
        signal for signal in packet["signals"] if signal["id"] in signal_ids
    ]
    packet["memoryReconciliations"] = [
        reconciliation
        for reconciliation in packet["memoryReconciliations"]
        if reconciliation["findingId"] in signal_ids
    ]
    packet["mellanniQueries"] = [
        query for query in packet["mellanniQueries"] if query["findingId"] in signal_ids
    ]
    for review in packet["itemReviews"]:
        review["signalIds"] = [
            signal_id for signal_id in review["signalIds"] if signal_id in signal_ids
        ]
        if not review["signalIds"]:
            review["disposition"] = "excluded"
            review["reason"] = "Excluded from this focused test packet."
    included_item_ids = {
        review["itemId"]
        for review in packet["itemReviews"]
        if review["disposition"] == "included"
    }
    packet["sources"] = [
        source for source in packet["sources"] if source["id"] in included_item_ids
    ]
    digest["sources"] = [
        source for source in digest["sources"] if source["id"] in included_item_ids
    ]


class SupabaseContentTests(unittest.TestCase):
    def test_digest_manifest_rejects_failed_collection(self) -> None:
        with self.assertRaisesRegex(ValueError, "collection failed"):
            require_digest_ready_manifest({"exit_code": 2, "items": []})

    def test_digest_manifest_verifies_bound_youtube_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, manifest_path, _ = ready_youtube_manifest(
                root,
                [
                    "https://m.youtube.com/watch?v=one",
                    "https://youtu.be/two",
                ],
            )
            require_digest_ready_manifest(manifest, manifest_path)

    def test_digest_manifest_rejects_stale_sidecar_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, manifest_path, sidecar_path = ready_youtube_manifest(
                root, ["https://www.youtube.com/watch?v=one"]
            )
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            sidecar["run_id"] = "stale-run"
            sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stale YouTube sidecar run_id mismatch"):
                require_digest_ready_manifest(manifest, manifest_path)

    def test_digest_manifest_rejects_collection_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, manifest_path, sidecar_path = ready_youtube_manifest(
                root, ["https://www.youtube.com/watch?v=one"]
            )
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            sidecar["collection_manifest_sha256"] = "0" * 64
            sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sidecar manifest hash mismatch"):
                require_digest_ready_manifest(manifest, manifest_path)

    def test_digest_manifest_rejects_artifact_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, manifest_path, _ = ready_youtube_manifest(
                root, ["https://www.youtube.com/watch?v=one"]
            )
            (root / "youtube" / "item-0.md").write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "artifact hash mismatch"):
                require_digest_ready_manifest(manifest, manifest_path)

    def test_digest_manifest_rejects_youtube_details_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, manifest_path, _ = ready_youtube_manifest(
                root, ["https://www.youtube.com/watch?v=one"]
            )
            (root / "youtube" / "item-0.json").write_text(
                "tampered", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "details hash mismatch"):
                require_digest_ready_manifest(manifest, manifest_path)

    def test_digest_manifest_rejects_collection_artifact_hash_mismatch(self) -> None:
        digest, packet = example_documents()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, manifest_path, _ = ready_packet_manifest(root, packet)
            (root / "items" / "item-0.md").write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "collection artifact hash mismatch"):
                require_digest_ready_manifest(manifest, manifest_path)

    def test_evidence_packet_requires_review_for_every_collected_item(self) -> None:
        digest, packet = example_documents()
        with tempfile.TemporaryDirectory() as temp:
            manifest, manifest_path, _ = ready_packet_manifest(Path(temp), packet)
            keep_packet_signals(digest, packet, {"protect-margin-test"})
            packet["itemReviews"] = [
                review
                for review in packet["itemReviews"]
                if review["disposition"] == "included"
            ]
            with self.assertRaisesRegex(ValueError, "cover every collection manifest item"):
                require_evidence_packet_bound_to_manifest(
                    packet, manifest, manifest_path
                )

    def test_evidence_packet_rejects_foreign_manifest_hash(self) -> None:
        _, packet = example_documents()
        with tempfile.TemporaryDirectory() as temp:
            manifest, manifest_path, _ = ready_packet_manifest(Path(temp), packet)
            packet["collectionManifestSha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "manifest hash mismatch"):
                require_evidence_packet_bound_to_manifest(
                    packet, manifest, manifest_path
                )

    def test_prior_digest_reference_must_exist_in_captured_snapshot(self) -> None:
        _, packet = example_documents()
        packet["priorDigestFindings"] = [
            {
                "digestSlug": "older-digest",
                "findingId": "invented-finding",
                "title": "Invented finding",
            }
        ]
        with self.assertRaisesRegex(ValueError, "absent from the captured published snapshot"):
            require_prior_digest_findings_bound(packet, [])

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_publication_rejects_old_linked_run_without_compact_proof(
        self, request_json
    ) -> None:
        digest, packet = example_documents()
        row = stored_digest_row(digest, packet)
        request_json.side_effect = [
            [row],
            [{"digest_id": "digest-id", "private_body": row["private_body"]}],
            [
                {
                    "digest_id": "digest-id",
                    "status": "succeeded",
                    "outcome": "digest",
                    "manifest": {"collection": {"run_id": "old-run"}},
                }
            ],
        ]
        with self.assertRaisesRegex(ValueError, "no linked successful proof"):
            require_linked_digest_run(
                "https://example.supabase.co", "secret", digest["slug"]
            )

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_publication_rejects_content_locked_legacy_approval(self, request_json) -> None:
        digest, packet = example_documents()
        row = stored_digest_row(digest, packet)
        proof = {
            "schema_version": "legacy-1",
            "digest_content_sha256": row["content_sha256"],
            "legacy_approved_publication": True,
            "reason": "Previously approved publication restored after proof migration",
        }
        request_json.side_effect = [
            [row],
            [{"digest_id": "digest-id", "private_body": row["private_body"]}],
            [
                {
                    "digest_id": "digest-id",
                    "status": "succeeded",
                    "outcome": "digest",
                    "manifest": {"runProof": proof},
                }
            ],
        ]

        with self.assertRaisesRegex(ValueError, "no linked successful proof"):
            require_linked_digest_run(
                "https://example.supabase.co", "secret", digest["slug"]
            )

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_publication_rejects_invalid_legacy_approval(self, request_json) -> None:
        digest, packet = example_documents()
        row = stored_digest_row(digest, packet)
        proof = {
            "schema_version": "legacy-1",
            "digest_content_sha256": row["content_sha256"],
            "legacy_approved_publication": False,
            "reason": "Not approved",
        }
        request_json.side_effect = [
            [row],
            [{"digest_id": "digest-id", "private_body": row["private_body"]}],
            [
                {
                    "digest_id": "digest-id",
                    "status": "succeeded",
                    "outcome": "digest",
                    "manifest": {"runProof": proof},
                }
            ],
        ]

        with self.assertRaisesRegex(ValueError, "no linked successful proof"):
            require_linked_digest_run(
                "https://example.supabase.co", "secret", digest["slug"]
            )

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_publication_rejects_unverified_linked_proof(self, request_json) -> None:
        digest, packet = example_documents()
        with tempfile.TemporaryDirectory() as temp:
            manifest, manifest_path, _ = ready_packet_manifest(Path(temp), packet)
            proof = build_run_proof(
                manifest,
                manifest_path,
                digest_document=digest,
                evidence_packet=packet,
            )
        proof["agentic_verified"] = False
        row = stored_digest_row(digest, packet)
        request_json.side_effect = [
            [row],
            [{"digest_id": "digest-id", "private_body": row["private_body"]}],
            [
                {
                    "digest_id": "digest-id",
                    "status": "succeeded",
                    "outcome": "digest",
                    "manifest": {"runProof": proof},
                }
            ],
        ]
        with self.assertRaisesRegex(ValueError, "no linked successful proof"):
            require_linked_digest_run(
                "https://example.supabase.co", "secret", digest["slug"]
            )

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_publication_rejects_old_proof_for_changed_digest_content(
        self, request_json
    ) -> None:
        digest, packet = example_documents()
        with tempfile.TemporaryDirectory() as temp:
            manifest, manifest_path, _ = ready_packet_manifest(Path(temp), packet)
            proof = build_run_proof(
                manifest,
                manifest_path,
                digest_document=digest,
                evidence_packet=packet,
            )
        changed = deepcopy(digest)
        changed["summary"] = "Changed after the verified run."
        row = stored_digest_row(changed, packet)
        request_json.side_effect = [
            [row],
            [{"digest_id": "digest-id", "private_body": row["private_body"]}],
            [
                {
                    "digest_id": "digest-id",
                    "status": "succeeded",
                    "outcome": "digest",
                    "manifest": {"runProof": proof},
                }
            ],
        ]
        with self.assertRaisesRegex(ValueError, "no linked successful proof"):
            require_linked_digest_run(
                "https://example.supabase.co", "secret", digest["slug"]
            )

    def test_exact_readback_rejects_changed_private_body(self) -> None:
        digest, packet = example_documents()
        row = stored_digest_row(digest, packet)
        expected_hash = row["content_sha256"]
        row["private_body"] = {"schemaVersion": 1, "actions": []}
        with self.assertRaisesRegex(RuntimeError, "content did not match"):
            require_digest_readback(
                [row],
                digest_id="digest-id",
                slug=digest["slug"],
                status="draft",
                expected_content_sha256=expected_hash,
            )

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    @patch("mellanni_marketing_intelligence.supabase_content.credentials")
    def test_set_digest_published_uses_db_proof_after_raw_artifacts_deleted(
        self, credentials_mock, request_json
    ) -> None:
        credentials_mock.return_value = ("https://example.supabase.co", "secret")
        digest, packet = example_documents()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, manifest_path, sidecar_path = ready_packet_manifest(root, packet)
            proof = build_run_proof(
                manifest,
                manifest_path,
                digest_document=digest,
                evidence_packet=packet,
            )
            manifest_path.unlink()
            sidecar_path.unlink()
            sidecar_path.parent.rmdir()
            row = stored_digest_row(digest, packet)
            request_json.side_effect = [
                [row],
                [{"digest_id": "digest-id", "private_body": row["private_body"]}],
                [
                    {
                        "digest_id": "digest-id",
                        "status": "succeeded",
                        "outcome": "digest",
                        "manifest": {"runProof": proof},
                    }
                ],
                [{"id": "digest-id", "slug": digest["slug"], "status": "published"}],
            ]
            result = supabase_main(
                [
                    "set-digest-state",
                    "--slug",
                    digest["slug"],
                    "--state",
                    "published",
                ]
            )
        self.assertEqual(result, 0)
        self.assertEqual(request_json.call_count, 4)
        self.assertEqual(
            request_json.call_args_list[-1].args[2],
            "rpc/publish_digest_with_verified_run",
        )

    @patch("mellanni_marketing_intelligence.supabase_content.set_digest_state")
    @patch("mellanni_marketing_intelligence.supabase_content.require_linked_digest_run")
    @patch("mellanni_marketing_intelligence.supabase_content.credentials")
    def test_set_digest_published_manifest_is_optional_extra_validation(
        self, credentials_mock, linked_mock, state_mock
    ) -> None:
        credentials_mock.return_value = ("https://example.supabase.co", "secret")
        state_mock.return_value = {"slug": "weekly", "status": "published"}
        _, packet = example_documents()
        with tempfile.TemporaryDirectory() as temp:
            manifest, manifest_path, _ = ready_packet_manifest(Path(temp), packet)
            expected_proof = build_collection_proof(manifest, manifest_path)
            result = supabase_main(
                [
                    "set-digest-state",
                    "--slug",
                    "weekly",
                    "--state",
                    "published",
                    "--manifest",
                    str(manifest_path),
                ]
            )
        self.assertEqual(result, 0)
        linked_mock.assert_called_once_with(
            "https://example.supabase.co", "secret", "weekly", expected_proof
        )

    @patch("mellanni_marketing_intelligence.supabase_content.list_digests")
    @patch("mellanni_marketing_intelligence.supabase_content.set_digest_state")
    @patch("mellanni_marketing_intelligence.supabase_content.require_linked_digest_run")
    @patch("mellanni_marketing_intelligence.supabase_content.record_run")
    @patch("mellanni_marketing_intelligence.supabase_content.push_digest")
    @patch("mellanni_marketing_intelligence.supabase_content.credentials")
    def test_push_publish_cli_links_compact_proof_before_publication(
        self,
        credentials_mock,
        push_mock,
        record_mock,
        linked_mock,
        state_mock,
        list_mock,
    ) -> None:
        credentials_mock.return_value = ("https://example.supabase.co", "secret")
        push_mock.return_value = {
            "id": "digest-id",
            "slug": "2026-08-31-weekly-marketing-digest",
            "status": "draft",
        }
        state_mock.return_value = {
            "id": "digest-id",
            "slug": "2026-08-31-weekly-marketing-digest",
            "status": "published",
        }
        digest, packet = example_documents()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, manifest_path, _ = ready_packet_manifest(root, packet)
            digest_path = root / "digest.json"
            packet_path = root / "packet.json"
            digest_path.write_text(json.dumps(digest), encoding="utf-8")
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            expected_proof = build_run_proof(
                manifest,
                manifest_path,
                digest_document=digest,
                evidence_packet=packet,
            )
            list_mock.side_effect = [[], [stored_digest_row(digest, packet)]]
            result = supabase_main(
                [
                    "push-digest",
                    "--input",
                    str(digest_path),
                    "--evidence-packet",
                    str(packet_path),
                    "--manifest",
                    str(manifest_path),
                    "--publish",
                ]
            )
        self.assertEqual(result, 0)
        self.assertFalse(push_mock.call_args.kwargs["publish"])
        record_mock.assert_called_once()
        self.assertEqual(record_mock.call_args.kwargs["run_proof"], expected_proof)
        self.assertNotIn("evidence_packet", record_mock.call_args.kwargs)
        linked_mock.assert_called_once_with(
            "https://example.supabase.co",
            "secret",
            digest["slug"],
            expected_proof,
        )
        state_mock.assert_called_once_with(
            "https://example.supabase.co",
            "secret",
            "2026-08-31-weekly-marketing-digest",
            status="published",
        )

    @patch("mellanni_marketing_intelligence.supabase_content.record_run")
    @patch("mellanni_marketing_intelligence.supabase_content.push_digest")
    @patch("mellanni_marketing_intelligence.supabase_content.credentials")
    def test_foreign_valid_packet_fails_before_db_write_or_record(
        self, credentials_mock, push_mock, record_mock
    ) -> None:
        credentials_mock.return_value = ("https://example.supabase.co", "secret")
        digest, packet = example_documents()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, manifest_path, _ = ready_packet_manifest(root, packet)
            manifest["items"][0]["url"] = "https://example.com/foreign"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            packet["collectionManifestSha256"] = hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest()
            digest_path = root / "digest.json"
            packet_path = root / "packet.json"
            digest_path.write_text(json.dumps(digest), encoding="utf-8")
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "source URL/ID set does not match"):
                supabase_main(
                    [
                        "push-digest",
                        "--input",
                        str(digest_path),
                        "--evidence-packet",
                        str(packet_path),
                        "--manifest",
                        str(manifest_path),
                    ]
                )
        push_mock.assert_not_called()
        record_mock.assert_not_called()

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
        keep_packet_signals(digest, packet, {"creator-commerce-signal"})
        digest["privacy"] = {
            "exactValuesPublished": False,
            "businessIdentifiersPublished": False,
        }

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

        with self.assertRaisesRegex(ValueError, "actions: has 5 items; expected at most 4"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

    def test_digest_validation_reports_every_independent_error(self) -> None:
        digest, packet = example_documents()
        digest["actions"][0]["mellanniEvidence"]["privateQueryRefs"] = ["missing-query"]
        digest["signals"][0]["externalSignal"] = "Rewritten signal text."
        digest["sources"][0]["name"] = "Renamed source"

        with self.assertRaises(ValueError) as raised:
            digest_to_row(digest, publish=False, evidence_packet=packet)
        message = str(raised.exception)
        self.assertIn("validation errors", message)
        self.assertIn("missing Mellanni query", message)
        self.assertIn("changes packet external signal text", message)
        self.assertIn("name differs from packet", message)

    def test_schema_validation_reports_every_schema_error(self) -> None:
        digest, packet = example_documents()
        del digest["title"]
        del digest["summary"]
        del packet["memoryBatch"]

        with self.assertRaises(ValueError) as raised:
            digest_to_row(digest, publish=False, evidence_packet=packet)
        message = str(raised.exception)
        self.assertIn("'title' is a required property", message)
        self.assertIn("'summary' is a required property", message)
        self.assertIn("'memoryBatch' is a required property", message)

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

    def test_digest_rejects_every_unknown_memory_reference(self) -> None:
        digest, packet = example_documents()
        digest["signals"][0]["memory"]["privateEvidenceRefs"].append(
            "unknown-memory-reconciliation"
        )

        with self.assertRaisesRegex(ValueError, "unknown memory reconciliation"):
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

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_digest_push_uses_atomic_private_body_rpc(self, request_json) -> None:
        request_json.side_effect = [
            [],
            [{"id": "digest-id", "slug": "weekly-intelligence-brief", "status": "draft"}],
        ]
        digest, packet = example_documents()

        stored = push_digest(
            "https://example.supabase.co",
            "secret",
            digest,
            publish=False,
            evidence_packet=packet,
        )

        self.assertEqual(stored["id"], "digest-id")
        self.assertEqual(request_json.call_args.args[2], "rpc/upsert_digest_with_private_body")
        payload = request_json.call_args.kwargs["payload"]
        self.assertIn("p_body", payload)
        self.assertIn("p_private_body", payload)
        self.assertRegex(payload["p_content_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("private_body", payload["p_body"])

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_digest_push_refuses_to_unpublish_existing_slug(self, request_json) -> None:
        request_json.return_value = [{"id": "digest-id", "status": "published"}]
        digest, packet = example_documents()

        with self.assertRaisesRegex(ValueError, "currently published"):
            push_digest(
                "https://example.supabase.co",
                "secret",
                digest,
                publish=False,
                evidence_packet=packet,
            )
        request_json.assert_called_once()
        self.assertIn("slug=eq.", request_json.call_args.args[2])

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_digest_push_can_explicitly_replace_published_slug(self, request_json) -> None:
        request_json.side_effect = [
            [{"id": "digest-id", "status": "published"}],
            [{"id": "digest-id", "status": "draft"}],
        ]
        digest, packet = example_documents()

        stored = push_digest(
            "https://example.supabase.co",
            "secret",
            digest,
            publish=False,
            evidence_packet=packet,
            replace_published=True,
        )
        self.assertEqual(stored["status"], "draft")
        self.assertEqual(
            request_json.call_args.args[2], "rpc/upsert_digest_with_private_body"
        )

    def test_content_hash_rpc_migration_matches_digest_payload(self) -> None:
        migration = (
            PROJECT_ROOT
            / "supabase"
            / "migrations"
            / "20260907180000_content_bound_digest_publication.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("add column content_sha256 text", migration)
        self.assertIn("add column run_key text unique", migration)
        self.assertIn("p_content_sha256 text", migration)
        self.assertIn("publish_digest_with_verified_run", migration)
        self.assertIn("digests_guard_content_and_publication", migration)
        self.assertIn("before insert or update on public.digests", migration)
        self.assertIn("new digest must start as draft", migration)
        self.assertIn("where status = 'published'", migration)
        self.assertIn("digest_private_bodies_invalidate_digest", migration)
        self.assertIn("digest_content_sha256", migration)

    def test_legacy_restore_migration_is_exact_and_content_locked(self) -> None:
        migration = (
            PROJECT_ROOT
            / "supabase"
            / "migrations"
            / "20260910120000_restore_preproof_publications.sql"
        ).read_text(encoding="utf-8")
        self.assertGreaterEqual(migration.count("'legacy-1'"), 2)
        self.assertIn("has_verified_digest_publication_basis", migration)
        self.assertIn("legacy_approved_publication", migration)
        self.assertIn("expected_updated_at", migration)
        self.assertIn("restoration expected 3 rows", migration)
        for slug in (
            "2026-08-27-growth-needs-proof",
            "2026-08-28-contribution-gates-and-funnel-economics",
            "2026-08-31-weekly-marketing-digest",
        ):
            self.assertIn(slug, migration)

    def test_followup_migration_closes_legacy_publication_path(self) -> None:
        migration = (
            PROJECT_ROOT
            / "supabase"
            / "migrations"
            / "20260914120000_close_legacy_publication_path.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("has_verified_digest_publication_basis", migration)
        self.assertIn("schema_version' = '2'", migration)
        self.assertIn("agentic_verified' = 'true'", migration)
        self.assertNotIn("legacy_approved_publication", migration)
        self.assertNotIn("'legacy-1'", migration)
        self.assertIn("legacy publication lock expected 3 published rows", migration)

    def test_publication_timestamp_migration_keeps_proof_gate(self) -> None:
        migrations = PROJECT_ROOT / "supabase" / "migrations"
        previous = (migrations / "20260910120000_restore_preproof_publications.sql").read_text(
            encoding="utf-8"
        )
        migration = (migrations / "20261101120000_server_clock_digest_published_at.sql").read_text(
            encoding="utf-8"
        )

        def guard_body(sql: str) -> str:
            start = sql.index("create or replace function private.guard_digest_content_and_publication()")
            return sql[start : sql.index("$$;", start)]

        current = guard_body(migration)
        prior = guard_body(previous)
        for line in prior.splitlines():
            self.assertIn(line, current)
        self.assertIn("new.published_at := timezone('utc', now());", current)
        self.assertIn("new.published_at := old.published_at;", current)
        self.assertIn("has_verified_digest_publication_basis(", current)
        self.assertIn(
            "revoke all on function private.guard_digest_content_and_publication()",
            migration,
        )

    def test_authenticated_digest_allows_internal_business_metrics(self) -> None:
        digest, packet = example_documents()
        digest["summary"] = "Sales reached $1,250,000 across 18,400 orders."
        digest["actions"][0]["mellanniEvidence"]["entityScope"] = (
            "ASIN B012345678 / SKU MLN-SHEET-001 / campaign SP-BRAND-042"
        )
        digest["actions"][0]["kpi"] = "Reduce ACoS from 31%"
        digest["actions"][0]["guidance"] = "Scale when return reaches 3.2x."
        digest["sources"][0]["note"] = "Internal baseline is 31 pct."
        packet["sources"][0]["note"] = "Internal baseline is 31 pct."

        row = digest_to_row(digest, publish=False, evidence_packet=packet)

        self.assertEqual(
            row["summary"],
            "Sales reached $1,250,000 across 18,400 orders.",
        )
        self.assertTrue(row["body"]["privacy"]["exactValuesPublished"])
        self.assertTrue(row["body"]["privacy"]["businessIdentifiersPublished"])
        self.assertEqual(row["body"]["actions"][0]["kpi"], "Reduce ACoS from 31%")
        self.assertEqual(
            row["body"]["actions"][0]["guidance"],
            "Scale when return reaches 3.2x.",
        )
        self.assertIn(
            "ASIN B012345678",
            row["body"]["actions"][0]["mellanniEvidence"]["entityScope"],
        )

    def test_authenticated_digest_rejects_restricted_identity_identifiers(self) -> None:
        digest, packet = example_documents()
        digest["actions"][0]["mellanniEvidence"]["entityScope"] = (
            "Amazon account ID ACCT12345"
        )
        with self.assertRaisesRegex(
            ValueError,
            "restricted account or identity identifier",
        ):
            digest_to_row(digest, publish=False, evidence_packet=packet)

    def test_authenticated_digest_rejects_restricted_data_in_every_visible_field(self) -> None:
        cases = (
            ("summary", "customer email: jane@example.com", "email address"),
            ("summary", "Customer Jane Doe was refunded.", "personal name"),
            ("summary", "Customer callback: 555-0134.", "phone number"),
            ("summary", "Customer phone: 5551234567.", "phone number"),
            ("summary", "Reference 123456789012 pending.", "long digit run"),
            (
                "summary",
                "Amazon order 111-2223334-5556667 was refunded.",
                "Amazon order ID",
            ),
            ("summary", "row: {order_id: REDACTED}", "raw provider row"),
            ("summary", "client_secret=synthetic_secret_value", "secret or credential"),
            (
                "summary",
                "Authorization: Bearer syntheticbearertoken",
                "bearer or cloud credential",
            ),
            ("summary", "AWS key AKIAIOSFODNN7EXAMPLE", "bearer or cloud credential"),
            ("summary", "Call +44 20 7946 0958.", "phone number"),
            ("summary", "provider result: [{customer: hidden}]", "raw provider row"),
            ("summary", "account_id: acct_123456789", "identity identifier"),
            ("summary", "billing profile ID: BILL12345", "identity identifier"),
            ("timebox", "employee ID: EMP12345", "identity identifier"),
        )
        for field, value, expected_error in cases:
            with self.subTest(field=field, value=value):
                digest, packet = example_documents()
                if field == "timebox":
                    digest["actions"][0][field] = value
                else:
                    digest[field] = value
                with self.assertRaisesRegex(ValueError, expected_error):
                    digest_to_row(digest, publish=False, evidence_packet=packet)

    def test_member_visible_privacy_flags_are_derived_not_agent_supplied(self) -> None:
        digest, packet = example_documents()
        self.assertNotIn("privacy", digest)
        row = digest_to_row(digest, publish=False, evidence_packet=packet)
        self.assertEqual(
            row["body"]["privacy"],
            {"exactValuesPublished": True, "businessIdentifiersPublished": True},
        )

    def test_agent_supplied_privacy_flags_are_ignored(self) -> None:
        digest, packet = example_documents()
        digest["actions"] = []
        keep_packet_signals(digest, packet, {"creator-commerce-signal"})
        digest["privacy"] = {
            "exactValuesPublished": True,
            "businessIdentifiersPublished": True,
        }

        row = digest_to_row(digest, publish=False, evidence_packet=packet)
        self.assertEqual(
            row["body"]["privacy"],
            {"exactValuesPublished": False, "businessIdentifiersPublished": False},
        )

    def test_digest_caps_actions_and_signals_at_ten_combined(self) -> None:
        digest, packet = example_documents()
        signal = digest["signals"][0]
        packet_signal = packet["signals"][1]
        reconciliation = packet["memoryReconciliations"][1]
        review = packet["itemReviews"][1]
        for index in range(9):
            finding_id = f"extra-signal-{index}"
            candidate = deepcopy(signal)
            candidate["id"] = finding_id
            candidate["memory"]["privateEvidenceRefs"] = [f"memory-extra-{index}"]
            digest["signals"].append(candidate)
            extra_signal = deepcopy(packet_signal)
            extra_signal["id"] = finding_id
            packet["signals"].append(extra_signal)
            memory = deepcopy(reconciliation)
            memory["id"] = f"memory-extra-{index}"
            memory["findingId"] = finding_id
            packet["memoryReconciliations"].append(memory)
            review["signalIds"].append(finding_id)

        with self.assertRaisesRegex(ValueError, "at most 10 combined"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

    def test_authenticated_digest_allows_long_numeric_campaign_id(self) -> None:
        digest, packet = example_documents()
        digest["actions"][0]["mellanniEvidence"]["entityScope"] = (
            "campaign ID 123456789012345"
        )

        row = digest_to_row(digest, publish=False, evidence_packet=packet)

        self.assertTrue(row["body"]["privacy"]["businessIdentifiersPublished"])
        self.assertIn(
            "campaign ID 123456789012345",
            row["body"]["actions"][0]["mellanniEvidence"]["entityScope"],
        )

    def test_authenticated_digest_marks_nonnumeric_campaign_name(self) -> None:
        digest, packet = example_documents()
        digest["actions"][0]["mellanniEvidence"]["entityScope"] = "campaign SP-BRAND"

        row = digest_to_row(digest, publish=False, evidence_packet=packet)

        self.assertTrue(row["body"]["privacy"]["businessIdentifiersPublished"])

    def test_exact_value_flag_is_provenance_neutral(self) -> None:
        digest, packet = example_documents()
        digest["actions"] = []
        digest["signals"][0]["whyItMatters"] = "External benchmark conversion rose 31%."
        keep_packet_signals(digest, packet, {"creator-commerce-signal"})
        digest["privacy"] = {
            "exactValuesPublished": True,
            "businessIdentifiersPublished": False,
        }

        row = digest_to_row(digest, publish=False, evidence_packet=packet)

        self.assertTrue(row["body"]["privacy"]["exactValuesPublished"])
        self.assertFalse(row["body"]["privacy"]["businessIdentifiersPublished"])

    def test_business_identifier_flag_ignores_portfolio_year(self) -> None:
        digest, packet = example_documents()
        digest["actions"] = []
        digest["signals"][0]["whyItMatters"] = "Portfolio 2026 review remains external."
        keep_packet_signals(digest, packet, {"creator-commerce-signal"})
        digest["privacy"] = {
            "exactValuesPublished": False,
            "businessIdentifiersPublished": False,
        }

        row = digest_to_row(digest, publish=False, evidence_packet=packet)

        self.assertFalse(row["body"]["privacy"]["businessIdentifiersPublished"])

    def test_authenticated_digest_allows_numeric_business_range(self) -> None:
        digest, packet = example_documents()
        digest["actions"][0]["guidance"] = "Coverage ranged 1500-2000 units."

        row = digest_to_row(digest, publish=False, evidence_packet=packet)

        self.assertEqual(
            row["body"]["actions"][0]["guidance"],
            "Coverage ranged 1500-2000 units.",
        )

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
                "statement": "Useful signal omitted from member-visible digest.",
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
        packet["itemReviews"][1]["signalIds"].append("unused-signal")
        with self.assertRaisesRegex(ValueError, "exactly match selected packet signals"):
            digest_to_row(digest, publish=False, evidence_packet=packet)

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_digest_run_rejects_raw_evidence_packet(self, request_json) -> None:
        _, packet = example_documents()
        with self.assertRaisesRegex(ValueError, "requires compact verified run proof"):
            record_run(
                "https://example.supabase.co",
                "secret",
                {"exit_code": 0, "source_statuses": []},
                digest_id="digest-id",
                evidence_packet=packet,
                outcome="digest",
            )
        request_json.assert_not_called()

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_digest_run_rejects_legacy_publication_proof(self, request_json) -> None:
        with self.assertRaisesRegex(ValueError, "missing or obsolete"):
            record_run(
                "https://example.supabase.co",
                "secret",
                {"exit_code": 0, "source_statuses": []},
                digest_id="digest-id",
                run_proof={
                    "schema_version": "legacy-1",
                    "digest_content_sha256": "a" * 64,
                    "legacy_approved_publication": True,
                    "reason": "Old one-time approval",
                },
                outcome="digest",
            )
        request_json.assert_not_called()

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_digest_run_stores_only_compact_proof(self, request_json) -> None:
        digest, packet = example_documents()
        with tempfile.TemporaryDirectory() as temp:
            manifest, manifest_path, _ = ready_packet_manifest(Path(temp), packet)
            proof = build_run_proof(
                manifest,
                manifest_path,
                digest_document=digest,
                evidence_packet=packet,
            )
            record_run(
                "https://example.supabase.co",
                "secret",
                manifest,
                digest_id="digest-id",
                run_proof=proof,
                outcome="digest",
            )
        stored = request_json.call_args.kwargs["payload"]["manifest"]
        self.assertEqual(stored, {"runProof": proof})
        self.assertNotIn("sources", json.dumps(stored))
        self.assertRegex(
            request_json.call_args.kwargs["payload"]["run_key"],
            r"^digest:[0-9a-f]{64}$",
        )
        self.assertEqual(
            request_json.call_args.args[2], "runs?on_conflict=run_key"
        )
        self.assertEqual(
            request_json.call_args.kwargs["prefer"],
            "resolution=ignore-duplicates,return=minimal",
        )

    @patch("mellanni_marketing_intelligence.supabase_content._request_json", return_value=[])
    def test_list_digests_can_filter_status(self, request_json) -> None:
        self.assertEqual(
            list_digests("https://example.supabase.co", "secret", status="published"), []
        )
        self.assertIn("status=eq.published", request_json.call_args.args[2])

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_list_digests_joins_private_body_by_digest_id(self, request_json) -> None:
        request_json.side_effect = [
            [{"id": "digest-id", "slug": "weekly-brief", "status": "draft"}],
            [{"digest_id": "digest-id", "private_body": {"actions": ["private"]}}],
        ]

        rows = list_digests(
            "https://example.supabase.co", "secret", status="draft"
        )

        self.assertEqual(rows[0]["private_body"], {"actions": ["private"]})
        self.assertIn("digest_private_bodies", request_json.call_args_list[1].args[2])
        self.assertIn("digest_id=in.(digest-id)", request_json.call_args_list[1].args[2])

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_list_digests_rejects_missing_private_body(self, request_json) -> None:
        request_json.side_effect = [
            [{"id": "digest-id", "slug": "weekly-brief", "status": "draft"}],
            [],
        ]

        with self.assertRaisesRegex(RuntimeError, "without matching private body"):
            list_digests("https://example.supabase.co", "secret", status="draft")

    @patch("mellanni_marketing_intelligence.supabase_content._request_json", return_value=[])
    def test_list_members_defaults_to_active_only(self, request_json) -> None:
        self.assertEqual(
            list_members(
                "https://example.supabase.co", "secret", include_inactive=False
            ),
            [],
        )
        self.assertIn("active=eq.true", request_json.call_args.args[2])

    @patch("mellanni_marketing_intelligence.supabase_content._request_json")
    def test_member_can_be_deactivated_by_exact_user_id(self, request_json) -> None:
        request_json.return_value = [
            {
                "user_id": "11111111-1111-1111-1111-111111111111",
                "email": "reader@mellanni.com",
                "active": False,
            }
        ]

        member = set_member_state(
            "https://example.supabase.co",
            "secret",
            "11111111-1111-1111-1111-111111111111",
            active=False,
        )

        self.assertFalse(member["active"])
        self.assertEqual(request_json.call_args.kwargs["payload"], {"active": False})
        self.assertIn("11111111-1111-1111-1111-111111111111", request_json.call_args.args[2])

    def test_member_state_requires_uuid(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be a UUID"):
            set_member_state(
                "https://example.supabase.co",
                "secret",
                "reader@mellanni.com",
                active=False,
            )

    @patch(
        "mellanni_marketing_intelligence.supabase_content._request_json",
        return_value=[{"slug": "weekly-brief", "status": "published"}],
    )
    def test_digest_publication_uses_atomic_verified_rpc(self, request_json) -> None:
        digest = set_digest_state(
            "https://example.supabase.co",
            "secret",
            "weekly-brief",
            status="published",
        )
        self.assertEqual(digest["status"], "published")
        self.assertEqual(
            request_json.call_args.args[2], "rpc/publish_digest_with_verified_run"
        )
        self.assertEqual(
            request_json.call_args.kwargs["payload"], {"p_slug": "weekly-brief"}
        )

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
                    "set-member-state",
                    "--user-id",
                    "11111111-1111-1111-1111-111111111111",
                    "--state",
                    "inactive",
                ]
            )
            .state,
            "inactive",
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
