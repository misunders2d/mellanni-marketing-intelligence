from __future__ import annotations

import hashlib
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Callable

from .models import ContentItem, Source, SourceStatus

USER_AGENT = "MellanniMarketingIntelligence/0.1 (+local research runner)"
MAX_PAGE_BYTES = 2_000_000
MAX_FEED_BYTES = 10_000_000
MAX_CONTENT_CHARS = 30_000
Fetch = Callable[[str], tuple[str, str]]


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if not key.lower().startswith("utm_") and key.lower() not in {"ref", "source"}]
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, urllib.parse.urlencode(query), ""))


def fetch_url(url: str, timeout: float = 20.0) -> tuple[str, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/html;q=0.9, */*;q=0.5"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_type()
        limit = MAX_FEED_BYTES if any(marker in content_type for marker in ("rss", "atom", "xml")) else MAX_PAGE_BYTES
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError(f"response exceeds {limit} bytes")
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace"), content_type


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self._ignored += 1
        elif tag in {"p", "h1", "h2", "h3", "h4", "li", "blockquote", "br", "article", "section"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "template"} and self._ignored:
            self._ignored -= 1
        elif tag in {"p", "h1", "h2", "h3", "h4", "li", "blockquote", "article", "section"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored:
            self.parts.append(data)


class _DiscoveryParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.feed_urls: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "link" and "alternate" in values.get("rel", "").lower() and any(marker in values.get("type", "").lower() for marker in ("rss", "atom", "xml")):
            href = values.get("href")
            if href:
                self.feed_urls.append(urllib.parse.urljoin(self.base_url, href))
        if tag == "a" and values.get("href"):
            self._href = urllib.parse.urljoin(self.base_url, values["href"])
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            text = _clean_text(" ".join(self._text))
            self.links.append((self._href, text))
            self._href = None
            self._text = []


@dataclass(frozen=True)
class _RawEntry:
    title: str
    url: str
    published_at: str | None
    summary: str


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def html_to_text(value: str) -> str:
    parser = _TextParser()
    parser.feed(value)
    return _clean_text(" ".join(parser.parts))[:MAX_CONTENT_CHARS]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(node: ET.Element, names: set[str]) -> str:
    for child in list(node):
        if _local_name(child.tag) in names:
            return "".join(child.itertext()).strip()
    return ""


def _entry_link(node: ET.Element) -> str:
    for child in list(node):
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        rel = child.attrib.get("rel", "alternate")
        if href and rel in {"alternate", ""}:
            return href
        if child.text and child.text.strip():
            return child.text.strip()
    return ""


def parse_date(value: str) -> str | None:
    if not value.strip():
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def parse_feed(document: str, base_url: str) -> list[_RawEntry]:
    try:
        root = ET.fromstring(document)
    except ET.ParseError:
        return []
    entries: list[_RawEntry] = []
    for node in root.iter():
        if _local_name(node.tag) not in {"item", "entry"}:
            continue
        title = _child_text(node, {"title"}) or "Untitled"
        url = urllib.parse.urljoin(base_url, _entry_link(node) or _child_text(node, {"guid", "id"}))
        if not url.startswith(("http://", "https://")):
            continue
        published = _child_text(node, {"pubdate", "published", "updated", "date"})
        summary = _child_text(node, {"description", "summary", "content", "encoded"})
        entries.append(_RawEntry(_clean_text(title), canonical_url(url), parse_date(published), html_to_text(summary)))
    return entries


def _looks_like_article(source: Source, home_url: str, url: str, title: str) -> bool:
    if len(title) < 12 or url == canonical_url(home_url):
        return False
    parsed_home = urllib.parse.urlsplit(home_url)
    parsed = urllib.parse.urlsplit(url)
    allowed_hosts = {parsed_home.netloc.lower(), *(host for host in source.allowed_hosts if not host.startswith("."))}
    allowed_suffixes = tuple(host for host in source.allowed_hosts if host.startswith("."))
    host = parsed.netloc.lower()
    if parsed.scheme not in {"http", "https"} or (host not in allowed_hosts and not host.endswith(allowed_suffixes)):
        return False
    if any(parsed.path.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".svg", ".pdf", ".zip")):
        return False
    lowered = title.lower()
    if lowered in {"home", "about", "contact", "subscribe", "login", "sign in", "privacy policy", "terms of service"}:
        return False
    if source.include_patterns and not any(pattern.lower() in url.lower() for pattern in source.include_patterns):
        return False
    return True


def _index_entries(source: Source, document: str) -> tuple[list[_RawEntry], list[str]]:
    parser = _DiscoveryParser(source.home_url)
    parser.feed(document)
    seen: set[str] = set()
    entries: list[_RawEntry] = []
    for url, title in parser.links:
        clean_url = canonical_url(url)
        if clean_url in seen or not _looks_like_article(source, source.home_url, clean_url, title):
            continue
        seen.add(clean_url)
        entries.append(_RawEntry(title, clean_url, None, ""))
    return entries, parser.feed_urls


def _feed_candidates(source: Source, discovered: list[str]) -> list[str]:
    parsed = urllib.parse.urlsplit(source.home_url)
    origin = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/", "", ""))
    common = [urllib.parse.urljoin(origin, value) for value in ("feed", "feed/", "rss", "rss.xml", "feed.xml")]
    result: list[str] = []
    for url in (*source.feed_urls, *discovered, *common):
        clean = canonical_url(url)
        if clean not in result:
            result.append(clean)
    return result[:8]


def _within_window(published_at: str | None, cutoff: datetime) -> bool:
    if not published_at:
        return True
    return datetime.fromisoformat(published_at) >= cutoff


def collect_source(source: Source, since_days: int, fetcher: Fetch = fetch_url) -> tuple[list[ContentItem], SourceStatus]:
    status = SourceStatus(slug=source.slug, name=source.name)
    cutoff = datetime.now(UTC) - timedelta(days=since_days)
    home_document = ""
    try:
        home_document, _ = fetcher(source.home_url)
    except Exception as exc:  # explicit feeds can still keep source operational
        status.errors.append(f"home fetch failed: {type(exc).__name__}: {exc}")

    index_entries, discovered_feeds = _index_entries(source, home_document) if home_document else ([], [])
    entries: list[_RawEntry] = []
    explicit_feeds = {canonical_url(url) for url in source.feed_urls}
    probe_errors: list[str] = []
    for feed_url in _feed_candidates(source, discovered_feeds):
        try:
            feed_document, _ = fetcher(feed_url)
            candidate_entries = parse_feed(feed_document, feed_url)
            if source.include_patterns and feed_url not in explicit_feeds:
                candidate_entries = [
                    entry
                    for entry in candidate_entries
                    if any(pattern.lower() in entry.url.lower() for pattern in source.include_patterns)
                ]
        except Exception as exc:  # feed candidates are expected to vary
            probe_errors.append(f"feed candidate failed {feed_url}: {type(exc).__name__}: {exc}")
            continue
        if candidate_entries:
            entries = candidate_entries
            status.method = f"feed:{feed_url}"
            break

    if not entries:
        entries = index_entries
        status.method = "html-index"
        if not entries:
            status.errors.extend(probe_errors[-2:])

    status.discovered = len(entries)
    accepted: list[ContentItem] = []
    for entry in entries:
        if len(accepted) >= source.max_items or not _within_window(entry.published_at, cutoff):
            continue
        page_text = ""
        try:
            page_document, content_type = fetcher(entry.url)
            page_text = html_to_text(page_document) if "html" in content_type or "xml" not in content_type else entry.summary
        except Exception as exc:
            status.errors.append(f"item fetch failed {entry.url}: {type(exc).__name__}: {exc}")
        content = max((entry.summary, page_text, entry.title), key=len)[:MAX_CONTENT_CHARS]
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        item_id = hashlib.sha256(f"{entry.url}\n{content_hash}".encode("utf-8")).hexdigest()
        accepted.append(
            ContentItem(
                item_id=item_id,
                source_slug=source.slug,
                source_name=source.name,
                url=entry.url,
                title=entry.title,
                published_at=entry.published_at,
                content=content,
                content_hash=content_hash,
            )
        )
    status.accepted = len(accepted)
    return accepted, status
