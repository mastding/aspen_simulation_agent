from __future__ import annotations

from typing import Any, Dict


def build_api_layer(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    api_endpoints = deps["api_endpoints"]
    api_wiring = deps["api_wiring"]
    telemetry_repo = deps["telemetry_repo"]
    memory_core_ops = deps["memory_core_ops"]
    memory_storage_ops = deps["memory_storage_ops"]
    return {
        "start_rl_job": api_endpoints.build_start_rl_job_endpoint(
            rl_job_service=deps["rl_job_service"],
            runtime_state=deps["runtime_state"],
            now_iso_fn=deps["training_artifacts"].now_iso,
            run_rl_job_fn=deps["_run_rl_job"],
        ),
        "stop_rl_job": api_endpoints.build_stop_rl_job_endpoint(
            rl_job_service=deps["rl_job_service"],
            runtime_state=deps["runtime_state"],
            append_log_fn=deps["_rl_append_log"],
        ),
        "list_rl_jobs": api_endpoints.build_list_rl_jobs_endpoint(
            rl_job_service=deps["rl_job_service"],
            runtime_state=deps["runtime_state"],
        ),
        "list_rl_task_history": api_endpoints.build_list_rl_task_history_endpoint(
            rl_job_service=deps["rl_job_service"],
            deps_builder_fn=lambda: api_wiring.build_rl_task_history_deps(
                query_task_history_sqlite_fn=lambda **kw: telemetry_repo.query_task_history(
                    db_path=deps["DB_PATH"], json_loads_or_default=deps["_json_loads_or_default"], **kw
                )
            ),
        ),
        "api_memory_build": api_endpoints.build_memory_build_endpoint(
            memory_api_service=deps["memory_api_service"],
            deps_builder_fn=lambda: api_wiring.build_memory_build_deps(
                build_memory_from_rollouts_fn=deps["_build_memory_from_rollouts"],
                get_memory_stats_fn=lambda: memory_core_ops.get_memory_stats(deps={"db_connect_fn": deps["_db_connect"]}),
            ),
        ),
        "api_memory_search": api_endpoints.build_memory_search_endpoint(
            memory_api_service=deps["memory_api_service"],
            deps_builder_fn=lambda: api_wiring.build_memory_search_deps(search_memory_cases_fn=deps["_search_memory_cases"]),
        ),
        "api_memory_stats": api_endpoints.build_memory_stats_endpoint(
            memory_api_service=deps["memory_api_service"],
            deps_builder_fn=lambda: api_wiring.build_memory_stats_deps(
                get_memory_stats_fn=lambda: memory_core_ops.get_memory_stats(deps={"db_connect_fn": deps["_db_connect"]})
            ),
        ),
        "api_memory_backfill": api_endpoints.build_memory_backfill_endpoint(
            memory_api_service=deps["memory_api_service"],
            deps_builder_fn=lambda: api_wiring.build_memory_backfill_deps(
                backfill_memory_documents_fn=lambda limit=1000: memory_storage_ops.backfill_memory_documents(
                    limit=limit,
                    deps={
                        "db_connect_fn": deps["_db_connect"],
                        "json_dumps_fn": deps["_json_dumps"],
                        "memory_docs_dir": deps["MEMORY_DOCS_DIR"],
                    },
                )
            ),
        ),
        "api_memory_clear": api_endpoints.build_memory_clear_endpoint(
            memory_api_service=deps["memory_api_service"],
            deps_builder_fn=lambda: api_wiring.build_memory_clear_deps(
                clear_all_memory_fn=lambda: memory_core_ops.clear_all_memory(deps={"db_connect_fn": deps["_db_connect"]})
            ),
        ),
        "api_memory_usages": api_endpoints.build_memory_usages_endpoint(
            memory_api_service=deps["memory_api_service"],
            deps_builder_fn=lambda: api_wiring.build_memory_usages_deps(
                query_memory_usage_summary_fn=lambda *, limit, q, task_type: memory_core_ops.query_memory_usage_summary(
                    limit=limit, q=q, task_type=task_type, deps={"db_connect_fn": deps["_db_connect"]}
                )
            ),
        ),
        "api_memory_usage_events": api_endpoints.build_memory_usage_events_endpoint(
            memory_api_service=deps["memory_api_service"],
            deps_builder_fn=lambda: api_wiring.build_memory_usage_events_deps(
                query_memory_usage_events_fn=lambda *, memory_id, limit, offset: memory_core_ops.query_memory_usage_events(
                    memory_id=memory_id,
                    limit=limit,
                    offset=offset,
                    deps={"db_connect_fn": deps["_db_connect"], "json_loads_or_default_fn": deps["_json_loads_or_default"]},
                )
            ),
        ),
        "api_memory_quality": api_endpoints.build_memory_quality_endpoint(
            memory_api_service=deps["memory_api_service"],
            deps_builder_fn=lambda: api_wiring.build_memory_quality_deps(
                query_memory_quality_metrics_fn=lambda: memory_core_ops.query_memory_quality_metrics(
                    deps={"db_connect_fn": deps["_db_connect"], "json_loads_or_default_fn": deps["_json_loads_or_default"]}
                )
            ),
        ),
        "api_memory_aliases": api_endpoints.build_memory_aliases_endpoint(
            memory_api_service=deps["memory_api_service"],
            deps_builder_fn=lambda: api_wiring.build_memory_aliases_deps(
                query_memory_aliases_fn=lambda *, status, limit: _query_memory_aliases(
                    db_connect_fn=deps["_db_connect"],
                    status=status,
                    limit=limit,
                )
            ),
        ),
        "api_memory_alias_review": api_endpoints.build_memory_alias_review_endpoint(
            memory_api_service=deps["memory_api_service"],
            deps_builder_fn=lambda: api_wiring.build_memory_alias_review_deps(
                review_memory_alias_fn=lambda *, alias_type, raw_text, action, normalized_value="": _review_memory_alias(
                    db_connect_fn=deps["_db_connect"],
                    alias_type=alias_type,
                    raw_text=raw_text,
                    action=action,
                    normalized_value=normalized_value,
                )
            ),
        ),
        "chat_resume_context": api_endpoints.build_chat_resume_context_endpoint(
            memory_api_service=deps["memory_api_service"],
            deps_builder_fn=lambda: api_wiring.build_chat_resume_context_deps(
                build_resume_prompt_fn=deps["_build_resume_prompt"],
                safe_str_fn=deps["safe_str_fn"],
            ),
        ),
        "get_rl_job": api_endpoints.build_get_rl_job_endpoint(
            rl_job_service=deps["rl_job_service"],
            get_job_fn=deps["_rl_get_job"],
        ),
    }


def _query_memory_aliases(*, db_connect_fn: Any, status: str, limit: int) -> Dict[str, Any]:
    normalized_status = str(status or "").strip().lower() or "validated"
    cap = max(1, min(int(limit or 20), 200))
    with db_connect_fn() as conn:
        method_total = conn.execute(
            "SELECT COUNT(1) AS c FROM dynamic_method_aliases WHERE status = ?",
            (normalized_status,),
        ).fetchone()["c"]
        method_candidate_total = conn.execute(
            "SELECT COUNT(1) AS c FROM dynamic_method_aliases WHERE status = 'candidate'"
        ).fetchone()["c"]
        method_validated_total = conn.execute(
            "SELECT COUNT(1) AS c FROM dynamic_method_aliases WHERE status = 'validated'"
        ).fetchone()["c"]
        method_rows = conn.execute(
            """
            SELECT raw_text, normalized_value, source, confidence, seen_count, accepted_count, status, first_seen_rollout_id, example_text, updated_at
            FROM dynamic_method_aliases
            WHERE status = ?
            ORDER BY accepted_count DESC, seen_count DESC, updated_at DESC
            LIMIT ?
            """,
            (normalized_status, cap),
        ).fetchall()

    def _pack(rows: Any) -> list[Dict[str, Any]]:
        return [
            {
                "raw_text": str(row["raw_text"] or ""),
                "normalized_value": str(row["normalized_value"] or ""),
                "source": str(row["source"] or ""),
                "confidence": float(row["confidence"] or 0.0),
                "seen_count": int(row["seen_count"] or 0),
                "accepted_count": int(row["accepted_count"] or 0),
                "status": str(row["status"] or ""),
                "first_seen_rollout_id": str(row["first_seen_rollout_id"] or ""),
                "example_text": str(row["example_text"] or ""),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    return {
        "methods": _pack(method_rows),
        "summary": {
            "status": normalized_status,
            "method_total": int(method_total or 0),
            "method_candidate_total": int(method_candidate_total or 0),
            "method_validated_total": int(method_validated_total or 0),
        },
    }


def _review_memory_alias(
    *,
    db_connect_fn: Any,
    alias_type: str,
    raw_text: str,
    action: str,
    normalized_value: str = "",
) -> Dict[str, Any]:
    table = "dynamic_method_aliases"
    next_status = "validated" if action == "approve" else "rejected"
    with db_connect_fn() as conn:
        row = conn.execute(
            f"""
            SELECT raw_text, normalized_value, source, confidence, seen_count, accepted_count, status, first_seen_rollout_id, updated_at
            FROM {table}
            WHERE raw_text = ?
            LIMIT 1
            """,
            (raw_text,),
        ).fetchone()
        if row is None:
            raise ValueError(f"alias not found: {raw_text}")
        final_normalized = normalized_value or str(row["normalized_value"] or "").strip().upper()
        accepted_count = int(row["accepted_count"] or 0)
        if action == "approve":
            accepted_count = max(1, accepted_count + 1)
        conn.execute(
            f"""
            UPDATE {table}
            SET normalized_value = ?, status = ?, accepted_count = ?, updated_at = strftime('%s','now')
            WHERE raw_text = ?
            """,
            (final_normalized, next_status, accepted_count, raw_text),
        )
        conn.commit()

    return {
        "alias_type": alias_type,
        "raw_text": raw_text,
        "normalized_value": final_normalized,
        "status": next_status,
    }


