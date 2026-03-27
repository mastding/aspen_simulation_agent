from __future__ import annotations

import ntpath
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from tools.download_aspen_file import AspenDownloadError


def root_handler(*, model: str) -> Dict[str, Any]:
    return {
        "message": "Aspen Simulation Backend (RL) is running",
        "version": "2.3.0",
        "model": model,
        "persistence": "sqlite",
    }


def health_handler(*, model: str, data_dir: Path, query_statistics_sqlite_fn) -> Dict[str, Any]:
    stats = query_statistics_sqlite_fn()
    return {
        "status": "healthy",
        "service": "aspen-simulation-rl",
        "model": model,
        "data_dir": str(data_dir),
        "store": "InMemoryLightningStore + SQLite",
        **stats,
    }


def download_handler(*, file_path: str, download_aspen_file_fn, logger) -> StreamingResponse:
    try:
        result = download_aspen_file_fn(file_path)
        safe_name = ntpath.basename(str(file_path)) or result.file_name or "download.bin"
        safe_name = safe_name.replace('"', "")
        headers = {
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Source": "aspen-remote",
            "X-File-Path": file_path,
        }
        return StreamingResponse(
            iter([result.content]),
            media_type=result.content_type or "application/octet-stream",
            headers=headers,
        )
    except AspenDownloadError as exc:
        logger.warning("Remote download failed: %s", exc)
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except Exception as exc:
        logger.exception("Download failed")
        raise HTTPException(status_code=500, detail=f"Download failed: {exc}")


def rollouts_handler(*, limit: int, offset: int, query_rollouts_sqlite_fn, logger) -> Dict[str, Any]:
    try:
        records = query_rollouts_sqlite_fn(limit=max(1, min(limit, 500)), offset=max(0, offset))
        return {"total": len(records), "rollouts": records}
    except Exception as exc:
        logger.exception("query rollouts failed")
        raise HTTPException(status_code=500, detail=str(exc))


def clear_rollouts_handler(*, reset_rollouts_db_fn, logger) -> Dict[str, Any]:
    try:
        reset_rollouts_db_fn()
        return {"ok": True, "message": "\u4efb\u52a1\u5386\u53f2\u5df2\u6e05\u7a7a"}
    except Exception as exc:
        logger.exception("clear rollouts failed")
        raise HTTPException(status_code=500, detail=str(exc))


def rollout_spans_handler(*, rollout_id: str, query_spans_sqlite_fn, logger) -> Dict[str, Any]:
    try:
        spans = query_spans_sqlite_fn(rollout_id)
        return {"rollout_id": rollout_id, "total_spans": len(spans), "spans": spans}
    except Exception as exc:
        logger.exception("query spans failed")
        raise HTTPException(status_code=500, detail=str(exc))


def statistics_handler(*, query_statistics_sqlite_fn, logger) -> Dict[str, Any]:
    try:
        return query_statistics_sqlite_fn()
    except Exception as exc:
        logger.exception("statistics failed")
        raise HTTPException(status_code=500, detail=str(exc))


def artifacts_handler(*, limit: int, offset: int, status: Optional[str], query_artifacts_sqlite_fn, logger) -> Dict[str, Any]:
    try:
        return query_artifacts_sqlite_fn(limit=max(1, min(limit, 500)), offset=max(0, offset), status=status)
    except Exception as exc:
        logger.exception("artifacts query failed")
        raise HTTPException(status_code=500, detail=str(exc))


def metrics_overview_handler(*, query_metrics_overview_sqlite_fn, logger) -> Dict[str, Any]:
    try:
        return query_metrics_overview_sqlite_fn()
    except Exception as exc:
        logger.exception("metrics overview failed")
        raise HTTPException(status_code=500, detail=str(exc))


def list_training_runs_handler(*, limit: int, training_runs_dir: Path, training_exports_dir: Path, logger) -> Dict[str, Any]:
    try:
        runs: List[Dict[str, Any]] = []
        if training_runs_dir.exists():
            for run_dir in sorted(
                [p for p in training_runs_dir.iterdir() if p.is_dir() and p.name.startswith("run_")],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[: max(1, min(limit, 200))]:
                files = sorted([f.name for f in run_dir.iterdir() if f.is_file()])
                runs.append(
                    {
                        "run_id": run_dir.name,
                        "modified_time": run_dir.stat().st_mtime,
                        "files": files,
                        "has_prompt_candidates": any(
                            (
                                name.endswith("_candidate_0211.txt")
                                or ("_candidate-run_" in name and name.endswith(".txt"))
                                or name in {
                                    "system_prompt_candidate.txt",
                                    "schema_check_prompt_candidate.txt",
                                    "thought_process_prompt_candidate.txt",
                                }
                            )
                            for name in files
                        ),
                        "has_schema_candidate": any(
                            (name.startswith("schema_descriptions_candidate-") and name.endswith(".json"))
                            or name == "schema_descriptions_candidate_0211.json"
                            for name in files
                        ),
                        "has_training_report": (
                            "training_report.md" in files or "training_report_0211.md" in files
                        ),
                    }
                )
        exports: List[Dict[str, Any]] = []
        if training_exports_dir.exists():
            for d in sorted(
                [p for p in training_exports_dir.iterdir() if p.is_dir()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:20]:
                exports.append({"name": d.name, "modified_time": d.stat().st_mtime, "files": sorted([f.name for f in d.iterdir() if f.is_file()])})
        return {"runs": runs, "exports": exports}
    except Exception as exc:
        logger.exception("list training runs failed")
        raise HTTPException(status_code=500, detail=str(exc))


def clear_training_runs_handler(*, training_runs_dir: Path, training_exports_dir: Path, logger) -> Dict[str, Any]:
    import shutil
    try:
        removed_runs = 0
        removed_exports = 0

        if training_runs_dir.exists():
            for p in training_runs_dir.iterdir():
                if p.is_dir() and p.name.startswith("run_"):
                    shutil.rmtree(p, ignore_errors=False)
                    removed_runs += 1

        if training_exports_dir.exists():
            for p in training_exports_dir.iterdir():
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=False)
                    removed_exports += 1

        return {
            "ok": True,
            "message": "\u8bad\u7ec3\u4ea7\u7269\u5df2\u6e05\u7a7a",
            "removed_runs": removed_runs,
            "removed_exports": removed_exports,
        }
    except Exception as exc:
        logger.exception("clear training runs failed")
        raise HTTPException(status_code=500, detail=str(exc))


def get_training_file_handler(
    *,
    run_id: str,
    file_name: str,
    safe_run_id_fn,
    training_runs_dir: Path,
    read_small_text_fn,
    logger,
) -> Dict[str, Any]:
    try:
        rid = safe_run_id_fn(run_id)
        if "/" in file_name or "\\" in file_name or ".." in file_name:
            raise ValueError("invalid file_name")
        file_path = training_runs_dir / rid / file_name
        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(str(file_path))
        content = read_small_text_fn(file_path)
        parsed_json: Optional[Any] = None
        if file_path.suffix.lower() == ".json":
            try:
                import json as _json
                parsed_json = _json.loads(content)
            except Exception:
                parsed_json = None
        return {
            "run_id": rid,
            "file_name": file_name,
            "path": str(file_path),
            "size": file_path.stat().st_size,
            "content": content if parsed_json is None else None,
            "json": parsed_json,
        }
    except Exception as exc:
        logger.exception("get training file failed")
        raise HTTPException(status_code=500, detail=str(exc))


def publish_training_result_handler(
    *,
    payload: Dict[str, Any],
    safe_run_id_fn,
    schema_default_target: Path,
    training_runs_dir: Path,
    rl_dir: Path,
    prompt_dir: Path,
    base_parent_dir: Path,
    prompt_version_file: Path,
    prompt_version_service: Any,
    upsert_prompt_version_fn,
    logger,
) -> Dict[str, Any]:
    try:
        run_id = safe_run_id_fn(payload.get("run_id", ""))
        apply_prompts = bool(payload.get("apply_prompts", True))
        # schema 发布功能当前前端下线，后端保持兼容但默认关闭
        apply_schema = bool(payload.get("apply_schema", False))
        dry_run = bool(payload.get("dry_run", True))
        register_prompt_version = bool(payload.get("register_prompt_version", True))
        activate_candidate = bool(payload.get("activate_candidate", False))
        prompt_assignment_mode = str(payload.get("prompt_assignment_mode", "shadow") or "shadow")
        prompt_canary_ratio = float(payload.get("prompt_canary_ratio", 0.1) or 0.1)
        schema_target = str(payload.get("schema_target", str(schema_default_target))).strip()
        prompt_targets = payload.get("prompt_targets") or []
        if isinstance(prompt_targets, str):
            prompt_targets = [x.strip() for x in prompt_targets.split(",") if x.strip()]
        if not isinstance(prompt_targets, list):
            prompt_targets = []
        prompt_targets = [str(x).strip() for x in prompt_targets if str(x).strip()]
        run_dir = training_runs_dir / run_id
        if not run_dir.exists() or not run_dir.is_dir():
            raise FileNotFoundError(f"run not found: {run_id}")

        results: List[Dict[str, Any]] = []
        py = sys.executable or "python3"
        if apply_prompts:
            prompt_script = rl_dir / "src" / "apply_prompt_candidates.py"
            cmd = [py, str(prompt_script), "--run-dir", str(run_dir), "--prompt-dir", str(prompt_dir), "--emit-json"]
            if prompt_targets:
                cmd.extend(["--only", ",".join(prompt_targets)])
            if not dry_run:
                cmd.append("--apply")
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(base_parent_dir), timeout=120)
            parsed = None
            try:
                parsed = json.loads((proc.stdout or "").strip() or "{}")
            except Exception:
                parsed = None
            results.append({
                "step": "apply_prompts",
                "command": cmd,
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "parsed": parsed,
            })

        if apply_schema:
            schema_script = rl_dir / "src" / "apply_schema_candidate.py"
            candidate = run_dir / f"schema_descriptions_candidate-{run_id}.json"
            if not candidate.exists():
                legacy = run_dir / "schema_descriptions_candidate_0211.json"
                if legacy.exists():
                    candidate = legacy
                else:
                    # fallback: pick latest schema candidate in run dir
                    cands = sorted(run_dir.glob("schema_descriptions_candidate-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                    if cands:
                        candidate = cands[0]
                    else:
                        raise FileNotFoundError(f"schema candidate missing in run: {run_dir}")
            cmd = [py, str(schema_script), "--candidate", str(candidate), "--target", schema_target]
            if not dry_run:
                cmd.append("--apply")
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(base_parent_dir), timeout=120)
            results.append({"step": "apply_schema", "command": cmd, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr})

        has_error = any(int(item.get("returncode", 1)) != 0 for item in results)
        prompt_version_result = None
        if not has_error and register_prompt_version:
            manifest_path = run_dir / "prompt_version_manifest.json"
            if manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                prompt_version_id = str(manifest.get("version_id") or "").strip()
                if prompt_version_id:
                    upsert_prompt_version_fn(
                        prompt_version_id=prompt_version_id,
                        source_run_id=str(manifest.get("run_id") or run_id),
                        status="candidate",
                        assignment_mode=prompt_assignment_mode,
                        canary_ratio=prompt_canary_ratio,
                        manifest_obj=manifest,
                    )
                    registry = prompt_version_service.register_prompt_candidate(
                        registry_path=prompt_version_file,
                        manifest=manifest,
                        assignment_mode=prompt_assignment_mode,
                        canary_ratio=prompt_canary_ratio,
                        activate_candidate=activate_candidate,
                    )
                    prompt_version_result = {
                        "registered": True,
                        "prompt_version_id": prompt_version_id,
                        "activated_candidate": activate_candidate,
                        "assignment_mode": prompt_assignment_mode,
                        "canary_ratio": prompt_canary_ratio,
                        "registry": registry,
                    }
                    if apply_prompts and not dry_run:
                        registry = prompt_version_service.mark_published_version(
                            registry_path=prompt_version_file,
                            manifest=manifest,
                        )
                        upsert_prompt_version_fn(
                            prompt_version_id=prompt_version_id,
                            source_run_id=str(manifest.get("run_id") or run_id),
                            status="published",
                            assignment_mode="full",
                            canary_ratio=1.0,
                            manifest_obj=manifest,
                        )
                        prompt_version_result["published"] = True
                        prompt_version_result["registry"] = registry
            else:
                prompt_version_result = {
                    "registered": False,
                    "missing_manifest": True,
                    "manifest_path": str(manifest_path),
                }
        return {
            "run_id": run_id,
            "dry_run": dry_run,
            "apply_prompts": apply_prompts,
            "apply_schema": apply_schema,
            "prompt_targets": prompt_targets,
            "results": results,
            "prompt_version": prompt_version_result,
            "ok": not has_error,
        }
    except Exception as exc:
        logger.exception("publish training result failed")
        raise HTTPException(status_code=500, detail=str(exc))


def get_prompt_versions_handler(
    *,
    prompt_version_file: Path,
    prompt_version_service: Any,
    logger,
) -> Dict[str, Any]:
    try:
        registry = prompt_version_service.load_prompt_version_registry(prompt_version_file)
        return {
            "ok": True,
            "registry_path": str(prompt_version_file),
            "registry": registry,
        }
    except Exception as exc:
        logger.exception("get prompt versions failed")
        raise HTTPException(status_code=500, detail=str(exc))


def update_prompt_versions_handler(
    *,
    payload: Dict[str, Any],
    prompt_version_file: Path,
    prompt_version_service: Any,
    logger,
) -> Dict[str, Any]:
    try:
        registry = prompt_version_service.update_prompt_registry(
            registry_path=prompt_version_file,
            mode=payload.get("mode"),
            canary_ratio=payload.get("canary_ratio"),
            candidate_version_id=payload.get("candidate_version_id"),
        )
        return {
            "ok": True,
            "registry_path": str(prompt_version_file),
            "registry": registry,
        }
    except Exception as exc:
        logger.exception("update prompt versions failed")
        raise HTTPException(status_code=500, detail=str(exc))
