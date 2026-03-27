from __future__ import annotations

from typing import Any, Dict


def build_chat_execution_deps(*, runtime_state, deps: Dict[str, Any]) -> Dict[str, Any]:
    def _get_state() -> Dict[str, Any]:
        return {"task_counter": runtime_state.task_counter}

    def _set_state(**kwargs: Any) -> None:
        if "task_counter" in kwargs:
            runtime_state.task_counter = int(kwargs["task_counter"])
        if kwargs.get("reset_agent"):
            runtime_state.agent_instance = None

    def _reset_agent() -> None:
        runtime_state.agent_instance = None

    return {
        "get_state_fn": _get_state,
        "set_state_fn": _set_state,
        "AspenTask": deps["AspenTaskCls"],
        "get_agent_fn": deps["get_agent_fn"],
        "reset_agent_fn": _reset_agent,
        "store": deps["store"],
        "persist_rollout_start_fn": lambda rollout_id, attempt_id, status, mode, start_time, input_obj, metadata_obj, user_id=None: deps["telemetry_repo"].persist_rollout_start(
            db_path=deps["db_path"],
            json_dumps=deps["json_dumps_fn"],
            rollout_id=rollout_id,
            attempt_id=attempt_id,
            status=status,
            mode=mode,
            start_time=start_time,
            input_obj=input_obj,
            metadata_obj=metadata_obj,
            user_id=user_id,
        ),
        "safe_emit_message_fn": lambda message: deps["emitter_utils"].safe_emit_message(
            message,
            emit_message_fn=deps["al_emit_message_fn"],
            logger=deps["logger"],
        ),
        "safe_emit_annotation_fn": lambda payload: deps["emitter_utils"].safe_emit_annotation(
            payload,
            emit_annotation_fn=deps["al_emit_annotation_fn"],
            logger=deps["logger"],
        ),
        "persist_span_fn": lambda rollout_id, name, attributes, start_time=None, end_time=None, span_id=None: deps["telemetry_repo"].persist_span(
            db_path=deps["db_path"],
            json_dumps=deps["json_dumps_fn"],
            rollout_id=rollout_id,
            name=name,
            attributes=attributes,
            start_time=start_time,
            end_time=end_time,
            span_id=span_id,
        ),
        "infer_task_type_fn": deps["infer_task_type_fn"],
        "build_memory_context_for_task_fn": deps["build_memory_context_for_task_fn"],
        "log_memory_usage_events_fn": lambda rollout_id, query_text, task_type, source, hits: deps["memory_core_ops"].log_memory_usage_events(
            rollout_id=rollout_id,
            query_text=query_text,
            task_type=task_type,
            source=source,
            hits=hits,
            deps={
                "db_connect_fn": deps["db_connect_fn"],
                "json_dumps_fn": deps["json_dumps_fn"],
            },
        ),
        "safe_str_fn": deps["safe_str_fn"],
        "estimate_prompt_tokens_fn": lambda text: deps["reward_engine"].estimate_prompt_tokens(text),
        "build_auto_resume_prompt_fn": deps["chat_helpers"].build_auto_resume_prompt,
        "safe_operation_context_fn": lambda name, attrs: deps["emitter_utils"].safe_operation_context(
            name,
            attrs,
            OperationContextCls=deps["OperationContextCls"],
            logger=deps["logger"],
        ),
        "extract_tool_result_payload_fn": deps["chat_helpers"].extract_tool_result_payload,
        "is_context_overflow_error_fn": deps["chat_helpers"].is_context_overflow_error,
        "query_spans_sqlite_fn": lambda rollout_id: deps["telemetry_repo"].query_spans(
            db_path=deps["db_path"],
            json_loads_or_default=deps["json_loads_or_default_fn"],
            rollout_id=rollout_id,
        ),
        "collect_simulation_metrics_fn": deps["collect_simulation_metrics_fn"],
        "extract_run_attempts_fn": deps["extract_run_attempts_fn"],
        "extract_strategy_from_spans_fn": deps["extract_strategy_from_spans_fn"],
        "extract_config_snippet_from_spans_fn": deps["extract_config_snippet_from_spans_fn"],
        "extract_pitfall_details_from_spans_fn": deps["extract_pitfall_details_from_spans_fn"],
        "build_pitfall_summary_fn": deps["build_pitfall_summary_fn"],
        "extract_pitfalls_from_spans_fn": deps["extract_pitfalls_from_spans_fn"],
        "memory_tags_fn": deps["memory_tags_fn"],
        "upsert_case_fn": deps["upsert_case_fn"],
        "calculate_reward_fn": lambda response_content, tool_call_count, file_download_count, *, task_type="unknown", simulation_metrics=None, user_message="", elapsed_seconds=0.0, memory_hit_count=0, memory_usage_count=0, spans=None: deps["reward_engine"].calculate_reward(
            response_content,
            tool_call_count,
            file_download_count,
            task_type=task_type,
            simulation_metrics=simulation_metrics,
            user_message=user_message,
            infer_task_type_fn=deps["infer_task_type_fn"],
            elapsed_seconds=elapsed_seconds,
            memory_hit_count=memory_hit_count,
            memory_usage_count=memory_usage_count,
            spans=spans,
        ),
        "safe_emit_reward_fn": lambda *, reward, dimensions=None: deps["emitter_utils"].safe_emit_reward(
            reward=reward,
            dimensions=dimensions,
            emit_reward_fn=deps["al_emit_reward_fn"],
            logger=deps["logger"],
        ),
        "persist_rollout_status_fn": lambda rollout_id, status, end_time=None: deps["telemetry_repo"].persist_rollout_status(
            deps["db_path"],
            rollout_id=rollout_id,
            status=status,
            end_time=end_time,
        ),
        "finalize_memory_usage_events_fn": lambda rollout_id, status, reward, tool_call_count: deps["memory_core_ops"].finalize_memory_usage_events(
            rollout_id=rollout_id,
            status=status,
            reward=reward,
            tool_call_count=tool_call_count,
            deps={"db_connect_fn": deps["db_connect_fn"]},
        ),
        "auto_upsert_memory_from_rollout_fn": deps["auto_upsert_memory_from_rollout_fn"],
        "build_user_friendly_error_fn": deps["chat_helpers"].build_user_friendly_error,
        "policy_suggest_fn": deps.get("policy_suggest_fn"),
        "build_policy_guidance_fn": deps.get("build_policy_guidance_fn"),
        "logger": deps["logger"],
        "memory_min_reward": deps["memory_min_reward"],
        "policy_mode": deps.get("policy_mode", "off"),
        "select_prompt_assignment_fn": deps.get("select_prompt_assignment_fn"),
        "build_effective_system_prompt_fn": deps.get("build_effective_system_prompt_fn"),
        "record_prompt_assignment_fn": deps.get("record_prompt_assignment_fn"),
        "prompt_version_mode": deps.get("prompt_version_mode", "off"),
    }
