from __future__ import annotations

import json
from pathlib import Path

from .models import Source


def load_sources(path: Path) -> list[Source]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("sources")
    if not isinstance(rows, list) or not rows:
        raise ValueError("sources config must contain a non-empty 'sources' list")

    sources: list[Source] = []
    seen: set[str] = set()
    for row in rows:
        slug = str(row["slug"]).strip()
        if not slug or slug in seen:
            raise ValueError(f"duplicate or empty source slug: {slug!r}")
        seen.add(slug)
        sources.append(
            Source(
                slug=slug,
                name=str(row["name"]).strip(),
                home_url=str(row["home_url"]).strip(),
                priority=str(row.get("priority", "C")).strip(),
                why=str(row.get("why", "")).strip(),
                include_patterns=tuple(str(value) for value in row.get("include_patterns", [])),
                allowed_hosts=tuple(str(value).lower() for value in row.get("allowed_hosts", [])),
                feed_urls=tuple(str(value) for value in row.get("feed_urls", [])),
                max_items=int(row.get("max_items", 5)),
            )
        )
    return sources
