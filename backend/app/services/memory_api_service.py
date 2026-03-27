from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException


async def api_memory_build(*, payload: Dict[str, Any], deps: Dict[str, Any]) -> Dict[str, Any]:
    result = deps["build_memory_from_rollouts_fn"](
        min_reward=float(payload.get("min_reward", 0.8)),
        limit=int(payload.get("limit", 200)),
    )
    stats = deps["get_memory_stats_fn"]()
    return {"ok": True, "result": result, "stats": stats}


async def api_memory_search(*, q: str, top_k: int, task_type: str, deps: Dict[str, Any]) -> Dict[str, Any]:
    items = deps["search_memory_cases_fn"](q, top_k=top_k, task_type=task_type.strip())
    return {"total": len(items), "items": items}


async def api_memory_stats(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    return deps["get_memory_stats_fn"]()


async def api_memory_backfill(*, payload: Dict[str, Any], deps: Dict[str, Any]) -> Dict[str, Any]:
    result = deps["backfill_memory_documents_fn"](limit=int(payload.get("limit", 1000)))
    return {"ok": True, **result}


async def api_memory_clear(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    result = deps["clear_all_memory_fn"]()
    return {"ok": True, **result}


async def api_memory_usages(*, limit: int, q: str, task_type: str, deps: Dict[str, Any]) -> Dict[str, Any]:
    items = deps["query_memory_usage_summary_fn"](limit=limit, q=q, task_type=task_type)
    return {"total": len(items), "items": items}


async def api_memory_usage_events(*, memory_id: str, limit: int, offset: int, deps: Dict[str, Any]) -> Dict[str, Any]:
    events = deps["query_memory_usage_events_fn"](memory_id=memory_id, limit=limit, offset=offset)
    return {"memory_id": memory_id, "total": len(events), "items": events}


async def api_memory_quality(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    return deps["query_memory_quality_metrics_fn"]()


async def api_memory_aliases(*, status: str, limit: int, deps: Dict[str, Any]) -> Dict[str, Any]:
    normalized_status = str(status or "").strip().lower()
    if normalized_status not in {"candidate", "validated"}:
        normalized_status = "validated"
    capped_limit = max(1, min(int(limit or 20), 200))
    rows = deps["query_memory_aliases_fn"](status=normalized_status, limit=capped_limit)
    return {
        "status": normalized_status,
        "limit": capped_limit,
        "methods": rows.get("methods", []),
        "summary": rows.get("summary", {}),
    }


async def api_memory_alias_review(*, payload: Dict[str, Any], deps: Dict[str, Any]) -> Dict[str, Any]:
    alias_type = str(payload.get("alias_type", "")).strip().lower()
    raw_text = str(payload.get("raw_text", "")).strip()
    action = str(payload.get("action", "")).strip().lower()
    normalized_value = str(payload.get("normalized_value", "")).strip().upper()
    if alias_type != "method":
        raise HTTPException(status_code=400, detail="alias_type must be method")
    if not raw_text:
        raise HTTPException(status_code=400, detail="raw_text is required")
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="action must be approve or reject")
    result = deps["review_memory_alias_fn"](
        alias_type=alias_type,
        raw_text=raw_text,
        action=action,
        normalized_value=normalized_value,
    )
    return {"ok": True, **result}


async def chat_resume_context(*, payload: Dict[str, Any], deps: Dict[str, Any]) -> Dict[str, Any]:
    rollout_id = str(payload.get("rollout_id", "")).strip()
    if not rollout_id:
        raise HTTPException(status_code=400, detail="rollout_id is required")
    resume_message = str(payload.get("resume_message", "")).strip()
    try:
        ctx = deps["build_resume_prompt_fn"](rollout_id, resume_message)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "rollout_id": rollout_id,
        "original_message": ctx.get("original_message", ""),
        "reward": ctx.get("reward"),
        "tool_call_count": ctx.get("tool_call_count"),
        "resume_prompt_preview": deps["safe_str_fn"](ctx.get("resume_prompt", ""), 2000),
    }



def memory_case_payload_by_id(*, memory_id: str, deps: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with deps["db_connect_fn"]() as conn:
        row = conn.execute(
            """
            SELECT memory_id, task_text, task_type, tags_json, strategy_text, config_snippet,
                   pitfalls_text, failure_reason, fix_action, lesson, md_path, features_json,
                   source_rollout_id, reward, tool_call_count, updated_at
            FROM memory_cases
            WHERE memory_id = ?
            LIMIT 1
            """,
            (memory_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "memory_id": row["memory_id"],
        "task_text": row["task_text"] or "",
        "task_type": row["task_type"] or "",
        "tags": deps["json_loads_or_default_fn"](row["tags_json"], []),
        "strategy_text": row["strategy_text"] or "",
        "config_snippet": row["config_snippet"] or "",
        "pitfalls_text": row["pitfalls_text"] or "",
        "failure_reason": row["failure_reason"] or "",
        "fix_action": row["fix_action"] or "",
        "lesson": row["lesson"] or "",
        "md_path": row["md_path"] or "",
        "features": deps["json_loads_or_default_fn"](row["features_json"], {}),
        "source_rollout_id": row["source_rollout_id"] or "",
        "reward": float(row["reward"] or 0.0),
        "tool_call_count": int(row["tool_call_count"] or 0),
        "updated_at": row["updated_at"],
    }


async def memory_search_experience_tool(*, query: str, top_k: int = 5, task_type: str = "", deps: Dict[str, Any]) -> str:
    q = str(query or "").strip()
    if not q:
        return deps["json_dumps_fn"]({"ok": False, "error": "query is empty", "items": []})
    t = str(task_type or "").strip().lower()
    items = deps["search_memory_cases_fn"](q, top_k=max(1, min(int(top_k or 5), 10)), task_type=t)
    out = []
    for x in items:
        fx = x.get("features", {}) if isinstance(x, dict) else {}
        out.append({
            "memory_id": x.get("memory_id"),
            "task_text": deps["safe_str_fn"](x.get("task_text", ""), 240),
            "task_type": x.get("task_type"),
            "memory_kind": x.get("memory_kind", ""),
            "reward": x.get("reward", 0),
            "score": x.get("score", 0),
            "schema_hash": (fx.get("schema_hash", "") if isinstance(fx, dict) else ""),
            "md_path": x.get("md_path", ""),
            "match": x.get("match", {}),
        })
    return deps["json_dumps_fn"]({"ok": True, "query": q, "total": len(out), "items": out})


async def memory_get_experience_tool(*, memory_id: str, include_markdown: bool = True, deps: Dict[str, Any]) -> str:
    mid = str(memory_id or "").strip()
    if not mid:
        return deps["json_dumps_fn"]({"ok": False, "error": "memory_id is empty"})
    item = memory_case_payload_by_id(
        memory_id=mid,
        deps={
            "db_connect_fn": deps["db_connect_fn"],
            "json_loads_or_default_fn": deps["json_loads_or_default_fn"],
        },
    )
    if not item:
        return deps["json_dumps_fn"]({"ok": False, "error": f"memory not found: {mid}"})
    markdown = ""
    if include_markdown:
        abs_path = deps["memory_docs_dir"] / f"{mid}.md"
        if abs_path.exists():
            markdown = deps["safe_str_fn"](abs_path.read_text(encoding="utf-8", errors="replace"), 25000)
    item["markdown"] = markdown
    return deps["json_dumps_fn"]({"ok": True, "item": item})


