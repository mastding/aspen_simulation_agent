from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional


def log_memory_usage_events(
    *,
    rollout_id: str,
    query_text: str,
    task_type: str,
    source: str,
    hits: List[Dict[str, Any]],
    deps: Dict[str, Any],
) -> int:
    if not hits:
        return 0
    now = time.time()
    inserted = 0
    with deps["db_connect_fn"]() as conn:
        for idx, item in enumerate(hits, start=1):
            if not isinstance(item, dict):
                continue
            memory_id = str(item.get("memory_id", "")).strip()
            if not memory_id:
                continue
            usage_id = f"muse-{uuid.uuid4().hex[:16]}"
            conn.execute(
                '''
                INSERT INTO memory_usage_events(
                    usage_id, rollout_id, memory_id, hit_rank, match_score, match_details_json,
                    query_text, task_type, source, status, reward, tool_call_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, NULL, ?, ?)
                ''',
                (
                    usage_id,
                    rollout_id,
                    memory_id,
                    int(idx),
                    float(item.get("score", 0.0) or 0.0),
                    deps["json_dumps_fn"](item.get("match", {})),
                    query_text,
                    task_type,
                    source,
                    now,
                    now,
                ),
            )
            inserted += 1
        conn.commit()
    return inserted


def finalize_memory_usage_events(
    *,
    rollout_id: str,
    status: str,
    reward: Optional[float],
    tool_call_count: Optional[int],
    deps: Dict[str, Any],
) -> int:
    now = time.time()
    normalized = str(status or "").strip().lower()
    if normalized not in {"succeeded", "failed", "cancelled"}:
        normalized = "failed"
    with deps["db_connect_fn"]() as conn:
        cur = conn.execute(
            '''
            UPDATE memory_usage_events
            SET status = ?, reward = ?, tool_call_count = ?, updated_at = ?
            WHERE rollout_id = ? AND status = 'pending'
            ''',
            (
                normalized,
                None if reward is None else float(reward),
                None if tool_call_count is None else int(tool_call_count),
                now,
                rollout_id,
            ),
        )
        conn.commit()
        return int(cur.rowcount or 0)


def _query_rollout_tool_call_counts(*, deps: Dict[str, Any]) -> Dict[str, int]:
    with deps["db_connect_fn"]() as conn:
        rows = conn.execute("SELECT rollout_id, attributes_json FROM spans WHERE name = 'tool_call_request'").fetchall()
    counts: Dict[str, int] = {}
    for row in rows:
        rid = str(row["rollout_id"])
        attrs = deps["json_loads_or_default_fn"](row["attributes_json"], {})
        calls = attrs.get("tool_calls")
        if isinstance(calls, list):
            counts[rid] = counts.get(rid, 0) + len(calls)
    return counts


def query_memory_usage_summary(
    *,
    limit: int,
    q: str,
    task_type: str,
    deps: Dict[str, Any],
) -> List[Dict[str, Any]]:
    where_sql = []
    args: List[Any] = []
    if q.strip():
        where_sql.append("m.task_text LIKE ?")
        args.append(f"%{q.strip()}%")
    if task_type.strip():
        where_sql.append("m.task_type = ?")
        args.append(task_type.strip())
    where_clause = ("WHERE " + " AND ".join(where_sql)) if where_sql else ""
    sql = f'''
        SELECT
            m.memory_id,
            m.task_text,
            m.task_type,
            m.source_rollout_id,
            m.strategy_text,
            m.config_snippet,
            m.pitfalls_text,
            m.failure_reason,
            m.fix_action,
            m.lesson,
            m.reward AS memory_reward,
            m.updated_at,
            COUNT(e.id) AS use_count,
            SUM(CASE WHEN e.status = 'succeeded' THEN 1 ELSE 0 END) AS hit_success_count,
            SUM(CASE WHEN e.status IN ('succeeded','failed') THEN 1 ELSE 0 END) AS finished_count,
            AVG(CASE WHEN e.status IN ('succeeded','failed') THEN e.match_score END) AS avg_match_score,
            MAX(e.created_at) AS last_used_at
        FROM memory_cases m
        LEFT JOIN memory_usage_events e ON e.memory_id = m.memory_id
        {where_clause}
        GROUP BY m.memory_id
        ORDER BY m.updated_at DESC
        LIMIT ?
    '''
    args.append(max(1, min(int(limit), 1000)))
    with deps["db_connect_fn"]() as conn:
        rows = conn.execute(sql, tuple(args)).fetchall()
    items: List[Dict[str, Any]] = []
    for row in rows:
        finished = int(row["finished_count"] or 0)
        succ = int(row["hit_success_count"] or 0)
        items.append(
            {
                "memory_id": row["memory_id"],
                "task_text": row["task_text"] or "",
                "source_rollout_id": row["source_rollout_id"] or None,
                "task_type": row["task_type"] or "",
                "strategy_text": row["strategy_text"] or "",
                "config_snippet": row["config_snippet"] or "",
                "pitfalls_text": row["pitfalls_text"] or "",
                "failure_reason": row["failure_reason"] or "",
                "fix_action": row["fix_action"] or "",
                "lesson": row["lesson"] or "",
                "memory_reward": round(float(row["memory_reward"] or 0.0), 4),
                "updated_at": row["updated_at"],
                "use_count": int(row["use_count"] or 0),
                "hit_success_count": succ,
                "finished_count": finished,
                "hit_success_rate": round(succ / finished, 4) if finished > 0 else 0.0,
                "avg_match_score": round(float(row["avg_match_score"] or 0.0), 4),
                "last_used_at": row["last_used_at"],
            }
        )
    return items


def query_memory_usage_events(
    *,
    memory_id: str,
    limit: int,
    offset: int,
    deps: Dict[str, Any],
) -> List[Dict[str, Any]]:
    with deps["db_connect_fn"]() as conn:
        rows = conn.execute(
            '''
            SELECT usage_id, rollout_id, memory_id, hit_rank, match_score, match_details_json,
                   query_text, task_type, source, status, reward, tool_call_count, created_at, updated_at
            FROM memory_usage_events
            WHERE memory_id = ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            ''',
            (memory_id, max(1, min(int(limit), 1000)), max(0, int(offset))),
        ).fetchall()
    return [
        {
            "usage_id": r["usage_id"],
            "rollout_id": r["rollout_id"],
            "memory_id": r["memory_id"],
            "hit_rank": int(r["hit_rank"] or 0),
            "match_score": round(float(r["match_score"] or 0.0), 4),
            "match_details": deps["json_loads_or_default_fn"](r["match_details_json"], {}),
            "query_text": r["query_text"] or "",
            "task_type": r["task_type"] or "",
            "source": r["source"] or "",
            "status": r["status"] or "pending",
            "reward": None if r["reward"] is None else round(float(r["reward"]), 4),
            "tool_call_count": None if r["tool_call_count"] is None else int(r["tool_call_count"]),
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def query_memory_low_quality_candidates(*, limit: int, deps: Dict[str, Any]) -> List[Dict[str, Any]]:
    capped = max(1, min(int(limit or 20), 100))
    with deps["db_connect_fn"]() as conn:
        rows = conn.execute(
            """
            SELECT
                e.memory_id,
                COUNT(1) AS retrieved_count,
                SUM(CASE WHEN e.status IN ('succeeded','failed','cancelled') THEN 1 ELSE 0 END) AS applied_count,
                SUM(CASE WHEN e.status = 'succeeded' THEN 1 ELSE 0 END) AS success_after_use,
                AVG(CASE WHEN e.status IN ('succeeded','failed') THEN e.reward END) AS avg_reward_after_use,
                MAX(e.created_at) AS last_used_at,
                m.task_text,
                m.task_type,
                m.reward AS memory_reward,
                m.updated_at
            FROM memory_usage_events e
            JOIN memory_cases m ON m.memory_id = e.memory_id
            GROUP BY e.memory_id
            HAVING (applied_count >= 2 AND (1.0 * success_after_use / applied_count) < 0.5)
                OR (retrieved_count >= 5 AND applied_count = 0)
            ORDER BY
                CASE WHEN applied_count > 0 THEN (1.0 * success_after_use / applied_count) ELSE 0 END ASC,
                avg_reward_after_use ASC,
                retrieved_count DESC,
                COALESCE(last_used_at, 0) ASC
            LIMIT ?
            """,
            (capped,),
        ).fetchall()
    items: List[Dict[str, Any]] = []
    for row in rows:
        applied = int(row["applied_count"] or 0)
        success = int(row["success_after_use"] or 0)
        items.append({
            "memory_id": str(row["memory_id"] or ""),
            "task_text": str(row["task_text"] or ""),
            "task_type": str(row["task_type"] or ""),
            "retrieved_count": int(row["retrieved_count"] or 0),
            "applied_count": applied,
            "success_after_use": success,
            "success_rate": round(success / applied, 4) if applied > 0 else 0.0,
            "avg_reward_after_use": round(float(row["avg_reward_after_use"] or 0.0), 4),
            "memory_reward": round(float(row["memory_reward"] or 0.0), 4),
            "last_used_at": row["last_used_at"],
            "updated_at": row["updated_at"],
        })
    return items


def query_memory_quality_metrics(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    tool_calls_by_rollout = _query_rollout_tool_call_counts(deps=deps)
    with deps["db_connect_fn"]() as conn:
        rollout_rows = conn.execute("SELECT rollout_id, status FROM rollouts WHERE status IN ('succeeded','failed')").fetchall()
        usage_rows = conn.execute(
            '''
            SELECT rollout_id, status, tool_call_count
            FROM memory_usage_events
            WHERE status IN ('succeeded','failed')
            '''
        ).fetchall()
    hit_rollout_status: Dict[str, str] = {}
    hit_rollout_tool_calls: Dict[str, int] = {}
    for row in usage_rows:
        rid = str(row["rollout_id"])
        status = str(row["status"] or "").strip()
        if rid not in hit_rollout_status:
            hit_rollout_status[rid] = status
        if status == "succeeded":
            hit_rollout_status[rid] = "succeeded"
        tc = row["tool_call_count"]
        if tc is not None:
            hit_rollout_tool_calls[rid] = int(tc)
    total_hit = 0
    succ_hit = 0
    hit_steps: List[int] = []
    no_hit_steps: List[int] = []
    for row in rollout_rows:
        rid = str(row["rollout_id"])
        status = str(row["status"] or "")
        if rid in hit_rollout_status:
            total_hit += 1
            if status == "succeeded":
                succ_hit += 1
            tc = hit_rollout_tool_calls.get(rid, tool_calls_by_rollout.get(rid))
            if tc is not None:
                hit_steps.append(int(tc))
        else:
            tc = tool_calls_by_rollout.get(rid)
            if tc is not None:
                no_hit_steps.append(int(tc))
    avg_hit_steps = round(sum(hit_steps) / len(hit_steps), 3) if hit_steps else 0.0
    avg_no_hit_steps = round(sum(no_hit_steps) / len(no_hit_steps), 3) if no_hit_steps else 0.0
    step_reduction = round(avg_no_hit_steps - avg_hit_steps, 3) if (hit_steps and no_hit_steps) else 0.0

    low_quality_candidates = query_memory_low_quality_candidates(limit=10, deps=deps)
    with deps["db_connect_fn"]() as conn:
        usage_stats_row = conn.execute(
            """
            SELECT
                COUNT(DISTINCT memory_id) AS total,
                COUNT(1) AS retrieved_total,
                SUM(CASE WHEN status IN ('succeeded','failed','cancelled') THEN 1 ELSE 0 END) AS applied_total,
                SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS success_total,
                AVG(CASE WHEN status IN ('succeeded','failed') THEN reward END) AS avg_reward_after_use
            FROM memory_usage_events
            """
        ).fetchone()
        dynamic_rows = conn.execute(
            "SELECT status, COUNT(1) AS c FROM dynamic_method_aliases GROUP BY status"
        ).fetchall()
        dynamic_component_rows = conn.execute(
            "SELECT status, COUNT(1) AS c FROM dynamic_component_aliases GROUP BY status"
        ).fetchall()
    dynamic_counts = {str(row["status"] or "candidate"): int(row["c"] or 0) for row in dynamic_rows}
    dynamic_component_counts = {str(row["status"] or "candidate"): int(row["c"] or 0) for row in dynamic_component_rows}

    return {
        "memory_hit_rollouts": total_hit,
        "memory_hit_success_rate": round(succ_hit / total_hit, 4) if total_hit > 0 else 0.0,
        "memory_hit_avg_steps": avg_hit_steps,
        "memory_non_hit_avg_steps": avg_no_hit_steps,
        "memory_avg_step_reduction": step_reduction,
        "dynamic_method_alias_total": int(sum(dynamic_counts.values())),
        "dynamic_method_alias_validated": int(dynamic_counts.get("validated", 0)),
        "dynamic_method_alias_candidate": int(dynamic_counts.get("candidate", 0)),
        "dynamic_component_alias_total": int(sum(dynamic_component_counts.values())),
        "dynamic_component_alias_validated": int(dynamic_component_counts.get("validated", 0)),
        "dynamic_component_alias_candidate": int(dynamic_component_counts.get("candidate", 0)),
        "memory_usage_stats_total": int(usage_stats_row["total"] or 0),
        "memory_usage_stats_retrieved_total": int(usage_stats_row["retrieved_total"] or 0),
        "memory_usage_stats_applied_total": int(usage_stats_row["applied_total"] or 0),
        "memory_usage_stats_success_total": int(usage_stats_row["success_total"] or 0),
        "memory_usage_stats_avg_reward_after_use": round(float(usage_stats_row["avg_reward_after_use"] or 0.0), 4),
        "low_quality_candidates": low_quality_candidates,
    }


def build_resume_prompt(
    *,
    rollout_id: str,
    resume_message: str,
    deps: Dict[str, Any],
) -> Dict[str, Any]:
    with deps["db_connect_fn"]() as conn:
        row = conn.execute("SELECT rollout_id, status, metadata_json FROM rollouts WHERE rollout_id = ?", (rollout_id,)).fetchone()
    if row is None:
        raise ValueError(f"rollout not found: {rollout_id}")
    metadata = deps["json_loads_or_default_fn"](row["metadata_json"], {})
    original_message = str(metadata.get("user_message", "")).strip()
    spans = deps["query_spans_sqlite_fn"](rollout_id)
    config_snippet = deps["extract_config_snippet_from_spans_fn"](spans)
    strategy_text = deps["extract_strategy_from_spans_fn"](spans)
    pitfalls_text = deps["extract_pitfalls_from_spans_fn"](spans)
    reward, tool_count = deps["extract_reward_and_tool_count_fn"](spans)
    resume_instruction = str(resume_message or "").strip()
    if not resume_instruction:
        resume_instruction = "请基于上次已完成状态继续推进，不要重做已验证通过的步骤，只做最小必要修改。"
    safe_str = deps["safe_str_fn"]
    prompt = f'''你正在继续一个已执行过的复杂流程模拟任务。必须续跑，不要从零重做。
续跑规则：
1) 优先复用已有配置，仅做最小增量修改。
2) 已成功/已验证步骤禁止推翻。
3) 先输出“恢复确认”，再执行下一步工具调用。

【原始任务】
{original_message}

【上次rollout_id】{rollout_id}
【上次状态】{row["status"]}
【上次reward】{reward}
【上次工具调用次数】{tool_count}

【上次策略与结论摘要】
{safe_str(strategy_text, 3000)}

【上次关键配置片段】
{safe_str(config_snippet, 5000)}

【上次错误/风险】
{safe_str(pitfalls_text or '无', 2000)}

【本次续跑目标】
{resume_instruction}'''
    return {
        "rollout_id": rollout_id,
        "original_message": original_message,
        "reward": reward,
        "tool_call_count": tool_count,
        "strategy_text": strategy_text,
        "config_snippet": config_snippet,
        "pitfalls_text": pitfalls_text,
        "resume_prompt": prompt,
    }


def build_memory_context_for_task(*, user_message: str, top_k: int, deps: Dict[str, Any]) -> Dict[str, Any]:
    task_type = deps["infer_task_type_fn"](user_message)
    hits = deps["search_memory_cases_fn"](user_message, top_k=top_k, task_type=task_type)
    if not hits:
        return {"hits": [], "context_text": ""}
    safe_str = deps["safe_str_fn"]
    lines = ["【历史最佳实践参考（请优先复用）】"]
    for idx, item in enumerate(hits, start=1):
        lines.append(f"{idx}. 任务: {safe_str(item.get('task_text', ''), 220)}")
        lines.append(f"   类型: {item.get('task_type', 'unknown')} | reward: {item.get('reward', 0)}")
        strategy = safe_str(item.get("strategy_text", ""), 450)
        if strategy:
            lines.append(f"   策略: {strategy}")
        cfg = safe_str(item.get("config_snippet", ""), 600)
        if cfg:
            lines.append(f"   配置片段: {cfg}")
        pitfalls = safe_str(item.get("pitfalls_text", ""), 260)
        if pitfalls:
            lines.append(f"   风险: {pitfalls}")
    lines.append("请保持与上述实践一致，优先最小改动，避免推翻已验证配置。")
    return {"hits": hits, "context_text": "\n".join(lines)}



def get_memory_stats(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    with deps["db_connect_fn"]() as conn:
        total = conn.execute("SELECT COUNT(1) FROM memory_cases").fetchone()[0]
        type_rows = conn.execute(
            "SELECT task_type, COUNT(1) AS c FROM memory_cases GROUP BY task_type"
        ).fetchall()
        avg_reward_row = conn.execute("SELECT AVG(reward) AS a FROM memory_cases").fetchone()
    return {
        "total": int(total),
        "by_type": {str(r["task_type"] or "unknown"): int(r["c"]) for r in type_rows},
        "avg_reward": round(float(avg_reward_row["a"] or 0.0), 4),
    }


def clear_all_memory(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    with deps["db_connect_fn"]() as conn:
        case_count = int(conn.execute("SELECT COUNT(1) FROM memory_cases").fetchone()[0] or 0)
        usage_count = int(conn.execute("SELECT COUNT(1) FROM memory_usage_events").fetchone()[0] or 0)
        conn.execute("DELETE FROM memory_usage_events")
        conn.execute("DELETE FROM memory_cases")
    return {
        "deleted_memory_cases": case_count,
        "deleted_usage_events": usage_count,
    }


def delete_single_memory(*, memory_id: str, deps: Dict[str, Any]) -> Dict[str, Any]:
    with deps["db_connect_fn"]() as conn:
        row = conn.execute("SELECT memory_id FROM memory_cases WHERE memory_id = ?", (memory_id,)).fetchone()
        if not row:
            return {"deleted": False, "message": f"Memory {memory_id} not found"}
        conn.execute("DELETE FROM memory_usage_events WHERE memory_id = ?", (memory_id,))
        conn.execute("DELETE FROM memory_cases WHERE memory_id = ?", (memory_id,))
    return {"deleted": True, "memory_id": memory_id}
