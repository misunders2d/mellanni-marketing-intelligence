from __future__ import annotations

import unittest

from mellanni_marketing_intelligence.supabase_content import (
    digest_to_row,
    source_rows_to_config,
)


class SupabaseContentTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
