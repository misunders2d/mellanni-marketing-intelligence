from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
from typing import Any

from .pipeline import run_fetch
from .supabase_content import (
    PROJECT_ROOT,
    SUPABASE_PROJECT_REF,
    build_run_proof,
    credentials,
    digest_to_row,
    fetch_enabled_sources,
    list_digests,
    push_digest,
    record_run,
    require_digest_readback,
    require_digest_ready_manifest,
    require_evidence_packet_bound_to_manifest,
    require_prior_digest_findings_bound,
    source_rows_to_config,
)


DEFAULT_RUN_ROOT = Path(
    os.environ.get("MELLANNI_WEEKLY_RUN_ROOT", "/tmp/mellanni-marketing-weekly")
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    content = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        temporary.replace(path)
        os.chmod(path, 0o600)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _secure_tree(run_dir: Path) -> None:
    for path in [run_dir, *run_dir.rglob("*")]:
        if path.is_symlink():
            raise RuntimeError(f"refusing unsafe weekly run symlink: {path}")
        os.chmod(path, 0o700 if path.is_dir() else 0o600)


def _assert_safe_resume_tree(run_root: Path, run_dir: Path) -> None:
    for path in [run_root, run_dir, *run_dir.rglob("*")]:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise RuntimeError(f"refusing unsafe weekly resume symlink: {path}")
        if mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise RuntimeError(
                f"refusing unsafe weekly resume: group/other-writable path {path}"
            )


def _week_start() -> str:
    today = datetime.now(UTC).date()
    return (today - timedelta(days=today.weekday())).isoformat()


def _invocation(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "project_ref": args.project_ref,
        "env_file": str(args.env_file.resolve()),
        "since_days": args.since_days,
        "fetch_workers": args.fetch_workers,
        "youtube_concurrency": args.youtube_concurrency,
        "youtube_timeout_ms": args.youtube_timeout_ms,
        "youtube_batch_deadline_ms": args.youtube_batch_deadline_ms,
        "max_videos": args.max_videos,
    }


def _active_run(
    run_root: Path, *, week_start: str, invocation: dict[str, Any]
) -> tuple[Path, dict[str, Any]] | None:
    if not run_root.exists():
        return None
    for state_path in sorted(run_root.glob("*/run-state.json"), reverse=True):
        run_dir = state_path.parent
        _assert_safe_resume_tree(run_root, run_dir)
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"cannot inspect weekly run state {state_path}: {exc}") from exc
        if state.get("status") == "completed":
            continue
        if state.get("status") == "failed" and (run_dir / "run-receipt.json").is_file():
            continue
        if state.get("week_start") != week_start:
            raise RuntimeError(
                "refusing weekly resume: active run belongs to a different week "
                f"(run_id={state.get('run_id')!r}, stored={state.get('week_start')!r}, "
                f"current={week_start!r}). Recovery: review and move {run_dir} out of "
                f"{run_root}, then rerun; this runner never abandons stale runs automatically."
            )
        if state.get("invocation") != invocation:
            raise RuntimeError(
                "refusing weekly resume: active run invocation parameters differ from this "
                f"command (run_id={state.get('run_id')!r}). Recovery: rerun with original "
                f"parameters {json.dumps(state.get('invocation'), sort_keys=True)}, or review "
                f"and move {run_dir} out of {run_root}; then rerun."
            )
        _secure_tree(run_dir)
        return run_dir, state
    return None


def _new_run(
    run_root: Path, *, week_start: str, invocation: dict[str, Any]
) -> tuple[Path, dict[str, Any]]:
    run_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(run_root, 0o700)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = run_root / run_id
    run_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    state: dict[str, Any] = {
        "schema_version": 2,
        "run_id": run_id,
        "week_start": week_start,
        "invocation": invocation,
        "status": "running",
        "stage": "source_snapshot",
        "started_at": _now(),
        "updated_at": _now(),
        "paths": {
            "source_snapshot": str(run_dir / "sources.json"),
            "evidence_packet": str(run_dir / "evidence-packet.json"),
            "digest": str(run_dir / "digest.json"),
            "prior_digests": str(run_dir / "prior-digests.json"),
            "state": str(run_dir / "run-state.json"),
            "receipt": str(run_dir / "run-receipt.json"),
        },
        "stages": {},
    }
    _atomic_json(run_dir / "run-state.json", state)
    return run_dir, state


def _save_state(run_dir: Path, state: dict[str, Any], stage: str, **values: Any) -> None:
    state.update(values)
    state.pop("last_error", None)
    state["stage"] = stage
    state["updated_at"] = _now()
    state.setdefault("stages", {})[stage] = {"status": "completed", "at": _now()}
    _atomic_json(run_dir / "run-state.json", state)


def _record_resumable_error(
    run_dir: Path, state: dict[str, Any], exc: BaseException
) -> None:
    state["status"] = "running"
    state["updated_at"] = _now()
    state["last_error"] = {
        "at": _now(),
        "stage": state.get("stage"),
        "error": f"{type(exc).__name__}: {exc}"[:1000],
        "resumable": True,
    }
    _atomic_json(run_dir / "run-state.json", state)


def _write_receipt(run_dir: Path, receipt: dict[str, Any]) -> None:
    path = run_dir / "run-receipt.json"
    if path.exists():
        raise RuntimeError(f"immutable run receipt already exists: {path}")
    _atomic_json(path, receipt)


def _recover_completed_receipt(
    run_dir: Path, state: dict[str, Any]
) -> dict[str, Any] | None:
    receipt_path = run_dir / "run-receipt.json"
    if not receipt_path.exists():
        return None
    if "run_link" not in state.get("stages", {}):
        raise RuntimeError(
            "refusing weekly receipt recovery: run linkage was not recorded in state"
        )
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot recover weekly run receipt: {exc}") from exc
    if (
        receipt.get("immutable") is not True
        or receipt.get("outcome") != "draft"
        or receipt.get("run_id") != state.get("run_id")
        or receipt.get("digest", {}).get("readback_verified") is not True
    ):
        raise RuntimeError("refusing weekly receipt recovery: receipt is invalid")
    for receipt_field, path_field in (
        ("collection_manifest_sha256", "manifest"),
        ("youtube_sidecar_sha256", "youtube_sidecar"),
        ("evidence_packet_sha256", "evidence_packet"),
        ("digest_sha256", "digest"),
    ):
        path = Path(state["paths"][path_field])
        if not path.is_file() or receipt.get(receipt_field) != _sha256(path):
            raise RuntimeError(
                f"refusing weekly receipt recovery: {path_field} hash mismatch"
            )
    state.update({"status": "completed", "stage": "completed", "updated_at": _now()})
    _atomic_json(run_dir / "run-state.json", state)
    _secure_tree(run_dir)
    return receipt


def _finish_failed_run(
    run_dir: Path,
    state: dict[str, Any],
    *,
    base_url: str | None,
    key: str | None,
) -> dict[str, Any]:
    reason = str(state.get("failure_reason") or "weekly run failed")
    manifest_path_value = state.get("paths", {}).get("manifest")
    recorded = state.get("no_digest_recorded") is True
    record_error = str(state.get("record_error") or "")
    if not recorded and manifest_path_value and base_url and key:
        try:
            manifest = json.loads(Path(manifest_path_value).read_text(encoding="utf-8"))
            record_run(
                base_url,
                key,
                manifest,
                digest_id=None,
                outcome="no-digest",
                reason=reason[:1000],
            )
            recorded = True
            record_error = ""
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            record_error = f"{type(exc).__name__}: {exc}"[:1000]
    state.update(
        {
            "status": "failed",
            "stage": "failed",
            "updated_at": _now(),
            "failure_reason": reason,
            "no_digest_recorded": recorded,
            "record_error": record_error,
        }
    )
    _atomic_json(run_dir / "run-state.json", state)
    receipt = {
        "schema_version": 1,
        "immutable": True,
        "run_id": state["run_id"],
        "outcome": "no-digest",
        "reason": reason,
        "no_digest_recorded": recorded,
        "record_error": record_error,
        "finished_at": _now(),
        "stages": state.get("stages", {}),
    }
    if manifest_path_value and Path(manifest_path_value).is_file():
        receipt["collection_manifest_sha256"] = _sha256(Path(manifest_path_value))
    _write_receipt(run_dir, receipt)
    _secure_tree(run_dir)
    return receipt


def _fail(
    run_dir: Path,
    state: dict[str, Any],
    reason: str,
    *,
    base_url: str | None = None,
    key: str | None = None,
) -> None:
    state.update(
        {
            "status": "failed",
            "stage": "failed",
            "updated_at": _now(),
            "failure_reason": reason,
            "no_digest_recorded": False,
            "record_error": "",
        }
    )
    _atomic_json(run_dir / "run-state.json", state)
    _finish_failed_run(
        run_dir,
        state,
        base_url=base_url,
        key=key,
    )


def _run_youtube(
    manifest_path: Path,
    *,
    concurrency: int,
    timeout_ms: int,
    batch_deadline_ms: int,
    max_videos: int,
) -> dict[str, Any]:
    command = [
        "node",
        "--env-file-if-exists=.env",
        str(PROJECT_ROOT / "scripts" / "youtube-summary.mjs"),
        "--manifest",
        str(manifest_path),
        "--processing",
        "agentic",
        "--concurrency",
        str(concurrency),
        "--timeout-ms",
        str(timeout_ms),
        "--batch-deadline-ms",
        str(batch_deadline_ms),
        "--max-items",
        str(max_videos),
    ]
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=(batch_deadline_ms / 1000) + 30,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown error"
        raise RuntimeError(f"YouTube batch failed with exit {result.returncode}: {detail}")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("YouTube batch returned invalid JSON") from exc
    return value


def run_weekly(args: argparse.Namespace) -> dict[str, Any]:
    run_root = args.run_root.resolve()
    week_start = _week_start()
    invocation = _invocation(args)
    active = _active_run(run_root, week_start=week_start, invocation=invocation)
    run_dir, state = (
        active
        if active
        else _new_run(run_root, week_start=week_start, invocation=invocation)
    )
    base_url: str | None = None
    key: str | None = None
    try:
        recovered_receipt = _recover_completed_receipt(run_dir, state)
        if recovered_receipt is not None:
            return recovered_receipt
        if state.get("status") == "failed":
            try:
                base_url, key = credentials(args.env_file, project_ref=args.project_ref)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError):
                base_url = key = None
            return _finish_failed_run(
                run_dir,
                state,
                base_url=base_url,
                key=key,
            )
        paths = state["paths"]
        if args.fail_reason:
            try:
                base_url, key = credentials(args.env_file, project_ref=args.project_ref)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError):
                base_url = key = None
            _fail(run_dir, state, args.fail_reason, base_url=base_url, key=key)
            return json.loads((run_dir / "run-receipt.json").read_text(encoding="utf-8"))

        base_url, key = credentials(args.env_file, project_ref=args.project_ref)
        if "source_snapshot" not in state["stages"]:
            config = source_rows_to_config(fetch_enabled_sources(base_url, key))
            _atomic_json(Path(paths["source_snapshot"]), config)
            _save_state(
                run_dir,
                state,
                "source_snapshot",
                source_count=len(config["sources"]),
            )

        if "collection" not in state["stages"]:
            manifest = run_fetch(
                config_path=Path(paths["source_snapshot"]),
                journal_root=run_dir / "journal",
                since_days=args.since_days,
                fetch_workers=args.fetch_workers,
            )
            manifest_path = Path(str(manifest["manifest_path"]))
            state["paths"]["manifest"] = str(manifest_path)
            _secure_tree(run_dir)
            _save_state(
                run_dir,
                state,
                "collection",
                item_count=int(manifest["item_count"]),
                source_failures=int(manifest["source_failures"]),
            )
            if int(manifest["exit_code"]) != 0:
                _fail(
                    run_dir,
                    state,
                    f"collection failed with {manifest['source_failures']} fatal source error(s)",
                    base_url=base_url,
                    key=key,
                )
                return json.loads((run_dir / "run-receipt.json").read_text(encoding="utf-8"))

        manifest_path = Path(state["paths"]["manifest"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if int(manifest.get("exit_code", 2)) != 0 or int(
            manifest.get("source_failures", 1)
        ) != 0:
            _fail(
                run_dir,
                state,
                f"collection failed with {manifest.get('source_failures', 'unknown')} fatal source error(s)",
                base_url=base_url,
                key=key,
            )
            return json.loads(
                (run_dir / "run-receipt.json").read_text(encoding="utf-8")
            )
        if "youtube" not in state["stages"]:
            youtube = _run_youtube(
                manifest_path,
                concurrency=args.youtube_concurrency,
                timeout_ms=args.youtube_timeout_ms,
                batch_deadline_ms=args.youtube_batch_deadline_ms,
                max_videos=args.max_videos,
            )
            _secure_tree(run_dir)
            try:
                require_digest_ready_manifest(manifest, manifest_path)
            except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
                _fail(
                    run_dir,
                    state,
                    f"fatal YouTube evidence invariant: {type(exc).__name__}: {exc}"[:1000],
                    base_url=base_url,
                    key=key,
                )
                return json.loads(
                    (run_dir / "run-receipt.json").read_text(encoding="utf-8")
                )
            state["paths"]["youtube_sidecar"] = str(
                manifest_path.parent / "youtube" / "youtube-summary-manifest.json"
            )
            _save_state(run_dir, state, "youtube", youtube=youtube)

        if "prior_digests" not in state["stages"]:
            prior = list_digests(base_url, key, status="published")
            _atomic_json(Path(paths["prior_digests"]), {"digests": prior})
            _save_state(run_dir, state, "prior_digests", prior_digest_count=len(prior))

        evidence_path = Path(paths["evidence_packet"])
        digest_path = Path(paths["digest"])
        if not evidence_path.is_file() or not digest_path.is_file():
            state.update({"status": "awaiting_synthesis", "stage": "awaiting_synthesis", "updated_at": _now()})
            _atomic_json(run_dir / "run-state.json", state)
            return {
                "status": "awaiting_synthesis",
                "run_id": state["run_id"],
                "run_dir": str(run_dir),
                "manifest": str(manifest_path),
                "collection_manifest_sha256": _sha256(manifest_path),
                "youtube_sidecar": state["paths"]["youtube_sidecar"],
                "prior_digests": paths["prior_digests"],
                "write_evidence_packet": str(evidence_path),
                "write_digest": str(digest_path),
                "resume_command": "UV_CACHE_DIR=/tmp/uv-cache uv run mellanni-weekly",
            }

        evidence_packet = json.loads(evidence_path.read_text(encoding="utf-8"))
        digest_document = json.loads(digest_path.read_text(encoding="utf-8"))
        try:
            require_digest_ready_manifest(manifest, manifest_path)
            require_evidence_packet_bound_to_manifest(
                evidence_packet, manifest, manifest_path
            )
            prior_snapshot = json.loads(
                Path(paths["prior_digests"]).read_text(encoding="utf-8")
            )
            require_prior_digest_findings_bound(
                evidence_packet, prior_snapshot.get("digests") or []
            )
            expected_row = digest_to_row(
                digest_document,
                publish=False,
                evidence_packet=evidence_packet,
            )
            run_proof = build_run_proof(
                manifest,
                manifest_path,
                digest_document=digest_document,
                evidence_packet=evidence_packet,
            )
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            _fail(
                run_dir,
                state,
                f"fatal digest evidence invariant: {type(exc).__name__}: {exc}"[:1000],
                base_url=base_url,
                key=key,
            )
            return json.loads(
                (run_dir / "run-receipt.json").read_text(encoding="utf-8")
            )
        _save_state(run_dir, state, "validation")

        if "draft_write" not in state["stages"]:
            digest = push_digest(
                base_url,
                key,
                digest_document,
                publish=False,
                evidence_packet=evidence_packet,
            )
            if digest.get("status") != "draft":
                raise RuntimeError("digest write did not return draft status")
            _save_state(run_dir, state, "draft_write", digest_id=digest.get("id"))
        digest = {
            "id": state.get("digest_id"),
            "slug": digest_document["slug"],
            "status": "draft",
        }

        if "readback" not in state["stages"]:
            require_digest_readback(
                list_digests(base_url, key, status="draft"),
                digest_id=str(digest.get("id", "")),
                slug=digest_document["slug"],
                status="draft",
                expected_content_sha256=expected_row["content_sha256"],
            )
            _save_state(run_dir, state, "readback")
        if "run_link" not in state["stages"]:
            record_run(
                base_url,
                key,
                manifest,
                digest_id=digest.get("id"),
                run_proof=run_proof,
                outcome="digest",
            )
            _save_state(run_dir, state, "run_link")

        receipt = {
            "schema_version": 1,
            "immutable": True,
            "run_id": state["run_id"],
            "outcome": "draft",
            "finished_at": _now(),
            "source_count": state["source_count"],
            "item_count": state["item_count"],
            "collection_manifest_sha256": _sha256(manifest_path),
            "youtube_sidecar_sha256": _sha256(Path(state["paths"]["youtube_sidecar"])),
            "evidence_packet_sha256": _sha256(evidence_path),
            "digest_sha256": _sha256(digest_path),
            "run_proof": run_proof,
            "digest": {
                "id": digest.get("id"),
                "slug": digest.get("slug"),
                "status": digest.get("status"),
                "readback_verified": True,
            },
            "stages": state["stages"],
        }
        _write_receipt(run_dir, receipt)
        state.update({"status": "completed", "stage": "completed", "updated_at": _now()})
        _atomic_json(run_dir / "run-state.json", state)
        _secure_tree(run_dir)
        return receipt
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        if state.get("status") not in {"failed", "completed"}:
            _record_resumable_error(run_dir, state, exc)
            _secure_tree(run_dir)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run or resume the deterministic Mellanni weekly digest workflow"
    )
    parser.add_argument("--run-root", type=Path, default=DEFAULT_RUN_ROOT)
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--project-ref", default=os.environ.get("SUPABASE_PROJECT_REF", SUPABASE_PROJECT_REF))
    parser.add_argument("--since-days", type=int, default=8)
    parser.add_argument("--fetch-workers", type=int, default=6)
    parser.add_argument("--youtube-concurrency", type=int, default=2)
    parser.add_argument("--youtube-timeout-ms", type=int, default=600000)
    parser.add_argument("--youtube-batch-deadline-ms", type=int, default=3600000)
    parser.add_argument("--max-videos", type=int, default=25)
    parser.add_argument("--fail-reason", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    numeric = (
        args.since_days,
        args.fetch_workers,
        args.youtube_concurrency,
        args.youtube_timeout_ms,
        args.youtube_batch_deadline_ms,
        args.max_videos,
    )
    if any(value < 1 for value in numeric):
        raise SystemExit("all day, worker, timeout, deadline, and cap values must be positive")
    try:
        result = run_weekly(args)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise SystemExit(str(exc)) from exc
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 2 if result.get("outcome") == "no-digest" else 0


if __name__ == "__main__":
    raise SystemExit(main())
