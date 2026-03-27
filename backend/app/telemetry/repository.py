from __future__ import annotations

import sqlite3
import time
import uuid
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def db_connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_rollout_tables(db_path: Path) -> None:
    with db_connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS rollouts (
                rollout_id TEXT PRIMARY KEY,
                attempt_id TEXT,
                status TEXT NOT NULL,
                mode TEXT,
                start_time REAL,
                end_time REAL,
                input_json TEXT,
                metadata_json TEXT,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS spans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rollout_id TEXT NOT NULL,
                span_id TEXT,
                name TEXT NOT NULL,
                start_time REAL,
                end_time REAL,
                attributes_json TEXT,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS prompt_versions (
                prompt_version_id TEXT PRIMARY KEY,
                source_run_id TEXT,
                status TEXT NOT NULL,
                assignment_mode TEXT,
                canary_ratio REAL,
                manifest_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS prompt_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rollout_id TEXT NOT NULL,
                prompt_version_id TEXT,
                bucket TEXT,
                assignment_json TEXT,
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_rollouts_start_time ON rollouts(start_time DESC);
            CREATE INDEX IF NOT EXISTS idx_spans_rollout_id ON spans(rollout_id);
            CREATE INDEX IF NOT EXISTS idx_spans_name ON spans(name);
            CREATE INDEX IF NOT EXISTS idx_prompt_versions_updated ON prompt_versions(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_prompt_assignments_rollout ON prompt_assignments(rollout_id);

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE,
                phone TEXT NOT NULL UNIQUE,
                password TEXT DEFAULT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                nickname TEXT DEFAULT '',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                title TEXT DEFAULT '新对话',
                messages_json TEXT DEFAULT '[]',
                updated_at REAL NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id, updated_at DESC);
            """
        )
        # Add user_id column to rollouts if missing
        try:
            conn.execute("ALTER TABLE rollouts ADD COLUMN user_id TEXT DEFAULT NULL")
        except Exception:
            pass
        conn.commit()


def persist_rollout_start(
    *,
    db_path: Path,
    json_dumps: Callable[[Any], str],
    rollout_id: str,
    attempt_id: str,
    status: str,
    mode: str,
    start_time: float,
    input_obj: Dict[str, Any],
    metadata_obj: Dict[str, Any],
    user_id: Optional[str] = None,
) -> None:
    now = time.time()
    with db_connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO rollouts(
                rollout_id, attempt_id, status, mode, start_time, end_time,
                input_json, metadata_json, user_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(rollout_id) DO UPDATE SET
                attempt_id=excluded.attempt_id,
                status=excluded.status,
                mode=excluded.mode,
                start_time=excluded.start_time,
                input_json=excluded.input_json,
                metadata_json=excluded.metadata_json,
                user_id=excluded.user_id,
                updated_at=excluded.updated_at
            """,
            (
                rollout_id,
                attempt_id,
                status,
                mode,
                start_time,
                None,
                json_dumps(input_obj),
                json_dumps(metadata_obj),
                user_id,
                now,
            ),
        )
        conn.commit()


def persist_rollout_status(db_path: Path, rollout_id: str, status: str, end_time: Optional[float] = None) -> None:
    now = time.time()
    with db_connect(db_path) as conn:
        conn.execute(
            """
            UPDATE rollouts
            SET status = ?, end_time = ?, updated_at = ?
            WHERE rollout_id = ?
            """,
            (status, end_time if end_time is not None else now, now, rollout_id),
        )
        conn.commit()


def persist_span(
    *,
    db_path: Path,
    json_dumps: Callable[[Any], str],
    rollout_id: str,
    name: str,
    attributes: Dict[str, Any],
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    span_id: Optional[str] = None,
) -> None:
    now = time.time()
    s = start_time if start_time is not None else now
    e = end_time if end_time is not None else now
    sid = span_id or f"span_{uuid.uuid4().hex[:16]}"

    with db_connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO spans(
                rollout_id, span_id, name, start_time, end_time, attributes_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (rollout_id, sid, name, s, e, json_dumps(attributes), now),
        )
        conn.commit()


def upsert_prompt_version(
    *,
    db_path: Path,
    json_dumps: Callable[[Any], str],
    prompt_version_id: str,
    source_run_id: Optional[str],
    status: str,
    assignment_mode: Optional[str],
    canary_ratio: Optional[float],
    manifest_obj: Dict[str, Any],
) -> None:
    now = time.time()
    with db_connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO prompt_versions(
                prompt_version_id, source_run_id, status, assignment_mode, canary_ratio,
                manifest_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(prompt_version_id) DO UPDATE SET
                source_run_id=excluded.source_run_id,
                status=excluded.status,
                assignment_mode=excluded.assignment_mode,
                canary_ratio=excluded.canary_ratio,
                manifest_json=excluded.manifest_json,
                updated_at=excluded.updated_at
            """,
            (
                prompt_version_id,
                source_run_id,
                status,
                assignment_mode,
                canary_ratio,
                json_dumps(manifest_obj),
                now,
                now,
            ),
        )
        conn.commit()


def record_prompt_assignment(
    *,
    db_path: Path,
    json_dumps: Callable[[Any], str],
    rollout_id: str,
    prompt_version_id: Optional[str],
    bucket: str,
    assignment_obj: Dict[str, Any],
) -> None:
    now = time.time()
    with db_connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO prompt_assignments(
                rollout_id, prompt_version_id, bucket, assignment_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                rollout_id,
                prompt_version_id,
                bucket,
                json_dumps(assignment_obj),
                now,
            ),
        )
        conn.commit()


def _parse_json_maybe(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _extract_memory_search_summary(attrs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    tool_results = attrs.get("tool_results")
    if not isinstance(tool_results, list):
        return None

    for item in tool_results:
        if not isinstance(item, dict):
            continue
        if str(item.get("tool_name") or "") != "memory_search_experience":
            continue
        parsed = _parse_json_maybe(item.get("result"))
        if not isinstance(parsed, dict):
            continue
        items = parsed.get("items")
        hits = items if isinstance(items, list) else []
        query_text = str(parsed.get("query") or "").strip()
        task_type = str(parsed.get("task_type") or "") or None
        enrichment_keys: List[str] = []
        enrichment_values: Dict[str, List[str]] = {}
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            match = hit.get("match")
            if not isinstance(match, dict):
                continue
            enrichment = match.get("query_enrichment")
            if not isinstance(enrichment, dict):
                continue
            for key, value in enrichment.items():
                if value and key not in enrichment_keys:
                    enrichment_keys.append(str(key))
                values = value if isinstance(value, list) else [value]
                merged = enrichment_values.setdefault(str(key), [])
                for entry in values:
                    text = str(entry or "").strip()
                    if text and text not in merged:
                        merged.append(text)
        if not enrichment_values:
            fallback = _fallback_query_enrichment(query_text=query_text, task_type=task_type)
            for key, values in fallback.items():
                if values:
                    enrichment_keys.append(key)
                    enrichment_values[key] = values
        return {
            "memory_search_used": True,
            "memory_hit_count": int(parsed.get("total") or len(hits) or 0),
            "memory_enrichment_keys": enrichment_keys,
            "memory_enrichment": enrichment_values,
        }
    return None


def _fallback_query_enrichment(*, query_text: str, task_type: Optional[str]) -> Dict[str, List[str]]:
    text = str(query_text or "").strip()
    lowered = text.lower()
    enrichment: Dict[str, List[str]] = {}

    if task_type:
        enrichment["task_type"] = [str(task_type)]

    methods: List[str] = []
    for method in ("CHAO-SEA", "UNIQUAC", "ELECNRTL", "NRTL-HOC", "NRTL", "PENG-ROB", "SRK", "IDEAL"):
        if method.lower() in lowered:
            methods.append(method)
    if methods:
        enrichment["methods"] = methods

    equipment: List[str] = []
    if any(token in lowered for token in ("mix", "??")):
        equipment.append("mixer")
    if any(token in lowered for token in ("heatx", "heater", "??")):
        equipment.append("heatx")
    if any(token in lowered for token in ("pump", "?")):
        equipment.append("pump")
    if any(token in lowered for token in ("compress", "compr", "??")):
        equipment.append("compr")
    if any(token in lowered for token in ("valve", "?")):
        equipment.append("valve")
    if any(token in lowered for token in ("flash", "??")):
        equipment.append("flash")
    if any(token in lowered for token in ("separator", "sep", "???")):
        equipment.append("sep")
    if any(token in lowered for token in ("radfrac", "column", "tower", "??")):
        equipment.append("radfrac")
    if equipment:
        enrichment["equipment"] = list(dict.fromkeys(equipment))

    streams = re.findall(r"\b(?:FEED\d+|PRODUCT|RECYCLE|DISTILLATE|BOTTOMS|TOP\d+|BOT\d+|VAPOR\d+|LIQ\d+)\b", text, flags=re.IGNORECASE)
    if streams:
        enrichment["streams"] = list(dict.fromkeys(s.upper() for s in streams))

    return enrichment


def query_rollouts(
    *,
    db_path: Path,
    json_loads_or_default: Callable[[str | None, Any], Any],
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    with db_connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT r.rollout_id, r.attempt_id, r.status, r.mode, r.start_time, r.end_time, r.input_json, r.metadata_json, r.user_id, COALESCE(u.phone, "") AS user_phone
            FROM rollouts r
            LEFT JOIN users u ON r.user_id = u.user_id
            ORDER BY r.start_time DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

        rollout_ids = [r["rollout_id"] for r in rows]
        reward_summary_map: Dict[str, Dict[str, Any]] = {}
        memory_summary_map: Dict[str, Dict[str, Any]] = {}
        tool_call_count_map: Dict[str, int] = {}
        if rollout_ids:
            placeholders = ",".join("?" for _ in rollout_ids)
            reward_rows = conn.execute(
                f"""
                SELECT s.rollout_id, s.attributes_json
                FROM spans AS s
                INNER JOIN (
                    SELECT rollout_id, MAX(id) AS max_id
                    FROM spans
                    WHERE name = 'reward' AND rollout_id IN ({placeholders})
                    GROUP BY rollout_id
                ) AS latest
                ON s.id = latest.max_id
                """,
                rollout_ids,
            ).fetchall()
            for reward_row in reward_rows:
                attrs = json_loads_or_default(reward_row["attributes_json"], {})
                reward_value = attrs.get("reward")
                reward_summary_map[reward_row["rollout_id"]] = {
                    "reward": None if reward_value is None else str(reward_value),
                    "dominant_failure_category": attrs.get("dominant_failure_category") or None,
                }
            # First check memory_retrieval spans (direct memory hits)
            memory_rows = conn.execute(
                f"""
                SELECT rollout_id, attributes_json
                FROM spans
                WHERE name = 'memory_retrieval' AND rollout_id IN ({placeholders})
                ORDER BY id DESC
                """,
                rollout_ids,
            ).fetchall()
            for mem_row in memory_rows:
                if mem_row["rollout_id"] in memory_summary_map:
                    continue
                attrs = json_loads_or_default(mem_row["attributes_json"], {})
                hit_count = attrs.get("hit_count", 0)
                if hit_count > 0:
                    memory_summary_map[mem_row["rollout_id"]] = {
                        "memory_search_used": True,
                        "memory_hit_count": int(hit_count),
                        "memory_enrichment_keys": [],
                        "memory_enrichment": {},
                    }

            # Count tool_execution spans for tool_call_count
            tool_count_rows = conn.execute(
                f"""
                SELECT rollout_id, COUNT(*) as cnt
                FROM spans
                WHERE name = 'tool_execution' AND rollout_id IN ({placeholders})
                GROUP BY rollout_id
                """,
                rollout_ids,
            ).fetchall()
            for tc_row in tool_count_rows:
                tool_call_count_map[tc_row["rollout_id"]] = tc_row["cnt"]

            # Then check tool_execution spans (for memory_search_experience tool)
            tool_rows = conn.execute(
                f"""
                SELECT rollout_id, attributes_json
                FROM spans
                WHERE name = 'tool_execution' AND rollout_id IN ({placeholders})
                ORDER BY id DESC
                """,
                rollout_ids,
            ).fetchall()
            for tool_row in tool_rows:
                if tool_row["rollout_id"] in memory_summary_map:
                    continue
                attrs = json_loads_or_default(tool_row["attributes_json"], {})
                summary = _extract_memory_search_summary(attrs)
                if summary:
                    memory_summary_map[tool_row["rollout_id"]] = summary

    result: List[Dict[str, Any]] = []
    for r in rows:
        metadata = json_loads_or_default(r["metadata_json"], {})
        reward_summary = reward_summary_map.get(
            r["rollout_id"],
            {"reward": None, "dominant_failure_category": None},
        )
        memory_summary = memory_summary_map.get(
            r["rollout_id"],
            {"memory_search_used": False, "memory_hit_count": 0, "memory_enrichment_keys": [], "memory_enrichment": {}},
        )
        result.append(
            {
                "rollout_id": r["rollout_id"],
                "attempt_id": r["attempt_id"],
                "status": r["status"],
                "mode": r["mode"],
                "user_display_name": r["user_phone"] if r["user_phone"] else ("admin" if not r["user_id"] else r["user_id"]),
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "input": json_loads_or_default(r["input_json"], {}),
                "metadata": metadata,
                "summary": {
                    **reward_summary,
                    **memory_summary,
                    "tool_call_count": tool_call_count_map.get(r["rollout_id"], 0),
                    "prompt_version_id": metadata.get("prompt_version_id"),
                    "prompt_applied_version_id": metadata.get("prompt_applied_version_id"),
                    "prompt_bucket": metadata.get("prompt_bucket"),
                },
            }
        )
    return result


def query_spans(
    *,
    db_path: Path,
    json_loads_or_default: Callable[[str | None, Any], Any],
    rollout_id: str,
) -> List[Dict[str, Any]]:
    with db_connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT span_id, name, start_time, end_time, attributes_json
            FROM spans
            WHERE rollout_id = ?
            ORDER BY id ASC
            """,
            (rollout_id,),
        ).fetchall()

    return [
        {
            "span_id": r["span_id"],
            "name": r["name"],
            "start_time": r["start_time"],
            "end_time": r["end_time"],
            "attributes": json_loads_or_default(r["attributes_json"], {}),
        }
        for r in rows
    ]


def query_statistics(
    *,
    db_path: Path,
    json_loads_or_default: Callable[[str | None, Any], Any],
) -> Dict[str, Any]:
    with db_connect(db_path) as conn:
        total_rollouts = conn.execute("SELECT COUNT(1) FROM rollouts").fetchone()[0]
        succeeded = conn.execute("SELECT COUNT(1) FROM rollouts WHERE status = 'succeeded'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(1) FROM rollouts WHERE status = 'failed'").fetchone()[0]
        running = conn.execute("SELECT COUNT(1) FROM rollouts WHERE status = 'running'").fetchone()[0]
        reward_rows = conn.execute("SELECT attributes_json FROM spans WHERE name = 'reward'").fetchall()

    rewards: List[float] = []
    for row in reward_rows:
        attrs = json_loads_or_default(row["attributes_json"], {})
        try:
            rewards.append(float(attrs.get("reward")))
        except Exception:
            continue

    avg_reward = sum(rewards) / len(rewards) if rewards else 0.0
    return {
        "total_rollouts": int(total_rollouts),
        "succeeded": int(succeeded),
        "failed": int(failed),
        "running": int(running),
        "reward_samples": len(rewards),
        "average_reward": round(avg_reward, 6),
        "db_path": str(db_path),
    }


def query_metrics_overview(
    *,
    db_path: Path,
    json_loads_or_default: Callable[[str | None, Any], Any],
    query_statistics_fn: Callable[[], Dict[str, Any]],
    query_memory_quality_metrics_fn: Callable[[], Dict[str, Any]],
) -> Dict[str, Any]:
    base = query_statistics_fn()

    with db_connect(db_path) as conn:
        rollout_rows = conn.execute(
            "SELECT start_time, status FROM rollouts WHERE start_time IS NOT NULL ORDER BY start_time ASC"
        ).fetchall()
        tool_rows = conn.execute(
            "SELECT attributes_json FROM spans WHERE name = 'tool_call_request'"
        ).fetchall()
        error_rows = conn.execute(
            "SELECT rollout_id, attributes_json FROM spans WHERE name = 'tool_execution' AND attributes_json LIKE '%is_error%' ORDER BY id DESC LIMIT 200"
        ).fetchall()
        auto_resume_rows = conn.execute(
            "SELECT attributes_json FROM spans WHERE name = 'auto_resume_result'"
        ).fetchall()
        auto_resume_trigger_rows = conn.execute(
            "SELECT COUNT(1) AS c FROM spans WHERE name = 'auto_resume_triggered'"
        ).fetchone()

    total_tool_calls = 0
    for row in tool_rows:
        attrs = json_loads_or_default(row["attributes_json"], {})
        calls = attrs.get("tool_calls")
        if isinstance(calls, list):
            total_tool_calls += len(calls)

    total_rollouts = max(1, int(base.get("total_rollouts", 0)))
    avg_tool_calls = round(total_tool_calls / total_rollouts, 3)

    # Enhanced error tracking with more details
    err_details: Dict[str, Dict[str, Any]] = {}
    for row in error_rows:
        attrs = json_loads_or_default(row["attributes_json"], {})
        rollout_id = row["rollout_id"]
        
        # Extract errors from tool_results
        tool_results = attrs.get("tool_results", [])
        if not isinstance(tool_results, list):
            continue
            
        for tr in tool_results:
            if not isinstance(tr, dict) or not tr.get("is_error"):
                continue
            
            # Get error message
            result = tr.get("result", {})
            # Parse result if it's a string
            if isinstance(result, str):
                try:
                    import ast
                    result = ast.literal_eval(result)
                except:
                    pass
            
            if isinstance(result, dict):
                raw = str(result.get("error_message", "")).strip()
            else:
                raw = str(result).strip()
            
            if not raw:
                continue
            
            # Get error message: prefer content after ERROR keyword
            if 'ERROR' in raw:
                err_idx = raw.find('ERROR')
                after_error = raw[err_idx + 5:].strip()
                first_line = after_error.split(chr(10))[0].strip() if after_error else ''
                if first_line:
                    key = first_line[:120]
                else:
                    key = raw.splitlines()[0][:120]
            else:
                key = raw.splitlines()[0][:120]
        
            if key not in err_details:
                err_details[key] = {
                    "message": key,
                    "count": 0,
                    "task_type": None,
                    "error_category": None,
                    "equipment_type": None,
                    "error_classification": None,
                    "rollout_ids": []
                }
            
            err_details[key]["count"] += 1
            err_details[key]["rollout_ids"].append(rollout_id)
            
            # Extract task type, equipment type, and error category from tool_results
            tool_results = attrs.get("tool_results", [])
            if isinstance(tool_results, list):
                for tr in tool_results:
                    if not isinstance(tr, dict):
                        continue
                    
                    # Get error category from run_simulation error_type field
                    if not err_details[key]["error_category"]:
                        result_raw = tr.get("result", "")
                        parsed_result = None
                        if isinstance(result_raw, str):
                            try:
                                import ast
                                parsed_result = ast.literal_eval(result_raw)
                            except:
                                try:
                                    parsed_result = json.loads(result_raw)
                                except:
                                    pass
                        elif isinstance(result_raw, dict):
                            parsed_result = result_raw
                        
                        if isinstance(parsed_result, dict):
                            error_type = parsed_result.get("error_type", "")
                            if "运行过程" in error_type:
                                err_details[key]["error_category"] = "runtime"
                            elif "配置" in error_type:
                                err_details[key]["error_category"] = "config"
                        
                        # Fallback to failure_category
                        if not err_details[key]["error_category"]:
                            err_details[key]["error_category"] = tr.get("failure_category")
                    
                    # Try to extract equipment type from tool result
                    if not err_details[key]["equipment_type"]:
                        result = tr.get("result", "")
                        if isinstance(result, str):
                            block_match = re.search(r"block[s]?.*?type[:\s]+([A-Z][A-Za-z0-9]+)", result, re.IGNORECASE)
                            if block_match:
                                err_details[key]["equipment_type"] = block_match.group(1)
            
            # Classify error based on message content
                if not err_details[key]["error_classification"]:
                    msg_lower = key.lower()
                    if any(kw in msg_lower for kw in ["schema", "config", "parameter", "field", "missing", "required"]):
                        err_details[key]["error_classification"] = "配置缺失"
                    elif any(kw in msg_lower for kw in ["converge", "solver", "numerical", "flash"]):
                        err_details[key]["error_classification"] = "收敛失败"
                    elif any(kw in msg_lower for kw in ["timeout", "timed out"]):
                        err_details[key]["error_classification"] = "超时"
                    elif any(kw in msg_lower for kw in ["connection", "network", "http"]):
                        err_details[key]["error_classification"] = "网络错误"
                    else:
                        err_details[key]["error_classification"] = "其他"
    
        # Get task type for each error by querying rollouts
        for err_key, err_info in err_details.items():
            if err_info["rollout_ids"]:
                # Get task type from the first rollout
                rollout_id = err_info["rollout_ids"][0]
                rollout_row = conn.execute(
                    "SELECT metadata_json, input_json FROM rollouts WHERE rollout_id = ?",
                    (rollout_id,)
                ).fetchone()
                if rollout_row:
                    metadata = json_loads_or_default(rollout_row["metadata_json"], {})
                    err_info["task_type"] = metadata.get("task_type")
                    
                    # Infer task_type from user message if not set
                    if not err_info["task_type"]:
                        input_data = json_loads_or_default(rollout_row["input_json"], {})
                        user_msg = input_data.get("user_requirement", "") or metadata.get("user_message", "")
                        if user_msg:
                            msg_lower = user_msg.lower()
                            process_keywords = ["流程", "工艺", "多个", "串联", "并联", "混合后", "分离后", "依次"]
                            if any(kw in msg_lower for kw in process_keywords):
                                err_info["task_type"] = "process"
                            else:
                                err_info["task_type"] = "unit"
                    
                    # Try to get equipment type from metadata if not found yet
                    if not err_info["equipment_type"]:
                        err_info["equipment_type"] = metadata.get("equipment_type")
        
    # Remove rollout_ids from final output (too large)
    # Keep first rollout_id for reference
    for err_info in err_details.values():
        if err_info["rollout_ids"]:
            err_info["rollout_id"] = err_info["rollout_ids"][0]
        err_info.pop("rollout_ids", None)
    # Keep first rollout_id for reference
    top_errors = sorted(
        list(err_details.values()),
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    daily: Dict[str, Dict[str, int]] = {}
    for row in rollout_rows:
        ts = row["start_time"]
        if ts is None:
            continue
        day = time.strftime("%Y-%m-%d", time.localtime(float(ts)))
        rec = daily.setdefault(day, {"total": 0, "succeeded": 0, "failed": 0})
        rec["total"] += 1
        if row["status"] == "succeeded":
            rec["succeeded"] += 1
        elif row["status"] == "failed":
            rec["failed"] += 1

    trend = [
        {"date": k, **v}
        for k, v in sorted(daily.items(), key=lambda x: x[0])[-14:]
    ]

    auto_resume_total = int(auto_resume_trigger_rows["c"]) if auto_resume_trigger_rows else 0
    auto_resume_success = 0
    step_delta_sum = 0.0
    step_delta_count = 0
    for row in auto_resume_rows:
        attrs = json_loads_or_default(row["attributes_json"], {})
        if bool(attrs.get("success")):
            auto_resume_success += 1
        try:
            step_delta = float(attrs.get("step_delta", 0.0))
            step_delta_sum += step_delta
            step_delta_count += 1
        except Exception:
            pass
    auto_resume_success_rate = round(auto_resume_success / auto_resume_total, 4) if auto_resume_total > 0 else 0.0
    avg_step_delta = round(step_delta_sum / step_delta_count, 3) if step_delta_count > 0 else 0.0

    memory_quality = query_memory_quality_metrics_fn()
    prompt_version_overview = query_prompt_version_overview(
        db_path=db_path,
        json_loads_or_default=json_loads_or_default,
        limit=1000,
    )

    return {
        **base,
        "total_tool_calls": total_tool_calls,
        "average_tool_calls_per_rollout": avg_tool_calls,
        "top_errors": top_errors,
        "daily_trend": trend,
        "auto_resume_count": auto_resume_total,
        "auto_resume_success_rate": auto_resume_success_rate,
        "auto_resume_avg_step_delta": avg_step_delta,
        "prompt_version_overview": prompt_version_overview,
        **memory_quality,
    }


def query_prompt_version_overview(
    *,
    db_path: Path,
    json_loads_or_default: Callable[[str | None, Any], Any],
    limit: int = 1000,
) -> Dict[str, Any]:
    with db_connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT rollout_id, prompt_version_id, bucket, assignment_json
            FROM prompt_assignments
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
    if not rows:
        return {"total_assignments": 0, "versions": []}

    rollout_ids = [str(r["rollout_id"]) for r in rows if str(r["rollout_id"] or "").strip()]
    status_map: Dict[str, str] = {}
    reward_map: Dict[str, Dict[str, Any]] = {}
    if rollout_ids:
        placeholders = ",".join("?" for _ in rollout_ids)
        with db_connect(db_path) as conn:
            rollout_rows = conn.execute(
                f"SELECT rollout_id, status FROM rollouts WHERE rollout_id IN ({placeholders})",
                rollout_ids,
            ).fetchall()
            for row in rollout_rows:
                status_map[str(row["rollout_id"])] = str(row["status"] or "")
            reward_rows = conn.execute(
                f"""
                SELECT s.rollout_id, s.attributes_json
                FROM spans AS s
                INNER JOIN (
                    SELECT rollout_id, MAX(id) AS max_id
                    FROM spans
                    WHERE name = 'reward' AND rollout_id IN ({placeholders})
                    GROUP BY rollout_id
                ) AS latest
                ON s.id = latest.max_id
                """,
                rollout_ids,
            ).fetchall()
            for row in reward_rows:
                reward_map[str(row["rollout_id"])] = json_loads_or_default(row["attributes_json"], {})

    grouped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        rollout_id = str(row["rollout_id"] or "")
        prompt_version_id = str(row["prompt_version_id"] or "").strip() or "published_static"
        bucket = str(row["bucket"] or "").strip() or "published"
        rec = grouped.setdefault(
            prompt_version_id,
            {
                "prompt_version_id": prompt_version_id,
                "bucket_breakdown": {},
                "sample_count": 0,
                "success_count": 0,
                "reward_sum": 0.0,
                "reward_count": 0,
                "task_specific_sum": 0.0,
                "task_specific_count": 0,
                "failure_penalty_sum": 0.0,
                "failure_penalty_count": 0,
            },
        )
        rec["sample_count"] += 1
        rec["bucket_breakdown"][bucket] = int(rec["bucket_breakdown"].get(bucket, 0) or 0) + 1
        if status_map.get(rollout_id) == "succeeded":
            rec["success_count"] += 1
        reward_attrs = reward_map.get(rollout_id, {})
        try:
            rec["reward_sum"] += float(reward_attrs.get("reward"))
            rec["reward_count"] += 1
        except Exception:
            pass
        try:
            rec["task_specific_sum"] += float(reward_attrs.get("task_specific_score"))
            rec["task_specific_count"] += 1
        except Exception:
            pass
        try:
            rec["failure_penalty_sum"] += float(reward_attrs.get("failure_penalty"))
            rec["failure_penalty_count"] += 1
        except Exception:
            pass

    versions: List[Dict[str, Any]] = []
    for rec in grouped.values():
        sample_count = int(rec["sample_count"] or 0)
        versions.append(
            {
                "prompt_version_id": rec["prompt_version_id"],
                "sample_count": sample_count,
                "success_rate": round(float(rec["success_count"] or 0) / sample_count, 4) if sample_count > 0 else 0.0,
                "avg_reward": round(float(rec["reward_sum"] or 0.0) / max(1, int(rec["reward_count"] or 0)), 6) if rec["reward_count"] else None,
                "avg_task_specific_score": round(float(rec["task_specific_sum"] or 0.0) / max(1, int(rec["task_specific_count"] or 0)), 6) if rec["task_specific_count"] else None,
                "avg_failure_penalty": round(float(rec["failure_penalty_sum"] or 0.0) / max(1, int(rec["failure_penalty_count"] or 0)), 6) if rec["failure_penalty_count"] else None,
                "bucket_breakdown": rec["bucket_breakdown"],
            }
        )
    versions.sort(key=lambda x: (int(x.get("sample_count", 0)), str(x.get("prompt_version_id", ""))), reverse=True)
    return {
        "total_assignments": len(rows),
        "versions": versions[:10],
    }



def init_app_tables(*, db_path: Path, json_dumps: Callable[[Any], str]) -> None:
    init_rollout_tables(db_path)
    with db_connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memory_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT UNIQUE,
                task_hash TEXT UNIQUE,
                task_text TEXT NOT NULL,
                task_type TEXT,
                tags_json TEXT,
                strategy_text TEXT,
                config_snippet TEXT,
                pitfalls_text TEXT,
                failure_reason TEXT,
                fix_action TEXT,
                lesson TEXT,
                source_rollout_id TEXT,
                reward REAL,
                tool_call_count INTEGER,
                success INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memory_updated_at ON memory_cases(updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_memory_task_type ON memory_cases(task_type);

            CREATE TABLE IF NOT EXISTS memory_usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usage_id TEXT UNIQUE,
                rollout_id TEXT NOT NULL,
                memory_id TEXT NOT NULL,
                hit_rank INTEGER NOT NULL,
                match_score REAL,
                match_details_json TEXT,
                query_text TEXT,
                task_type TEXT,
                source TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                reward REAL,
                tool_call_count INTEGER,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_mem_usage_rollout ON memory_usage_events(rollout_id);
            CREATE INDEX IF NOT EXISTS idx_mem_usage_memory ON memory_usage_events(memory_id);
            CREATE INDEX IF NOT EXISTS idx_mem_usage_created ON memory_usage_events(created_at DESC);

            CREATE TABLE IF NOT EXISTS memory_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id TEXT UNIQUE NOT NULL,
                task_hash TEXT,
                md_path TEXT,
                md_sha1 TEXT,
                features_json TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_mem_docs_memory ON memory_documents(memory_id);
            CREATE INDEX IF NOT EXISTS idx_mem_docs_updated ON memory_documents(updated_at DESC);

            CREATE TABLE IF NOT EXISTS dynamic_method_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_text TEXT UNIQUE NOT NULL,
                normalized_value TEXT NOT NULL,
                source TEXT,
                confidence REAL NOT NULL DEFAULT 0.0,
                seen_count INTEGER NOT NULL DEFAULT 1,
                accepted_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'candidate',
                first_seen_rollout_id TEXT,
                example_text TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_dynamic_method_norm ON dynamic_method_aliases(normalized_value);
            CREATE INDEX IF NOT EXISTS idx_dynamic_method_status ON dynamic_method_aliases(status);

            CREATE TABLE IF NOT EXISTS dynamic_component_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_text TEXT UNIQUE NOT NULL,
                normalized_value TEXT NOT NULL,
                source TEXT,
                confidence REAL NOT NULL DEFAULT 0.0,
                seen_count INTEGER NOT NULL DEFAULT 1,
                accepted_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'candidate',
                first_seen_rollout_id TEXT,
                example_text TEXT,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_dynamic_component_norm ON dynamic_component_aliases(normalized_value);
            CREATE INDEX IF NOT EXISTS idx_dynamic_component_status ON dynamic_component_aliases(status);
            """
        )

        existing_cols = {
            str(r["name"])
            for r in conn.execute("PRAGMA table_info(memory_cases)").fetchall()
        }
        for col_name, col_type in [
            ("failure_reason", "TEXT"),
            ("fix_action", "TEXT"),
            ("lesson", "TEXT"),
            ("md_path", "TEXT"),
            ("features_json", "TEXT"),
        ]:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE memory_cases ADD COLUMN {col_name} {col_type}")

        existing_doc_cols = {
            str(r["name"])
            for r in conn.execute("PRAGMA table_info(memory_documents)").fetchall()
        }
        if "features_json" not in existing_doc_cols:
            conn.execute("ALTER TABLE memory_documents ADD COLUMN features_json TEXT")

        now = time.time()
        rows = conn.execute("SELECT id, match_details_json FROM memory_usage_events WHERE match_score IS NULL").fetchall()
        for r in rows:
            try:
                details = json.loads(r["match_details_json"] or "{}")
                score = float(details.get("score", 0.0)) if isinstance(details, dict) else 0.0
            except Exception:
                score = 0.0
            conn.execute(
                "UPDATE memory_usage_events SET match_score=?, updated_at=? WHERE id=?",
                (score, now, r["id"]),
            )

        conn.execute(
            "UPDATE memory_cases SET features_json = ? WHERE features_json IS NULL OR features_json = ''",
            (json_dumps({}),),
        )
        conn.execute(
            "UPDATE memory_documents SET features_json = ? WHERE features_json IS NULL OR features_json = ''",
            (json_dumps({}),),
        )
        conn.commit()



def _extract_file_paths_from_attributes(attrs: Dict[str, Any], *, ntpath_mod, max_text_file_size: int) -> List[Dict[str, str]]:
    files: Dict[str, Dict[str, str]] = {}

    def add_file(path_value: Any, file_type: str) -> None:
        path = str(path_value or "").strip()
        if not path:
            return
        files[path] = {
            "path": path,
            "type": file_type,
            "name": ntpath_mod.basename(path) or path,
        }

    direct_result = attrs.get("result")
    if isinstance(direct_result, dict):
        nested = direct_result.get("file_paths")
        if isinstance(nested, list):
            for item in nested:
                if isinstance(item, dict):
                    add_file(item.get("path"), str(item.get("type") or "result"))
        for key, file_type in [
            ("aspen_file_path", "aspen"),
            ("config_file_path", "config"),
            ("result_file_path", "result"),
            ("path", "result"),
        ]:
            if key in direct_result:
                add_file(direct_result.get(key), file_type)

    for key, file_type in [
        ("aspen_file_path", "aspen"),
        ("config_file_path", "config"),
        ("result_file_path", "result"),
        ("file_path", "result"),
    ]:
        if key in attrs:
            add_file(attrs.get(key), file_type)

    text_preview = str(attrs.get("result") or attrs.get("content") or "")
    if text_preview and len(text_preview) <= max_text_file_size and (".txt" in text_preview or ".md" in text_preview):
        for token in text_preview.replace("\n", " ").split(" "):
            token = token.strip().strip("\"'")
            if token.endswith((".txt", ".md")):
                add_file(token, "text")

    tool_results = attrs.get("tool_results")
    if isinstance(tool_results, list):
        for result in tool_results:
            if not isinstance(result, dict):
                continue
            nested = result.get("file_paths")
            if isinstance(nested, list):
                for item in nested:
                    if isinstance(item, dict):
                        add_file(item.get("path"), str(item.get("type") or "result"))
    return list(files.values())


def query_artifacts(
    *,
    db_path: Path,
    json_loads_or_default: Callable[[str | None, Any], Any],
    ntpath_mod,
    max_text_file_size: int,
    limit: int,
    offset: int,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    with db_connect(db_path) as conn:
        where = ""
        params: List[Any] = []
        if status:
            where = "WHERE status = ?"
            params.append(status)
        total = conn.execute(f"SELECT COUNT(1) FROM rollouts {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT rollout_id, status, start_time, end_time, input_json, metadata_json
            FROM rollouts
            {where}
            ORDER BY start_time DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()

        items: List[Dict[str, Any]] = []
        for row in rows:
            rollout_id = str(row["rollout_id"])
            span_rows = conn.execute(
                """
                SELECT name, attributes_json
                FROM spans
                WHERE rollout_id = ?
                ORDER BY id ASC
                """,
                (rollout_id,),
            ).fetchall()

            dedup: Dict[str, Dict[str, str]] = {}
            for span in span_rows:
                attrs = json_loads_or_default(span["attributes_json"], {})
                for file_item in _extract_file_paths_from_attributes(
                    attrs,
                    ntpath_mod=ntpath_mod,
                    max_text_file_size=max_text_file_size,
                ):
                    dedup[file_item["path"]] = file_item

            items.append(
                {
                    "rollout_id": rollout_id,
                    "status": row["status"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "message": json_loads_or_default(row["metadata_json"], {}).get("user_message", ""),
                    "files": list(dedup.values()),
                }
            )

    return {"total": int(total), "items": items}


def query_task_history(
    *,
    db_path: Path,
    json_loads_or_default: Callable[[str | None, Any], Any],
    limit: int = 200,
    status: Optional[str] = None,
    q: str = "",
    label: str = "",
    start_time_from: Optional[float] = None,
    start_time_to: Optional[float] = None,
) -> List[Dict[str, Any]]:
    with db_connect(db_path) as conn:
        where_clauses: List[str] = []
        params: List[Any] = []
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        if start_time_from is not None:
            where_clauses.append("start_time >= ?")
            params.append(float(start_time_from))
        if start_time_to is not None:
            where_clauses.append("start_time <= ?")
            params.append(float(start_time_to))
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        rows = conn.execute(
            f"""
            SELECT rollout_id, status, start_time, end_time, metadata_json
            FROM rollouts
            {where_sql}
            ORDER BY start_time DESC
            LIMIT ?
            """,
            params + [max(1, min(int(limit), 1000))],
        ).fetchall()

    q_l = q.strip().lower()
    label_l = label.strip().lower()
    dedup: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        metadata = json_loads_or_default(row["metadata_json"], {})
        msg = str(metadata.get("user_message", "")).strip()
        if not msg:
            continue
        row_label = str(metadata.get("label", "")).strip()
        if q_l and q_l not in msg.lower():
            continue
        if label_l and label_l not in row_label.lower():
            continue

        item = dedup.get(msg)
        if item is None:
            dedup[msg] = {
                "task_id": f"msg-{uuid.uuid5(uuid.NAMESPACE_OID, msg).hex[:16]}",
                "message": msg,
                "latest_rollout_id": str(row["rollout_id"]),
                "latest_status": str(row["status"]),
                "latest_start_time": row["start_time"],
                "latest_end_time": row["end_time"],
                "label": row_label,
                "sample_count": 1,
            }
        else:
            item["sample_count"] = int(item.get("sample_count", 1)) + 1

    items = list(dedup.values())
    items.sort(key=lambda x: float(x.get("latest_start_time") or 0), reverse=True)
    return items


def reset_rollouts_db(*, db_path: Path) -> None:
    with db_connect(db_path) as conn:
        conn.execute("DELETE FROM prompt_assignments")
        conn.execute("DELETE FROM spans")
        conn.execute("DELETE FROM rollouts")
        conn.commit()


def delete_single_rollout(*, db_path: Path, rollout_id: str) -> Dict[str, Any]:
    with db_connect(db_path) as conn:
        row = conn.execute("SELECT rollout_id FROM rollouts WHERE rollout_id = ?", (rollout_id,)).fetchone()
        if not row:
            return {"deleted": False, "message": f"Rollout {rollout_id} not found"}
        conn.execute("DELETE FROM spans WHERE rollout_id = ?", (rollout_id,))
        conn.execute("DELETE FROM prompt_assignments WHERE rollout_id = ?", (rollout_id,))
        conn.execute("DELETE FROM rollouts WHERE rollout_id = ?", (rollout_id,))
        conn.commit()
    return {"deleted": True, "rollout_id": rollout_id}


