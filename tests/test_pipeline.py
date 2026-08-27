from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from mellanni_marketing_intelligence.collector import Fetch, canonical_url, parse_feed
from mellanni_marketing_intelligence.pipeline import run_fetch


HOME = "https://example.com/"
FEED = "https://example.com/feed.xml"
ARTICLE = "https://example.com/articles/useful-test"
FAILED_FEED = "https://example.com/broken.xml"


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
    def _write_config(self, root: Path, **overrides: object) -> Path:
        row: dict[str, object] = {
            "slug": "test",
            "name": "Test Source",
            "home_url": HOME,
            "priority": "A",
            "why": "test",
            "include_patterns": ["/articles/"],
        }
        row.update(overrides)
        config = root / "sources.json"
        config.write_text(json.dumps({"sources": [row]}), encoding="utf-8")
        return config

    def _run(self, root: Path, config: Path, fetcher: Fetch) -> dict[str, object]:
        return run_fetch(
            config_path=config,
            journal_root=root / "journal",
            since_days=8,
            fetch_workers=2,
            fetcher=fetcher,
        )

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
            config = self._write_config(root)
            manifest = self._run(root, config, fake_fetch)
            self.assertEqual(manifest["exit_code"], 0)
            self.assertEqual(manifest["item_count"], 1)
            item_path = Path(manifest["journal_dir"]) / str(manifest["items"][0]["journal_path"])
            self.assertTrue(item_path.is_file())
            self.assertIn("14 percent conversion lift", item_path.read_text(encoding="utf-8"))
            self.assertTrue(Path(manifest["manifest_path"]).is_file())

    def test_probe_failure_is_preserved_when_later_feed_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root, feed_urls=[FAILED_FEED, FEED])

            def fetch(url: str) -> tuple[str, str]:
                if url == FAILED_FEED:
                    raise OSError("first feed failed")
                return fake_fetch(url)

            manifest = self._run(root, config, fetch)
            status = manifest["source_statuses"][0]
            self.assertEqual(status["errors"], [])
            self.assertEqual(len(status["warnings"]), 1)
            self.assertIn("first feed failed", status["warnings"][0])
            self.assertEqual(status["feed_candidates_probed"], 2)
            self.assertEqual(status["accepted"], 1)
            self.assertEqual(manifest["source_failures"], 0)
            self.assertEqual(manifest["exit_code"], 0)

    def test_feed_failures_are_preserved_when_html_fallback_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root, feed_urls=[FAILED_FEED])
            home = f'<html><body><a href="{ARTICLE}">Useful conversion test article</a></body></html>'

            def fetch(url: str) -> tuple[str, str]:
                if url == HOME:
                    return home, "text/html"
                if url == ARTICLE:
                    return fake_fetch(url)
                raise OSError("feed unavailable")

            manifest = self._run(root, config, fetch)
            status = manifest["source_statuses"][0]
            self.assertEqual(status["method"], "html-index")
            self.assertEqual(
                status["fallback_reason"],
                f"home_fetch=ok; feed_probes={status['feed_candidates_probed']}; "
                f"feed_errors={status['feed_candidates_probed']}; feed_empty=0; html_index=used",
            )
            self.assertEqual(status["errors"], [])
            self.assertEqual(len(status["warnings"]), status["feed_candidates_probed"])
            self.assertEqual(status["accepted"], 1)
            self.assertEqual(manifest["source_failures"], 0)
            self.assertEqual(manifest["exit_code"], 0)

    def test_total_failure_keeps_failure_signal_and_all_probe_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root)

            def fetch(url: str) -> tuple[str, str]:
                if url == HOME:
                    return "<html></html>", "text/html"
                raise OSError("feed unavailable")

            manifest = self._run(root, config, fetch)
            status = manifest["source_statuses"][0]
            self.assertEqual(status["accepted"], 0)
            self.assertEqual(len(status["errors"]), 1)
            self.assertIn("no usable feed or index", status["errors"][0])
            self.assertEqual(len(status["warnings"]), status["feed_candidates_probed"])
            self.assertEqual(manifest["source_failures"], 1)
            self.assertEqual(manifest["exit_code"], 2)
            self.assertTrue(status["fallback_reason"].endswith("html_index=empty"))

    def test_warnings_do_not_fail_source_when_feed_items_are_outside_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root, feed_urls=[FAILED_FEED, FEED])
            old_feed = """<?xml version="1.0"?><rss><channel><item><title>Old useful article</title><link>https://example.com/articles/old</link><pubDate>Tue, 25 Aug 2020 12:00:00 GMT</pubDate><description>Old summary.</description></item></channel></rss>"""

            def fetch(url: str) -> tuple[str, str]:
                if url == HOME:
                    return "<html></html>", "text/html"
                if url == FAILED_FEED:
                    raise OSError("first feed failed")
                if url == FEED:
                    return old_feed, "application/rss+xml"
                raise OSError(f"unexpected URL: {url}")

            manifest = self._run(root, config, fetch)
            status = manifest["source_statuses"][0]
            self.assertEqual(status["discovered"], 1)
            self.assertEqual(status["accepted"], 0)
            self.assertEqual(status["errors"], [])
            self.assertTrue(status["warnings"])
            self.assertEqual(manifest["source_failures"], 0)
            self.assertEqual(manifest["exit_code"], 0)

    def test_fallback_reason_distinguishes_home_failure_and_empty_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root, feed_urls=[FEED])

            def fetch(url: str) -> tuple[str, str]:
                if url == HOME:
                    raise OSError("homepage unavailable")
                return "<rss><channel></channel></rss>", "application/rss+xml"

            manifest = self._run(root, config, fetch)
            status = manifest["source_statuses"][0]
            self.assertIn("home_fetch=failed", status["fallback_reason"])
            self.assertIn(f"feed_probes={status['feed_candidates_probed']}", status["fallback_reason"])
            self.assertIn("feed_errors=0", status["fallback_reason"])
            self.assertIn(f"feed_empty={status['feed_candidates_probed']}", status["fallback_reason"])
            self.assertTrue(status["fallback_reason"].endswith("html_index=empty"))
            self.assertTrue(any("home fetch failed" in error for error in status["errors"]))

    def test_twelve_explicit_feed_failures_are_not_sliced(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            explicit = [f"https://example.com/explicit-{index}.xml" for index in range(12)]
            config = self._write_config(root, feed_urls=explicit)

            def fetch(url: str) -> tuple[str, str]:
                if url == HOME:
                    return "<html></html>", "text/html"
                raise OSError("feed unavailable")

            manifest = self._run(root, config, fetch)
            status = manifest["source_statuses"][0]
            failures = [warning for warning in status["warnings"] if warning.startswith("feed candidate failed")]
            self.assertEqual(len(failures), 12)
            self.assertEqual(status["feed_candidates_probed"], 12)
            self.assertGreater(status["feed_candidates_total"], status["feed_candidates_probed"])
            self.assertEqual(
                status["feed_candidates_truncated"],
                status["feed_candidates_total"] - status["feed_candidates_probed"],
            )
            self.assertEqual(len(status["errors"]), 1)

    def test_explicit_feeds_are_never_truncated_and_discovered_cap_is_visible(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            explicit = [f"https://example.com/explicit-{index}.xml" for index in range(3)]
            discovered = [f"https://example.com/discovered-{index}.xml" for index in range(9)]
            config = self._write_config(root, feed_urls=explicit, max_feed_candidates=8)
            links = "".join(
                f'<link rel="alternate" type="application/rss+xml" href="{url}">' for url in discovered
            )
            calls: list[str] = []

            def fetch(url: str) -> tuple[str, str]:
                calls.append(url)
                if url == HOME:
                    return f"<html><head>{links}</head></html>", "text/html"
                raise OSError("feed unavailable")

            manifest = self._run(root, config, fetch)
            status = manifest["source_statuses"][0]
            self.assertTrue(all(url in calls for url in explicit))
            self.assertEqual(status["feed_candidates_probed"], 8)
            self.assertGreater(status["feed_candidates_total"], status["feed_candidates_probed"])
            self.assertGreater(status["feed_candidates_truncated"], 0)
            self.assertTrue(any("feed candidate limit skipped" in warning for warning in status["warnings"]))

    def test_empty_feed_warning_survives_later_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            empty_feed = "https://example.com/empty.xml"
            config = self._write_config(root, feed_urls=[empty_feed, FEED])

            def fetch(url: str) -> tuple[str, str]:
                if url == empty_feed:
                    return "<rss><channel></channel></rss>", "application/rss+xml"
                return fake_fetch(url)

            manifest = self._run(root, config, fetch)
            status = manifest["source_statuses"][0]
            self.assertEqual(status["errors"], [])
            self.assertTrue(any("returned no entries" in warning for warning in status["warnings"]))
            self.assertEqual(status["accepted"], 1)

    def test_manifest_v2_records_stable_run_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root)
            expected_hash = hashlib.sha256(config.read_bytes()).hexdigest()
            first = self._run(root, config, fake_fetch)
            second = self._run(root, config, fake_fetch)
            self.assertEqual(first["schema_version"], 2)
            self.assertEqual(first["run_params"]["since_days"], 8)
            self.assertEqual(first["run_params"]["fetch_workers"], 2)
            self.assertEqual(first["run_params"]["source_slugs"], [])
            self.assertEqual(first["run_params"]["config_sha256"], expected_hash)
            self.assertEqual(second["run_params"]["config_sha256"], expected_hash)
            self.assertEqual(first["warning_count"], sum(len(row["warnings"]) for row in first["source_statuses"]))


if __name__ == "__main__":
    unittest.main()
