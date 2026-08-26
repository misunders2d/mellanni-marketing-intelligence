from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mellanni_marketing_intelligence.collector import canonical_url, parse_feed
from mellanni_marketing_intelligence.pipeline import run_fetch


HOME = "https://example.com/"
FEED = "https://example.com/feed.xml"
ARTICLE = "https://example.com/articles/useful-test"


def fake_fetch(url: str) -> tuple[str, str]:
    documents = {
        HOME: ('<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head></html>', "text/html"),
        FEED: (
            """<?xml version="1.0"?><rss><channel><item><title>Useful conversion test</title><link>https://example.com/articles/useful-test?utm_source=x</link><pubDate>Tue, 25 Aug 2026 12:00:00 GMT</pubDate><description><![CDATA[Measured test summary.]]></description></item></channel></rss>""",
            "application/rss+xml",
        ),
        ARTICLE: ("<html><body><article><h1>Useful conversion test</h1><p>Brand changed one listing image and measured a 14 percent conversion lift against a matched baseline.</p></article></body></html>", "text/html"),
    }
    if url not in documents:
        raise OSError(f"unexpected URL: {url}")
    return documents[url]


class PipelineTests(unittest.TestCase):
    def test_canonical_url_removes_tracking(self) -> None:
        self.assertEqual(canonical_url("HTTPS://Example.com/a/?utm_source=x&keep=1#part"), "https://example.com/a?keep=1")

    def test_parse_feed(self) -> None:
        document, _ = fake_fetch(FEED)
        entries = parse_feed(document, FEED)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].url, ARTICLE)

    def test_fetch_writes_local_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "sources.json"
            config.write_text(json.dumps({"sources": [{"slug": "test", "name": "Test Source", "home_url": HOME, "priority": "A", "why": "test", "include_patterns": ["/articles/"]}]}), encoding="utf-8")
            manifest = run_fetch(
                config_path=config,
                journal_root=root / "journal",
                since_days=8,
                fetch_workers=2,
                fetcher=fake_fetch,
            )
            self.assertEqual(manifest["exit_code"], 0)
            self.assertEqual(manifest["item_count"], 1)
            item_path = Path(manifest["journal_dir"]) / str(manifest["items"][0]["journal_path"])
            self.assertTrue(item_path.is_file())
            self.assertIn("14 percent conversion lift", item_path.read_text(encoding="utf-8"))
            self.assertTrue(Path(manifest["manifest_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
