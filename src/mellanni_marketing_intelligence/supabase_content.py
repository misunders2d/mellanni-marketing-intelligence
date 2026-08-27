from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SOURCE_FIELDS = (
    "slug,name,home_url,priority,why,include_patterns,allowed_hosts,"
    "feed_urls,max_items,max_feed_candidates"
)


def _env_value(name: str, env_file: Path) -> str:
    existing = os.environ.get(name, "").strip()
    if existing:
        return existing
    if not env_file.exists():
        return ""

    prefix = name + "="
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return value
    return ""


def credentials(env_file: Path) -> tuple[str, str]:
    url = _env_value("SUPABASE_URL", env_file)
    key = _env_value("SUPABASE_SECRET_KEY", env_file) or _env_value(
        "SUPABASE_SERVICE_ROLE_KEY", env_file
    )
    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SECRET_KEY are required in the environment or project .env"
        )
    return url.rstrip("/"), key


def _request_json(
    base_url: str,
    key: str,
    path: str,
    *,
    method: str = "GET",
    payload: Any | None = None,
    prefer: str = "",
) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json", "apikey": key}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if prefer:
        headers["Prefer"] = prefer
    if key.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + key

    request = Request(
        base_url + "/rest/v1/" + path,
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            response_body = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Supabase request failed: {exc.reason}") from exc

    return json.loads(response_body) if response_body else None


def fetch_enabled_sources(base_url: str, key: str) -> list[dict[str, Any]]:
    rows = _request_json(
        base_url,
        key,
        "sources?select=" + SOURCE_FIELDS + "&enabled=eq.true&order=name.asc",
    )
    if not isinstance(rows, list):
        raise RuntimeError("Supabase sources response was not a list")
    if not rows:
        raise RuntimeError(
            "Supabase returned no enabled sources; check source configuration and runner credentials"
        )
    return rows


def source_rows_to_config(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    for row in rows:
        source = {
            "slug": row["slug"],
            "name": row["name"],
            "home_url": row["home_url"],
            "priority": row.get("priority", "A"),
            "why": row.get("why", ""),
            "include_patterns": row.get("include_patterns") or [],
            "allowed_hosts": row.get("allowed_hosts") or [],
            "feed_urls": row.get("feed_urls") or [],
            "max_items": int(row.get("max_items", 5)),
            "max_feed_candidates": int(row.get("max_feed_candidates", 8)),
        }
        sources.append(source)
    return {"sources": sources}


def digest_to_row(document: dict[str, Any], *, publish: bool) -> dict[str, Any]:
    required_strings = ("slug", "date", "title", "summary")
    for field in required_strings:
        if not isinstance(document.get(field), str) or not document[field].strip():
            raise ValueError(f"digest field {field!r} must be a non-empty string")
    if not SLUG_PATTERN.fullmatch(document["slug"]):
        raise ValueError("digest slug must contain lowercase letters, numbers, and hyphens only")
    date.fromisoformat(document["date"])

    topics = document.get("topics")
    findings = document.get("findings")
    sources = document.get("sources")
    if not isinstance(topics, list) or not all(isinstance(item, str) for item in topics):
        raise ValueError("digest topics must be a list of strings")
    if not isinstance(findings, list) or not all(isinstance(item, str) for item in findings):
        raise ValueError("digest findings must be a list of strings")
    if not isinstance(sources, list):
        raise ValueError("digest sources must be a list")
    for source in sources:
        if not isinstance(source, dict) or not all(
            isinstance(source.get(field), str) and source[field].strip()
            for field in ("name", "url")
        ):
            raise ValueError("each digest source needs non-empty name and url strings")

    body = {
        "topics": topics,
        "findings": findings,
        "sources": [
            {
                "name": source["name"],
                "url": source["url"],
                "note": source.get("note", ""),
            }
            for source in sources
        ],
        "isSample": document.get("isSample") is True,
    }
    return {
        "slug": document["slug"],
        "published_on": document["date"],
        "status": "published" if publish else "draft",
        "title": document["title"],
        "summary": document["summary"],
        "body": body,
        "published_at": datetime.now(timezone.utc).isoformat() if publish else None,
    }


def push_digest(
    base_url: str,
    key: str,
    document: dict[str, Any],
    *,
    publish: bool,
) -> dict[str, Any]:
    row = digest_to_row(document, publish=publish)
    rows = _request_json(
        base_url,
        key,
        "digests?on_conflict=slug",
        method="POST",
        payload=row,
        prefer="resolution=merge-duplicates,return=representation",
    )
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("Supabase digest upsert did not return exactly one row")
    return rows[0]


def record_run(
    base_url: str,
    key: str,
    manifest: dict[str, Any],
    *,
    digest_id: str | None,
) -> None:
    statuses = manifest.get("source_statuses") or []
    error_count = sum(len(status.get("errors") or []) for status in statuses)
    payload = {
        "status": "succeeded" if int(manifest.get("exit_code", 1)) == 0 else "failed",
        "started_at": manifest.get("started_at") or datetime.now(timezone.utc).isoformat(),
        "finished_at": manifest.get("finished_at") or datetime.now(timezone.utc).isoformat(),
        "source_count": int(manifest.get("source_count", 0)),
        "item_count": int(manifest.get("item_count", 0)),
        "warning_count": int(manifest.get("warning_count", 0)),
        "error_count": error_count,
        "manifest": manifest,
        "digest_id": digest_id,
    }
    _request_json(
        base_url,
        key,
        "runs",
        method="POST",
        payload=payload,
        prefer="return=minimal",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Exchange Mellanni source configuration and digests with Supabase"
    )
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export-sources")
    export_parser.add_argument("--output", type=Path, required=True)

    push_parser = subparsers.add_parser("push-digest")
    push_parser.add_argument("--input", type=Path, required=True)
    push_parser.add_argument("--manifest", type=Path)
    push_parser.add_argument("--publish", action="store_true")

    run_parser = subparsers.add_parser("record-run")
    run_parser.add_argument("--manifest", type=Path, required=True)
    run_parser.add_argument("--digest-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        base_url, key = credentials(args.env_file)
        if args.command == "export-sources":
            config = source_rows_to_config(fetch_enabled_sources(base_url, key))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(config, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(json.dumps({"source_count": len(config["sources"]), "output": str(args.output)}))
            return 0

        if args.command == "record-run":
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            record_run(base_url, key, manifest, digest_id=args.digest_id)
            print(
                json.dumps(
                    {
                        "status": "recorded",
                        "run_status": "succeeded"
                        if int(manifest.get("exit_code", 1)) == 0
                        else "failed",
                    }
                )
            )
            return 0

        document = json.loads(args.input.read_text(encoding="utf-8"))
        digest = push_digest(base_url, key, document, publish=args.publish)
        if args.manifest:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            record_run(base_url, key, manifest, digest_id=digest.get("id"))
        print(json.dumps({"digest_id": digest.get("id"), "slug": digest.get("slug"), "status": digest.get("status")}))
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
