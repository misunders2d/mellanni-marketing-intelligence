from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .editorial import (
    private_digest_body,
    public_digest_body,
    validate_digest,
    validate_evidence_packet,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUPABASE_PROJECT_REF = "ietmqlcntwzlogdefwni"
DEFAULT_SUPABASE_HOME = Path(
    os.environ.get(
        "MELLANNI_SUPABASE_HOME", str(Path.home() / ".config" / "supabase" / "company")
    )
).expanduser()
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SOURCE_FIELDS = (
    "slug,name,home_url,priority,why,include_patterns,allowed_hosts,"
    "feed_urls,max_items,max_feed_candidates"
)
SOURCE_ADMIN_FIELDS = SOURCE_FIELDS + ",enabled,updated_at"
DIGEST_ADMIN_FIELDS = (
    "id,slug,published_on,status,title,summary,body,private_body,updated_at"
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


def _company_cli_credentials(project_ref: str) -> tuple[str, str]:
    env = os.environ.copy()
    env["SUPABASE_NO_KEYRING"] = "1"
    env["SUPABASE_HOME"] = str(DEFAULT_SUPABASE_HOME)
    try:
        result = subprocess.run(
            [
                "supabase",
                "projects",
                "api-keys",
                "--project-ref",
                project_ref,
                "--output",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError(
            "Supabase runner credentials are missing and company CLI profile lookup failed"
        ) from exc

    rows = json.loads(result.stdout)
    if not isinstance(rows, list):
        raise ValueError("Supabase CLI API-key response was not a list")
    service_role = next(
        (
            row.get("api_key")
            for row in rows
            if row.get("name") == "service_role" and row.get("type") == "legacy"
        ),
        "",
    )
    if not isinstance(service_role, str) or not service_role:
        raise ValueError("Supabase company profile has no usable service_role key")
    return f"https://{project_ref}.supabase.co", service_role


def credentials(env_file: Path, *, project_ref: str) -> tuple[str, str]:
    url = _env_value("SUPABASE_URL", env_file)
    key = _env_value("SUPABASE_SECRET_KEY", env_file) or _env_value(
        "SUPABASE_SERVICE_ROLE_KEY", env_file
    )
    if url and key:
        return url.rstrip("/"), key
    return _company_cli_credentials(project_ref)


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


def list_sources(base_url: str, key: str, *, include_disabled: bool) -> list[dict[str, Any]]:
    path = "sources?select=" + SOURCE_ADMIN_FIELDS
    if not include_disabled:
        path += "&enabled=eq.true"
    path += "&order=name.asc"
    rows = _request_json(base_url, key, path)
    if not isinstance(rows, list):
        raise RuntimeError("Supabase sources response was not a list")
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


def source_document_to_row(document: dict[str, Any]) -> dict[str, Any]:
    for field in ("slug", "name", "home_url"):
        if not isinstance(document.get(field), str) or not document[field].strip():
            raise ValueError(f"source field {field!r} must be a non-empty string")
    slug = document["slug"].strip()
    name = document["name"].strip()
    home_url = document["home_url"].strip()
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError("source slug must contain lowercase letters, numbers, and hyphens only")
    if not home_url.startswith(("http://", "https://")):
        raise ValueError("source home_url must use http or https")

    row: dict[str, Any] = {
        "slug": slug,
        "name": name,
        "home_url": home_url,
        "priority": str(document.get("priority", "A")).strip() or "A",
        "why": str(document.get("why", "")).strip(),
        "enabled": document.get("enabled", True),
    }
    if not isinstance(row["enabled"], bool):
        raise ValueError("source enabled must be a boolean")

    for field in ("include_patterns", "allowed_hosts", "feed_urls"):
        value = document.get(field, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"source {field} must be a list of strings")
        row[field] = value

    for field, default in (("max_items", 5), ("max_feed_candidates", 8)):
        value = int(document.get(field, default))
        if not 1 <= value <= 100:
            raise ValueError(f"source {field} must be between 1 and 100")
        row[field] = value
    return row


def upsert_source(base_url: str, key: str, document: dict[str, Any]) -> dict[str, Any]:
    rows = _request_json(
        base_url,
        key,
        "sources?on_conflict=slug",
        method="POST",
        payload=source_document_to_row(document),
        prefer="resolution=merge-duplicates,return=representation",
    )
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("Supabase source upsert did not return exactly one row")
    return rows[0]


def set_source_state(base_url: str, key: str, slug: str, *, enabled: bool) -> dict[str, Any]:
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError("source slug must contain lowercase letters, numbers, and hyphens only")
    rows = _request_json(
        base_url,
        key,
        "sources?slug=eq." + quote(slug, safe=""),
        method="PATCH",
        payload={"enabled": enabled},
        prefer="return=representation",
    )
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError(f"source {slug!r} was not found")
    return rows[0]


def digest_to_row(
    document: dict[str, Any],
    *,
    publish: bool,
    evidence_packet: dict[str, Any],
) -> dict[str, Any]:
    validate_digest(document, evidence_packet)
    return {
        "slug": document["slug"],
        "published_on": document["date"],
        "status": "published" if publish else "draft",
        "title": document["title"],
        "summary": document["summary"],
        "body": public_digest_body(document),
        "private_body": private_digest_body(document),
        "published_at": datetime.now(timezone.utc).isoformat() if publish else None,
    }


def push_digest(
    base_url: str,
    key: str,
    document: dict[str, Any],
    *,
    publish: bool,
    evidence_packet: dict[str, Any],
) -> dict[str, Any]:
    row = digest_to_row(
        document,
        publish=publish,
        evidence_packet=evidence_packet,
    )
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


def list_digests(base_url: str, key: str, *, status: str) -> list[dict[str, Any]]:
    path = "digests?select=" + DIGEST_ADMIN_FIELDS
    if status != "all":
        path += "&status=eq." + quote(status, safe="")
    path += "&order=published_on.desc"
    rows = _request_json(base_url, key, path)
    if not isinstance(rows, list):
        raise RuntimeError("Supabase digests response was not a list")
    return rows


def set_digest_state(base_url: str, key: str, slug: str, *, status: str) -> dict[str, Any]:
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError("digest slug must contain lowercase letters, numbers, and hyphens only")
    if status not in {"draft", "published"}:
        raise ValueError("digest status must be draft or published")
    publishing = status == "published"
    rows = _request_json(
        base_url,
        key,
        "digests?slug=eq." + quote(slug, safe=""),
        method="PATCH",
        payload={
            "status": status,
            "published_at": datetime.now(timezone.utc).isoformat() if publishing else None,
        },
        prefer="return=representation",
    )
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError(f"digest {slug!r} was not found")
    return rows[0]


def record_run(
    base_url: str,
    key: str,
    manifest: dict[str, Any],
    *,
    digest_id: str | None,
    evidence_packet: dict[str, Any] | None = None,
    outcome: str = "collection",
    reason: str = "",
) -> None:
    if outcome not in {"collection", "digest", "no-digest"}:
        raise ValueError("run outcome must be collection, digest, or no-digest")
    if outcome == "no-digest" and not reason.strip():
        raise ValueError("no-digest run outcome requires a reason")
    statuses = manifest.get("source_statuses") or []
    error_count = sum(len(status.get("errors") or []) for status in statuses)
    collection_succeeded = int(manifest.get("exit_code", 1)) == 0
    run_status = "succeeded" if collection_succeeded and outcome != "no-digest" else "failed"
    payload = {
        "status": run_status,
        "outcome": outcome,
        "outcome_reason": reason.strip(),
        "started_at": manifest.get("started_at") or datetime.now(timezone.utc).isoformat(),
        "finished_at": manifest.get("finished_at") or datetime.now(timezone.utc).isoformat(),
        "source_count": int(manifest.get("source_count", 0)),
        "item_count": int(manifest.get("item_count", 0)),
        "warning_count": int(manifest.get("warning_count", 0)),
        "error_count": error_count,
        "manifest": manifest
        if evidence_packet is None
        else {"collection": manifest, "evidencePacket": evidence_packet},
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
    parser.add_argument(
        "--project-ref", default=os.environ.get("SUPABASE_PROJECT_REF", SUPABASE_PROJECT_REF)
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export-sources")
    export_parser.add_argument("--output", type=Path, required=True)

    source_list_parser = subparsers.add_parser("list-sources")
    source_list_parser.add_argument("--all", action="store_true")

    source_upsert_parser = subparsers.add_parser("upsert-source")
    source_upsert_parser.add_argument("--input", type=Path, required=True)

    source_state_parser = subparsers.add_parser("set-source-state")
    source_state_parser.add_argument("--slug", required=True)
    source_state_parser.add_argument("--state", choices=("enabled", "paused"), required=True)

    push_parser = subparsers.add_parser("push-digest")
    push_parser.add_argument("--input", type=Path, required=True)
    push_parser.add_argument("--evidence-packet", type=Path, required=True)
    push_parser.add_argument("--manifest", type=Path)
    push_parser.add_argument("--publish", action="store_true")

    digest_list_parser = subparsers.add_parser("list-digests")
    digest_list_parser.add_argument(
        "--status", choices=("all", "draft", "published"), default="all"
    )

    digest_state_parser = subparsers.add_parser("set-digest-state")
    digest_state_parser.add_argument("--slug", required=True)
    digest_state_parser.add_argument("--state", choices=("draft", "published"), required=True)

    validate_parser = subparsers.add_parser("validate-digest")
    validate_parser.add_argument("--input", type=Path, required=True)
    validate_parser.add_argument("--evidence-packet", type=Path, required=True)

    packet_parser = subparsers.add_parser("validate-evidence-packet")
    packet_parser.add_argument("--input", type=Path, required=True)

    run_parser = subparsers.add_parser("record-run")
    run_parser.add_argument("--manifest", type=Path, required=True)
    run_parser.add_argument("--digest-id")
    run_parser.add_argument(
        "--outcome", choices=("collection", "no-digest"), default="collection"
    )
    run_parser.add_argument("--reason", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-digest":
            document = json.loads(args.input.read_text(encoding="utf-8"))
            evidence_packet = json.loads(
                args.evidence_packet.read_text(encoding="utf-8")
            )
            digest_to_row(
                document,
                publish=False,
                evidence_packet=evidence_packet,
            )
            print(json.dumps({"status": "valid", "slug": document["slug"]}))
            return 0

        if args.command == "validate-evidence-packet":
            packet = json.loads(args.input.read_text(encoding="utf-8"))
            validate_evidence_packet(packet)
            print(
                json.dumps(
                    {
                        "status": "valid",
                        "signal_count": len(packet["signals"]),
                        "mellanni_query_count": len(packet["mellanniQueries"]),
                    }
                )
            )
            return 0

        base_url, key = credentials(args.env_file, project_ref=args.project_ref)
        if args.command == "export-sources":
            config = source_rows_to_config(fetch_enabled_sources(base_url, key))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(config, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(json.dumps({"source_count": len(config["sources"]), "output": str(args.output)}))
            return 0

        if args.command == "list-sources":
            rows = list_sources(base_url, key, include_disabled=args.all)
            print(json.dumps({"source_count": len(rows), "sources": rows}, ensure_ascii=False))
            return 0

        if args.command == "upsert-source":
            document = json.loads(args.input.read_text(encoding="utf-8"))
            source = upsert_source(base_url, key, document)
            print(json.dumps({"slug": source.get("slug"), "enabled": source.get("enabled")}))
            return 0

        if args.command == "set-source-state":
            source = set_source_state(
                base_url, key, args.slug, enabled=args.state == "enabled"
            )
            print(json.dumps({"slug": source.get("slug"), "enabled": source.get("enabled")}))
            return 0

        if args.command == "list-digests":
            rows = list_digests(base_url, key, status=args.status)
            print(json.dumps({"digest_count": len(rows), "digests": rows}, ensure_ascii=False))
            return 0

        if args.command == "set-digest-state":
            digest = set_digest_state(base_url, key, args.slug, status=args.state)
            print(json.dumps({"slug": digest.get("slug"), "status": digest.get("status")}))
            return 0

        if args.command == "record-run":
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            record_run(
                base_url,
                key,
                manifest,
                digest_id=args.digest_id,
                outcome=args.outcome,
                reason=args.reason,
            )
            run_status = (
                "succeeded"
                if int(manifest.get("exit_code", 1)) == 0
                and args.outcome != "no-digest"
                else "failed"
            )
            print(
                json.dumps(
                    {
                        "status": "recorded",
                        "run_status": run_status,
                        "outcome": args.outcome,
                        "reason": args.reason.strip(),
                    }
                )
            )
            return 0

        document = json.loads(args.input.read_text(encoding="utf-8"))
        evidence_packet = json.loads(
            args.evidence_packet.read_text(encoding="utf-8")
        )
        digest = push_digest(
            base_url,
            key,
            document,
            publish=args.publish,
            evidence_packet=evidence_packet,
        )
        if args.manifest:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            record_run(
                base_url,
                key,
                manifest,
                digest_id=digest.get("id"),
                evidence_packet=evidence_packet,
                outcome="digest",
            )
        print(json.dumps({"digest_id": digest.get("id"), "slug": digest.get("slug"), "status": digest.get("status")}))
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
