from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _merge_unique(items: List[str], additions: List[str]) -> List[str]:
    seen = {str(item).strip() for item in items if str(item).strip()}
    merged = [str(item).strip() for item in items if str(item).strip()]
    for item in additions:
        val = str(item).strip()
        if val and val not in seen:
            merged.append(val)
            seen.add(val)
    return merged


def _enrich_query_structures(*, query: str, task_type: str, query_fields: Dict[str, List[str]], query_profile: Dict[str, Any]) -> Dict[str, Any]:
    enriched_fields = {str(k): list(v) for k, v in (query_fields or {}).items()}
    enriched_profile = dict(query_profile or {})
    entities = dict(enriched_profile.get("entities", {}) if isinstance(enriched_profile.get("entities", {}), dict) else {})
    lower_query = str(query or "").lower()
    additions: Dict[str, List[str]] = {}
    inferred_equipment: List[str] = []
    task_family = str(enriched_profile.get("task_family", "")).strip()

    if not enriched_fields.get("equipment"):
        if task_family == "mixing_calculation":
            inferred_equipment.append("mixer")
        elif task_family == "heat_exchange_task":
            inferred_equipment.append("heatx")
        elif task_family == "pressure_adjustment_task":
            if any(token in lower_query for token in ["pump", "泵"]):
                inferred_equipment.append("pump")
            elif any(token in lower_query for token in ["compressor", "压缩"]):
                inferred_equipment.append("compr")
            elif any(token in lower_query for token in ["valve", "阀"]):
                inferred_equipment.append("valve")
        elif task_family == "separation_task":
            if any(token in lower_query for token in ["flash", "闪蒸"]):
                inferred_equipment.append("flash")
            elif any(token in lower_query for token in ["separator", "sep", "分离器"]):
                inferred_equipment.append("sep")

    if inferred_equipment:
        enriched_fields["equipment"] = _merge_unique(enriched_fields.get("equipment", []), inferred_equipment)
        entities["equipment_types"] = _merge_unique(list(entities.get("equipment_types", [])), inferred_equipment)
        additions["equipment"] = inferred_equipment

    if task_type and str(enriched_profile.get("task_type", "")).strip().lower() != str(task_type).strip().lower():
        enriched_profile["task_type"] = str(task_type).strip().lower()
        additions["task_type"] = [str(task_type).strip().lower()]

    enriched_profile["entities"] = entities
    return {
        "query_fields": enriched_fields,
        "query_profile": enriched_profile,
        "enrichment": additions,
    }


def auto_upsert_memory_from_rollout(
    *,
    rollout_id: str,
    task_text: str,
    reward: float,
    tool_call_count: int,
    min_reward: float = 0.8,
    task_type_hint: str = "",
    equipment_type_hint: str = "",
    deps: Dict[str, Any],
) -> Dict[str, Any]:
    task_text = str(task_text or "").strip()
    if not task_text:
        return {"ok": False, "reason": "empty_task_text"}
    if float(reward) < float(min_reward):
        return {"ok": False, "reason": "low_reward", "reward": float(reward), "min_reward": float(min_reward)}

    spans = deps["query_spans_sqlite_fn"](rollout_id)
    metrics = deps["collect_simulation_metrics_fn"](spans)
    attempts = deps["extract_run_attempts_fn"](spans)

    task_type = str(task_type_hint or "").strip().lower()
    if task_type not in {"unit", "process"}:
        task_type = deps["infer_task_type_fn"](task_text)
    equipment_type = str(equipment_type_hint or "").strip().lower()

    strategy_text = deps["extract_strategy_from_spans_fn"](spans)
    config_snippet = deps["extract_config_snippet_from_spans_fn"](spans)
    pitfall_details = deps["extract_pitfall_details_from_spans_fn"](spans)
    pitfall_summary = deps["build_pitfall_summary_fn"](attempts)
    extract_pitfalls_text = deps["extract_pitfalls_from_spans_fn"]
    upsert_case = deps["upsert_case_fn"]
    memory_tags = deps["memory_tags_fn"]

    added_kinds: List[str] = []
    run_calls = int(metrics.get("run_simulation_calls", 0) or 0)
    run_success = int(metrics.get("run_simulation_success", 0) or 0)
    run_fail_total = int(metrics.get("run_simulation_fail_total", 0) or 0)
    get_result_success = int(metrics.get("get_result_success", 0) or 0)
    rounds_completed = int(metrics.get("rounds_completed", 0) or 0)

    if task_type == "unit":
        if run_success >= 1 and run_calls == 1 and get_result_success >= 1:
            upsert_case(
                task_text=task_text,
                task_type=task_type,
                tags=memory_tags(task_type, "success_golden", equipment_type),
                strategy_text=strategy_text,
                config_snippet=config_snippet,
                pitfalls_text="",
                failure_reason="",
                fix_action="",
                lesson="一次成功的模拟任务，配置参数可直接复用。",
                source_rollout_id=rollout_id,
                reward=max(float(reward), 0.98),
                tool_call_count=int(tool_call_count),
                memory_kind="success_golden",
                task_hash_salt=equipment_type or "unit-golden",
            )
            added_kinds.append("success_golden")
        elif run_success >= 1:
            upsert_case(
                task_text=task_text,
                task_type=task_type,
                tags=memory_tags(task_type, "success_recovered", equipment_type),
                strategy_text=strategy_text,
                config_snippet=config_snippet,
                pitfalls_text=pitfall_summary.get("summary") or pitfall_details.get("summary", ""),
                failure_reason=pitfall_summary.get("failure_reason") or pitfall_details.get("failure_reason", ""),
                fix_action=pitfall_summary.get("fix_action") or pitfall_details.get("fix_action", ""),
                lesson=pitfall_summary.get("lesson") or pitfall_details.get("lesson", ""),
                source_rollout_id=rollout_id,
                reward=float(reward),
                tool_call_count=int(tool_call_count),
                memory_kind="success_recovered",
                task_hash_salt=equipment_type or "unit-recovered",
            )
            added_kinds.append("success_recovered")
        if run_fail_total > 0 and "success_recovered" not in added_kinds:
            upsert_case(
                task_text=task_text,
                task_type=task_type,
                tags=memory_tags(task_type, "pitfall_recovery" if run_success > 0 else "pitfall_failure", equipment_type),
                strategy_text="",
                config_snippet=config_snippet,
                pitfalls_text=pitfall_summary.get("summary") or extract_pitfalls_text(spans),
                failure_reason=pitfall_summary.get("failure_reason") or pitfall_details.get("failure_reason", ""),
                fix_action=pitfall_summary.get("fix_action") or pitfall_details.get("fix_action", ""),
                lesson=pitfall_summary.get("lesson") or pitfall_details.get("lesson", ""),
                source_rollout_id=rollout_id,
                reward=max(0.01, float(reward) * 0.85),
                tool_call_count=int(tool_call_count),
                memory_kind="pitfall_recovery" if run_success > 0 else "pitfall_failure",
                task_hash_salt=f"{equipment_type}|pitfall|{run_fail_total}",
            )
            added_kinds.append("pitfall_recovery" if run_success > 0 else "pitfall_failure")
    else:
        if rounds_completed > 0:
            upsert_case(
                task_text=task_text,
                task_type=task_type,
                tags=memory_tags(task_type, "process_global", equipment_type),
                strategy_text=strategy_text,
                config_snippet=config_snippet,
                pitfalls_text=pitfall_summary.get("summary") or extract_pitfalls_text(spans),
                failure_reason=pitfall_summary.get("failure_reason") or pitfall_details.get("failure_reason", ""),
                fix_action=pitfall_summary.get("fix_action") or pitfall_details.get("fix_action", ""),
                lesson=pitfall_summary.get("lesson") or pitfall_details.get("lesson", ""),
                source_rollout_id=rollout_id,
                reward=float(reward),
                tool_call_count=int(tool_call_count),
                memory_kind="process_global",
                task_hash_salt=equipment_type or f"rounds-{rounds_completed}",
            )
            added_kinds.append("process_global")
            for idx in range(1, max(1, rounds_completed) + 1):
                upsert_case(
                    task_text=task_text,
                    task_type=task_type,
                    tags=memory_tags(task_type, "process_stage", equipment_type),
                    strategy_text=f"第{idx}阶段：优先最小化修改，保留已验证的上游配置。",
                    config_snippet=config_snippet,
                    pitfalls_text="",
                    failure_reason="",
                    fix_action="",
                    lesson="可复用的流程模块配置，后续类似任务可直接参考。",
                    source_rollout_id=rollout_id,
                    reward=max(0.01, float(reward) - (idx - 1) * 0.02),
                    tool_call_count=int(tool_call_count),
                    memory_kind="process_stage",
                    task_hash_salt=f"{equipment_type}|stage-{idx}",
                )
            added_kinds.append("process_stage")
        if run_fail_total > 0:
            upsert_case(
                task_text=task_text,
                task_type=task_type,
                tags=memory_tags(task_type, "pitfall_recovery" if run_success > 0 else "pitfall_failure", equipment_type),
                strategy_text="",
                config_snippet=config_snippet,
                pitfalls_text=pitfall_summary.get("summary") or extract_pitfalls_text(spans),
                failure_reason=pitfall_summary.get("failure_reason") or pitfall_details.get("failure_reason", ""),
                fix_action=pitfall_summary.get("fix_action") or pitfall_details.get("fix_action", ""),
                lesson=pitfall_summary.get("lesson") or pitfall_details.get("lesson", ""),
                source_rollout_id=rollout_id,
                reward=max(0.01, float(reward) * 0.85),
                tool_call_count=int(tool_call_count),
                memory_kind="pitfall_recovery" if run_success > 0 else "pitfall_failure",
                task_hash_salt=f"{equipment_type}|process-pitfall|{run_fail_total}",
            )
            added_kinds.append("pitfall_recovery" if run_success > 0 else "pitfall_failure")

    return {
        "ok": True,
        "task_type": task_type,
        "reward": float(reward),
        "tool_call_count": int(tool_call_count),
        "source_rollout_id": rollout_id,
        "run_simulation_calls": run_calls,
        "run_simulation_fail_total": run_fail_total,
        "memory_kinds": sorted(set(added_kinds)),
    }


def build_memory_from_rollouts(*, min_reward: float, limit: int, deps: Dict[str, Any]) -> Dict[str, Any]:
    with deps["db_connect_fn"]() as conn:
        quality_rows = conn.execute(
            """
            SELECT
                memory_id,
                COUNT(1) AS retrieved_count,
                SUM(CASE WHEN status IN ('succeeded','failed','cancelled') THEN 1 ELSE 0 END) AS applied_count,
                SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS success_after_use,
                AVG(CASE WHEN status IN ('succeeded','failed') THEN reward END) AS avg_reward_after_use,
                MAX(created_at) AS last_used_at
            FROM memory_usage_events
            GROUP BY memory_id
            """
        ).fetchall()
        rows = conn.execute(
            '''
            SELECT rollout_id, status, start_time, metadata_json
            FROM rollouts
            WHERE status = 'succeeded'
            ORDER BY start_time DESC
            LIMIT ?
            ''',
            (max(1, min(int(limit), 2000)),),
        ).fetchall()
    scanned = 0
    added_or_updated = 0
    skipped_low_reward = 0
    for row in rows:
        scanned += 1
        rollout_id = str(row["rollout_id"])
        metadata = deps["json_loads_or_default_fn"](row["metadata_json"], {})
        task_text = str(metadata.get("user_message", "")).strip()
        if not task_text:
            continue
        spans = deps["query_spans_sqlite_fn"](rollout_id)
        reward, tool_count = deps["extract_reward_and_tool_count_fn"](spans)
        if reward < float(min_reward):
            skipped_low_reward += 1
            continue
        task_type = deps["infer_task_type_fn"](task_text)
        strategy_text = deps["extract_strategy_from_spans_fn"](spans)
        config_snippet = deps["extract_config_snippet_from_spans_fn"](spans)
        pitfall_details = deps["extract_pitfall_details_from_spans_fn"](spans)
        pitfalls_text = deps["extract_pitfalls_from_spans_fn"](spans)
        deps["upsert_case_fn"](
            task_text=task_text,
            task_type=task_type,
            tags=[task_type],
            strategy_text=strategy_text,
            config_snippet=config_snippet,
            pitfalls_text=pitfalls_text,
            failure_reason=pitfall_details.get("failure_reason", ""),
            fix_action=pitfall_details.get("fix_action", ""),
            lesson=pitfall_details.get("lesson", ""),
            source_rollout_id=rollout_id,
            reward=reward,
            tool_call_count=tool_count,
        )
        added_or_updated += 1
    return {
        "scanned": scanned,
        "added_or_updated": added_or_updated,
        "skipped_low_reward": skipped_low_reward,
        "min_reward": min_reward,
    }


def _memory_kind_from_tags(tags: List[str]) -> str:
    for t in tags:
        if isinstance(t, str) and t.startswith("kind:"):
            return t.split(":", 1)[1].strip()
    return ""


def search_memory_cases(*, query: str, top_k: int, task_type: str, deps: Dict[str, Any]) -> List[Dict[str, Any]]:
    q = deps["normalize_text_fn"](query)
    if not q:
        return []
    q_tokens = [t for t in q.split(" ") if t]
    query_task_type = (task_type or "").strip().lower()
    if query_task_type not in {"unit", "process"}:
        query_task_type = deps["infer_task_type_fn"](query)
    dynamic_methods = deps.get("list_validated_dynamic_methods_fn", lambda: [])()
    dynamic_component_aliases = deps.get("list_validated_dynamic_component_aliases_fn", lambda: {})()
    query_fields = deps["extract_match_fields_fn"](
        [query],
        dynamic_methods=dynamic_methods,
        dynamic_component_aliases=dynamic_component_aliases,
    )
    query_profile = deps["build_semantic_profile_fn"](
        texts=[query],
        task_type=query_task_type,
        dynamic_methods=dynamic_methods,
        dynamic_component_aliases=dynamic_component_aliases,
    )
    enrichment_pack = _enrich_query_structures(
        query=query,
        task_type=query_task_type,
        query_fields=query_fields,
        query_profile=query_profile,
    )
    query_fields = enrichment_pack["query_fields"]
    query_profile = enrichment_pack["query_profile"]
    query_enrichment = enrichment_pack["enrichment"]
    has_structured_query = any(bool(query_fields.get(k)) for k in ["equipment", "equipment_ids", "streams", "flow", "ops", "methods", "components"])
    with deps["db_connect_fn"]() as conn:
        quality_rows = conn.execute(
            """
            SELECT
                memory_id,
                COUNT(1) AS retrieved_count,
                SUM(CASE WHEN status IN ('succeeded','failed','cancelled') THEN 1 ELSE 0 END) AS applied_count,
                SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS success_after_use,
                AVG(CASE WHEN status IN ('succeeded','failed') THEN reward END) AS avg_reward_after_use,
                MAX(created_at) AS last_used_at
            FROM memory_usage_events
            GROUP BY memory_id
            """
        ).fetchall()
        rows = conn.execute(
            '''
            SELECT memory_id, task_text, task_type, tags_json, strategy_text, config_snippet,
                   pitfalls_text, failure_reason, fix_action, lesson, md_path, features_json,
                   source_rollout_id, reward, tool_call_count, updated_at
            FROM memory_cases
            ORDER BY updated_at DESC
            LIMIT 1500
            '''
        ).fetchall()
    quality_by_memory = {
        str(row["memory_id"]): {
            "retrieved_count": int(row["retrieved_count"] or 0),
            "applied_count": int(row["applied_count"] or 0),
            "success_after_use": int(row["success_after_use"] or 0),
            "avg_reward_after_use": float(row["avg_reward_after_use"] or 0.0),
            "last_used_at": row["last_used_at"],
        }
        for row in quality_rows
    }
    now_ts = __import__("time").time()
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for row in rows:
        rec = {
            "memory_id": row["memory_id"],
            "task_text": row["task_text"],
            "task_type": row["task_type"],
            "tags": deps["json_loads_or_default_fn"](row["tags_json"], []),
            "strategy_text": row["strategy_text"] or "",
            "config_snippet": row["config_snippet"] or "",
            "pitfalls_text": row["pitfalls_text"] or "",
            "failure_reason": row["failure_reason"] or "",
            "fix_action": row["fix_action"] or "",
            "lesson": row["lesson"] or "",
            "source_rollout_id": row["source_rollout_id"] or "",
            "md_path": row["md_path"] or "",
            "features": deps["json_loads_or_default_fn"](row["features_json"], {}),
            "reward": float(row["reward"] or 0.0),
            "tool_call_count": int(row["tool_call_count"] or 0),
            "updated_at": row["updated_at"],
        }
        mem_features = rec.get("features", {}) if isinstance(rec.get("features"), dict) else {}
        mem_fields = mem_features.get("match_fields") or deps["extract_match_fields_fn"]([
            rec["task_text"],
            rec["strategy_text"],
            rec["config_snippet"],
        ], dynamic_methods=dynamic_methods, dynamic_component_aliases=dynamic_component_aliases)
        mem_profile = mem_features.get("semantic_profile") or deps["build_semantic_profile_fn"](
            texts=[rec["task_text"], rec["strategy_text"], rec["config_snippet"]],
            task_type=rec.get("task_type", ""),
            dynamic_methods=dynamic_methods,
            dynamic_component_aliases=dynamic_component_aliases,
        )
        semantic_pack = deps["score_semantic_similarity_fn"](query_profile=query_profile, memory_profile=mem_profile)
        semantic_score = float(semantic_pack.get("score", 0.0) or 0.0)
        semantic_detail = semantic_pack.get("details", {}) if isinstance(semantic_pack, dict) else {}

        strict_detail: Dict[str, Any] = {"mode": "lexical_only", "ranking_score": 0.0}
        strict_ok = True
        rescued_by_semantics = False
        structured_match_score = 0.0
        if has_structured_query:
            strict_ok, strict_detail = deps["match_required_fields_fn"](query_fields, mem_fields)
            structured_match_score = float(strict_detail.get("ranking_score", 0.0) or 0.0)
            if not strict_ok:
                rescued_by_semantics = semantic_score >= 1.2 and structured_match_score >= 0.3
                if not rescued_by_semantics:
                    continue

        hay = deps["normalize_text_fn"](
            " ".join(
                [
                    rec["task_text"],
                    rec["strategy_text"],
                    " ".join(rec.get("tags", [])),
                    " ".join(query_profile.get("query_expansion_terms", [])),
                    " ".join(mem_profile.get("query_expansion_terms", [])),
                    str(mem_profile.get("task_family", "")),
                    str(mem_profile.get("summary_text", "")),
                ]
            )
        )
        score = 0.0
        token_hits = 0
        for tk in q_tokens:
            if tk in hay:
                token_hits += 1
                score += 1.0
        exact_query_hit = False
        if q in hay:
            exact_query_hit = True
            score += 1.5
        task_type_boost = 0.0
        if query_task_type and rec["task_type"] == query_task_type:
            task_type_boost = 0.8
            score += task_type_boost
        kind = _memory_kind_from_tags(rec.get("tags", []))
        kind_boost = {
            "success_golden": 1.2,
            "success_recovered": 0.8,
            "process_global": 1.0,
            "process_stage": 0.6,
            "pitfall_recovery": 0.5,
            "pitfall_failure": 0.2,
        }.get(kind, 0.0)
        score += kind_boost
        reward_boost = min(1.0, rec["reward"]) * 0.3
        score += reward_boost
        score += structured_match_score
        score += semantic_score
        quality_info = quality_by_memory.get(rec["memory_id"], {})
        retrieved_count = int(quality_info.get("retrieved_count", 0) or 0)
        applied_count = int(quality_info.get("applied_count", 0) or 0)
        success_after_use = int(quality_info.get("success_after_use", 0) or 0)
        avg_reward_after_use = float(quality_info.get("avg_reward_after_use", 0.0) or 0.0)
        success_rate = (success_after_use / applied_count) if applied_count > 0 else 0.0
        usage_rate = (applied_count / retrieved_count) if retrieved_count > 0 else 0.0
        recency_days = None
        last_used_at = quality_info.get("last_used_at")
        if last_used_at is not None:
            recency_days = max(0.0, (now_ts - float(last_used_at)) / 86400.0)
        recency_boost = 0.0
        if recency_days is not None:
            if recency_days <= 7:
                recency_boost = 0.2
            elif recency_days <= 30:
                recency_boost = 0.1
            elif recency_days >= 180:
                recency_boost = -0.1
        quality_score = (success_rate * 0.8) + (max(0.0, min(1.0, avg_reward_after_use)) * 0.5) + (usage_rate * 0.3) + recency_boost
        if applied_count >= 2 and success_rate < 0.4:
            quality_score -= 0.25
        score += quality_score
        strict_penalty = 0.0
        if rescued_by_semantics:
            strict_penalty = -0.35
            score += strict_penalty
        if score <= 0:
            continue
        rec["score"] = round(score, 4)
        rec["memory_kind"] = kind
        rec["features"] = {**mem_features, "match_fields": mem_fields, "semantic_profile": mem_profile}
        rec["match"] = {
            "token_hits": token_hits,
            "query_token_count": len(q_tokens),
            "exact_query_hit": exact_query_hit,
            "task_type_boost": round(task_type_boost, 4),
            "kind_boost": round(kind_boost, 4),
            "reward_boost": round(reward_boost, 4),
            "structured_match_score": round(structured_match_score, 4),
            "semantic_score": round(semantic_score, 4),
            "quality_score": round(quality_score, 4),
            "quality": {
                "retrieved_count": retrieved_count,
                "applied_count": applied_count,
                "success_after_use": success_after_use,
                "success_rate": round(success_rate, 4),
                "usage_rate": round(usage_rate, 4),
                "avg_reward_after_use": round(avg_reward_after_use, 4),
                "recency_days": None if recency_days is None else round(recency_days, 2),
            },
            "semantic": semantic_detail,
            "strict_match": strict_detail,
            "query_enrichment": query_enrichment,
            "strict_rescued_by_semantics": rescued_by_semantics,
            "strict_penalty": round(strict_penalty, 4),
        }
        scored.append((score, rec))
    scored.sort(key=lambda x: x[0], reverse=True)
    ranked = [x for _, x in scored]
    if not ranked:
        return []
    mode = query_task_type
    selected: List[Dict[str, Any]] = []
    used_ids: set = set()

    def pick_one(kinds: List[str]) -> None:
        for item in ranked:
            if item.get("memory_id") in used_ids:
                continue
            if item.get("memory_kind") in kinds:
                selected.append(item)
                used_ids.add(item.get("memory_id"))
                return

    def pick_many(kinds: List[str], limit_n: int) -> None:
        count = 0
        for item in ranked:
            if count >= limit_n:
                return
            if item.get("memory_id") in used_ids:
                continue
            if item.get("memory_kind") in kinds:
                selected.append(item)
                used_ids.add(item.get("memory_id"))
                count += 1

    if mode == "unit":
        pick_one(["success_golden", "success_recovered"])
        pick_many(["pitfall_recovery", "pitfall_failure"], 2)
    elif mode == "process":
        pick_one(["process_global", "success_recovered", "success_golden"])
        pick_many(["process_stage"], 2)
        pick_many(["pitfall_recovery", "pitfall_failure"], 2)
    else:
        pick_one(["success_golden", "success_recovered", "process_global"])
        pick_many(["pitfall_recovery", "pitfall_failure"], 2)

    cap = max(1, min(int(top_k), 20))
    for item in ranked:
        if len(selected) >= cap:
            break
        mid = item.get("memory_id")
        if mid in used_ids:
            continue
        selected.append(item)
        used_ids.add(mid)
    return selected[:cap]
