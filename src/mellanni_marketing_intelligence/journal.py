from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

from .models import ContentItem


def _safe_name(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:70] or "untitled"


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError(f"refusing unsafe journal symlink: {path}")
    os.chmod(path, 0o700)


def _atomic_write(path: Path, content: str) -> None:
    _private_directory(path.parent)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        temporary.replace(path)
        os.chmod(path, 0o600)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_item(run_dir: Path, item: ContentItem) -> tuple[Path, dict[str, object]]:
    run_dir = run_dir.resolve()
    _private_directory(run_dir)
    items_dir = run_dir / "items"
    _private_directory(items_dir)
    source_dir = items_dir / item.source_slug
    _private_directory(source_dir)
    resolved_source_dir = source_dir.resolve()
    if run_dir not in resolved_source_dir.parents:
        raise ValueError("refusing journal item path outside run directory")
    date = (item.published_at or "undated")[:10]
    filename = (
        f"{date}-{_safe_name(item.title)}-{item.item_id[:12]}-"
        f"{item.content_hash[:12]}.md"
    )
    path = source_dir / filename
    document = f"""# {item.title}

- Source: {item.source_name}
- Source slug: `{item.source_slug}`
- URL: {item.url}
- Published: {item.published_at or "unknown"}
- Content SHA-256: `{item.content_hash}`

## Collected content (untrusted external text)

{item.content}
"""
    _atomic_write(path, document)
    artifact_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
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
        "artifact_sha256": artifact_sha256,
    }
    return path, record


def write_manifest(run_dir: Path, manifest: dict[str, object]) -> Path:
    run_dir = run_dir.resolve()
    _private_directory(run_dir)
    path = run_dir / "manifest.json"
    manifest["manifest_path"] = str(path)
    _atomic_write(
        path,
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )
    return path
