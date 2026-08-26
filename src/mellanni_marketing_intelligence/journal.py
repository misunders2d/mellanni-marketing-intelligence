from __future__ import annotations

import json
import re
from pathlib import Path

from .models import ContentItem


def _safe_name(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:70] or "untitled"


def write_item(run_dir: Path, item: ContentItem) -> tuple[Path, dict[str, object]]:
    source_dir = run_dir / "items" / item.source_slug
    source_dir.mkdir(parents=True, exist_ok=True)
    date = (item.published_at or "undated")[:10]
    filename = f"{date}-{_safe_name(item.title)}-{item.content_hash[:12]}.md"
    path = source_dir / filename
    document = f"""# {item.title}

- Source: {item.source_name}
- Source slug: `{item.source_slug}`
- URL: {item.url}
- Published: {item.published_at or "unknown"}
- Content SHA-256: `{item.content_hash}`

## Collected content

{item.content}
"""
    path.write_text(document, encoding="utf-8")
    record: dict[str, object] = {
        "item_id": item.item_id,
        "source_slug": item.source_slug,
        "source_name": item.source_name,
        "title": item.title,
        "url": item.url,
        "published_at": item.published_at,
        "content_hash": item.content_hash,
        "content_chars": len(item.content),
        "journal_path": str(path.relative_to(run_dir)),
    }
    return path, record


def write_manifest(run_dir: Path, manifest: dict[str, object]) -> Path:
    path = run_dir / "manifest.json"
    manifest["manifest_path"] = str(path.resolve())
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return path
