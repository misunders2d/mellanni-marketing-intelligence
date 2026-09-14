from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .collector import Fetch, collect_source, fetch_url
from .journal import write_item, write_manifest
from .models import ContentItem, Source, SourceStatus
from .sources import load_sources


def _collect_all(sources: list[Source], since_days: int, workers: int, fetcher: Fetch) -> tuple[list[ContentItem], list[SourceStatus]]:
    items: list[ContentItem] = []
    statuses: list[SourceStatus] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        futures = {executor.submit(collect_source, source, since_days, fetcher): source for source in sources}
        for future in as_completed(futures):
            source = futures[future]
            try:
                source_items, status = future.result()
            except Exception as exc:
                source_items = []
                status = SourceStatus(source.slug, source.name, errors=[f"collector crashed: {type(exc).__name__}: {exc}"])
            items.extend(source_items)
            statuses.append(status)
    statuses.sort(key=lambda status: status.slug)
    items.sort(key=lambda item: (item.source_slug, item.published_at or "", item.title), reverse=True)
    return items, statuses


def run_fetch(
    *,
    config_path: Path,
    journal_root: Path,
    since_days: int,
    fetch_workers: int,
    source_slugs: tuple[str, ...] = (),
    fetcher: Fetch = fetch_url,
) -> dict[str, Any]:
    started = datetime.now(UTC)
    run_id = started.strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = journal_root / run_id
    journal_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    journal_root.chmod(0o700)
    run_dir.mkdir(mode=0o700, exist_ok=False)

    config_sha256 = hashlib.sha256(config_path.read_bytes()).hexdigest()
    sources = load_sources(config_path)
    if source_slugs:
        requested = set(source_slugs)
        known = {source.slug for source in sources}
        unknown = sorted(requested - known)
        if unknown:
            raise ValueError(f"unknown source slug(s): {', '.join(unknown)}")
        sources = [source for source in sources if source.slug in requested]

    items, statuses = _collect_all(sources, since_days, fetch_workers, fetcher)
    item_ids = [item.item_id for item in items]
    if len(item_ids) != len(set(item_ids)):
        raise RuntimeError("collector returned duplicate item IDs")
    item_records: list[dict[str, object]] = []
    for item in items:
        _, record = write_item(run_dir, item)
        item_records.append(record)

    source_failures = sum(1 for status in statuses if status.errors)
    manifest: dict[str, Any] = {
        "schema_version": 3,
        "run_id": run_id,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "journal_dir": str(run_dir.resolve()),
        "source_count": len(sources),
        "source_failures": source_failures,
        "warning_count": sum(len(status.warnings) for status in statuses),
        "run_params": {
            "since_days": since_days,
            "fetch_workers": fetch_workers,
            "source_slugs": list(source_slugs),
            "config_path": str(config_path.resolve()),
            "config_sha256": config_sha256,
        },
        "item_count": len(items),
        "items": item_records,
        "source_statuses": [status.to_dict() for status in statuses],
        "exit_code": 2 if source_failures else 0,
    }
    write_manifest(run_dir, manifest)
    return manifest
