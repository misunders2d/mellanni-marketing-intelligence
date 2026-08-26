from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_fetch


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Mellanni marketing sources into a local journal")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "sources.json")
    parser.add_argument("--journal-root", type=Path, default=PROJECT_ROOT / "journal")
    parser.add_argument("--since-days", type=int, default=8)
    parser.add_argument("--fetch-workers", type=int, default=6)
    parser.add_argument("--source", action="append", default=[], help="Fetch only one source slug; repeat for several")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.since_days < 1 or args.fetch_workers < 1:
        raise SystemExit("day and worker values must be positive")
    manifest = run_fetch(
        config_path=args.config,
        journal_root=args.journal_root,
        since_days=args.since_days,
        fetch_workers=args.fetch_workers,
        source_slugs=tuple(args.source),
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    return int(manifest["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
