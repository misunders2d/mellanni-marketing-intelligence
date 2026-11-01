from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import UUID

from .collector import is_youtube_url
from .editorial import (
    private_digest_body,
    public_digest_body,
    ValidationErrors,
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
    "id,slug,published_on,status,title,summary,body,content_sha256,updated_at"
)
MEMBER_ADMIN_FIELDS = "user_id,email,role,active,updated_at"


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


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def digest_content_sha256(row: dict[str, Any]) -> str:
    required = (
        "slug",
        "published_on",
        "title",
        "summary",
        "body",
        "private_body",
    )
    missing = [field for field in required if field not in row]
    if missing:
        raise ValueError(
            "cannot fingerprint digest with missing fields: " + ", ".join(missing)
        )
    return _canonical_sha256({field: row[field] for field in required})


def digest_to_row(
    document: dict[str, Any],
    *,
    publish: bool,
    evidence_packet: dict[str, Any],
) -> dict[str, Any]:
    validate_digest(document, evidence_packet)
    row = {
        "slug": document["slug"],
        "published_on": document["date"],
        "status": "published" if publish else "draft",
        "title": document["title"],
        "summary": document["summary"],
        "body": public_digest_body(document),
        "private_body": private_digest_body(document),
        "published_at": datetime.now(timezone.utc).isoformat() if publish else None,
    }
    row["content_sha256"] = digest_content_sha256(row)
    return row


def push_digest(
    base_url: str,
    key: str,
    document: dict[str, Any],
    *,
    publish: bool,
    evidence_packet: dict[str, Any],
    replace_published: bool = False,
) -> dict[str, Any]:
    row = digest_to_row(
        document,
        publish=publish,
        evidence_packet=evidence_packet,
    )
    existing = _request_json(
        base_url,
        key,
        "digests?select=id,status&slug=eq." + quote(row["slug"], safe=""),
    )
    if not isinstance(existing, list):
        raise RuntimeError("Supabase digest slug lookup did not return a list")
    if not replace_published and any(
        isinstance(current, dict) and current.get("status") == "published"
        for current in existing
    ):
        raise ValueError(
            f"refusing digest write: slug {row['slug']!r} is currently published and "
            "the write would return it to draft. Use a new slug, or pass "
            "--replace-published after confirming the published digest should be replaced."
        )
    payload = {f"p_{field}": value for field, value in row.items()}
    rows = _request_json(
        base_url,
        key,
        "rpc/upsert_digest_with_private_body",
        method="POST",
        payload=payload,
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
    if not rows:
        return rows

    private_rows = _request_json(
        base_url,
        key,
        "digest_private_bodies?select=digest_id,private_body",
    )
    if not isinstance(private_rows, list):
        raise RuntimeError("Supabase private digest bodies response was not a list")
    private_by_digest = {
        row["digest_id"]: row["private_body"]
        for row in private_rows
        if isinstance(row, dict) and "digest_id" in row and "private_body" in row
    }
    missing_private_bodies = {
        row.get("id")
        for row in rows
        if isinstance(row, dict) and row.get("id") not in private_by_digest
    }
    if missing_private_bodies:
        raise RuntimeError(
            "Supabase returned digests without matching private body rows"
        )
    for row in rows:
        if isinstance(row, dict):
            row["private_body"] = private_by_digest[row["id"]]
    return rows


def set_digest_state(base_url: str, key: str, slug: str, *, status: str) -> dict[str, Any]:
    if not SLUG_PATTERN.fullmatch(slug):
        raise ValueError("digest slug must contain lowercase letters, numbers, and hyphens only")
    if status not in {"draft", "published"}:
        raise ValueError("digest status must be draft or published")
    if status == "published":
        rows = _request_json(
            base_url,
            key,
            "rpc/publish_digest_with_verified_run",
            method="POST",
            payload={"p_slug": slug},
        )
    else:
        rows = _request_json(
            base_url,
            key,
            "digests?slug=eq." + quote(slug, safe=""),
            method="PATCH",
            payload={"status": "draft", "published_at": None},
            prefer="return=representation",
        )
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError(f"digest {slug!r} was not found")
    return rows[0]


def list_members(base_url: str, key: str, *, include_inactive: bool) -> list[dict[str, Any]]:
    path = "members?select=" + MEMBER_ADMIN_FIELDS
    if not include_inactive:
        path += "&active=eq.true"
    path += "&order=email.asc"
    rows = _request_json(base_url, key, path)
    if not isinstance(rows, list):
        raise RuntimeError("Supabase members response was not a list")
    return rows


def set_member_state(
    base_url: str,
    key: str,
    user_id: str,
    *,
    active: bool,
) -> dict[str, Any]:
    try:
        normalized_user_id = str(UUID(user_id))
    except ValueError as exc:
        raise ValueError("member user ID must be a UUID") from exc

    rows = _request_json(
        base_url,
        key,
        "members?user_id=eq." + quote(normalized_user_id, safe=""),
        method="PATCH",
        payload={"active": active},
        prefer="return=representation",
    )
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError(f"member {normalized_user_id!r} was not found")
    return rows[0]


def record_run(
    base_url: str,
    key: str,
    manifest: dict[str, Any],
    *,
    digest_id: str | None,
    evidence_packet: dict[str, Any] | None = None,
    run_proof: dict[str, Any] | None = None,
    outcome: str = "collection",
    reason: str = "",
) -> None:
    if outcome not in {"collection", "digest", "no-digest"}:
        raise ValueError("run outcome must be collection, digest, or no-digest")
    if outcome == "no-digest" and not reason.strip():
        raise ValueError("no-digest run outcome requires a reason")
    if outcome == "digest" and run_proof is None:
        raise ValueError("digest run outcome requires compact verified run proof")
    if outcome != "digest" and run_proof is not None:
        raise ValueError("compact run proof is only valid for a digest run outcome")
    statuses = manifest.get("source_statuses") or []
    error_count = sum(len(status.get("errors") or []) for status in statuses)
    collection_succeeded = int(manifest.get("exit_code", 1)) == 0
    run_status = "succeeded" if collection_succeeded and outcome != "no-digest" else "failed"
    if run_proof is not None:
        if evidence_packet is not None:
            raise ValueError("compact run proof cannot include a raw evidence packet")
        validate_run_proof(run_proof)
        stored_manifest: dict[str, Any] = {"runProof": run_proof}
    else:
        stored_manifest = (
            manifest
            if evidence_packet is None
            else {"collection": manifest, "evidencePacket": evidence_packet}
        )
    run_identity = (
        _canonical_sha256(run_proof)
        if run_proof is not None
        else _canonical_sha256(
            {
                "run_id": manifest.get("run_id"),
                "outcome": outcome,
                "reason": reason.strip(),
            }
        )
    )
    payload = {
        "run_key": f"{outcome}:{run_identity}",
        "status": run_status,
        "outcome": outcome,
        "outcome_reason": reason.strip(),
        "started_at": manifest.get("started_at") or datetime.now(timezone.utc).isoformat(),
        "finished_at": manifest.get("finished_at") or datetime.now(timezone.utc).isoformat(),
        "source_count": int(manifest.get("source_count", 0)),
        "item_count": int(manifest.get("item_count", 0)),
        "warning_count": int(manifest.get("warning_count", 0)),
        "error_count": error_count,
        "manifest": stored_manifest,
        "digest_id": digest_id,
    }
    _request_json(
        base_url,
        key,
        "runs?on_conflict=run_key",
        method="POST",
        payload=payload,
        prefer="resolution=ignore-duplicates,return=minimal",
    )


def _path_inside(root: Path, relative: str, label: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        raise ValueError(f"refusing digest write: {label} path must be relative to run directory")
    resolved = (root / path).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"refusing digest write: {label} path escapes run directory")
    return resolved


def require_digest_ready_manifest(
    manifest: dict[str, Any], manifest_path: Path | None = None
) -> None:
    if int(manifest.get("exit_code", 1)) != 0:
        raise ValueError(
            f"refusing digest write: collection failed (exit_code={manifest.get('exit_code')})"
        )
    if manifest.get("schema_version") != 3:
        raise ValueError("refusing digest write: collection manifest schema is obsolete")
    if manifest_path is None:
        raise ValueError(
            "refusing digest write: manifest path is required to verify collection evidence"
        )
    manifest_path = manifest_path.resolve()
    run_dir = manifest_path.parent
    if not manifest_path.is_file():
        raise ValueError("refusing digest write: collection manifest file is missing")
    declared_manifest_path = manifest.get("manifest_path")
    if (
        not isinstance(declared_manifest_path, str)
        or Path(declared_manifest_path).resolve() != manifest_path
    ):
        raise ValueError("refusing digest write: collection manifest path mismatch")

    items = manifest.get("items")
    statuses = manifest.get("source_statuses")
    if not isinstance(items, list) or not isinstance(statuses, list):
        raise ValueError("refusing digest write: collection items and statuses are required")
    source_count = int(manifest.get("source_count", -1))
    item_count = int(manifest.get("item_count", -1))
    source_failures = sum(
        1
        for status in statuses
        if isinstance(status, dict) and status.get("errors")
    )
    if (
        source_count != len(statuses)
        or item_count != len(items)
        or int(manifest.get("source_failures", -1)) != source_failures
        or source_failures != 0
    ):
        raise ValueError("refusing digest write: collection manifest counts are inconsistent")

    item_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("refusing digest write: invalid collection item record")
        item_id = str(item.get("item_id", ""))
        if not item_id or item_id in item_ids:
            raise ValueError("refusing digest write: collection item IDs must be unique")
        item_ids.add(item_id)
        artifact = _path_inside(
            run_dir, str(item.get("journal_path", "")), "collection artifact"
        )
        if not artifact.is_file():
            raise ValueError("refusing digest write: collection artifact is missing")
        artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if artifact_hash != item.get("artifact_sha256"):
            raise ValueError("refusing digest write: collection artifact hash mismatch")

    youtube_count = sum(
        1
        for item in manifest.get("items") or []
        if is_youtube_url(str(item.get("url", "")))
    )
    if youtube_count:
        sidecar_path = run_dir / "youtube" / "youtube-summary-manifest.json"
        try:
            summary = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"refusing digest write: invalid YouTube sidecar {sidecar_path}: {exc}"
            ) from exc
        manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        expected_items = [
            (str(item.get("item_id", "")), str(item.get("url", "")))
            for item in manifest.get("items") or []
            if is_youtube_url(str(item.get("url", "")))
        ]
        if summary.get("run_id") != manifest.get("run_id"):
            raise ValueError(
                "refusing digest write: stale YouTube sidecar run_id mismatch; rerun YouTube batch"
            )
        if summary.get("collection_manifest_sha256") != manifest_hash:
            raise ValueError(
                "refusing digest write: YouTube sidecar manifest hash mismatch; rerun YouTube batch"
            )
        if (
            summary.get("status") != "succeeded"
            or summary.get("processing") != "agentic"
            or int(summary.get("expected", -1)) != youtube_count
            or int(summary.get("succeeded", -1)) != youtube_count
            or int(summary.get("failed", -1)) != 0
            or summary.get("expected_urls") != [url for _, url in expected_items]
        ):
            raise ValueError(
                f"refusing digest write: YouTube coverage incomplete "
                f"(expected={youtube_count}, succeeded={summary.get('succeeded')}, "
                f"failed={summary.get('failed')})"
            )
        results = summary.get("results")
        if not isinstance(results, list) or len(results) != youtube_count:
            raise ValueError("refusing digest write: YouTube result records are incomplete")
        actual_items: list[tuple[str, str]] = []
        for result in sorted(results, key=lambda row: int(row.get("index", -1))):
            if not isinstance(result, dict):
                raise ValueError("refusing digest write: invalid YouTube result record")
            actual_items.append((str(result.get("item_id", "")), str(result.get("url", ""))))
            evidence = result.get("processing_evidence") or {}
            if (
                result.get("processing") != "agentic"
                or not isinstance(result.get("model"), str)
                or not result["model"].strip()
                or evidence.get("processingCall") is not True
                or evidence.get("processingResult") is not True
                or evidence.get("agenticProcessingUsed") is not True
            ):
                raise ValueError("refusing digest write: YouTube agentic evidence is incomplete")
            artifact = _path_inside(run_dir, str(result.get("artifact_path", "")), "artifact")
            details = _path_inside(run_dir, str(result.get("details_path", "")), "details")
            if not artifact.is_file() or not details.is_file():
                raise ValueError("refusing digest write: YouTube artifact is missing")
            artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
            if artifact_hash != result.get("artifact_sha256"):
                raise ValueError("refusing digest write: YouTube artifact hash mismatch")
            details_hash = hashlib.sha256(details.read_bytes()).hexdigest()
            if details_hash != result.get("details_sha256"):
                raise ValueError("refusing digest write: YouTube details hash mismatch")
        if actual_items != expected_items:
            raise ValueError("refusing digest write: YouTube result coverage does not match manifest")


def evidence_packet_manifest_errors(
    evidence_packet: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path,
) -> list[str]:
    errors: list[str] = []
    manifest_path = manifest_path.resolve()
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if evidence_packet.get("collectionManifestSha256") != manifest_hash:
        errors.append(
            "refusing digest write: evidence packet collection manifest hash mismatch"
        )

    packet_sources = evidence_packet.get("sources")
    item_reviews = evidence_packet.get("itemReviews")
    manifest_items = manifest.get("items")
    if not all(
        isinstance(value, list)
        for value in (packet_sources, item_reviews, manifest_items)
    ):
        errors.append(
            "refusing digest write: packet sources, item reviews, and manifest items are required"
        )
        return errors

    manifest_by_id = {
        str(item.get("item_id", "")): str(item.get("url", ""))
        for item in manifest_items
        if isinstance(item, dict)
    }
    review_ids = [
        str(review.get("itemId", ""))
        for review in item_reviews
        if isinstance(review, dict)
    ]
    if (
        len(manifest_by_id) != len(manifest_items)
        or len(review_ids) != len(item_reviews)
        or len(set(review_ids)) != len(review_ids)
        or set(review_ids) != set(manifest_by_id)
    ):
        unreviewed = sorted(set(manifest_by_id) - set(review_ids))
        unknown = sorted(set(review_ids) - set(manifest_by_id))
        errors.append(
            "refusing digest write: item reviews must cover every collection manifest item exactly once"
            + (f"; unreviewed: {', '.join(unreviewed[:10])}" if unreviewed else "")
            + (f"; not in manifest: {', '.join(unknown[:10])}" if unknown else "")
        )
    for review in item_reviews:
        if not isinstance(review, dict) or "url" not in review:
            continue
        expected_url = manifest_by_id.get(str(review.get("itemId", "")))
        if expected_url is not None and review["url"] != expected_url:
            errors.append(
                f"refusing digest write: item review {review.get('itemId')!r} url differs from manifest"
            )

    packet_set = {
        (str(source.get("id", "")), str(source.get("url", "")))
        for source in packet_sources
        if isinstance(source, dict)
    }
    manifest_set = set(manifest_by_id.items())
    if len(packet_set) != len(packet_sources) or not packet_set.issubset(manifest_set):
        errors.append(
            "refusing digest write: evidence packet source URL/ID set does not match collection manifest items"
        )
    return errors


def require_evidence_packet_bound_to_manifest(
    evidence_packet: dict[str, Any],
    manifest: dict[str, Any],
    manifest_path: Path,
) -> None:
    validate_evidence_packet(evidence_packet)
    errors = evidence_packet_manifest_errors(evidence_packet, manifest, manifest_path)
    if errors:
        raise ValidationErrors(errors)


def require_prior_digest_findings_bound(
    evidence_packet: dict[str, Any], prior_digests: list[dict[str, Any]]
) -> None:
    available: dict[tuple[str, str], str] = {}
    for digest in prior_digests:
        slug = str(digest.get("slug", ""))
        body = digest.get("body")
        if not slug or not isinstance(body, dict):
            continue
        for finding in [*(body.get("actions") or []), *(body.get("signals") or [])]:
            if isinstance(finding, dict):
                finding_id = str(finding.get("id", ""))
                title = str(finding.get("title", ""))
                if finding_id and title:
                    available[(slug, finding_id)] = title

    references = evidence_packet.get("priorDigestFindings")
    if not isinstance(references, list):
        raise ValueError("evidence packet prior digest findings are required")
    seen: set[tuple[str, str]] = set()
    for reference in references:
        if not isinstance(reference, dict):
            raise ValueError("evidence packet prior digest finding is invalid")
        key = (str(reference.get("digestSlug", "")), str(reference.get("findingId", "")))
        if key in seen:
            raise ValueError("evidence packet prior digest findings must be unique")
        seen.add(key)
        if available.get(key) != reference.get("title"):
            raise ValueError(
                "evidence packet prior digest finding is absent from the captured published snapshot"
            )


def build_collection_proof(
    manifest: dict[str, Any], manifest_path: Path
) -> dict[str, Any]:
    require_digest_ready_manifest(manifest, manifest_path)
    manifest_path = manifest_path.resolve()
    sidecar_path = manifest_path.parent / "youtube" / "youtube-summary-manifest.json"
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"refusing digest write: invalid YouTube sidecar {sidecar_path}: {exc}"
        ) from exc
    youtube_count = sum(
        1
        for item in manifest.get("items") or []
        if is_youtube_url(str(item.get("url", "")))
    )
    expected_urls = [
        str(item.get("url", ""))
        for item in manifest.get("items") or []
        if is_youtube_url(str(item.get("url", "")))
    ]
    expected_status = "succeeded" if youtube_count else "not-required"
    if (
        sidecar.get("run_id") != manifest.get("run_id")
        or sidecar.get("collection_manifest_sha256")
        != hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        or sidecar.get("status") != expected_status
        or sidecar.get("processing") != "agentic"
        or int(sidecar.get("expected", -1)) != youtube_count
        or int(sidecar.get("succeeded", -1)) != youtube_count
        or int(sidecar.get("failed", -1)) != 0
        or sidecar.get("expected_urls") != expected_urls
    ):
        raise ValueError(
            "refusing digest write: YouTube sidecar is not fully bound and verified"
        )
    return {
        "run_id": manifest.get("run_id"),
        "collection_manifest_sha256": hashlib.sha256(
            manifest_path.read_bytes()
        ).hexdigest(),
        "youtube_sidecar_sha256": hashlib.sha256(sidecar_path.read_bytes()).hexdigest(),
        "counts": {
            "source_count": int(manifest.get("source_count", 0)),
            "item_count": int(
                manifest.get("item_count", len(manifest.get("items") or []))
            ),
            "youtube_count": youtube_count,
            "youtube_succeeded": int(sidecar.get("succeeded", 0)),
        },
        "agentic_verified": youtube_count == 0
        or (
            sidecar.get("processing") == "agentic"
            and int(sidecar.get("succeeded", -1)) == youtube_count
            and int(sidecar.get("failed", -1)) == 0
        ),
    }


def build_run_proof(
    manifest: dict[str, Any],
    manifest_path: Path,
    *,
    digest_document: dict[str, Any],
    evidence_packet: dict[str, Any],
) -> dict[str, Any]:
    require_evidence_packet_bound_to_manifest(
        evidence_packet, manifest, manifest_path
    )
    row = digest_to_row(
        digest_document,
        publish=False,
        evidence_packet=evidence_packet,
    )
    proof = {
        "schema_version": 2,
        **build_collection_proof(manifest, manifest_path),
        "evidence_packet_sha256": _canonical_sha256(evidence_packet),
        "digest_content_sha256": row["content_sha256"],
    }
    validate_run_proof(proof)
    return proof


def validate_run_proof(proof: dict[str, Any]) -> None:
    required_fields = {
        "schema_version",
        "run_id",
        "collection_manifest_sha256",
        "youtube_sidecar_sha256",
        "evidence_packet_sha256",
        "digest_content_sha256",
        "counts",
        "agentic_verified",
    }
    required_counts = {
        "source_count",
        "item_count",
        "youtube_count",
        "youtube_succeeded",
    }
    counts = proof.get("counts")
    hashes = (
        proof.get("collection_manifest_sha256"),
        proof.get("youtube_sidecar_sha256"),
        proof.get("evidence_packet_sha256"),
        proof.get("digest_content_sha256"),
    )
    if proof.get("schema_version") != 2 or set(proof) != required_fields:
        raise ValueError("refusing publication: linked run proof is missing or obsolete")
    if not isinstance(proof.get("run_id"), str) or not proof["run_id"].strip():
        raise ValueError("refusing publication: linked run proof has no run ID")
    if not all(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
        for value in hashes
    ):
        raise ValueError("refusing publication: linked run proof hashes are invalid")
    if (
        not isinstance(counts, dict)
        or set(counts) != required_counts
        or any(
            isinstance(counts.get(name), bool)
            or not isinstance(counts.get(name), int)
            or counts[name] < 0
            for name in required_counts
        )
        or counts["youtube_count"] > counts["item_count"]
    ):
        raise ValueError("refusing publication: linked run proof counts are invalid")
    if (
        counts["youtube_count"] != counts["youtube_succeeded"]
        or proof.get("agentic_verified") is not True
    ):
        raise ValueError("refusing publication: linked run proof is not agentic-verified")


def require_digest_readback(
    rows: list[dict[str, Any]],
    *,
    digest_id: str,
    slug: str,
    status: str,
    expected_content_sha256: str,
) -> dict[str, Any]:
    matches = [row for row in rows if row.get("slug") == slug]
    if len(matches) != 1:
        raise RuntimeError("draft readback did not return exactly one matching digest")
    row = matches[0]
    if row.get("id") != digest_id or row.get("status") != status:
        raise RuntimeError("draft readback did not match written digest identity or status")
    actual_hash = digest_content_sha256(row)
    if (
        row.get("content_sha256") != expected_content_sha256
        or actual_hash != expected_content_sha256
    ):
        raise RuntimeError("draft readback content did not match validated digest")
    return row


def require_linked_digest_run(
    base_url: str,
    key: str,
    slug: str,
    expected_collection_proof: dict[str, Any] | None = None,
) -> None:
    digests = _request_json(
        base_url,
        key,
        "digests?select=id,slug,published_on,title,summary,body,content_sha256&slug=eq."
        + quote(slug, safe=""),
    )
    if not isinstance(digests, list) or len(digests) != 1:
        raise ValueError(f"digest {slug!r} was not found for publication")
    digest = digests[0]
    digest_id = str(digest.get("id", ""))
    private_rows = _request_json(
        base_url,
        key,
        "digest_private_bodies?select=digest_id,private_body&digest_id=eq."
        + quote(digest_id, safe=""),
    )
    if not isinstance(private_rows, list) or len(private_rows) != 1:
        raise ValueError(f"digest {slug!r} has no exact private body for publication")
    digest["private_body"] = private_rows[0].get("private_body")
    current_content_sha256 = digest_content_sha256(digest)
    if digest.get("content_sha256") != current_content_sha256:
        raise ValueError(
            f"refusing publication: digest {slug!r} stored content hash is inconsistent"
        )

    runs = _request_json(
        base_url,
        key,
        "runs?select=digest_id,status,outcome,manifest&digest_id=eq."
        + quote(digest_id, safe="")
        + "&status=eq.succeeded&outcome=eq.digest",
    )
    for run in runs if isinstance(runs, list) else []:
        if (
            str(run.get("digest_id", "")) != digest_id
            or run.get("status") != "succeeded"
            or run.get("outcome") != "digest"
        ):
            continue
        stored = run.get("manifest") or {}
        proof = stored.get("runProof") if isinstance(stored, dict) else None
        if not isinstance(proof, dict):
            continue
        try:
            validate_run_proof(proof)
        except ValueError:
            continue
        collection_matches = expected_collection_proof is None or all(
            proof.get(field) == value
            for field, value in expected_collection_proof.items()
        )
        if (
            collection_matches
            and proof["digest_content_sha256"] == current_content_sha256
        ):
            return
    raise ValueError(
        f"refusing publication: digest {slug!r} has no linked successful proof for its current content"
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
    push_parser.add_argument("--manifest", type=Path, required=True)
    push_parser.add_argument("--publish", action="store_true")
    push_parser.add_argument(
        "--replace-published",
        action="store_true",
        help="allow overwriting a currently published digest with the same slug",
    )

    digest_list_parser = subparsers.add_parser("list-digests")
    digest_list_parser.add_argument(
        "--status", choices=("all", "draft", "published"), default="all"
    )

    digest_state_parser = subparsers.add_parser("set-digest-state")
    digest_state_parser.add_argument("--slug", required=True)
    digest_state_parser.add_argument("--state", choices=("draft", "published"), required=True)
    digest_state_parser.add_argument("--manifest", type=Path)

    member_list_parser = subparsers.add_parser("list-members")
    member_list_parser.add_argument("--all", action="store_true")

    member_state_parser = subparsers.add_parser("set-member-state")
    member_state_parser.add_argument("--user-id", required=True)
    member_state_parser.add_argument("--state", choices=("active", "inactive"), required=True)

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
            if args.state == "published":
                expected_collection_proof = None
                if args.manifest is not None:
                    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
                    expected_collection_proof = build_collection_proof(
                        manifest, args.manifest
                    )
                require_linked_digest_run(
                    base_url,
                    key,
                    args.slug,
                    expected_collection_proof,
                )
            digest = set_digest_state(base_url, key, args.slug, status=args.state)
            print(json.dumps({"slug": digest.get("slug"), "status": digest.get("status")}))
            return 0

        if args.command == "list-members":
            rows = list_members(base_url, key, include_inactive=args.all)
            print(json.dumps({"member_count": len(rows), "members": rows}, ensure_ascii=False))
            return 0

        if args.command == "set-member-state":
            member = set_member_state(
                base_url,
                key,
                args.user_id,
                active=args.state == "active",
            )
            print(
                json.dumps(
                    {
                        "user_id": member.get("user_id"),
                        "email": member.get("email"),
                        "active": member.get("active"),
                    }
                )
            )
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

        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        require_digest_ready_manifest(manifest, args.manifest)
        document = json.loads(args.input.read_text(encoding="utf-8"))
        evidence_packet = json.loads(
            args.evidence_packet.read_text(encoding="utf-8")
        )
        expected_row = digest_to_row(
            document,
            publish=False,
            evidence_packet=evidence_packet,
        )
        require_evidence_packet_bound_to_manifest(
            evidence_packet, manifest, args.manifest
        )
        require_prior_digest_findings_bound(
            evidence_packet,
            list_digests(base_url, key, status="published"),
        )
        run_proof = build_run_proof(
            manifest,
            args.manifest,
            digest_document=document,
            evidence_packet=evidence_packet,
        )
        digest = push_digest(
            base_url,
            key,
            document,
            publish=False,
            evidence_packet=evidence_packet,
            replace_published=args.replace_published,
        )
        if digest.get("status") != "draft":
            raise RuntimeError("digest write did not return draft status")
        require_digest_readback(
            list_digests(base_url, key, status="draft"),
            digest_id=str(digest.get("id", "")),
            slug=document["slug"],
            status="draft",
            expected_content_sha256=expected_row["content_sha256"],
        )
        record_run(
            base_url,
            key,
            manifest,
            digest_id=digest.get("id"),
            run_proof=run_proof,
            outcome="digest",
        )
        if args.publish:
            require_linked_digest_run(base_url, key, document["slug"], run_proof)
            digest = set_digest_state(
                base_url, key, document["slug"], status="published"
            )
        print(json.dumps({"digest_id": digest.get("id"), "slug": digest.get("slug"), "status": digest.get("status")}))
        return 0
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
