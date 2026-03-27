"""
Offline training from trajectory DB + prompt optimization artifacts.

This script does NOT modify original prompt files.
It saves candidate prompts and training reports for review.
"""

from __future__ import annotations

import argparse
import ast
import json
import random
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import os
import urllib.request


def _loads(raw: str, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _safe_tag(raw: str) -> str:
    text = "".join(ch for ch in str(raw or "") if ch.isalnum() or ch in {"-", "_"}).strip("_-")
    if not text:
        text = datetime.now().strftime("%Y%m%d_%H%M%S")
    return text[:64]


def _load_rollout_ids(path_text: str) -> Set[str]:
    if not path_text:
        return set()
    path = Path(path_text)
    if not path.exists():
        return set()
    ids: Set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        rid = line.strip()
        if rid:
            ids.add(rid)
    return ids


def load_rollouts_and_spans(
    db_path: Path,
    mode: str,
    rollout_ids: Optional[Set[str]] = None,
    time_from: Optional[float] = None,
    time_to: Optional[float] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        where_clauses: List[str] = []
        params: List[Any] = []

        if mode:
            where_clauses.append("mode = ?")
            params.append(mode)
        if time_from is not None:
            where_clauses.append("start_time >= ?")
            params.append(float(time_from))
        if time_to is not None:
            where_clauses.append("start_time <= ?")
            params.append(float(time_to))

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        rows = conn.execute(
            f"SELECT rollout_id,status,start_time,end_time,input_json,metadata_json FROM rollouts {where_sql} ORDER BY start_time ASC",
            params,
        ).fetchall()

        rollouts: List[Dict[str, Any]] = []
        for row in rows:
            rid = str(row["rollout_id"])
            if rollout_ids is not None and len(rollout_ids) > 0 and rid not in rollout_ids:
                continue
            rollouts.append(
                {
                    "rollout_id": rid,
                    "status": row["status"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "input": _loads(row["input_json"], {}),
                    "metadata": _loads(row["metadata_json"], {}),
                }
            )

        selected_ids = [item["rollout_id"] for item in rollouts]
        span_map: Dict[str, List[Dict[str, Any]]] = {rid: [] for rid in selected_ids}
        if selected_ids:
            placeholders = ",".join(["?"] * len(selected_ids))
            span_rows = conn.execute(
                f"SELECT rollout_id,name,attributes_json,start_time,end_time FROM spans WHERE rollout_id IN ({placeholders}) ORDER BY id ASC",
                selected_ids,
            ).fetchall()
            for row in span_rows:
                rid = str(row["rollout_id"])
                span_map.setdefault(rid, []).append(
                    {
                        "name": row["name"],
                        "attributes": _loads(row["attributes_json"], {}),
                        "start_time": row["start_time"],
                        "end_time": row["end_time"],
                    }
                )

        return rollouts, span_map
    finally:
        conn.close()


def load_memory_usage_rows(
    db_path: Path,
    rollout_ids: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT rollout_id, memory_id, hit_rank, match_score, status, reward, match_details_json
            FROM memory_usage_events
            ORDER BY id ASC
            """
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            rid = str(row["rollout_id"] or "").strip()
            if rollout_ids and rid not in rollout_ids:
                continue
            out.append(
                {
                    "rollout_id": rid,
                    "memory_id": str(row["memory_id"] or "").strip(),
                    "hit_rank": row["hit_rank"],
                    "match_score": row["match_score"],
                    "status": str(row["status"] or "").strip(),
                    "reward": row["reward"],
                    "match_details": _loads(row["match_details_json"], {}),
                }
            )
        return out
    finally:
        conn.close()


def _memory_quality_band(row: Dict[str, Any]) -> str:
    details = row.get("match_details", {}) or {}
    if isinstance(details, dict):
        for key in ("quality_band", "memory_quality_band"):
            value = str(details.get(key) or "").strip().lower()
            if value in {"high", "medium", "low", "unknown"}:
                return value
        try:
            quality_score = float(details.get("quality_score"))
        except Exception:
            quality_score = None
        if quality_score is not None:
            if quality_score >= 0.75:
                return "high"
            if quality_score >= 0.45:
                return "medium"
            return "low"
    reward = row.get("reward")
    try:
        reward_value = float(reward)
    except Exception:
        reward_value = None
    if reward_value is None:
        return "unknown"
    if reward_value >= 0.8:
        return "high"
    if reward_value >= 0.5:
        return "medium"
    return "low"


def summarize_memory_usage(memory_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not memory_rows:
        return {
            "total_usage_events": 0,
            "rollouts_with_memory_hits": 0,
            "avg_hit_rank": None,
            "avg_match_score": None,
            "memory_quality_bands": {"high": 0, "medium": 0, "low": 0, "unknown": 0},
            "high_quality_hit_success_rate": None,
            "low_quality_hit_success_rate": None,
            "top_hit_memories": [],
            "memory_hit_rollout_samples": [],
        }

    unique_rollouts: Set[str] = set()
    hit_ranks: List[float] = []
    match_scores: List[float] = []
    band_counter: Counter[str] = Counter()
    band_status_counter: Dict[str, Counter[str]] = {
        "high": Counter(),
        "medium": Counter(),
        "low": Counter(),
        "unknown": Counter(),
    }
    memory_stats: Dict[str, Dict[str, Any]] = {}
    hit_samples: List[Dict[str, Any]] = []

    for row in memory_rows:
        rid = str(row.get("rollout_id") or "").strip()
        memory_id = str(row.get("memory_id") or "").strip()
        if rid:
            unique_rollouts.add(rid)
        try:
            hit_ranks.append(float(row.get("hit_rank")))
        except Exception:
            pass
        try:
            match_scores.append(float(row.get("match_score")))
        except Exception:
            pass

        band = _memory_quality_band(row)
        band_counter[band] += 1
        status = str(row.get("status") or "").strip().lower()
        if status:
            band_status_counter.setdefault(band, Counter())[status] += 1

        if memory_id:
            stats = memory_stats.setdefault(
                memory_id,
                {
                    "memory_id": memory_id,
                    "hit_count": 0,
                    "quality_counter": Counter(),
                    "status_counter": Counter(),
                    "reward_values": [],
                    "example_rollout_id": "",
                },
            )
            stats["hit_count"] += 1
            stats["quality_counter"][band] += 1
            if status:
                stats["status_counter"][status] += 1
            try:
                stats["reward_values"].append(float(row.get("reward")))
            except Exception:
                pass
            if rid and not stats["example_rollout_id"]:
                stats["example_rollout_id"] = rid

        if len(hit_samples) < 12:
            hit_samples.append(
                {
                    "rollout_id": rid,
                    "memory_id": memory_id,
                    "quality_band": band,
                    "status": status or "unknown",
                    "reward": row.get("reward"),
                    "match_score": row.get("match_score"),
                }
            )

    def _band_success_rate(band: str) -> Optional[float]:
        counter = band_status_counter.get(band, Counter())
        total = sum(counter.values())
        if total <= 0:
            return None
        return round(counter.get("succeeded", 0) / total, 4)

    top_hit_memories: List[Dict[str, Any]] = []
    for stats in sorted(memory_stats.values(), key=lambda item: (-int(item["hit_count"]), str(item["memory_id"])))[0:10]:
        reward_values = stats["reward_values"]
        dominant_band = "unknown"
        if stats["quality_counter"]:
            dominant_band = stats["quality_counter"].most_common(1)[0][0]
        status_total = sum(stats["status_counter"].values())
        success_rate = (
            round(stats["status_counter"].get("succeeded", 0) / status_total, 4)
            if status_total > 0
            else None
        )
        top_hit_memories.append(
            {
                "memory_id": stats["memory_id"],
                "hit_count": stats["hit_count"],
                "quality_band": dominant_band,
                "success_rate": success_rate,
                "avg_reward_after_use": round(sum(reward_values) / len(reward_values), 4) if reward_values else None,
                "example_rollout_id": stats["example_rollout_id"] or None,
            }
        )

    return {
        "total_usage_events": len(memory_rows),
        "rollouts_with_memory_hits": len(unique_rollouts),
        "avg_hit_rank": round(sum(hit_ranks) / len(hit_ranks), 4) if hit_ranks else None,
        "avg_match_score": round(sum(match_scores) / len(match_scores), 4) if match_scores else None,
        "memory_quality_bands": {
            "high": int(band_counter.get("high", 0)),
            "medium": int(band_counter.get("medium", 0)),
            "low": int(band_counter.get("low", 0)),
            "unknown": int(band_counter.get("unknown", 0)),
        },
        "high_quality_hit_success_rate": _band_success_rate("high"),
        "low_quality_hit_success_rate": _band_success_rate("low"),
        "top_hit_memories": top_hit_memories,
        "memory_hit_rollout_samples": hit_samples,
    }


def _classify_error_type(error_text: str, explicit_type: str = "") -> str:
    et = str(explicit_type or "").strip().lower()
    text = str(error_text or "").strip().lower()
    merged = f"{et} {text}"

    if any(k in merged for k in ["timeout", "\u8d85\u65f6"]):
        return "timeout"
    if any(k in merged for k in ["schema", "\u5b57\u6bb5", "\u7aef\u53e3", "\u53c2\u6570", "\u914d\u7f6e", "config"]):
        return "config"
    if any(k in merged for k in ["unit", "\u5355\u4f4d", "moe", "kmol", "kg"]):
        return "unit"
    if any(k in merged for k in ["\u8fd0\u884c\u8fc7\u7a0b", "runtime", "\u6536\u655b", "converge", "\u8fed\u4ee3", "\u6c42\u89e3"]):
        return "runtime"
    return "other"


def _span_tool_name(span: Dict[str, Any]) -> str:
    attrs = span.get("attributes", {}) or {}
    candidates = [
        attrs.get("tool_name"),
        attrs.get("tool"),
        attrs.get("function_name"),
        attrs.get("name"),
        span.get("name"),
    ]
    for c in candidates:
        t = str(c or "").strip().lower()
        if not t:
            continue
        if "run_simulation" in t:
            return "run_simulation"
        if "get_schema" in t:
            return "get_schema"
        if "get_result" in t:
            return "get_result"
        if "memory_search_experience" in t:
            return "memory_search_experience"
        if "memory_get_experience" in t:
            return "memory_get_experience"
    return ""


def _parse_payload_text(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except Exception:
        pass
    try:
        return ast.literal_eval(text)
    except Exception:
        return {"_raw": text}


def _normalize_result_obj(obj: Any) -> Dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    return {"_raw": str(obj or "")}


def _extract_run_sim_error(result_obj: Dict[str, Any]) -> Tuple[bool, str, str]:
    # Returns (is_failure, error_message, explicit_error_type)
    success_val = result_obj.get("success")
    if isinstance(success_val, bool):
        is_success = success_val
    else:
        # Fallback heuristics for old payloads
        msg = str(result_obj.get("message", ""))
        is_success = ("\u6210\u529f" in msg and "\u5931\u8d25" not in msg) or bool(result_obj.get("result_file_path"))

    if is_success:
        return (False, "", "")

    err = str(result_obj.get("error_message") or result_obj.get("error") or result_obj.get("message") or "").strip()
    err_type = str(result_obj.get("error_type") or "").strip()

    if not err:
        raw = str(result_obj.get("_raw") or "").strip()
        if raw:
            err = raw[:400]

    # Still treat as failure when success is false/unknown and contains error cues.
    if err:
        return (True, err, err_type)

    # Unknown object but no success marker: conservatively as failure with generic text.
    return (True, "run_simulation \u5931\u8d25\uff08\u672a\u8fd4\u56de\u660e\u786e\u9519\u8bef\u4fe1\u606f\uff09", err_type)


def summarize_training_data(rollouts: List[Dict[str, Any]], span_map: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    total = len(rollouts)
    status_count = Counter([str(item["status"]) for item in rollouts])
    succeeded = [item for item in rollouts if item["status"] == "succeeded"]

    reward_values: List[float] = []
    error_counter: Counter[str] = Counter()
    error_type_counter: Counter[str] = Counter()
    failure_category_counter: Counter[str] = Counter()
    progress_stage_counter: Counter[str] = Counter()
    validator_gap_counter: Counter[str] = Counter()
    failed_task_msgs: List[str] = []
    succeeded_task_msgs: List[str] = []
    failure_rollout_samples: List[Dict[str, Any]] = []

    success_run_sim_calls: List[int] = []
    failed_run_sim_calls: List[int] = []
    success_get_result_calls: List[int] = []

    for rollout in rollouts:
        rid = rollout["rollout_id"]
        msg = str(rollout.get("metadata", {}).get("user_message", "")).strip()
        spans = span_map.get(rid, [])
        rollout_failure_categories: Set[str] = set()
        rollout_validator_gaps: Set[str] = set()

        run_sim_calls = 0
        get_result_calls = 0

        if rollout["status"] == "succeeded":
            if msg:
                succeeded_task_msgs.append(msg)
        else:
            if msg:
                failed_task_msgs.append(msg)

        call_id_to_tool: Dict[str, str] = {}

        for span in spans:
            attrs = span.get("attributes", {}) or {}
            span_name = str(span.get("name") or "").strip().lower()

            if span_name == "reward":
                try:
                    reward_values.append(float(attrs.get("reward")))
                except Exception:
                    pass
                failure_categories = attrs.get("failure_categories")
                if isinstance(failure_categories, list):
                    for item in failure_categories:
                        cat = str(item or "").strip()
                        if cat:
                            rollout_failure_categories.add(cat)
                single_failure = str(attrs.get("failure_category") or "").strip()
                if single_failure:
                    rollout_failure_categories.add(single_failure)
                validator_scores = attrs.get("validator_scores")
                if isinstance(validator_scores, dict):
                    for key, value in validator_scores.items():
                        try:
                            score = float(value)
                        except Exception:
                            continue
                        if score < 0.8:
                            rollout_validator_gaps.add(str(key))

            # Legacy explicit error span support
            if span_name == "error":
                err = str(attrs.get("error", "")).strip()
                err_type = str(attrs.get("error_type", "")).strip()
                if err:
                    error_counter[err[:200]] += 1
                    error_type_counter[_classify_error_type(err, err_type)] += 1
                failure_categories = attrs.get("failure_categories")
                if isinstance(failure_categories, list):
                    for item in failure_categories:
                        cat = str(item or "").strip()
                        if cat:
                            rollout_failure_categories.add(cat)
                single_failure = str(attrs.get("failure_category") or "").strip()
                if single_failure:
                    rollout_failure_categories.add(single_failure)

            if span_name == "task_progress":
                stage = str(attrs.get("stage") or "").strip()
                if stage:
                    progress_stage_counter[stage] += 1
                progress_failure = str(attrs.get("failure_category") or "").strip()
                if progress_failure:
                    rollout_failure_categories.add(progress_failure)

            # Parse tool call requests
            if span_name == "tool_call_request":
                calls = attrs.get("tool_calls")
                if isinstance(calls, list):
                    for item in calls:
                        if not isinstance(item, dict):
                            continue
                        call_id = str(item.get("id") or "").strip()
                        fn = str(item.get("function_name") or "").strip().lower()
                        if call_id:
                            call_id_to_tool[call_id] = fn
                        if "run_simulation" in fn:
                            run_sim_calls += 1
                        elif "get_result" in fn:
                            get_result_calls += 1

            # Parse tool execution results (contains run_simulation failure details)
            if span_name == "tool_execution":
                results = attrs.get("tool_results")
                if not isinstance(results, list):
                    continue
                for item in results:
                    if not isinstance(item, dict):
                        continue
                    call_id = str(item.get("call_id") or "").strip()
                    mapped_tool = call_id_to_tool.get(call_id, "")
                    result_obj = _normalize_result_obj(_parse_payload_text(item.get("result")))

                    # Fallback tool detection from payload text when call map missing
                    if not mapped_tool:
                        raw = str(item.get("result") or "")
                        if "run_simulation" in raw:
                            mapped_tool = "run_simulation"
                        elif "get_result" in raw:
                            mapped_tool = "get_result"

                    if "run_simulation" in mapped_tool:
                        is_fail, err, err_type = _extract_run_sim_error(result_obj)
                        if is_fail:
                            error_counter[err[:200]] += 1
                            error_type_counter[_classify_error_type(err, err_type)] += 1
                    failure_category = str(item.get("failure_category") or "").strip()
                    if failure_category:
                        rollout_failure_categories.add(failure_category)

        if rollout["status"] == "succeeded":
            success_run_sim_calls.append(run_sim_calls)
            success_get_result_calls.append(get_result_calls)
        else:
            failed_run_sim_calls.append(run_sim_calls)
        for cat in rollout_failure_categories:
            failure_category_counter[cat] += 1
        for key in rollout_validator_gaps:
            validator_gap_counter[key] += 1
        if rollout["status"] != "succeeded" and len(failure_rollout_samples) < 12:
            failure_rollout_samples.append(
                {
                    "rollout_id": rid,
                    "status": rollout["status"],
                    "user_message": msg,
                    "failure_categories": sorted(list(rollout_failure_categories)),
                    "validator_gaps": sorted(list(rollout_validator_gaps)),
                }
            )

    success_rate = (len(succeeded) / total) if total else 0.0
    avg_reward = (sum(reward_values) / len(reward_values)) if reward_values else None

    success_run_sim_avg = (sum(success_run_sim_calls) / len(success_run_sim_calls)) if success_run_sim_calls else 0.0
    failed_run_sim_avg = (sum(failed_run_sim_calls) / len(failed_run_sim_calls)) if failed_run_sim_calls else 0.0
    observed_success_runs = [x for x in success_run_sim_calls if x > 0]
    single_pass_success = sum(1 for x in observed_success_runs if x == 1)
    retry_success = sum(1 for x in observed_success_runs if x > 1)
    success_get_result_rate = (
        sum(1 for x in success_get_result_calls if x > 0) / len(success_get_result_calls)
    ) if success_get_result_calls else 0.0
    observed_tool_events = sum(success_run_sim_calls) + sum(failed_run_sim_calls) + sum(success_get_result_calls)

    return {
        "total_rollouts": total,
        "status_count": dict(status_count),
        "success_rate": success_rate,
        "avg_reward": avg_reward,
        "top_errors": [{"error": e, "count": c} for e, c in error_counter.most_common(10)],
        "error_type_count": dict(error_type_counter),
        "top_failure_categories": [{"category": k, "count": v} for k, v in failure_category_counter.most_common(10)],
        "failure_category_count": dict(failure_category_counter),
        "progress_stage_count": dict(progress_stage_counter),
        "top_validator_gaps": [{"validator": k, "count": v} for k, v in validator_gap_counter.most_common(10)],
        "validator_gap_count": dict(validator_gap_counter),
        "success_attempt_stats": {
            "success_run_sim_avg": round(success_run_sim_avg, 4),
            "fail_run_sim_avg": round(failed_run_sim_avg, 4),
            "single_pass_success_rate": round((single_pass_success / len(observed_success_runs)), 4) if observed_success_runs else 0.0,
            "retry_success_rate": round((retry_success / len(observed_success_runs)), 4) if observed_success_runs else 0.0,
            "success_get_result_rate": round(success_get_result_rate, 4),
            "observed_tool_events": int(observed_tool_events),
            "observed_success_runs": int(len(observed_success_runs)),
        },
        "failed_task_samples": failed_task_msgs[:10],
        "succeeded_task_samples": succeeded_task_msgs[:10],
        "failure_rollout_samples": failure_rollout_samples,
    }


def _load_json_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def build_schema_delta_rows(current_rows: List[Dict[str, str]], target_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    target_map: Dict[Tuple[str, str], str] = {}
    for row in target_rows:
        key = (str(row.get("source", "")), str(row.get("path", "")))
        target_map[key] = str(row.get("description", ""))

    delta: List[Dict[str, Any]] = []
    for row in current_rows:
        source = str(row.get("source", ""))
        path = str(row.get("path", ""))
        desc = str(row.get("description", ""))
        key = (source, path)
        old_desc = target_map.get(key)
        if old_desc is None:
            delta.append({
                "change_type": "add",
                "source": source,
                "path": path,
                "description": desc,
            })
        elif old_desc != desc:
            delta.append({
                "change_type": "update",
                "source": source,
                "path": path,
                "description": desc,
                "old_description": old_desc,
            })
    return delta



def extract_schema_descriptions(schema_dir: Path, max_items: int = 300) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []

    def walk(node: Any, path: str, src: str) -> None:
        if len(items) >= max_items:
            return
        if isinstance(node, dict):
            if "description" in node and isinstance(node["description"], str):
                items.append({"source": src, "path": path or "$", "description": node["description"]})
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else key, src)
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                walk(value, f"{path}[{idx}]", src)

    for fp in sorted(schema_dir.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        walk(data, "", fp.name)
        if len(items) >= max_items:
            break
    return items




def append_unique_bullets(base_text: str, section_title: str, bullets: List[str]) -> str:
    base = (base_text or "").strip()
    existing: Set[str] = set()
    for line in base.splitlines():
        s = line.strip()
        if s.startswith("- "):
            existing.add(s[2:].strip())
    new_bullets = [b.strip() for b in bullets if str(b).strip() and str(b).strip() not in existing]
    if not new_bullets:
        return base
    return base + f"\n\n{section_title}\n- " + "\n- ".join(new_bullets)




def _extract_increment_bullets(base_text: str, candidate_text: str) -> List[str]:
    """Extract new content from OPTIMIZATION_ZONE areas only."""
    import re as _re

    bullets = []

    # Find all optimization zones in candidate
    zone_pattern = r'<!-- OPTIMIZATION_ZONE_START: ([^-]+) -->\s*(.+?)\s*<!-- OPTIMIZATION_ZONE_END: \1 -->'
    candidate_zones = _re.findall(zone_pattern, candidate_text, flags=_re.DOTALL)
    base_zones = _re.findall(zone_pattern, base_text, flags=_re.DOTALL)

    # Build base zone dict
    base_zone_dict = {name.strip(): content.strip() for name, content in base_zones}

    # Compare each zone
    for zone_name, zone_content in candidate_zones:
        zone_name = zone_name.strip()
        zone_content = zone_content.strip()

        # Skip if zone is empty or just comments
        if not zone_content or zone_content.startswith('<!-- 此区域'):
            continue

        base_content = base_zone_dict.get(zone_name, '').strip()

        # If base is empty or just comments, and candidate has content, it's new
        if (not base_content or base_content.startswith('<!-- 此区域')) and zone_content and not zone_content.startswith('<!-- 此区域'):
            # Extract numbered items from zone content
            items = _re.findall(r'^\s*\d+\.\s*(.+?)(?=^\s*\d+\.|$)', zone_content, flags=_re.MULTILINE | _re.DOTALL)
            for item in items:
                item_text = item.strip()
                if item_text and not item_text.startswith('<!--'):
                    bullets.append(f"[{zone_name}] {item_text}")
        # If both have content, extract the diff
        elif base_content and zone_content and base_content != zone_content:
            # Extract items from candidate that are not in base
            candidate_items = _re.findall(r'^\s*\d+\.\s*(.+?)(?=^\s*\d+\.|$)', zone_content, flags=_re.MULTILINE | _re.DOTALL)
            base_items = _re.findall(r'^\s*\d+\.\s*(.+?)(?=^\s*\d+\.|$)', base_content, flags=_re.MULTILINE | _re.DOTALL)

            base_items_normalized = [_normalize_bullet_text(item.strip()) for item in base_items]

            for item in candidate_items:
                item_text = item.strip()
                if item_text and not item_text.startswith('<!--'):
                    item_normalized = _normalize_bullet_text(item_text)
                    if item_normalized not in base_items_normalized:
                        bullets.append(f"[{zone_name}] {item_text}")

    return bullets



def _build_increment_candidate_text(bullets: List[str], title: str, run_id: str) -> str:
    clean = [b.strip() for b in bullets if str(b).strip()]
    if not clean:
        return ''
    marker = "\u8bad\u7ec3\u540e\u589e\u91cf"
    rid = str(run_id or "unknown").strip()
    return f"{marker}({rid}) - {title}\n- " + "\n- ".join(clean) + "\n"

def _dedup_keep_order(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for item in items:
        t = str(item or "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _merge_rationale_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for item in records:
        target = str(item.get("target") or "").strip()
        bullet = str(item.get("bullet") or "").strip()
        if not target or not bullet:
            continue
        key = (target, bullet)
        current = merged.get(key)
        if current is None:
            merged[key] = {
                "target": target,
                "bullet": bullet,
                "reasons": [str(item.get("reason") or "").strip()] if str(item.get("reason") or "").strip() else [],
                "evidence": [str(item.get("evidence") or "").strip()] if str(item.get("evidence") or "").strip() else [],
                "failure_categories": [str(x).strip() for x in item.get("failure_categories", []) if str(x).strip()],
                "validator_gaps": [str(x).strip() for x in item.get("validator_gaps", []) if str(x).strip()],
                "memory_signals": [str(x).strip() for x in item.get("memory_signals", []) if str(x).strip()],
            }
            continue
        reason = str(item.get("reason") or "").strip()
        if reason and reason not in current["reasons"]:
            current["reasons"].append(reason)
        evidence = str(item.get("evidence") or "").strip()
        if evidence and evidence not in current["evidence"]:
            current["evidence"].append(evidence)
        for key_name in ("failure_categories", "validator_gaps", "memory_signals"):
            for raw in item.get(key_name, []) or []:
                value = str(raw).strip()
                if value and value not in current[key_name]:
                    current[key_name].append(value)
    return list(merged.values())


def _call_llm_for_prompt_optimization(
    summary: Dict[str, Any],
    current_prompts: Dict[str, str],
) -> Dict[str, str]:
    """Call LLM to analyze training trajectory and generate optimized prompt zones."""
    import json as _json
    import re as _re

    # Get total rollouts for reporting
    total_rollouts = summary.get('total_rollouts', 0)

    api_url = os.environ.get("MODEL_API_URL", "").rstrip("/")
    api_key = os.environ.get("MODEL_API_KEY", "")
    model = os.environ.get("MODEL", "qwen3-max")

    if not api_url or not api_key:
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if k == "MODEL_API_URL":
                    api_url = v.rstrip("/")
                elif k == "MODEL_API_KEY":
                    api_key = v
                elif k == "MODEL":
                    model = v

    if not api_url or not api_key:
        print("[LLM prompt gen] No API config found, skipping")
        return current_prompts

    top_errors = summary.get("top_errors", []) or []
    error_type_count = summary.get("error_type_count", {}) or {}
    failure_category_count = summary.get("failure_category_count", {}) or {}
    stats = summary.get("success_attempt_stats", {}) or {}

    # Use all errors for optimization (no frequency threshold)
    errors_text = ""
    for i, err in enumerate(top_errors[:8], 1):
        e = str(err.get("error", ""))[:300]
        c = err.get("count", 0)
        errors_text += f"\n错误{i} (出现{c}次):\n{e}\n"

    sr = summary.get('success_rate', 0)
    spr = stats.get('single_pass_success_rate', 0)
    rsr = stats.get('retry_success_rate', 0)
    savg = stats.get('success_run_sim_avg', 0)

    # Categorize errors to determine which zones to optimize
    error_texts_lower = [str(e.get("error", "")).lower() for e in top_errors]

    # Detect error categories
    has_recycle = any("循环" in t or "recycle" in t for t in error_texts_lower)
    has_radfrac = any("radfrac" in t or "精馏" in t or "condenser" in t or "塔" in t for t in error_texts_lower)
    has_reactor = any("rstoic" in t or "反应" in t or "reactor" in t or "守恒" in t for t in error_texts_lower)
    has_field = any("字段" in t or "field" in t or "missing" in t or "required" in t for t in error_texts_lower)
    has_unit = any("单位" in t or "unit" in t for t in error_texts_lower)
    has_port = any("端口" in t or "port" in t or "connection" in t for t in error_texts_lower)

    # Build analysis prompt
    analysis_prompt = f"""你是 Aspen 化工模拟 Agent 的提示词优化专家。

## 训练统计
- 总rollout数: {total_rollouts}
- 成功率: {sr:.1%}
- 错误类型分布: {_json.dumps(error_type_count, ensure_ascii=False)}
- 失败类别: {_json.dumps(failure_category_count, ensure_ascii=False)}
- 单次通过率: {spr:.1%}
- 重试成功率: {rsr:.1%}
- 成功时平均run_simulation调用次数: {savg}

## 错误信息
{errors_text}

## 当前提示词结构
当前提示词包含以下优化区域（每个区域独立维护）：

**system prompt 优化区域：**
- 工具调用策略
- 配置生成策略

**schema_check prompt 优化区域：**
- 字段完整性检查
- 单位与数值检查
- 设备特定检查

**thought_process prompt 优化区域：**
- 循环流程错误恢复
- 精馏塔错误恢复
- 反应器错误恢复
- 通用错误恢复

## 任务要求
请根据上述**高频错误信息**，为相关的优化区域生成**补充性的错误恢复策略**。

**重要约束：**
1. 针对实际出现的错误生成策略（无频次限制）
2. 每条策略必须以"当出现XXX错误时"开头，明确触发条件
3. 包含具体的操作指令，不要笼统建议
4. 这些策略是对基线流程的**补充**，不是替代
5. 使用数字列表格式（与基线风格一致）

**输出格式要求（必须严格遵守）：**
1. 只返回纯JSON对象，不要有任何其他文字或解释
2. 不要用markdown code block包裹JSON
3. JSON的key必须是以下之一：system_tool_strategy, system_config_strategy, schema_field_check, schema_unit_check, schema_device_check, thought_recycle, thought_radfrac, thought_reactor, thought_general
4. 每个key的value是字符串，包含数字列表格式的建议（用
分隔多条）
5. 如果某个区域无需优化，不要包含该key

**示例输出（直接返回JSON，不要code block）：**
{{"thought_general": "1. 当run_simulation返回NO BLOCK PARAGRAPH错误时，检查blocks配置中是否遗漏了流程图中引用的设备
2. 当出现字段缺失错误时，对照JSON Schema检查必填字段是否完整"}}

**现在请直接返回JSON：**
"""


    try:
        body = _json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": analysis_prompt}],
            "temperature": 0.3,
            "max_tokens": 3000,
        }, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(
            f"{api_url}/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            result = _json.loads(resp.read().decode("utf-8"))

        reply = str(result.get("choices", [{}])[0].get("message", {}).get("content", "")).strip()
        # Strip thinking tags (qwen3)
        reply = _re.sub(r"<think>.*?</think>", "", reply, flags=_re.DOTALL).strip()

        # Try multiple extraction strategies
        zone_updates = None

        # Strategy 1: Extract from code block
        json_match = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", reply, flags=_re.DOTALL)
        if json_match:
            try:
                zone_updates = _json.loads(json_match.group(1))
            except:
                pass

        # Strategy 2: Find first JSON object in response
        if not zone_updates:
            json_match = _re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", reply, flags=_re.DOTALL)
            if json_match:
                try:
                    zone_updates = _json.loads(json_match.group(0))
                except:
                    pass

        # Strategy 3: Try parsing entire reply as JSON
        if not zone_updates:
            try:
                zone_updates = _json.loads(reply)
            except:
                pass

        if not zone_updates:
            print(f"[LLM prompt gen] Failed to extract JSON from reply: {reply[:200]}")
            return current_prompts

        # Apply zone updates to current prompts
        result_prompts = {}
        for prompt_name, prompt_text in current_prompts.items():
            updated_text = prompt_text

            if prompt_name == "llm_prompt.py":
                if "system_tool_strategy" in zone_updates:
                    updated_text = _replace_optimization_zone(
                        updated_text, "工具调用策略", zone_updates["system_tool_strategy"]
                    )
                if "system_config_strategy" in zone_updates:
                    updated_text = _replace_optimization_zone(
                        updated_text, "配置生成策略", zone_updates["system_config_strategy"]
                    )

            elif prompt_name == "schema_check.py":
                if "schema_field_check" in zone_updates:
                    updated_text = _replace_optimization_zone(
                        updated_text, "字段完整性检查", zone_updates["schema_field_check"]
                    )
                if "schema_unit_check" in zone_updates:
                    updated_text = _replace_optimization_zone(
                        updated_text, "单位与数值检查", zone_updates["schema_unit_check"]
                    )
                if "schema_device_check" in zone_updates:
                    updated_text = _replace_optimization_zone(
                        updated_text, "设备特定检查", zone_updates["schema_device_check"]
                    )

            elif prompt_name == "thought_process.py":
                if "thought_recycle" in zone_updates:
                    updated_text = _replace_optimization_zone(
                        updated_text, "循环流程错误恢复", zone_updates["thought_recycle"]
                    )
                if "thought_radfrac" in zone_updates:
                    updated_text = _replace_optimization_zone(
                        updated_text, "精馏塔错误恢复", zone_updates["thought_radfrac"]
                    )
                if "thought_reactor" in zone_updates:
                    updated_text = _replace_optimization_zone(
                        updated_text, "反应器错误恢复", zone_updates["thought_reactor"]
                    )
                if "thought_general" in zone_updates:
                    updated_text = _replace_optimization_zone(
                        updated_text, "通用错误恢复", zone_updates["thought_general"]
                    )

            result_prompts[prompt_name] = updated_text

        total_zones = len([k for k in zone_updates.keys() if zone_updates[k].strip()])
        print(f"[LLM prompt gen] Updated {total_zones} optimization zones via LLM")
        return result_prompts

    except Exception as exc:
        import traceback
        print(f"[LLM prompt gen] LLM call failed: {exc}")
        print(f"[LLM prompt gen] Exception type: {type(exc).__name__}")
        print(f"[LLM prompt gen] Traceback: {traceback.format_exc()}")
        # Try to print the raw response if available
        try:
            if 'result' in locals():
                print(f"[LLM prompt gen] API response: {result}")
            if 'reply' in locals():
                print(f"[LLM prompt gen] Extracted reply: {reply[:500]}")
        except:
            pass
        return current_prompts


def _replace_optimization_zone(text: str, zone_name: str, new_content: str) -> str:
    """Replace content in a specific optimization zone."""
    import re as _re
    pattern = rf'(<!-- OPTIMIZATION_ZONE_START: {_re.escape(zone_name)} -->).*?(<!-- OPTIMIZATION_ZONE_END: {_re.escape(zone_name)} -->)'
    replacement = rf'\1\n{new_content.strip()}\n\2'
    return _re.sub(pattern, replacement, text, flags=_re.DOTALL)


def build_prompt_candidates(base_system: str, base_schema_check: str, base_thought: str, summary: Dict[str, Any], *, prompts: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Build prompt candidates using LLM-based categorized zone optimization."""
    current_prompts = prompts or {
        "llm_prompt.py": base_system,
        "schema_check.py": base_schema_check,
        "thought_process.py": base_thought
    }

    # Call LLM to generate optimized prompts with categorized zones
    optimized_prompts = _call_llm_for_prompt_optimization(summary, current_prompts)

    return {
        "system_prompt_candidate": optimized_prompts.get("llm_prompt.py", base_system),
        "schema_check_prompt_candidate": optimized_prompts.get("schema_check.py", base_schema_check),
        "thought_process_prompt_candidate": optimized_prompts.get("thought_process.py", base_thought),
    }


def _apo_score(text: str, summary: Dict[str, Any]) -> float:
    score = 0.0
    lower = text.lower()
    top_errors = summary.get("top_errors", [])
    for item in top_errors:
        err = str(item.get("error", "")).lower()
        cnt = float(item.get("count", 0) or 0)
        if "schema" in err and "schema" in lower:
            score += 0.08 * cnt
        if "timeout" in err and "timeout" in lower:
            score += 0.06 * cnt
        if "unit" in err and "\u5355\u4f4d" in text:
            score += 0.05 * cnt
    # Shorter additions are preferred to reduce prompt bloat.
    score -= max(0, (len(text) - 1200)) / 6000.0
    return round(score, 6)


def run_apo_prompt_optimization(
    *,
    base_candidates: Dict[str, str],
    summary: Dict[str, Any],
    iterations: int,
    sample_size: int,
    exploration: float,
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    rng = random.Random(20260220)
    pool = []  # APO disabled - using LLM-based optimization instead
    best = dict(base_candidates)
    if not pool:
        return best, {
            "algo": "apo",
            "iterations": max(1, iterations),
            "sample_size": max(1, sample_size),
            "exploration": float(exploration),
            "best_score": _apo_score(best["system_prompt_candidate"], summary),
            "history": [],
            "note": "APO\u5b9e\u9a8c\u6a21\u5f0f\uff1a\u5f53\u524d\u8bad\u7ec3\u7a97\u53e3\u65e0\u53ef\u7528\u589e\u91cf\u4fe1\u53f7\uff0c\u672a\u751f\u6210\u65b0\u589e\u63d0\u793a\u8bcd\u3002",
        }
    best_score = _apo_score(best["system_prompt_candidate"], summary)
    history: List[Dict[str, Any]] = []

    for step in range(1, max(1, iterations) + 1):
        local_best = dict(best)
        local_best_score = best_score
        tried = 0
        for _ in range(max(1, sample_size)):
            tried += 1
            k = max(1, int(len(pool) * max(0.15, min(1.0, exploration))))
            picks = rng.sample(pool, k=min(k, len(pool)))
            addon = "\n- ".join(picks)

            candidate = dict(best)
            candidate["system_prompt_candidate"] = append_unique_bullets(
                best["system_prompt_candidate"],
                f"# APO Iter {step}",
                picks,
            )
            s = _apo_score(candidate["system_prompt_candidate"], summary)
            if s > local_best_score:
                local_best = candidate
                local_best_score = s

        improved = local_best_score > best_score
        if improved:
            best = local_best
            best_score = local_best_score
        history.append(
            {
                "iter": step,
                "tried": tried,
                "best_score": local_best_score,
                "accepted": improved,
            }
        )

    apo_result = {
        "algo": "apo",
        "iterations": max(1, iterations),
        "sample_size": max(1, sample_size),
        "exploration": float(exploration),
        "best_score": best_score,
        "history": history,
        "note": "APO\u5b9e\u9a8c\u6a21\u5f0f\uff1a\u5f53\u524d\u4e3a\u57fa\u4e8e\u8f68\u8ff9\u9519\u8bef\u5206\u5e03\u7684\u79bb\u7ebf\u5019\u9009\u641c\u7d22\uff0c\u4e0d\u6d89\u53ca\u6a21\u578b\u6743\u91cd\u66f4\u65b0\u3002",
    }
    return best, apo_result


def _normalize_bullet_text(text: str) -> str:
    t = str(text or "").strip().lower()
    t = t.replace("\uff08", "(").replace("\uff09", ")").replace("\uff1a", ":")
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[`'\".,;:!?()\[\]{}\-_/\\|]", "", t)
    return t


_ERROR_PATTERN_LIBRARY: List[Dict[str, Any]] = [
    {
        "tag": "sep2_unsolved_equations",
        "etype": "config",
        "match_any": ["sep2", "\u65b9\u7a0b\u65e0\u89e3", "\u65e0\u89e3\u7684\u89c4\u5b9a"],
        "signals": ["sep2", "\u65b9\u7a0b\u65e0\u89e3", "\u5206\u7387", "\u7269\u6599\u5e73\u8861", "\u89c4\u8303\u51b2\u7a81"],
        "bullets": {
            "schema_check": [
                "\u65b0\u589e\u68c0\u67e5\uff1aSep2 \u5206\u79bb\u89c4\u8303\u63d0\u4ea4\u524d\u6821\u9a8c\u7ec4\u5206\u5206\u7387\u8303\u56f4\u4e0e\u548c\u7ea6\u675f\uff0c\u907f\u514d\u4e92\u76f8\u77db\u76fe\u5bfc\u81f4\u65b9\u7a0b\u65e0\u89e3\u3002",
            ],
            "thought": [
                "\u65b0\u589e\u601d\u8003\u6b65\u9aa4\uff1aSep2 \u62a5\u65b9\u7a0b\u65e0\u89e3\u65f6\u5148\u6700\u5c0f\u5316\u89c4\u8303\u96c6\uff0c\u4ec5\u4fdd\u7559\u4e3b\u7ea6\u675f\u9010\u6b65\u6062\u590d\u5176\u4f59\u7ea6\u675f\u3002",
            ],
            "system": [
                "\u65b0\u589e\u6267\u884c\u7b56\u7565\uff1aSep2 \u5148\u7528\u6700\u5c0f\u53ef\u884c\u5206\u79bb\u89c4\u8303\u8dd1\u901a\uff0c\u518d\u6309\u76ee\u6807\u7eaf\u5ea6\u9010\u6b65\u6536\u7d27\u3002",
            ],
        },
    },
    {
        "tag": "tear_stream_invalid",
        "etype": "config",
        "match_any": ["\u6495\u88c2\u6d41\u80a1", "tear stream", "\u4e0d\u53ef\u4ee5\u662f\u6d41\u7a0b\u4e2d\u7684\u8fdb\u6599\u6d41\u80a1", "\u4e0d\u53ef\u4ee5\u662f\u6d41\u7a0b\u4e2d\u7684\u4ea7\u54c1\u6d41\u80a1"],
        "signals": ["\u6495\u88c2\u6d41\u80a1", "\u5faa\u73af\u6d41", "\u8fdb\u6599\u6d41\u80a1", "\u4ea7\u54c1\u6d41\u80a1", "tear"],
        "bullets": {
            "schema_check": [
                "\u65b0\u589e\u68c0\u67e5\uff1a\u5faa\u73af\u6536\u655b\u8bbe\u7f6e\u65f6\u7981\u6b62\u5c06\u8fdb\u6599\u6d41\u80a1\u6216\u4ea7\u54c1\u6d41\u80a1\u914d\u7f6e\u4e3a\u6495\u88c2\u6d41\u80a1\u3002",
            ],
            "thought": [
                "\u65b0\u589e\u601d\u8003\u6b65\u9aa4\uff1a\u51fa\u73b0\u6495\u88c2\u6d41\u80a1\u7ea6\u675f\u9519\u8bef\u65f6\uff0c\u5148\u91cd\u9009\u5185\u90e8\u5faa\u73af\u6d41\u80a1\u5e76\u4fdd\u6301\u5176\u8fde\u63a5\u95ed\u5408\u3002",
            ],
            "system": [
                "\u65b0\u589e\u6267\u884c\u7b56\u7565\uff1a\u6d89\u53ca\u5faa\u73af\u6d41\u7a0b\u5148\u9a8c\u8bc1\u6536\u655b\u56de\u8def\u62d3\u6251\uff0c\u518d\u63d0\u4ea4\u6495\u88c2\u6d41\u80a1\u8bbe\u7f6e\u3002",
            ],
        },
    },
    {
        "tag": "extract_invalid_symbol",
        "etype": "config",
        "match_any": ["extract", "\u65e0\u6548\u7b26\u53f7\u503c", "none\u4e0d\u662f\u4e00\u4e2a\u6709\u6548\u503c", "isothermal\u4e0d\u662f\u4e00\u4e2a\u6709\u6548\u503c"],
        "signals": ["extract", "\u65e0\u6548\u7b26\u53f7\u503c", "\u679a\u4e3e\u503c", "\u5408\u6cd5\u53d6\u503c", "isothermal", "none"],
        "bullets": {
            "schema_check": [
                "\u65b0\u589e\u68c0\u67e5\uff1aExtract \u5355\u5143\u679a\u4e3e\u5b57\u6bb5\u5fc5\u987b\u4f7f\u7528 schema \u5141\u8bb8\u503c\uff0c\u7981\u6b62\u63d0\u4ea4 NONE/ISOTHERMAL \u7b49\u975e\u6cd5\u7b26\u53f7\u3002",
            ],
            "thought": [
                "\u65b0\u589e\u601d\u8003\u6b65\u9aa4\uff1aExtract \u914d\u7f6e\u5931\u8d25\u65f6\u4f18\u5148\u56de\u67e5\u679a\u4e3e\u5b57\u6bb5\u5408\u6cd5\u503c\uff0c\u518d\u8c03\u6574\u64cd\u4f5c\u6761\u4ef6\u3002",
            ],
            "system": [
                "\u65b0\u589e\u6267\u884c\u7b56\u7565\uff1aExtract \u5148\u586b\u5145\u6700\u5c0f\u5fc5\u586b\u5b57\u6bb5\u5e76\u901a\u8fc7\u679a\u4e3e\u6821\u9a8c\uff0c\u518d\u8865\u5145\u9ad8\u7ea7\u64cd\u4f5c\u53c2\u6570\u3002",
            ],
        },
    },
    {
        "tag": "runtime_no_inlet_streams",
        "etype": "runtime",
        "match_any": ["there are no inlet streams", "\u6ca1\u6709\u5165\u53e3\u7269\u6d41", "no inlet streams"],
        "signals": ["\u5165\u53e3\u7269\u6d41", "inlet", "\u6d41\u7a0b\u8fde\u63a5", "\u6d41\u5411"],
        "bullets": {
            "schema_check": [
                "\u65b0\u589e\u68c0\u67e5\uff1a\u6d41\u7a0b\u8fd0\u884c\u524d\u9a8c\u8bc1\u81f3\u5c11\u5b58\u5728\u4e00\u80a1\u5165\u53e3\u7269\u6d41\u4e14\u5df2\u8fde\u63a5\u5230\u9996\u4e2a\u5355\u5143\u3002",
            ],
            "thought": [
                "\u65b0\u589e\u601d\u8003\u6b65\u9aa4\uff1a\u8fd0\u884c\u62a5\u65e0\u5165\u53e3\u7269\u6d41\u65f6\u5148\u68c0\u67e5\u6d41\u80a1\u547d\u540d\u3001\u8fde\u63a5\u5173\u7cfb\u548c\u8fdb\u6599\u6807\u8bb0\u3002",
            ],
            "system": [
                "\u65b0\u589e\u6267\u884c\u7b56\u7565\uff1a\u6d41\u7a0b\u7c7b\u4efb\u52a1\u5148\u6784\u5efa\u5e76\u9a8c\u8bc1\u8fdb\u6599-\u5355\u5143-\u4ea7\u54c1\u7684\u4e3b\u5e72\u8fde\u63a5\u518d\u8fd0\u884c\u3002",
            ],
        },
    },
    {
        "tag": "runtime_missing_block_paragraph",
        "etype": "runtime",
        "match_any": ["appears in the flowsheet, but no block paragraph", "no block paragraph", "\u672a\u8f93\u5165block\u6bb5"],
        "signals": ["block paragraph", "block", "\u6d41\u7a0b\u56fe\u6709\u5757\u65e0\u914d\u7f6e", "\u672a\u914d\u7f6e\u5355\u5143"],
        "bullets": {
            "schema_check": [
                "\u65b0\u589e\u68c0\u67e5\uff1a\u6d41\u7a0b\u56fe\u4e2d\u6bcf\u4e2a\u5355\u5143\u5757\u90fd\u5fc5\u987b\u6709\u5bf9\u5e94\u914d\u7f6e\u6bb5\uff0c\u7981\u6b62\u4ec5\u5b58\u5728\u62d3\u6251\u4e0d\u586b\u914d\u7f6e\u3002",
            ],
            "thought": [
                "\u65b0\u589e\u601d\u8003\u6b65\u9aa4\uff1a\u62a5 block \u7f3a\u5931\u914d\u7f6e\u65f6\u6309\u6d41\u7a0b\u987a\u5e8f\u8865\u9f50\u7f3a\u5931\u5355\u5143\u53c2\u6570\u540e\u91cd\u8bd5\u3002",
            ],
            "system": [
                "\u65b0\u589e\u6267\u884c\u7b56\u7565\uff1a\u6d41\u7a0b\u642d\u5efa\u5b8c\u6210\u540e\u6267\u884c\u5757\u914d\u7f6e\u5b8c\u6574\u6027\u68c0\u67e5\uff0c\u901a\u8fc7\u540e\u518d run_simulation\u3002",
            ],
        },
    },
]


def append_unique_bullets(base_text: str, section_title: str, bullets: List[str]) -> str:
    base = (base_text or "").strip()
    existing: Set[str] = set()
    for line in base.splitlines():
        s = line.strip()
        if s.startswith("- "):
            existing.add(_normalize_bullet_text(s[2:].strip()))
    new_bullets: List[str] = []
    for bullet in bullets:
        t = str(bullet or "").strip()
        if not t:
            continue
        nt = _normalize_bullet_text(t)
        if nt in existing:
            continue
        existing.add(nt)
        new_bullets.append(t)
    if not new_bullets:
        return base
    return base + f"\n\n{section_title}\n- " + "\n- ".join(new_bullets)


def _dedup_keep_order(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for item in items:
        t = str(item or "").strip()
        nt = _normalize_bullet_text(t)
        if not t or nt in seen:
            continue
        seen.add(nt)
        out.append(t)
    return out


def _extract_error_pattern_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    top_errors = summary.get("top_errors", []) or []
    matched: List[Dict[str, Any]] = []
    for pattern in _ERROR_PATTERN_LIBRARY:
        match_any = [str(x).lower() for x in pattern.get("match_any", [])]
        total_count = 0
        example = ""
        for item in top_errors:
            err = str(item.get("error", "")).lower()
            cnt = int(item.get("count", 0) or 0)
            if any(key in err for key in match_any):
                total_count += cnt
                if not example:
                    example = str(item.get("error", ""))[:220]
        if total_count > 0:
            matched.append(
                {
                    "tag": str(pattern.get("tag")),
                    "etype": str(pattern.get("etype", "other")),
                    "count": total_count,
                    "signals": pattern.get("signals", []),
                    "example": example,
                }
            )
    matched.sort(key=lambda x: int(x.get("count", 0)), reverse=True)
    return {"matched_patterns": matched, "matched_count": len(matched)}


def _build_template_additions(pattern_summary: Dict[str, Any]) -> Dict[str, List[str]]:
    add_system: List[str] = []
    add_schema: List[str] = []
    add_thought: List[str] = []
    matched_tags = {str(x.get("tag")) for x in pattern_summary.get("matched_patterns", [])}
    for pattern in _ERROR_PATTERN_LIBRARY:
        if str(pattern.get("tag")) not in matched_tags:
            continue
        etype = str(pattern.get("etype", "other")).strip().lower()
        bullets = pattern.get("bullets", {}) or {}
        # Strict ownership:
        # - config failure patterns -> schema_check prompt
        # - runtime failure patterns -> thought prompt
        # - system prompt is reserved for tool orchestration guidance
        if etype == "config":
            add_schema.extend([str(x) for x in bullets.get("schema_check", [])])
        elif etype == "runtime":
            add_thought.extend([str(x) for x in bullets.get("thought", [])])
    return {
        "system": _dedup_keep_order(add_system),
        "schema_check": _dedup_keep_order(add_schema),
        "thought": _dedup_keep_order(add_thought),
    }



def _apo_score_candidate(candidate: Dict[str, str], summary: Dict[str, Any]) -> float:
    score = 0.0
    system_text = str(candidate.get("system_prompt_candidate", ""))
    schema_text = str(candidate.get("schema_check_prompt_candidate", ""))
    thought_text = str(candidate.get("thought_process_prompt_candidate", ""))
    system_lower = system_text.lower()
    schema_lower = schema_text.lower()
    thought_lower = thought_text.lower()
    top_errors = summary.get("top_errors", []) or []
    error_type_count = summary.get("error_type_count", {}) or {}
    failure_category_count = summary.get("failure_category_count", {}) or {}
    validator_gap_count = summary.get("validator_gap_count", {}) or {}
    pattern_summary = _extract_error_pattern_summary(summary)

    for p in pattern_summary.get("matched_patterns", []):
        cnt = float(p.get("count", 0) or 0)
        etype = str(p.get("etype", "other"))
        signals = [str(x).lower() for x in p.get("signals", [])]
        if etype == "config" and any(sig and (sig in schema_lower) for sig in signals):
            score += 0.09 * cnt
        elif etype == "runtime" and any(sig and (sig in thought_lower) for sig in signals):
            score += 0.07 * cnt

    for item in top_errors:
        err = str(item.get("error", "")).lower()
        cnt = float(item.get("count", 0) or 0)
        if "schema" in err and "schema" in schema_lower:
            score += 0.08 * cnt
        if "timeout" in err and "timeout" in thought_lower:
            score += 0.06 * cnt
        if "unit" in err and "\u5355\u4f4d" in schema_text:
            score += 0.05 * cnt

    config_cnt = float(error_type_count.get("config", 0) or 0)
    runtime_cnt = float(error_type_count.get("runtime", 0) or 0)
    unit_cnt = float(error_type_count.get("unit", 0) or 0)
    if any(k in schema_text for k in ["\u914d\u7f6e", "\u5b57\u6bb5", "\u679a\u4e3e", "\u65b9\u7a0b\u65e0\u89e3", "\u6495\u88c2\u6d41\u80a1", "\u65e0\u6548\u7b26\u53f7"]):
        score += 0.03 * config_cnt
    if any(k in thought_text for k in ["\u8fd0\u884c\u5931\u8d25", "\u6536\u655b", "\u5165\u53e3\u7269\u6d41", "block", "\u6d41\u7a0b\u8fde\u63a5"]):
        score += 0.02 * runtime_cnt
    if "\u5355\u4f4d" in schema_text:
        score += 0.02 * unit_cnt
    if float(failure_category_count.get("simulation_config_error", 0) or 0) > 0 and ("simulation_config_error" in schema_text or "\u5fc5\u586b\u5b57\u6bb5" in schema_text):
        score += 0.08
    if float(failure_category_count.get("result_fetch_error", 0) or 0) + float(failure_category_count.get("result_timeout", 0) or 0) > 0 and ("get_result" in system_text or "\u7ed3\u679c" in system_text):
        score += 0.07
    if float(validator_gap_count.get("change_closed_loop", 0) or 0) > 0 and ("\u95ed\u73af" in thought_text or "get_result" in thought_text):
        score += 0.06
    if float(validator_gap_count.get("process_round_completion", 0) or 0) > 0 and ("\u8f6e\u6b21" in system_text or "stage" in system_lower):
        score += 0.05

    tool_flow_hits = 0
    if "get_schema" in system_lower and "run_simulation" in system_lower:
        tool_flow_hits += 1
    if "get_result" in system_lower:
        tool_flow_hits += 1
    if "\u5de5\u5177\u7b56\u7565" in system_text:
        tool_flow_hits += 1
    score += 0.05 * float(tool_flow_hits)

    score -= max(0.0, (len(system_text) - 1000)) / 8000.0
    score -= max(0.0, (len(schema_text) - 1000)) / 8000.0
    score -= max(0.0, (len(thought_text) - 1000)) / 8000.0
    return round(score, 6)


def run_apo_prompt_optimization(
    *,
    base_candidates: Dict[str, str],
    summary: Dict[str, Any],
    iterations: int,
    sample_size: int,
    exploration: float,
) -> Tuple[Dict[str, str], Dict[str, Any]]:
    rng = random.Random(20260220)
    pool = []  # APO disabled - using LLM-based optimization instead
    best = dict(base_candidates)
    if not pool:
        return best, {
            "algo": "apo",
            "iterations": max(1, iterations),
            "sample_size": max(1, sample_size),
            "exploration": float(exploration),
            "best_score": _apo_score_candidate(best, summary),
            "history": [],
            "note": "APO\u5b9e\u9a8c\u6a21\u5f0f\uff1a\u5f53\u524d\u8bad\u7ec3\u7a97\u53e3\u65e0\u53ef\u7528\u589e\u91cf\u4fe1\u53f7\uff0c\u672a\u751f\u6210\u65b0\u589e\u63d0\u793a\u8bcd\u3002",
        }
    best_score = _apo_score_candidate(best, summary)
    history: List[Dict[str, Any]] = []

    for step in range(1, max(1, iterations) + 1):
        local_best = dict(best)
        local_best_score = best_score
        tried = 0
        for _ in range(max(1, sample_size)):
            tried += 1
            k = max(1, int(len(pool) * max(0.15, min(1.0, exploration))))
            picks = rng.sample(pool, k=min(k, len(pool)))

            candidate = dict(best)
            grouped: Dict[str, List[str]] = {
                "system_prompt_candidate": [],
                "schema_check_prompt_candidate": [],
                "thought_process_prompt_candidate": [],
            }
            for item in picks:
                grouped[str(item.get("target"))].append(str(item.get("bullet", "")))

            if grouped["system_prompt_candidate"]:
                candidate["system_prompt_candidate"] = append_unique_bullets(
                    best["system_prompt_candidate"],
                    f"# APO Iter {step} System",
                    grouped["system_prompt_candidate"],
                )
            if grouped["schema_check_prompt_candidate"]:
                candidate["schema_check_prompt_candidate"] = append_unique_bullets(
                    best["schema_check_prompt_candidate"],
                    f"# APO Iter {step} Checks",
                    grouped["schema_check_prompt_candidate"],
                )
            if grouped["thought_process_prompt_candidate"]:
                candidate["thought_process_prompt_candidate"] = append_unique_bullets(
                    best["thought_process_prompt_candidate"],
                    f"# APO Iter {step} Thinking",
                    grouped["thought_process_prompt_candidate"],
                )

            s = _apo_score_candidate(candidate, summary)
            if s > local_best_score:
                local_best = candidate
                local_best_score = s

        improved = local_best_score > best_score
        if improved:
            best = local_best
            best_score = local_best_score
        history.append(
            {
                "iter": step,
                "tried": tried,
                "best_score": local_best_score,
                "accepted": improved,
            }
        )

    apo_result = {
        "algo": "apo",
        "iterations": max(1, iterations),
        "sample_size": max(1, sample_size),
        "exploration": float(exploration),
        "best_score": best_score,
        "history": history,
        "note": "APO\u5b9e\u9a8c\u6a21\u5f0f\uff1a\u5f53\u524d\u4e3a\u57fa\u4e8e\u8f68\u8ff9\u9519\u8bef\u5206\u5e03\u7684\u79bb\u7ebf\u5019\u9009\u641c\u7d22\uff0c\u4e0d\u6d89\u53ca\u6a21\u578b\u6743\u91cd\u66f4\u65b0\u3002",
    }
    return best, apo_result


def read_prompt_files(prompt_dir: Path) -> Dict[str, str]:
    return {
        "llm_prompt.py": (prompt_dir / "llm_prompt.py").read_text(encoding="utf-8"),
        "schema_check.py": (prompt_dir / "schema_check.py").read_text(encoding="utf-8"),
        "thought_process.py": (prompt_dir / "thought_process.py").read_text(encoding="utf-8"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline training and prompt artifact generation")
    parser.add_argument("--db-path", default="/run/code/dinglei/aspen_simulation_n../data/training/aspen_trajectories.db")
    parser.add_argument("--mode", default="test")
    parser.add_argument("--prompt-dir", default="/run/code/dinglei/aspen_simulation_n../prompt")
    parser.add_argument("--schema-dir", default="/run/code/dinglei/aspen_simulation_new/backend/aspen/schema")
    parser.add_argument("--schema-target", default="/run/code/dinglei/aspen_simulation_new/backend/rl/outputs/training_runs/schema_descriptions_0211.json")
    parser.add_argument("--output-root", default="/run/code/dinglei/aspen_simulation_new/backend/rl/outputs/training_runs")
    parser.add_argument("--rollout-ids-file", default="")
    parser.add_argument("--time-from", type=float, default=None)
    parser.add_argument("--time-to", type=float, default=None)
    parser.add_argument("--tag", default="")
    parser.add_argument("--algo", default="rgo", choices=["rgo", "apo"])
    parser.add_argument("--apo-iters", type=int, default=4)
    parser.add_argument("--apo-sample-size", type=int, default=6)
    parser.add_argument("--apo-exploration", type=float, default=0.35)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db_path)
    prompt_dir = Path(args.prompt_dir)
    schema_dir = Path(args.schema_dir)
    schema_target = Path(args.schema_target)
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_tag = _safe_tag(args.tag or stamp)
    out_dir = output_root / f"run_{run_tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    rollout_ids = _load_rollout_ids(args.rollout_ids_file)
    rollouts, span_map = load_rollouts_and_spans(
        db_path=db_path,
        mode=args.mode,
        rollout_ids=rollout_ids if rollout_ids else None,
        time_from=args.time_from,
        time_to=args.time_to,
    )
    summary = summarize_training_data(rollouts, span_map)
    memory_rows = load_memory_usage_rows(db_path, rollout_ids=rollout_ids if rollout_ids else None)
    summary["memory_usage_summary"] = summarize_memory_usage(memory_rows)
    pattern_summary = _extract_error_pattern_summary(summary)
    schema_desc = extract_schema_descriptions(schema_dir, max_items=400)
    target_bootstrapped = False
    if not schema_target.exists():
        schema_target.parent.mkdir(parents=True, exist_ok=True)
        schema_target.write_text(json.dumps(schema_desc, ensure_ascii=False, indent=2), encoding="utf-8")
        target_bootstrapped = True
    target_schema_rows = _load_json_list(schema_target)
    schema_delta_rows = [] if target_bootstrapped else build_schema_delta_rows(schema_desc, target_schema_rows)
    prompts = read_prompt_files(prompt_dir)

    # dynamic_prompt_additions removed - using LLM-based optimization only

    base_candidates = build_prompt_candidates(
        base_system=prompts["llm_prompt.py"],
        base_schema_check=prompts["schema_check.py"],
        base_thought=prompts["thought_process.py"],
        summary=summary,
        prompts=prompts,
    )
    apo_result: Optional[Dict[str, Any]] = None
    if args.algo == "apo":
        candidates, apo_result = run_apo_prompt_optimization(
            base_candidates=base_candidates,
            summary=summary,
            iterations=args.apo_iters,
            sample_size=args.apo_sample_size,
            exploration=args.apo_exploration,
        )
    else:
        candidates = base_candidates

    training_result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "mode": args.mode,
        "algo": args.algo,
        "db_path": str(db_path),
        "window": {
            "rollout_ids_file": args.rollout_ids_file or None,
            "rollout_ids_count": len(rollout_ids),
            "time_from": args.time_from,
            "time_to": args.time_to,
        },
        "algo_config": {
            "apo_iters": args.apo_iters,
            "apo_sample_size": args.apo_sample_size,
            "apo_exploration": args.apo_exploration,
        },
        "summary": summary,
        "prompt_increment_rationale": [],  # rationale removed with rule-based system
        "matched_error_patterns": pattern_summary,
        "schema_delta_summary": {
            "target_path": str(schema_target),
            "target_count": len(target_schema_rows),
            "current_count": len(schema_desc),
            "delta_count": len(schema_delta_rows),
            "target_bootstrapped": bool(target_bootstrapped),
        },
        "conclusion": {
            "quality": "not_ideal" if summary.get("success_rate", 0.0) < 0.8 else "acceptable",
            "recommendation": "\u5efa\u8bae\u8bc4\u5ba1\u5019\u9009\u63d0\u793a\u8bcd\u548cschema\uff0c\u518d\u51b3\u5b9a\u662f\u5426\u53d1\u5e03",
        },
    }
    if apo_result is not None:
        training_result["apo_result"] = apo_result

    (out_dir / "training_result.json").write_text(json.dumps(training_result, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "error_pattern_summary.json").write_text(json.dumps(pattern_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if apo_result is not None:
        (out_dir / "apo_result.json").write_text(json.dumps(apo_result, ensure_ascii=False, indent=2), encoding="utf-8")

    schema_candidate_name = f"schema_descriptions_candidate-{out_dir.name}.json"
    if schema_delta_rows:
        (out_dir / schema_candidate_name).write_text(json.dumps(schema_delta_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    system_increment = _build_increment_candidate_text(
        _extract_increment_bullets(prompts["llm_prompt.py"], candidates["system_prompt_candidate"]),
        "system_prompt",
        out_dir.name,
    )
    schema_increment = _build_increment_candidate_text(
        _extract_increment_bullets(prompts["schema_check.py"], candidates["schema_check_prompt_candidate"]),
        "schema_check_prompt",
        out_dir.name,
    )
    thought_increment = _build_increment_candidate_text(
        _extract_increment_bullets(prompts["thought_process.py"], candidates["thought_process_prompt_candidate"]),
        "thought_process_prompt",
        out_dir.name,
    )

    run_suffix = out_dir.name if out_dir.name.startswith("run_") else f"run_{out_dir.name}"
    system_increment_name = f"system_prompt_candidate-{run_suffix}.txt"
    schema_increment_name = f"schema_check_prompt_candidate-{run_suffix}.txt"
    thought_increment_name = f"thought_process_prompt_candidate-{run_suffix}.txt"

    prompt_artifacts: List[str] = []
    if system_increment:
        (out_dir / system_increment_name).write_text(system_increment, encoding="utf-8")
        prompt_artifacts.append(f"- {system_increment_name} (\u8bad\u7ec3\u540e\u589e\u91cf)")
    if schema_increment:
        (out_dir / schema_increment_name).write_text(schema_increment, encoding="utf-8")
        prompt_artifacts.append(f"- {schema_increment_name} (\u8bad\u7ec3\u540e\u589e\u91cf)")
    if thought_increment:
        (out_dir / thought_increment_name).write_text(thought_increment, encoding="utf-8")
        prompt_artifacts.append(f"- {thought_increment_name} (\u8bad\u7ec3\u540e\u589e\u91cf)")


    prompt_version_manifest = {
        "version_id": f"pv_{out_dir.name}",
        "run_id": out_dir.name,
        "algo": args.algo,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "increment_files": {
            "system": system_increment_name if system_increment else None,
            "schema_check": schema_increment_name if schema_increment else None,
            "thought": thought_increment_name if thought_increment else None,
        },
        "system_increment_file": system_increment_name if system_increment else None,
        "schema_increment_file": schema_increment_name if schema_increment else None,
        "thought_increment_file": thought_increment_name if thought_increment else None,
        "prompt_increment_rationale": [],  # rationale removed with rule-based system
        "summary_digest": {
            "success_rate": summary.get("success_rate", 0.0),
            "avg_reward": summary.get("avg_reward", 0.0),
            "top_failure_categories": summary.get("top_failure_categories", [])[:5],
            "top_validator_gaps": summary.get("top_validator_gaps", [])[:5],
        },
    }
    (out_dir / "prompt_version_manifest.json").write_text(
        json.dumps(prompt_version_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report_lines = [
        "# Offline Training Report",
        "",
        f"- Run Dir: {out_dir}",
        f"- Mode: {args.mode}",
        f"- Algo: {args.algo}",
        f"- Rollout IDs Filter: {len(rollout_ids)}",
        f"- Time Window: {args.time_from} ~ {args.time_to}",
        f"- Total Rollouts: {summary['total_rollouts']}",
        f"- Success Rate: {summary['success_rate']:.2%}",
        f"- Avg Reward: {summary['avg_reward']}",
        "",
        "## Status Count",
        json.dumps(summary["status_count"], ensure_ascii=False, indent=2),
        "",
        "## Top Errors",
        json.dumps(summary["top_errors"], ensure_ascii=False, indent=2),
        "",
        "## Top Failure Categories",
        json.dumps(summary.get("top_failure_categories", []), ensure_ascii=False, indent=2),
        "",
        "## Validator Gaps",
        json.dumps(summary.get("top_validator_gaps", []), ensure_ascii=False, indent=2),
        "",
        "## Failure Rollout Samples",
        json.dumps(summary.get("failure_rollout_samples", []), ensure_ascii=False, indent=2),
        "",
        "## Progress Stage Count",
        json.dumps(summary.get("progress_stage_count", {}), ensure_ascii=False, indent=2),
        "",
        "## Memory Usage Summary",
        json.dumps(summary.get("memory_usage_summary", {}), ensure_ascii=False, indent=2),
        "",
        "## Matched Error Patterns",
        json.dumps(pattern_summary, ensure_ascii=False, indent=2),
        "",
        "## Prompt Increment Rationale",
        json.dumps([], ensure_ascii=False, indent=2),  # rationale removed with rule-based system
        "",
        "## Prompt Artifacts",
        *prompt_artifacts,
        "- \u65e0\u65b0\u589e\u63d0\u793a\u8bcd\u589e\u91cf\u6587\u4ef6" if not prompt_artifacts else "",
        "- apo_result.json (only for APO)",
        "",
        "## Schema Artifacts",
        f"- {schema_candidate_name} (schema\u589e\u91cf/\u66f4\u65b0)" if schema_delta_rows else "- \u65e0\u65b0\u589eschema\u589e\u91cf\u6587\u4ef6",
        "",
        "## Notes",
        "- \u672c\u6b21\u811a\u672c\u4e0d\u4f1a\u4fee\u6539 backend/prompt \u4e0b\u539f\u59cb\u6587\u4ef6\u3002",
        "- \u82e5\u9700\u4e0a\u7ebf\uff0c\u8bf7\u4eba\u5de5\u8bc4\u5ba1\u540e\u66ff\u6362\u3002",
    ]
    (out_dir / "training_report.md").write_text("\n".join([x for x in report_lines if x != ""]) + "\n", encoding="utf-8")

    # Online mode: run comparison test
    comparison_report = None
    if args.mode == "online":
        try:
            from online_comparison import run_online_comparison
            print("Running online comparison test...")
            comparison_report = run_online_comparison(
                db_path=db_path,
                rollouts=rollouts,
                new_prompts=candidates,
                prompt_dir=prompt_dir,
            )
            (out_dir / "comparison_report.json").write_text(
                json.dumps(comparison_report, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            training_result["comparison_report"] = comparison_report
            print(f"Comparison report saved: {out_dir / 'comparison_report.json'}")
        except Exception as e:
            print(f"Warning: Online comparison failed: {e}")
            comparison_report = {"error": str(e)}

    print(f"Saved training artifacts to: {out_dir}")
    print(json.dumps({"success_rate": summary["success_rate"], "total_rollouts": summary["total_rollouts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()


