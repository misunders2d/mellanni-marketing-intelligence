from __future__ import annotations

import json
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
    set_digest_state,
    set_source_state,
    source_document_to_row,
    source_rows_to_config,
)


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
        row = digest_to_row(
            {
                "slug": "weekly-brief",
                "date": "2026-08-27",
                "title": "Weekly brief",
                "summary": "A concise summary.",
                "topics": ["Creative"],
                "findings": ["One finding."],
                "sources": [{"name": "Source", "url": "https://example.com", "note": "Evidence."}],
            },
            publish=False,
        )

        self.assertEqual(row["status"], "draft")
        self.assertIsNone(row["published_at"])
        self.assertEqual(row["body"]["topics"], ["Creative"])

    def test_digest_rejects_bad_slug(self) -> None:
        with self.assertRaisesRegex(ValueError, "slug"):
            digest_to_row(
                {
                    "slug": "Bad Slug",
                    "date": "2026-08-27",
                    "title": "Weekly brief",
                    "summary": "A concise summary.",
                    "topics": [],
                    "findings": [],
                    "sources": [],
                },
                publish=False,
            )

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


if __name__ == "__main__":
    unittest.main()
