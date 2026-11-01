from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .models import Source


SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _http_url(value: object, label: str) -> str:
    url = str(value).strip()
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{label} must use HTTP(S) with a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{label} must not contain userinfo")
    return url


def load_sources(path: Path) -> list[Source]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("sources")
    if not isinstance(rows, list) or not rows:
        raise ValueError("sources config must contain a non-empty 'sources' list")

    sources: list[Source] = []
    seen: set[str] = set()
    for row in rows:
        slug = str(row["slug"]).strip()
        if not SLUG_PATTERN.fullmatch(slug) or slug in seen:
            raise ValueError(f"invalid or duplicate source slug: {slug!r}")
        seen.add(slug)
        feed_urls = tuple(
            _http_url(value, f"source {slug!r} feed URL")
            for value in row.get("feed_urls", [])
        )
        sources.append(
            Source(
                slug=slug,
                name=str(row["name"]).strip(),
                home_url=_http_url(row["home_url"], f"source {slug!r} home URL"),
                priority=str(row.get("priority", "C")).strip(),
                why=str(row.get("why", "")).strip(),
                include_patterns=tuple(str(value) for value in row.get("include_patterns", [])),
                allowed_hosts=tuple(str(value).lower() for value in row.get("allowed_hosts", [])),
                feed_urls=feed_urls,
                max_items=int(row.get("max_items", 5)),
                max_feed_candidates=int(row.get("max_feed_candidates", 8)),
                evergreen=row.get("evergreen", False) is True,
            )
        )
    return sources
