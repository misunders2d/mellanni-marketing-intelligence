from __future__ import annotations

from argparse import Namespace
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from mellanni_marketing_intelligence.supabase_content import digest_to_row
from mellanni_marketing_intelligence.weekly import build_parser, run_weekly


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def args(run_root: Path, *extra: str) -> Namespace:
    return build_parser().parse_args(["--run-root", str(run_root), *extra])


def packet_sources() -> list[dict[str, str]]:
    packet = json.loads(
        (PROJECT_ROOT / "examples" / "evidence-packet.example.json").read_text(
            encoding="utf-8"
        )
    )
    return [
        {"item_id": source["id"], "url": source["url"]}
        for source in packet["sources"]
    ]


def fake_collection(**kwargs) -> dict:
    run_dir = kwargs["journal_root"] / "collection-run"
    item_dir = run_dir / "items"
    item_dir.mkdir(parents=True)
    items = []
    for index, source in enumerate(packet_sources()):
        artifact = item_dir / f"item-{index}.md"
        artifact.write_text(f"Evidence for {source['url']}", encoding="utf-8")
        items.append(
            {
                **source,
                "journal_path": f"items/item-{index}.md",
                "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            }
        )
    manifest_path = run_dir / "manifest.json"
    manifest = {
        "schema_version": 3,
        "run_id": "collection-run",
        "started_at": "2026-09-07T00:00:00+00:00",
        "finished_at": "2026-09-07T00:01:00+00:00",
        "source_count": 13,
        "source_failures": 0,
        "warning_count": 0,
        "item_count": len(items),
        "items": items,
        "source_statuses": [
            {"slug": f"source-{index}", "errors": []} for index in range(13)
        ],
        "exit_code": 0,
        "manifest_path": str(manifest_path),
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def fake_youtube(manifest_path: Path, **kwargs) -> dict:
    output = manifest_path.parent / "youtube"
    output.mkdir(exist_ok=True)
    value = {
        "schema_version": 2,
        "run_id": "collection-run",
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
    (output / "youtube-summary-manifest.json").write_text(
        json.dumps(value), encoding="utf-8"
    )
    return value


def write_synthesis(result: dict) -> tuple[dict, dict]:
    packet = json.loads(
        (PROJECT_ROOT / "examples" / "evidence-packet.example.json").read_text(
            encoding="utf-8"
        )
    )
    packet["collectionManifestSha256"] = result["collection_manifest_sha256"]
    digest = json.loads(
        (PROJECT_ROOT / "examples" / "digest.example.json").read_text(
            encoding="utf-8"
        )
    )
    Path(result["write_evidence_packet"]).write_text(
        json.dumps(packet), encoding="utf-8"
    )
    Path(result["write_digest"]).write_text(json.dumps(digest), encoding="utf-8")
    return digest, packet


def stored_draft(digest: dict, packet: dict) -> dict:
    return {
        "id": "digest-id",
        **digest_to_row(digest, publish=False, evidence_packet=packet),
    }


def source_rows() -> list[dict[str, str]]:
    return [
        {
            "slug": f"source-{index}",
            "name": f"Source {index}",
            "home_url": f"https://source-{index}.example/",
        }
        for index in range(13)
    ]


class RunnerMocks:
    def __init__(self, *, youtube_side_effect=fake_youtube) -> None:
        self.stack = ExitStack()
        self.credentials = self.stack.enter_context(
            patch("mellanni_marketing_intelligence.weekly.credentials")
        )
        self.sources = self.stack.enter_context(
            patch("mellanni_marketing_intelligence.weekly.fetch_enabled_sources")
        )
        self.fetch = self.stack.enter_context(
            patch(
                "mellanni_marketing_intelligence.weekly.run_fetch",
                side_effect=fake_collection,
            )
        )
        self.youtube = self.stack.enter_context(
            patch(
                "mellanni_marketing_intelligence.weekly._run_youtube",
                side_effect=youtube_side_effect,
            )
        )
        self.digests = self.stack.enter_context(
            patch("mellanni_marketing_intelligence.weekly.list_digests")
        )
        self.push = self.stack.enter_context(
            patch("mellanni_marketing_intelligence.weekly.push_digest")
        )
        self.record = self.stack.enter_context(
            patch("mellanni_marketing_intelligence.weekly.record_run")
        )
        self.credentials.return_value = ("https://example.supabase.co", "secret")
        self.sources.return_value = source_rows()
        self.digests.return_value = []

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return self.stack.__exit__(*exc_info)


class WeeklyRunnerTests(unittest.TestCase):
    @patch(
        "mellanni_marketing_intelligence.weekly._week_start",
        return_value="2026-09-07",
    )
    def test_cold_start_and_identical_command_resume_through_draft(
        self, _week_start_mock
    ) -> None:
        with RunnerMocks() as mocks:
            mocks.push.return_value = {
                "id": "digest-id",
                "slug": "2026-08-31-weekly-marketing-digest",
                "status": "draft",
            }
            with tempfile.TemporaryDirectory() as temp:
                run_root = Path(temp) / "weekly"
                first = run_weekly(args(run_root))
                self.assertEqual(first["status"], "awaiting_synthesis")
                self.assertEqual(
                    first["resume_command"],
                    "UV_CACHE_DIR=/tmp/uv-cache uv run mellanni-weekly",
                )
                self.assertEqual(
                    first["collection_manifest_sha256"],
                    hashlib.sha256(Path(first["manifest"]).read_bytes()).hexdigest(),
                )
                digest, packet = write_synthesis(first)
                mocks.digests.side_effect = [[stored_draft(digest, packet)]]

                receipt = run_weekly(args(run_root))
                self.assertEqual(receipt["outcome"], "draft")
                self.assertTrue(receipt["digest"]["readback_verified"])
                self.assertEqual(receipt["source_count"], 13)
                self.assertEqual(
                    set(receipt["run_proof"]),
                    {
                        "schema_version",
                        "run_id",
                        "collection_manifest_sha256",
                        "youtube_sidecar_sha256",
                        "evidence_packet_sha256",
                        "digest_content_sha256",
                        "counts",
                        "agentic_verified",
                    },
                )
                receipt_path = Path(first["run_dir"]) / "run-receipt.json"
                self.assertEqual(
                    json.loads(receipt_path.read_text(encoding="utf-8")), receipt
                )
                state = json.loads(
                    (Path(first["run_dir"]) / "run-state.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(state["status"], "completed")
                self.assertEqual(state["week_start"], "2026-09-07")
                self.assertEqual(state["invocation"]["since_days"], 8)

            mocks.push.assert_called_once()
            self.assertFalse(mocks.push.call_args.kwargs["publish"])
            mocks.record.assert_called_once()
            self.assertEqual(mocks.record.call_args.kwargs["outcome"], "digest")
            self.assertIn("run_proof", mocks.record.call_args.kwargs)
            self.assertNotIn("evidence_packet", mocks.record.call_args.kwargs)

    def test_weekly_tree_modes_are_private(self) -> None:
        with RunnerMocks():
            with tempfile.TemporaryDirectory() as temp:
                run_root = Path(temp) / "weekly"
                first = run_weekly(args(run_root))
                for root, directories, files in os.walk(run_root):
                    self.assertEqual(stat.S_IMODE(Path(root).stat().st_mode), 0o700)
                    for directory in directories:
                        self.assertEqual(
                            stat.S_IMODE((Path(root) / directory).stat().st_mode), 0o700
                        )
                    for filename in files:
                        self.assertEqual(
                            stat.S_IMODE((Path(root) / filename).stat().st_mode), 0o600
                        )
                self.assertTrue(Path(first["run_dir"]).is_dir())

    def test_resume_refuses_group_writable_state_before_credentials(self) -> None:
        with RunnerMocks() as mocks:
            with tempfile.TemporaryDirectory() as temp:
                run_root = Path(temp) / "weekly"
                first = run_weekly(args(run_root))
                state_path = Path(first["run_dir"]) / "run-state.json"
                state_path.chmod(0o660)
                with self.assertRaisesRegex(
                    RuntimeError, "refusing unsafe weekly resume: group/other-writable path"
                ):
                    run_weekly(args(run_root))
            self.assertEqual(mocks.credentials.call_count, 1)

    def test_resume_rejects_prior_week_before_credentials_with_recovery(self) -> None:
        with RunnerMocks() as mocks, patch(
            "mellanni_marketing_intelligence.weekly._week_start",
            side_effect=["2026-08-31", "2026-09-07"],
        ):
            with tempfile.TemporaryDirectory() as temp:
                run_root = Path(temp) / "weekly"
                run_weekly(args(run_root))
                with self.assertRaisesRegex(
                    RuntimeError,
                    r"active run belongs to a different week.*Recovery: review and move .*then rerun",
                ):
                    run_weekly(args(run_root))
            self.assertEqual(mocks.credentials.call_count, 1)

    def test_resume_rejects_parameter_mismatch_before_credentials_with_recovery(self) -> None:
        with RunnerMocks() as mocks:
            with tempfile.TemporaryDirectory() as temp:
                run_root = Path(temp) / "weekly"
                run_weekly(args(run_root))
                with self.assertRaisesRegex(
                    RuntimeError,
                    r"invocation parameters differ.*Recovery: rerun with original parameters .*then rerun",
                ):
                    run_weekly(args(run_root, "--since-days", "9"))
            self.assertEqual(mocks.credentials.call_count, 1)

    def test_youtube_transient_failure_retries_same_run_and_snapshot(self) -> None:
        attempts = 0

        def fails_once(manifest_path: Path, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("temporary YouTube outage")
            return fake_youtube(manifest_path, **kwargs)

        with RunnerMocks(youtube_side_effect=fails_once) as mocks:
            with tempfile.TemporaryDirectory() as temp:
                run_root = Path(temp) / "weekly"
                with self.assertRaisesRegex(RuntimeError, "temporary YouTube outage"):
                    run_weekly(args(run_root))
                run_dirs = [path for path in run_root.iterdir() if path.is_dir()]
                self.assertEqual(len(run_dirs), 1)
                state = json.loads(
                    (run_dirs[0] / "run-state.json").read_text(encoding="utf-8")
                )
                self.assertEqual(state["status"], "running")
                self.assertTrue(state["last_error"]["resumable"])
                self.assertFalse((run_dirs[0] / "run-receipt.json").exists())

                resumed = run_weekly(args(run_root))
                self.assertEqual(resumed["status"], "awaiting_synthesis")
                self.assertEqual(Path(resumed["run_dir"]), run_dirs[0])
            self.assertEqual(mocks.fetch.call_count, 1)
            self.assertEqual(mocks.sources.call_count, 1)
            self.assertEqual(mocks.youtube.call_count, 2)

    def test_supabase_snapshot_failure_retries_same_run(self) -> None:
        with RunnerMocks() as mocks:
            mocks.sources.side_effect = [
                RuntimeError("temporary Supabase outage"),
                source_rows(),
            ]
            with tempfile.TemporaryDirectory() as temp:
                run_root = Path(temp) / "weekly"
                with self.assertRaisesRegex(RuntimeError, "temporary Supabase outage"):
                    run_weekly(args(run_root))
                run_dir = next(run_root.iterdir())
                self.assertFalse((run_dir / "run-receipt.json").exists())
                resumed = run_weekly(args(run_root))
                self.assertEqual(Path(resumed["run_dir"]), run_dir)
                self.assertEqual(resumed["status"], "awaiting_synthesis")
            self.assertEqual(mocks.sources.call_count, 2)
            self.assertEqual(mocks.fetch.call_count, 1)

    def test_readback_failure_resumes_without_repeating_draft_write(self) -> None:
        with RunnerMocks() as mocks:
            mocks.push.return_value = {
                "id": "digest-id",
                "slug": "2026-08-31-weekly-marketing-digest",
                "status": "draft",
            }
            with tempfile.TemporaryDirectory() as temp:
                run_root = Path(temp) / "weekly"
                first = run_weekly(args(run_root))
                digest, packet = write_synthesis(first)
                mocks.digests.side_effect = [
                    RuntimeError("temporary readback outage"),
                    [stored_draft(digest, packet)],
                ]
                with self.assertRaisesRegex(RuntimeError, "temporary readback outage"):
                    run_weekly(args(run_root))
                self.assertFalse(
                    (Path(first["run_dir"]) / "run-receipt.json").exists()
                )
                receipt = run_weekly(args(run_root))
                self.assertEqual(receipt["outcome"], "draft")
                self.assertEqual(Path(first["run_dir"]), run_root / receipt["run_id"])
            mocks.push.assert_called_once()
            mocks.record.assert_called_once()

    def test_readback_rejects_changed_digest_content_before_run_link(self) -> None:
        with RunnerMocks() as mocks:
            mocks.push.return_value = {
                "id": "digest-id",
                "slug": "2026-08-31-weekly-marketing-digest",
                "status": "draft",
            }
            with tempfile.TemporaryDirectory() as temp:
                run_root = Path(temp) / "weekly"
                first = run_weekly(args(run_root))
                digest, packet = write_synthesis(first)
                changed = stored_draft(digest, packet)
                changed["summary"] = "Wrong stored summary."
                mocks.digests.side_effect = [[changed]]
                with self.assertRaisesRegex(RuntimeError, "content did not match"):
                    run_weekly(args(run_root))
            mocks.push.assert_called_once()
            mocks.record.assert_not_called()

    def test_existing_valid_receipt_recovers_crash_before_completed_state(self) -> None:
        with RunnerMocks() as mocks:
            mocks.push.return_value = {
                "id": "digest-id",
                "slug": "2026-08-31-weekly-marketing-digest",
                "status": "draft",
            }
            with tempfile.TemporaryDirectory() as temp:
                run_root = Path(temp) / "weekly"
                first = run_weekly(args(run_root))
                digest, packet = write_synthesis(first)
                mocks.digests.side_effect = [[stored_draft(digest, packet)]]
                receipt = run_weekly(args(run_root))
                state_path = Path(first["run_dir"]) / "run-state.json"
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state["status"] = "running"
                state["stage"] = "run_link"
                state_path.write_text(json.dumps(state), encoding="utf-8")
                credentials_calls = mocks.credentials.call_count

                recovered = run_weekly(args(run_root))

                self.assertEqual(recovered, receipt)
                self.assertEqual(mocks.credentials.call_count, credentials_calls)
                recovered_state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertEqual(recovered_state["status"], "completed")
            mocks.push.assert_called_once()
            mocks.record.assert_called_once()

    def test_invalid_packet_records_terminal_no_digest_before_draft_write(self) -> None:
        with RunnerMocks() as mocks:
            with tempfile.TemporaryDirectory() as temp:
                run_root = Path(temp) / "weekly"
                first = run_weekly(args(run_root))
                packet = json.loads(
                    (PROJECT_ROOT / "examples" / "evidence-packet.example.json").read_text(
                        encoding="utf-8"
                    )
                )
                packet["collectionManifestSha256"] = hashlib.sha256(
                    Path(first["manifest"]).read_bytes()
                ).hexdigest()
                packet["sources"][0]["id"] = "foreign-source"
                Path(first["write_evidence_packet"]).write_text(
                    json.dumps(packet), encoding="utf-8"
                )
                Path(first["write_digest"]).write_bytes(
                    (PROJECT_ROOT / "examples" / "digest.example.json").read_bytes()
                )
                receipt = run_weekly(args(run_root))
                self.assertEqual(receipt["outcome"], "no-digest")
                self.assertIn("references missing sources", receipt["reason"])
            mocks.push.assert_not_called()
            mocks.record.assert_called_once()
            self.assertEqual(mocks.record.call_args.kwargs["outcome"], "no-digest")

    def test_failed_manifest_is_rechecked_after_crash_before_fail_transition(self) -> None:
        def failed_collection(**kwargs) -> dict:
            manifest = fake_collection(**kwargs)
            manifest.update({"source_failures": 1, "exit_code": 2})
            Path(manifest["manifest_path"]).write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            return manifest

        with RunnerMocks() as mocks:
            mocks.fetch.side_effect = failed_collection
            with tempfile.TemporaryDirectory() as temp:
                run_root = Path(temp) / "weekly"
                with patch(
                    "mellanni_marketing_intelligence.weekly._fail",
                    side_effect=RuntimeError("crash before terminal transition"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "crash before terminal"):
                        run_weekly(args(run_root))
                receipt = run_weekly(args(run_root))
                self.assertEqual(receipt["outcome"], "no-digest")
                self.assertIn("collection failed", receipt["reason"])
            mocks.youtube.assert_not_called()
            mocks.record.assert_called_once()

    def test_failed_state_without_receipt_is_finalized_on_resume(self) -> None:
        def failed_collection(**kwargs) -> dict:
            manifest = fake_collection(**kwargs)
            manifest.update({"source_failures": 1, "exit_code": 2})
            Path(manifest["manifest_path"]).write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            return manifest

        with RunnerMocks() as mocks:
            mocks.fetch.side_effect = failed_collection
            with tempfile.TemporaryDirectory() as temp:
                run_root = Path(temp) / "weekly"
                with patch(
                    "mellanni_marketing_intelligence.weekly._write_receipt",
                    side_effect=RuntimeError("crash before receipt"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "crash before receipt"):
                        run_weekly(args(run_root))
                run_dir = next(path for path in run_root.iterdir() if path.is_dir())
                state = json.loads(
                    (run_dir / "run-state.json").read_text(encoding="utf-8")
                )
                self.assertEqual(state["status"], "failed")
                self.assertFalse((run_dir / "run-receipt.json").exists())

                receipt = run_weekly(args(run_root))
                self.assertEqual(receipt["outcome"], "no-digest")
                self.assertTrue((run_dir / "run-receipt.json").is_file())
            mocks.youtube.assert_not_called()
            mocks.record.assert_called_once()

    @patch("mellanni_marketing_intelligence.weekly.record_run")
    @patch("mellanni_marketing_intelligence.weekly.run_fetch")
    @patch("mellanni_marketing_intelligence.weekly.fetch_enabled_sources")
    @patch("mellanni_marketing_intelligence.weekly.credentials")
    def test_fatal_collection_writes_terminal_no_digest_receipt(
        self, credentials_mock, sources_mock, fetch_mock, record_mock
    ) -> None:
        credentials_mock.return_value = ("https://example.supabase.co", "secret")
        sources_mock.return_value = [
            {"slug": "source", "name": "Source", "home_url": "https://example.com/"}
        ]

        def failed_collection(**kwargs) -> dict:
            manifest = fake_collection(**kwargs)
            manifest.update({"source_failures": 1, "exit_code": 2})
            Path(manifest["manifest_path"]).write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            return manifest

        fetch_mock.side_effect = failed_collection
        with tempfile.TemporaryDirectory() as temp:
            result = run_weekly(args(Path(temp) / "weekly"))
            self.assertEqual(result["outcome"], "no-digest")
            self.assertTrue(result["no_digest_recorded"])
            self.assertIn("collection failed", result["reason"])
        record_mock.assert_called_once()
        self.assertEqual(record_mock.call_args.kwargs["outcome"], "no-digest")

    @patch(
        "mellanni_marketing_intelligence.weekly.credentials",
        side_effect=ValueError("credentials unavailable"),
    )
    def test_explicit_fail_reason_is_terminal_even_when_db_unavailable(
        self, credentials_mock
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = run_weekly(
                args(Path(temp) / "weekly", "--fail-reason", "operator stopped synthesis")
            )
            self.assertEqual(result["outcome"], "no-digest")
            self.assertFalse(result["no_digest_recorded"])
            self.assertEqual(result["reason"], "operator stopped synthesis")
        credentials_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
