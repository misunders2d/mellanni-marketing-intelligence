from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Source:
    slug: str
    name: str
    home_url: str
    priority: str
    why: str
    include_patterns: tuple[str, ...] = ()
    allowed_hosts: tuple[str, ...] = ()
    feed_urls: tuple[str, ...] = ()
    max_items: int = 5


@dataclass(frozen=True)
class ContentItem:
    item_id: str
    source_slug: str
    source_name: str
    url: str
    title: str
    published_at: str | None
    content: str
    content_hash: str


@dataclass
class SourceStatus:
    slug: str
    name: str
    method: str = "none"
    discovered: int = 0
    accepted: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
