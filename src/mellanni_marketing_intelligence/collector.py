from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
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
MIN_ARTICLE_TEXT_CHARS = 200
UNDATED_FETCH_MULTIPLIER = 3
TRACKING_QUERY_KEYS = {"ref", "source"}
LOCALE_QUERY_KEYS = {"mons_sel_locale", "locale", "lang", "language", "hl"}
Fetch = Callable[[str], tuple[str, str]]


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [
        (key, value)
        for key, value in query
        if not key.lower().startswith("utm_")
        and key.lower() not in TRACKING_QUERY_KEYS | LOCALE_QUERY_KEYS
    ]
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, urllib.parse.urlencode(query), ""))


def _assert_public_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must use HTTP(S) with a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URL userinfo is not allowed")
    try:
        addresses = {
            row[4][0]
            for row in socket.getaddrinfo(
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        }
    except socket.gaierror as exc:
        raise ValueError(f"URL hostname did not resolve: {parsed.hostname}") from exc
    if not addresses:
        raise ValueError(f"URL hostname did not resolve: {parsed.hostname}")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError(f"URL resolves to non-public address: {address}")


def _assert_public_response_peer(response: object) -> None:
    candidates = (
        getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None),
        getattr(getattr(response, "fp", None), "_sock", None),
        getattr(response, "_sock", None),
    )
    sock = next((candidate for candidate in candidates if candidate is not None), None)
    if sock is None:
        raise RuntimeError("could not verify connected response peer")
    peer = sock.getpeername()
    if not peer:
        raise RuntimeError("connected response peer was empty")
    address = ipaddress.ip_address(peer[0])
    if not address.is_global:
        raise ValueError(f"response connected to non-public address: {address}")


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        _assert_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_url(url: str, timeout: float = 20.0) -> tuple[str, str]:
    _assert_public_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/html;q=0.9, */*;q=0.5"})
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _SafeRedirectHandler(),
    )
    with opener.open(request, timeout=timeout) as response:
        _assert_public_response_peer(response)
        content_type = response.headers.get_content_type()
        limit = MAX_FEED_BYTES if any(marker in content_type for marker in ("rss", "atom", "xml")) else MAX_PAGE_BYTES
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError(f"response exceeds {limit} bytes")
        charset = response.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace"), content_type


_IGNORED_TAGS = {"script", "style", "noscript", "svg", "template"}
_CHROME_TAGS = {"nav", "footer", "aside", "form", "header"}
_BLOCK_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "br",
    "article", "section", "div", "tr", "pre", "figcaption",
}
_VOID_TAGS = {"br", "img", "hr", "meta", "link", "input", "source", "wbr"}


class _TextParser(HTMLParser):
    """Collect page text, keeping block breaks and separating article/main content.

    Navigation, footer, aside, form, and page-level header chrome is dropped. A
    header inside <article> or <main> is kept because it often holds the title.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.article_parts: list[str] = []
        self.main_parts: list[str] = []
        self.published_at: list[str] = []
        self._ignored = 0
        self._chrome: list[str] = []
        self._article = 0
        self._main = 0
        self._ld_json: list[str] | None = None

    def _emit(self, value: str) -> None:
        if self._ignored or self._chrome:
            return
        self.parts.append(value)
        if self._article:
            self.article_parts.append(value)
        if self._main:
            self.main_parts.append(value)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            name = (values.get("property") or values.get("name") or values.get("itemprop") or "").lower()
            if name in {"article:published_time", "datepublished", "date", "dc.date", "publish-date"}:
                self.published_at.append(values.get("content", ""))
            return
        if tag == "time" and values.get("datetime"):
            self.published_at.append(values["datetime"])
        if tag == "script" and values.get("type", "").lower() == "application/ld+json":
            self._ld_json = []
        if tag in _IGNORED_TAGS:
            self._ignored += 1
            return
        if tag in _CHROME_TAGS and not (tag == "header" and (self._article or self._main)):
            self._chrome.append(tag)
            return
        if tag == "article":
            self._article += 1
        elif tag == "main":
            self._main += 1
        if tag in _BLOCK_TAGS:
            self._emit("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._ld_json is not None:
            match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', "".join(self._ld_json))
            if match:
                self.published_at.append(match.group(1))
            self._ld_json = None
        if tag in _IGNORED_TAGS:
            if self._ignored:
                self._ignored -= 1
            return
        if self._chrome and self._chrome[-1] == tag:
            self._chrome.pop()
            return
        if tag in _BLOCK_TAGS and tag not in _VOID_TAGS:
            self._emit("\n")
        if tag == "article" and self._article:
            self._article -= 1
        elif tag == "main" and self._main:
            self._main -= 1

    def handle_data(self, data: str) -> None:
        if self._ld_json is not None:
            self._ld_json.append(data)
        self._emit(data)


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


def _clean_block_text(value: str) -> str:
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in value.split("\n")]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _parse_page(value: str) -> _TextParser:
    parser = _TextParser()
    parser.feed(value)
    parser.close()
    return parser


def _page_text(parser: _TextParser) -> str:
    for parts in (parser.article_parts, parser.main_parts):
        text = _clean_block_text("".join(parts))
        if len(text) >= MIN_ARTICLE_TEXT_CHARS:
            return text[:MAX_CONTENT_CHARS]
    return _clean_block_text("".join(parser.parts))[:MAX_CONTENT_CHARS]


def html_to_text(value: str) -> str:
    """Readable page text: prefer <article>, then <main>, keep paragraph breaks."""
    return _page_text(_parse_page(value))


def page_published_at(value: str) -> str | None:
    """First parseable publication date from page metadata, JSON-LD, or <time>."""
    for candidate in _parse_page(value).published_at:
        parsed = parse_date(candidate)
        if parsed:
            return parsed
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(node: ET.Element, names: set[str]) -> str:
    for child in list(node):
        if _local_name(child.tag) in names:
            return "".join(child.itertext()).strip()
    return ""


def _descendant_text(node: ET.Element, names: tuple[str, ...]) -> str:
    for name in names:
        for child in node.iter():
            if child is not node and _local_name(child.tag) == name:
                text = "".join(child.itertext()).strip()
                if text:
                    return text
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


def _parse_feed(document: str, base_url: str) -> tuple[list[_RawEntry], bool]:
    try:
        root = ET.fromstring(document)
    except ET.ParseError:
        return [], False
    if _local_name(root.tag) not in {"rss", "feed", "rdf", "channel"}:
        return [], False
    entries: list[_RawEntry] = []
    for node in root.iter():
        if _local_name(node.tag) not in {"item", "entry"}:
            continue
        title = _child_text(node, {"title"}) or "Untitled"
        url = urllib.parse.urljoin(base_url, _entry_link(node) or _child_text(node, {"guid", "id"}))
        if not url.startswith(("http://", "https://")):
            continue
        published = _child_text(node, {"pubdate", "published", "updated", "date"})
        summary = _descendant_text(
            node, ("description", "summary", "content", "encoded")
        )
        entries.append(_RawEntry(_clean_text(title), canonical_url(url), parse_date(published), html_to_text(summary)))
    return entries, True


def parse_feed(document: str, base_url: str) -> list[_RawEntry]:
    return _parse_feed(document, base_url)[0]


def is_youtube_url(url: str) -> bool:
    try:
        host = urllib.parse.urlsplit(url).hostname or ""
    except ValueError:
        return False
    host = host.lower().rstrip(".")
    return host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")


def _url_allowed_for_source(source: Source, url: str) -> bool:
    parsed_home = urllib.parse.urlsplit(source.home_url)
    parsed = urllib.parse.urlsplit(url)
    if is_youtube_url(source.home_url) and is_youtube_url(url):
        return parsed.scheme in {"http", "https"}
    allowed_hosts = {
        (parsed_home.hostname or "").lower(),
        *(host for host in source.allowed_hosts if not host.startswith(".")),
    }
    allowed_suffixes = tuple(
        host for host in source.allowed_hosts if host.startswith(".")
    )
    host = (parsed.hostname or "").lower()
    return parsed.scheme in {"http", "https"} and (
        host in allowed_hosts or host.endswith(allowed_suffixes)
    )


def _looks_like_article(source: Source, home_url: str, url: str, title: str) -> bool:
    # Navigation and locale links ("English - US", "List products") are short.
    if len(title) < 12 or len(re.findall(r"\w{2,}", title)) < 3:
        return False
    if url == canonical_url(home_url):
        return False
    parsed = urllib.parse.urlsplit(url)
    if not _url_allowed_for_source(source, url):
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
        # Query variants of one path are the same index page.
        parsed = urllib.parse.urlsplit(clean_url)
        path_identity = f"{parsed.netloc}{parsed.path}"
        if path_identity in seen or not _looks_like_article(source, source.home_url, clean_url, title):
            continue
        seen.add(path_identity)
        entries.append(_RawEntry(title, clean_url, None, ""))
    return entries, parser.feed_urls


def _dedupe_urls(urls: tuple[str, ...] | list[str]) -> list[str]:
    result: list[str] = []
    for url in urls:
        clean = canonical_url(url)
        if clean not in result:
            result.append(clean)
    return result


def _feed_candidates(source: Source, discovered: list[str]) -> tuple[list[str], int, int]:
    parsed = urllib.parse.urlsplit(source.home_url)
    origin = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/", "", ""))
    common = [urllib.parse.urljoin(origin, value) for value in ("feed", "feed/", "rss", "rss.xml", "feed.xml")]
    explicit = _dedupe_urls(source.feed_urls)
    rest = [url for url in _dedupe_urls([*discovered, *common]) if url not in explicit]
    total = len(explicit) + len(rest)
    budget = max(0, source.max_feed_candidates - len(explicit))
    candidates = [*explicit, *rest[:budget]]
    return candidates, total, total - len(candidates)


def _within_window(published_at: str | None, cutoff: datetime) -> bool:
    if not published_at:
        return True
    return datetime.fromisoformat(published_at) >= cutoff


def collect_source(source: Source, since_days: int, fetcher: Fetch = fetch_url) -> tuple[list[ContentItem], SourceStatus]:
    status = SourceStatus(slug=source.slug, name=source.name)
    cutoff = datetime.now(UTC) - timedelta(days=since_days)
    home_document = ""
    home_fetch_failed = False
    home_fetch_error = ""
    try:
        home_document, _ = fetcher(source.home_url)
    except Exception as exc:  # explicit feeds can still keep source operational
        home_fetch_failed = True
        home_fetch_error = f"home fetch failed: {type(exc).__name__}: {exc}"

    index_entries, discovered_feeds = _index_entries(source, home_document) if home_document else ([], [])
    entries: list[_RawEntry] = []
    usable_feed = False
    explicit_feeds = {canonical_url(url) for url in source.feed_urls}
    feed_candidates, feed_candidates_total, feed_candidates_truncated = _feed_candidates(source, discovered_feeds)
    status.feed_candidates_total = feed_candidates_total
    status.feed_candidates_truncated = feed_candidates_truncated
    if feed_candidates_truncated:
        status.warnings.append(
            f"feed candidate limit skipped {feed_candidates_truncated} of {feed_candidates_total} candidate(s)"
        )

    probe_error_count = 0
    probe_empty_count = 0
    valid_empty_explicit: str | None = None
    valid_stale_feed: tuple[str, list[_RawEntry]] | None = None
    for feed_url in feed_candidates:
        status.feed_candidates_probed += 1
        if feed_url not in explicit_feeds and not _url_allowed_for_source(source, feed_url):
            probe_error_count += 1
            status.warnings.append(f"feed candidate host is not allowed {feed_url}")
            continue
        try:
            feed_document, _ = fetcher(feed_url)
            candidate_entries, parsed = _parse_feed(feed_document, feed_url)
            if not parsed:
                probe_error_count += 1
                status.warnings.append(f"feed candidate was not valid XML {feed_url}")
                continue
            rejected_entries = [
                entry
                for entry in candidate_entries
                if not _url_allowed_for_source(source, entry.url)
            ]
            if rejected_entries:
                status.warnings.append(
                    f"feed candidate rejected {len(rejected_entries)} disallowed item host(s) {feed_url}"
                )
                candidate_entries = [
                    entry
                    for entry in candidate_entries
                    if _url_allowed_for_source(source, entry.url)
                ]
                if not candidate_entries:
                    probe_error_count += 1
                    continue
            if source.include_patterns and feed_url not in explicit_feeds:
                candidate_entries = [
                    entry
                    for entry in candidate_entries
                    if any(pattern.lower() in entry.url.lower() for pattern in source.include_patterns)
                ]
        except Exception as exc:  # feed candidates are expected to vary
            probe_error_count += 1
            status.warnings.append(f"feed candidate failed {feed_url}: {type(exc).__name__}: {exc}")
            continue
        if candidate_entries:
            if not any(
                _within_window(entry.published_at, cutoff)
                for entry in candidate_entries
            ):
                if valid_stale_feed is None:
                    valid_stale_feed = (feed_url, candidate_entries)
                status.warnings.append(
                    f"feed candidate has no in-window entries {feed_url}"
                )
                continue
            entries = candidate_entries
            status.method = f"feed:{feed_url}"
            usable_feed = True
            break
        if feed_url in explicit_feeds:
            if valid_empty_explicit is None:
                valid_empty_explicit = feed_url
            status.warnings.append(f"explicit feed is valid and currently empty {feed_url}")
            continue
        probe_empty_count += 1
        status.warnings.append(f"feed candidate returned no entries {feed_url}")

    if not entries and valid_stale_feed:
        stale_feed_url, entries = valid_stale_feed
        status.method = f"feed:{stale_feed_url}"
        usable_feed = True
    elif not entries and valid_empty_explicit:
        status.method = f"feed:{valid_empty_explicit}"
        usable_feed = True

    if not entries and not usable_feed:
        entries = index_entries
        status.method = "html-index"
        status.fallback_reason = (
            f"home_fetch={'failed' if home_fetch_failed else 'ok'}; "
            f"feed_probes={status.feed_candidates_probed}; "
            f"feed_errors={probe_error_count}; "
            f"feed_empty={probe_empty_count}; "
            f"html_index={'used' if entries else 'empty'}"
        )
        if not entries:
            detail = f"; {home_fetch_error}" if home_fetch_error else ""
            status.errors.append(
                f"no usable feed or index; {probe_error_count} feed probe(s) failed (see warnings){detail}"
            )

    if home_fetch_error:
        if usable_feed:
            status.warnings.append(f"{home_fetch_error}; recovered by feed")

    status.discovered = len(entries)
    eligible_entries = [entry for entry in entries if _within_window(entry.published_at, cutoff)]
    unique_entries: list[_RawEntry] = []
    seen_urls: set[str] = set()
    for entry in eligible_entries:
        identity = canonical_url(entry.url)
        if identity in seen_urls:
            continue
        seen_urls.add(identity)
        unique_entries.append(entry)
    duplicate_count = len(eligible_entries) - len(unique_entries)
    if duplicate_count:
        status.warnings.append(f"deduplicated {duplicate_count} repeated item(s)")
    eligible_entries = unique_entries
    # Undated entries need a page fetch to learn their date, so allow extra
    # fetches; entries that stay undated are rejected unless the source is
    # explicitly evergreen.
    fetch_budget = source.max_items * UNDATED_FETCH_MULTIPLIER
    accepted: list[ContentItem] = []
    attempted = 0
    undated_rejected = 0
    stale_rejected = 0
    for entry in eligible_entries:
        if len(accepted) >= source.max_items or attempted >= fetch_budget:
            break
        attempted += 1
        page_text = ""
        published_at = entry.published_at
        if not is_youtube_url(entry.url):
            try:
                page_document, content_type = fetcher(entry.url)
                if "html" in content_type or "xml" not in content_type:
                    page_text = html_to_text(page_document)
                    published_at = published_at or page_published_at(page_document)
                else:
                    page_text = entry.summary
            except Exception as exc:
                status.warnings.append(
                    f"item fetch failed {entry.url}; used feed fallback: {type(exc).__name__}: {exc}"
                )
        if published_at is None and not source.evergreen:
            undated_rejected += 1
            continue
        if not _within_window(published_at, cutoff):
            stale_rejected += 1
            continue
        content = max((entry.summary, page_text, entry.title), key=len)[:MAX_CONTENT_CHARS]
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        item_id = hashlib.sha256(
            f"{source.slug}\n{entry.url}\n{content_hash}".encode("utf-8")
        ).hexdigest()
        accepted.append(
            ContentItem(
                item_id=item_id,
                source_slug=source.slug,
                source_name=source.name,
                url=entry.url,
                title=entry.title,
                published_at=published_at,
                content=content,
                content_hash=content_hash,
            )
        )
    if undated_rejected:
        status.warnings.append(
            f"rejected {undated_rejected} undated item(s); mark the source evergreen to keep undated pages"
        )
    if stale_rejected:
        status.warnings.append(
            f"rejected {stale_rejected} item(s) whose page date is outside the window"
        )
    status.item_limit_truncated = (
        max(0, len(eligible_entries) - attempted)
        if len(accepted) >= source.max_items
        else 0
    )
    if status.item_limit_truncated:
        status.warnings.append(
            f"item limit truncated {status.item_limit_truncated} of {len(eligible_entries)} eligible item(s)"
        )
    status.accepted = len(accepted)
    return accepted, status
