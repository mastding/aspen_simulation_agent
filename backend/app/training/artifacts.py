from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def trim_logs(logs: List[Dict[str, Any]], limit: int = 2000) -> None:
    if len(logs) > limit:
        del logs[0 : len(logs) - limit]


def extract_run_id_from_training_stdout(stdout_lines: List[str]) -> Optional[str]:
    marker = "Saved training artifacts to:"
    for line in reversed(stdout_lines):
        raw = str(line).strip()
        if marker in raw:
            run_name = Path(raw.split(marker, 1)[1].strip()).name
            if run_name.startswith("run_"):
                return run_name
    return None


def extract_collection_file_from_stdout(stdout_lines: List[str]) -> Optional[Path]:
    marker = "Saved:"
    for line in reversed(stdout_lines):
        raw = str(line).strip()
        if marker in raw:
            candidate = Path(raw.split(marker, 1)[1].strip())
            if candidate.exists() and candidate.is_file():
                return candidate
    return None


def first_existing_file(base_dir: Path, names: List[str]) -> Optional[Path]:
    for name in names:
        p = base_dir / name
        if p.exists() and p.is_file():
            return p
    return None


def safe_run_id(run_id: str) -> str:
    run_id = str(run_id).strip()
    if not run_id or "/" in run_id or "\\" in run_id or ".." in run_id:
        raise ValueError("invalid run_id")
    return run_id


def read_small_text(path: Path, max_text_file_size: int) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if len(raw) > int(max_text_file_size):
        return raw[: int(max_text_file_size)] + "\n\n...[truncated]"
    return raw


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def line_delta(candidate_text: str, published_text: str) -> Tuple[int, List[str]]:
    cand_lines = [line for line in candidate_text.splitlines() if line.strip()]
    pub_set = set([line for line in published_text.splitlines() if line.strip()])
    added = [line for line in cand_lines if line not in pub_set]
    return len(added), added[:5]


def json_item_key_list(raw: str) -> List[Tuple[str, str, str]]:
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    result: List[Tuple[str, str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        result.append((str(item.get("source", "")), str(item.get("path", "")), str(item.get("description", ""))))
    return result



def _compare_prompt_file(
    *,
    run_dir: Path,
    artifact_names: List[str],
    published_file: Path,
    label: str,
) -> Dict[str, Any]:
    candidate_path = first_existing_file(run_dir, artifact_names)
    if candidate_path is None:
        return {
            "artifact": artifact_names[0],
            "label": label,
            "status": "missing",
            "has_new": False,
            "new_count": 0,
            "sample_new_lines": [],
            "published_path": str(published_file),
        }

    candidate_text = read_text_safe(candidate_path)
    published_text = read_text_safe(published_file)
    new_count, sample_lines = line_delta(candidate_text, published_text)
    return {
        "artifact": candidate_path.name,
        "label": label,
        "status": "ok",
        "has_new": new_count > 0,
        "new_count": new_count,
        "sample_new_lines": sample_lines,
        "published_path": str(published_file),
    }


def _compare_schema_file(run_dir: Path, schema_default_target: Path) -> Dict[str, Any]:
    run_id = run_dir.name
    candidate_path = first_existing_file(
        run_dir,
        [
            f"schema_descriptions_candidate-{run_id}.json",
            "schema_descriptions_candidate_0211.json",
            "schema_descriptions.json",
            "schema_descriptions_0211.json",
        ],
    )
    if candidate_path is None:
        return {
            "artifact": "schema_descriptions.json",
            "label": "schema_descriptions",
            "status": "missing",
            "has_new": False,
            "new_count": 0,
            "sample_new_lines": [],
            "published_path": str(schema_default_target),
        }

    candidate_raw = read_text_safe(candidate_path)
    published_raw = read_text_safe(schema_default_target) if schema_default_target.exists() else "[]"
    cand_keys = json_item_key_list(candidate_raw)
    pub_keys = set(json_item_key_list(published_raw))
    added = [k for k in cand_keys if k not in pub_keys]
    return {
        "artifact": candidate_path.name,
        "label": "schema_descriptions",
        "status": "ok",
        "has_new": len(added) > 0,
        "new_count": len(added),
        "sample_new_lines": [f"{x[1]}: {x[2][:80]}" for x in added[:5]],
        "published_path": str(schema_default_target),
    }


def build_training_overview(
    *,
    run_training: bool,
    training_result: Optional[Dict[str, Any]],
    task_total: int,
    succeeded: int,
    failed: int,
    training_runs_dir: Path,
    prompt_dir: Path,
    schema_default_target: Path,
) -> Dict[str, Any]:
    overview: Dict[str, Any] = {
        "run_training": run_training,
        "training_run_id": (training_result or {}).get("run_id"),
        "training_algo": str((training_result or {}).get("algo") or "rgo"),
        "artifacts": [],
        "artifact_diffs": [],
        "apo_result": None,
        "optimized_prompt": False,
        "optimized_schema": False,
        "need_publish": False,
        "summary": "",
        "publish_hint": "可进入训练发布页面（/training）评审并发布优化结果。",
    }

    if not run_training:
        overview["summary"] = f"本次采样共 {task_total} 条，成功 {succeeded}，失败 {failed}，未执行训练。"
        return overview

    if not training_result:
        overview["summary"] = "本次训练未产生新增提示词/Schema（候选与已发布内容一致）。"
        return overview

    if int(training_result.get("returncode", 1)) != 0:
        overview["summary"] = "训练执行失败，请查看执行日志。"
        return overview

    run_id = str(training_result.get("run_id") or "").strip()
    if not run_id:
        overview["summary"] = "本次训练未产生新增提示词/Schema（候选与已发布内容一致）。"
        return overview

    run_dir = training_runs_dir / run_id
    if not run_dir.exists() or not run_dir.is_dir():
        overview["summary"] = "训练完成但产物目录不存在。"
        return overview

    files = sorted([p.name for p in run_dir.iterdir() if p.is_file()])
    overview["artifacts"] = files
    apo_result_path = run_dir / "apo_result.json"
    if apo_result_path.exists() and apo_result_path.is_file():
        try:
            overview["apo_result"] = json.loads(apo_result_path.read_text(encoding="utf-8"))
        except Exception:
            overview["apo_result"] = None

    comparison_report_path = run_dir / "comparison_report.json"
    if comparison_report_path.exists() and comparison_report_path.is_file():
        try:
            overview["comparison_report"] = json.loads(comparison_report_path.read_text(encoding="utf-8"))
        except Exception:
            overview["comparison_report"] = None
    diffs = [
        _compare_prompt_file(
            run_dir=run_dir,
            artifact_names=[
                f"system_prompt_candidate-{run_id}.txt",
                "system_prompt_candidate.txt",
                "system_prompt_candidate_0211.txt",
            ],
            published_file=prompt_dir / "llm_prompt.py",
            label="system_prompt",
        ),
        _compare_prompt_file(
            run_dir=run_dir,
            artifact_names=[
                f"schema_check_prompt_candidate-{run_id}.txt",
                "schema_check_prompt_candidate.txt",
                "schema_check_prompt_candidate_0211.txt",
            ],
            published_file=prompt_dir / "schema_check.py",
            label="schema_check_prompt",
        ),
        _compare_prompt_file(
            run_dir=run_dir,
            artifact_names=[
                f"thought_process_prompt_candidate-{run_id}.txt",
                "thought_process_prompt_candidate.txt",
                "thought_process_prompt_candidate_0211.txt",
            ],
            published_file=prompt_dir / "thought_process.py",
            label="thought_process_prompt",
        ),
        _compare_schema_file(run_dir, schema_default_target),
    ]
    overview["artifact_diffs"] = diffs

    has_prompt = any(
        d.get("label") in {"system_prompt", "schema_check_prompt", "thought_process_prompt"} and d.get("has_new")
        for d in diffs
    )
    has_schema = any(d.get("label") == "schema_descriptions" and d.get("has_new") for d in diffs)

    overview["optimized_prompt"] = has_prompt
    overview["optimized_schema"] = has_schema
    overview["need_publish"] = bool(has_prompt or has_schema)

    if not overview["need_publish"]:
        result_only = [name for name in files if name in {"training_result.json", "training_report.md", "apo_result.json"}]
        overview["artifacts"] = result_only if result_only else files

    changed = [f"{d.get('artifact')} 新增 {int(d.get('new_count', 0))} 条" for d in diffs if d.get("has_new")]
    if changed:
        overview["summary"] = "本次训练有新增优化建议：" + "；".join(changed)
    else:
        overview["summary"] = "本次训练未产生新增提示词/Schema（候选与已发布内容一致）。"
    if overview.get("training_algo") == "apo" and isinstance(overview.get("apo_result"), dict):
        best_score = overview["apo_result"].get("best_score")
        iters = overview["apo_result"].get("iterations")
        overview["summary"] += f" APO结果：iters={iters}, best_score={best_score}。"

    return overview
