from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import unittest
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mellanni_marketing_intelligence.collector import (
    Fetch,
    _assert_public_response_peer,
    _assert_public_url,
    canonical_url,
    html_to_text,
    parse_feed,
)
from mellanni_marketing_intelligence.pipeline import run_fetch


HOME = "https://example.com/"
FEED = "https://example.com/feed.xml"
ARTICLE = "https://example.com/articles/useful-test"
FAILED_FEED = "https://example.com/broken.xml"
RECENT_RFC822 = format_datetime(datetime.now(UTC))
RECENT_ISO = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fake_fetch(url: str) -> tuple[str, str]:
    documents = {
        HOME: ('<html><head><link rel="alternate" type="application/rss+xml" href="/feed.xml"></head></html>', "text/html"),
        FEED: (
            f"""<?xml version="1.0"?><rss><channel><item><title>Useful conversion test</title><link>https://example.com/articles/useful-test?utm_source=x</link><pubDate>{RECENT_RFC822}</pubDate><description><![CDATA[Measured test summary.]]></description></item></channel></rss>""",
            "application/rss+xml",
        ),
        ARTICLE: (f"<html><head><meta property=\"article:published_time\" content=\"{RECENT_ISO}\"></head><body><article><h1>Useful conversion test</h1><p>Brand changed one listing image and measured a 14 percent conversion lift against a matched baseline.</p></article></body></html>", "text/html"),
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

    def test_public_url_guard_rejects_private_dns_and_userinfo(self) -> None:
        with patch(
            "mellanni_marketing_intelligence.collector.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("127.0.0.1", 80))],
        ):
            with self.assertRaisesRegex(ValueError, "non-public address"):
                _assert_public_url("http://metadata.example/latest")
        with self.assertRaisesRegex(ValueError, "userinfo"):
            _assert_public_url("https://user:pass@example.com/")

    def test_response_peer_guard_closes_dns_rebinding_gap(self) -> None:
        private_socket = SimpleNamespace(getpeername=lambda: ("127.0.0.1", 443))
        response = SimpleNamespace(
            fp=SimpleNamespace(raw=SimpleNamespace(_sock=private_socket))
        )
        with self.assertRaisesRegex(ValueError, "non-public address"):
            _assert_public_response_peer(response)

        public_socket = SimpleNamespace(getpeername=lambda: ("93.184.216.34", 443))
        response.fp.raw._sock = public_socket
        _assert_public_response_peer(response)

    def test_discovered_feed_on_unapproved_host_is_never_fetched(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root)
            hostile_feed = "http://127.0.0.1/internal.xml"
            calls: list[str] = []

            def fetch(url: str) -> tuple[str, str]:
                calls.append(url)
                if url == HOME:
                    return (
                        f'<link rel="alternate" type="application/rss+xml" href="{hostile_feed}">',
                        "text/html",
                    )
                raise OSError("no approved feed")

            manifest = self._run(root, config, fetch)
            self.assertNotIn(hostile_feed, calls)
            self.assertEqual(manifest["exit_code"], 2)
            self.assertTrue(
                any(
                    "host is not allowed" in warning
                    for warning in manifest["source_statuses"][0]["warnings"]
                )
            )

    def test_source_slug_cannot_escape_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root, slug="../../escape")
            with self.assertRaisesRegex(ValueError, "invalid or duplicate source slug"):
                self._run(root, config, fake_fetch)
            self.assertFalse((root / "escape").exists())

    def test_parse_feed(self) -> None:
        document, _ = fake_fetch(FEED)
        entries = parse_feed(document, FEED)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].url, ARTICLE)

    def test_parse_youtube_feed_keeps_nested_media_description(self) -> None:
        document = """<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/"><entry><title>Episode</title><link rel="alternate" href="https://www.youtube.com/watch?v=abc"/><published>2026-09-07T00:00:00Z</published><media:group><media:content url="https://www.youtube.com/v/abc"/><media:description>Creator tags Amazon products.</media:description></media:group></entry></feed>"""
        entries = parse_feed(document, "https://www.youtube.com/feeds/videos.xml")
        self.assertEqual(entries[0].summary, "Creator tags Amazon products.")

    def test_fetch_writes_hash_bound_private_local_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root)
            previous_umask = os.umask(0)
            try:
                manifest = self._run(root, config, fake_fetch)
            finally:
                os.umask(previous_umask)
            self.assertEqual(manifest["exit_code"], 0)
            self.assertEqual(manifest["item_count"], 1)
            self.assertEqual(manifest["schema_version"], 3)
            item_path = Path(manifest["journal_dir"]) / str(manifest["items"][0]["journal_path"])
            self.assertTrue(item_path.is_file())
            self.assertIn("14 percent conversion lift", item_path.read_text(encoding="utf-8"))
            self.assertEqual(
                manifest["items"][0]["artifact_sha256"],
                hashlib.sha256(item_path.read_bytes()).hexdigest(),
            )
            self.assertEqual(stat.S_IMODE(item_path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(item_path.parent.stat().st_mode), 0o700)
            self.assertTrue(Path(manifest["manifest_path"]).is_file())

    def test_distinct_same_content_items_get_distinct_artifacts(self) -> None:
        second_article = "https://example.com/articles/second"
        duplicate_shape_feed = f"""<rss><channel>
        <item><title>Same title</title><link>{ARTICLE}</link><pubDate>{RECENT_RFC822}</pubDate><description>Same content.</description></item>
        <item><title>Same title</title><link>{second_article}</link><pubDate>{RECENT_RFC822}</pubDate><description>Same content.</description></item>
        </channel></rss>"""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root)

            def fetch(url: str) -> tuple[str, str]:
                if url == HOME:
                    return '<link rel="alternate" type="application/rss+xml" href="/feed.xml">', "text/html"
                if url == FEED:
                    return duplicate_shape_feed, "application/rss+xml"
                if url in {ARTICLE, second_article}:
                    return "<p>Same content.</p>", "text/html"
                raise OSError(f"unexpected URL: {url}")

            manifest = self._run(root, config, fetch)
            paths = [row["journal_path"] for row in manifest["items"]]
            self.assertEqual(manifest["item_count"], 2)
            self.assertEqual(len(paths), len(set(paths)))
            self.assertEqual(
                len({row["item_id"] for row in manifest["items"]}), 2
            )

    def test_exact_duplicate_feed_items_are_deduplicated(self) -> None:
        repeated_feed = f"""<rss><channel>
        <item><title>Same title</title><link>{ARTICLE}</link><pubDate>{RECENT_RFC822}</pubDate><description>Same content.</description></item>
        <item><title>Same title</title><link>{ARTICLE}</link><pubDate>{RECENT_RFC822}</pubDate><description>Same content.</description></item>
        </channel></rss>"""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root)

            def fetch(url: str) -> tuple[str, str]:
                if url == HOME:
                    return '<link rel="alternate" type="application/rss+xml" href="/feed.xml">', "text/html"
                if url == FEED:
                    return repeated_feed, "application/rss+xml"
                if url == ARTICLE:
                    return "<p>Same content.</p>", "text/html"
                raise OSError(f"unexpected URL: {url}")

            manifest = self._run(root, config, fetch)
            self.assertEqual(manifest["item_count"], 1)
            self.assertTrue(
                any(
                    "deduplicated 1 repeated item" in warning
                    for warning in manifest["source_statuses"][0]["warnings"]
                )
            )

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

    def test_stale_first_feed_does_not_hide_later_fresh_feed(self) -> None:
        stale_feed = "https://example.com/stale.xml"
        stale_document = """<rss><channel><item><title>Old item</title><link>https://example.com/old</link><pubDate>Tue, 25 Aug 2020 12:00:00 GMT</pubDate><description>Old.</description></item></channel></rss>"""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root, feed_urls=[stale_feed, FEED])

            def fetch(url: str) -> tuple[str, str]:
                if url == stale_feed:
                    return stale_document, "application/rss+xml"
                return fake_fetch(url)

            manifest = self._run(root, config, fetch)
            status = manifest["source_statuses"][0]
            self.assertEqual(status["method"], f"feed:{FEED}")
            self.assertEqual(status["accepted"], 1)
            self.assertEqual(status["feed_candidates_probed"], 2)
            self.assertTrue(
                any("no in-window entries" in warning for warning in status["warnings"])
            )

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

    def _run_index(self, root: Path, home: str, pages: dict[str, str], **overrides: object) -> dict:
        config = self._write_config(root, feed_urls=[FAILED_FEED], **overrides)

        def fetch(url: str) -> tuple[str, str]:
            if url == HOME:
                return home, "text/html"
            if url in pages:
                return pages[url], "text/html"
            raise OSError("feed unavailable")

        return self._run(root, config, fetch)

    def test_undated_index_pages_are_rejected_unless_source_is_evergreen(self) -> None:
        home = f'<html><body><a href="{ARTICLE}">Useful conversion test article</a></body></html>'
        page = "<html><body><article><p>Undated evergreen guidance page.</p></article></body></html>"
        with tempfile.TemporaryDirectory() as temp:
            manifest = self._run_index(Path(temp), home, {ARTICLE: page})
            status = manifest["source_statuses"][0]
            self.assertEqual(status["accepted"], 0)
            self.assertTrue(any("rejected 1 undated" in warning for warning in status["warnings"]))
        with tempfile.TemporaryDirectory() as temp:
            manifest = self._run_index(Path(temp), home, {ARTICLE: page}, evergreen=True)
            self.assertEqual(manifest["source_statuses"][0]["accepted"], 1)

    def test_index_page_date_outside_window_is_rejected(self) -> None:
        home = f'<html><body><a href="{ARTICLE}">Useful conversion test article</a></body></html>'
        page = '<html><body><article><time datetime="2020-01-01T00:00:00Z">Jan 1</time><p>Old.</p></article></body></html>'
        with tempfile.TemporaryDirectory() as temp:
            manifest = self._run_index(Path(temp), home, {ARTICLE: page})
            status = manifest["source_statuses"][0]
            self.assertEqual(status["accepted"], 0)
            self.assertTrue(any("outside the window" in warning for warning in status["warnings"]))

    def test_index_drops_locale_variants_and_navigation_titles(self) -> None:
        dated = f'<html><head><meta property="article:published_time" content="{RECENT_ISO}"></head><body><article><p>Body.</p></article></body></html>'
        home = (
            "<html><body>"
            f'<a href="{ARTICLE}?mons_sel_locale=en_US">English - US</a>'
            f'<a href="{ARTICLE}?mons_sel_locale=es_US">Espanol - US</a>'
            '<a href="https://example.com/articles/list">List products</a>'
            f'<a href="{ARTICLE}?page=2">Useful conversion test article</a>'
            f'<a href="{ARTICLE}">Useful conversion test article again</a>'
            "</body></html>"
        )
        with tempfile.TemporaryDirectory() as temp:
            manifest = self._run_index(Path(temp), home, {f"{ARTICLE}?page=2": dated, ARTICLE: dated})
            status = manifest["source_statuses"][0]
            self.assertEqual(status["discovered"], 1)
            self.assertEqual([item["url"] for item in manifest["items"]], [f"{ARTICLE}?page=2"])

    def test_canonical_url_strips_locale_parameters(self) -> None:
        self.assertEqual(
            canonical_url("https://Sell.Amazon.com/blog/announcements/?mons_sel_locale=en_US&id=7"),
            "https://sell.amazon.com/blog/announcements?id=7",
        )

    def test_page_text_prefers_article_and_keeps_paragraphs(self) -> None:
        document = (
            "<html><body><header>Site menu Sign in</header><nav>Home Blog Pricing</nav>"
            "<article><header><h1>Prime Day results</h1></header>"
            f"<p>{'First paragraph with measured detail. ' * 4}</p>"
            f"<p>{'Second paragraph with the caveat. ' * 4}</p></article>"
            "<footer>Cookie settings Copyright</footer></body></html>"
        )
        text = html_to_text(document)
        self.assertTrue(text.startswith("Prime Day results"))
        self.assertIn("\n\nSecond paragraph", text)
        for chrome in ("Site menu", "Home Blog", "Cookie settings"):
            self.assertNotIn(chrome, text)

    def test_page_text_falls_back_to_whole_page_without_chrome(self) -> None:
        text = html_to_text(
            "<html><body><nav>Menu</nav><div><p>Short body.</p></div><footer>Legal</footer></body></html>"
        )
        self.assertEqual(text, "Short body.")

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

    def test_valid_empty_explicit_feed_recovers_home_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root, feed_urls=[FEED])

            def fetch(url: str) -> tuple[str, str]:
                if url == HOME:
                    raise OSError("homepage unavailable")
                return "<rss><channel></channel></rss>", "application/rss+xml"

            manifest = self._run(root, config, fetch)
            status = manifest["source_statuses"][0]
            self.assertEqual(status["method"], f"feed:{FEED}")
            self.assertEqual(status["accepted"], 0)
            self.assertEqual(status["errors"], [])
            self.assertTrue(any("recovered by feed" in warning for warning in status["warnings"]))
            self.assertEqual(manifest["exit_code"], 0)

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

    def test_valid_empty_explicit_feed_does_not_hide_later_items(self) -> None:
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
            self.assertTrue(any("valid and currently empty" in warning for warning in status["warnings"]))
            self.assertEqual(status["feed_candidates_probed"], 2)
            self.assertEqual(status["accepted"], 1)
            self.assertEqual(status["method"], f"feed:{FEED}")
            self.assertEqual(manifest["exit_code"], 0)

    def test_unrecognized_xml_is_not_a_valid_empty_feed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root, feed_urls=[FEED])

            def fetch(url: str) -> tuple[str, str]:
                if url == HOME:
                    return "<html></html>", "text/html"
                return "<Error><Message>rate limited</Message></Error>", "application/xml"

            manifest = self._run(root, config, fetch)
            self.assertEqual(manifest["source_failures"], 1)
            self.assertEqual(manifest["exit_code"], 2)
            self.assertIn("no usable feed or index", manifest["source_statuses"][0]["errors"][0])

    def test_item_limit_truncation_is_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root, feed_urls=[FEED], max_items=1)
            feed = f"""<rss><channel>
            <item><title>Useful article one</title><link>https://example.com/articles/one</link><pubDate>{RECENT_RFC822}</pubDate><description>One</description></item>
            <item><title>Useful article two</title><link>https://example.com/articles/two</link><pubDate>{RECENT_RFC822}</pubDate><description>Two</description></item>
            </channel></rss>"""

            def fetch(url: str) -> tuple[str, str]:
                if url == HOME:
                    return "<html></html>", "text/html"
                if url == FEED:
                    return feed, "application/rss+xml"
                return "<article>Full article.</article>", "text/html"

            manifest = self._run(root, config, fetch)
            status = manifest["source_statuses"][0]
            self.assertEqual(status["accepted"], 1)
            self.assertEqual(status["item_limit_truncated"], 1)
            self.assertTrue(any("item limit truncated" in warning for warning in status["warnings"]))
            self.assertEqual(status["errors"], [])
            self.assertEqual(manifest["exit_code"], 0)

    def test_item_fetch_failure_with_feed_fallback_is_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root, feed_urls=[FEED])

            def fetch(url: str) -> tuple[str, str]:
                if url == ARTICLE:
                    raise OSError("article blocked")
                return fake_fetch(url)

            manifest = self._run(root, config, fetch)
            status = manifest["source_statuses"][0]
            self.assertEqual(status["accepted"], 1)
            self.assertEqual(status["errors"], [])
            self.assertTrue(any("used feed fallback" in warning for warning in status["warnings"]))
            self.assertEqual(manifest["exit_code"], 0)

    def test_youtube_watch_page_is_never_scraped(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            youtube_feed = "https://www.youtube.com/feeds/videos.xml?channel_id=test"
            youtube_url = "https://m.youtube.com/watch?v=abc"
            config = self._write_config(
                root,
                home_url="https://www.youtube.com/@test",
                include_patterns=[],
                feed_urls=[youtube_feed],
            )
            feed = f"""<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/"><entry><title>Episode title long enough</title><link rel="alternate" href="{youtube_url}"/><published>{RECENT_ISO}</published><media:group><media:content/><media:description>Episode evidence.</media:description></media:group></entry></feed>"""
            calls: list[str] = []

            def fetch(url: str) -> tuple[str, str]:
                calls.append(url)
                if url == "https://www.youtube.com/@test":
                    return "<html></html>", "text/html"
                if url == youtube_feed:
                    return feed, "application/atom+xml"
                raise AssertionError(f"watch page fetched: {url}")

            manifest = self._run(root, config, fetch)
            self.assertEqual(manifest["exit_code"], 0)
            self.assertEqual(manifest["item_count"], 1)
            self.assertNotIn(youtube_url, calls)

    def test_one_failed_source_fails_run_even_when_another_source_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / "sources.json"
            config.write_text(
                json.dumps(
                    {
                        "sources": [
                            {
                                "slug": "good",
                                "name": "Good",
                                "home_url": HOME,
                                "feed_urls": [FEED],
                                "priority": "A",
                                "why": "test",
                                "include_patterns": ["/articles/"],
                            },
                            {
                                "slug": "broken",
                                "name": "Broken",
                                "home_url": "https://broken.example/",
                                "priority": "A",
                                "why": "test",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            def fetch(url: str) -> tuple[str, str]:
                if "broken.example" in url:
                    raise OSError("source unavailable")
                return fake_fetch(url)

            manifest = self._run(root, config, fetch)
            self.assertEqual(manifest["item_count"], 1)
            self.assertEqual(manifest["source_failures"], 1)
            self.assertEqual(manifest["exit_code"], 2)

    def test_manifest_v3_records_stable_run_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = self._write_config(root)
            expected_hash = hashlib.sha256(config.read_bytes()).hexdigest()
            first = self._run(root, config, fake_fetch)
            second = self._run(root, config, fake_fetch)
            self.assertEqual(first["schema_version"], 3)
            self.assertEqual(first["run_params"]["since_days"], 8)
            self.assertEqual(first["run_params"]["fetch_workers"], 2)
            self.assertEqual(first["run_params"]["source_slugs"], [])
            self.assertEqual(first["run_params"]["config_sha256"], expected_hash)
            self.assertEqual(second["run_params"]["config_sha256"], expected_hash)
            self.assertEqual(first["warning_count"], sum(len(row["warnings"]) for row in first["source_statuses"]))


if __name__ == "__main__":
    unittest.main()
