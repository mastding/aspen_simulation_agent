from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any, Dict, Optional


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def normalize_assignment_mode(raw: str) -> str:
    mode = str(raw or "off").strip().lower()
    if mode not in {"off", "shadow", "canary", "full"}:
        return "off"
    return mode


def load_prompt_version_registry(path: Path) -> Dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {
            "version": "none",
            "mode": "off",
            "canary_ratio": 0.1,
            "published_version_id": "published_static",
            "candidate_version_id": None,
            "versions": {},
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("invalid registry payload")
    except Exception:
        return {
            "version": "broken",
            "mode": "off",
            "canary_ratio": 0.1,
            "published_version_id": "published_static",
            "candidate_version_id": None,
            "versions": {},
        }
    payload.setdefault("mode", "off")
    payload.setdefault("canary_ratio", 0.1)
    payload.setdefault("published_version_id", "published_static")
    payload.setdefault("candidate_version_id", None)
    payload.setdefault("versions", {})
    return payload


def save_prompt_version_registry(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def should_use_candidate(*, mode: str, rollout_id: str, canary_ratio: float) -> bool:
    m = normalize_assignment_mode(mode)
    if m in {"off", "shadow"}:
        return False
    if m == "full":
        return True
    ratio = max(0.0, min(1.0, _safe_float(canary_ratio, 0.1)))
    rid = str(rollout_id or "")
    if not rid:
        return random.random() < ratio
    seed = int(hashlib.md5(rid.encode("utf-8")).hexdigest()[:8], 16)
    bucket = (seed % 10000) / 10000.0
    return bucket < ratio


def _should_select_candidate_shadow(*, mode: str, rollout_id: str, canary_ratio: float) -> bool:
    if normalize_assignment_mode(mode) != "shadow":
        return False
    ratio = max(0.0, min(1.0, _safe_float(canary_ratio, 0.1)))
    rid = str(rollout_id or "")
    if not rid:
        return random.random() < ratio
    seed = int(hashlib.md5(rid.encode("utf-8")).hexdigest()[:8], 16)
    bucket = (seed % 10000) / 10000.0
    return bucket < ratio


def register_prompt_candidate(
    *,
    registry_path: Path,
    manifest: Dict[str, Any],
    assignment_mode: str,
    canary_ratio: float,
    activate_candidate: bool,
) -> Dict[str, Any]:
    registry = load_prompt_version_registry(registry_path)
    version_id = str(manifest.get("version_id") or "").strip()
    if not version_id:
        raise ValueError("prompt version manifest missing version_id")
    versions = registry.setdefault("versions", {})
    versions[version_id] = {
        **manifest,
        "status": "candidate",
        "assignment_mode": normalize_assignment_mode(assignment_mode),
        "canary_ratio": max(0.0, min(1.0, _safe_float(canary_ratio, 0.1))),
    }
    if activate_candidate:
        registry["candidate_version_id"] = version_id
        registry["mode"] = normalize_assignment_mode(assignment_mode)
        registry["canary_ratio"] = max(0.0, min(1.0, _safe_float(canary_ratio, 0.1)))
    registry["version"] = f"pvreg_{int(time.time())}"
    registry["updated_at"] = time.time()
    save_prompt_version_registry(registry_path, registry)
    return registry


def mark_published_version(*, registry_path: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    registry = load_prompt_version_registry(registry_path)
    version_id = str(manifest.get("version_id") or "").strip()
    if not version_id:
        raise ValueError("prompt version manifest missing version_id")
    versions = registry.setdefault("versions", {})
    versions[version_id] = {
        **manifest,
        "status": "published",
        "assignment_mode": "full",
        "canary_ratio": 1.0,
    }
    registry["published_version_id"] = version_id
    if registry.get("candidate_version_id") == version_id:
        registry["candidate_version_id"] = None
    registry["version"] = f"pvreg_{int(time.time())}"
    registry["updated_at"] = time.time()
    save_prompt_version_registry(registry_path, registry)
    return registry


def update_prompt_registry(
    *,
    registry_path: Path,
    mode: Optional[str] = None,
    canary_ratio: Optional[float] = None,
    candidate_version_id: Optional[str] = None,
) -> Dict[str, Any]:
    registry = load_prompt_version_registry(registry_path)
    if mode is not None:
        registry["mode"] = normalize_assignment_mode(mode)
    if canary_ratio is not None:
        registry["canary_ratio"] = max(0.0, min(1.0, _safe_float(canary_ratio, 0.1)))
    if candidate_version_id is not None:
        value = str(candidate_version_id or "").strip() or None
        registry["candidate_version_id"] = value
    registry["version"] = f"pvreg_{int(time.time())}"
    registry["updated_at"] = time.time()
    save_prompt_version_registry(registry_path, registry)
    return registry


def select_prompt_assignment(
    *,
    registry_path: Path,
    rollout_id: str,
    user_message: str,
    task_type: str,
    mode: Optional[str] = None,
    canary_ratio: Optional[float] = None,
) -> Dict[str, Any]:
    registry = load_prompt_version_registry(registry_path)
    assignment_mode = normalize_assignment_mode(mode or str(registry.get("mode") or "off"))
    ratio = max(0.0, min(1.0, _safe_float(canary_ratio if canary_ratio is not None else registry.get("canary_ratio"), 0.1)))
    published_version_id = str(registry.get("published_version_id") or "published_static")
    candidate_version_id = str(registry.get("candidate_version_id") or "").strip() or None
    versions = registry.get("versions") or {}
    candidate_manifest = versions.get(candidate_version_id) if candidate_version_id else None

    select_candidate = False
    apply_candidate = False
    bucket = "published"
    if candidate_manifest:
        if assignment_mode == "shadow":
            select_candidate = _should_select_candidate_shadow(mode=assignment_mode, rollout_id=rollout_id, canary_ratio=ratio)
            bucket = "shadow_candidate" if select_candidate else "published"
        else:
            apply_candidate = should_use_candidate(mode=assignment_mode, rollout_id=rollout_id, canary_ratio=ratio)
            select_candidate = apply_candidate
            bucket = "candidate" if apply_candidate else "published"

    selected_version_id = candidate_version_id if select_candidate and candidate_version_id else published_version_id
    applied_version_id = candidate_version_id if apply_candidate and candidate_version_id else published_version_id
    return {
        "registry_version": registry.get("version"),
        "assignment_mode": assignment_mode,
        "canary_ratio": ratio,
        "user_message": str(user_message or "")[:200],
        "task_type": str(task_type or ""),
        "candidate_version_id": candidate_version_id,
        "published_version_id": published_version_id,
        "selected_version_id": selected_version_id,
        "applied_version_id": applied_version_id,
        "prompt_version_id": selected_version_id,
        "bucket": bucket,
        "apply_candidate": bool(apply_candidate),
        "manifest": candidate_manifest if select_candidate else None,
    }


def _read_small_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def build_effective_system_prompt(
    *,
    base_system_prompt: str,
    assignment: Dict[str, Any],
    training_runs_dir: Path,
) -> str:
    if not bool((assignment or {}).get("apply_candidate")):
        return base_system_prompt
    manifest = (assignment or {}).get("manifest") or {}
    run_id = str(manifest.get("run_id") or "").strip()
    if not run_id:
        return base_system_prompt
    run_dir = training_runs_dir / run_id
    increments = manifest.get("increment_files") or {}
    parts = []
    for key, label in (
        ("system", "System Prompt Increment"),
        ("schema_check", "Schema Check Increment"),
        ("thought", "Thought Process Increment"),
    ):
        file_name = str(increments.get(key) or "").strip()
        if not file_name:
            continue
        text = _read_small_text(run_dir / file_name)
        if text:
            parts.append(f"# {label}\n{text}")
    if not parts:
        return base_system_prompt
    suffix = "\n\n# Online Candidate Prompt Version\n" + "\n\n".join(parts)
    return f"{base_system_prompt.rstrip()}{suffix}\n"
