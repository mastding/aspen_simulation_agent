from __future__ import annotations

from typing import Any, Dict, List

from app.memory import core_ops as memory_core_ops
from app.memory import extractors as memory_extractors
from app.memory import matching as memory_matching
from app.memory import pipeline_ops as memory_pipeline_ops
from app.memory import storage_ops as memory_storage_ops
from app.rl import reward as reward_engine


def search_memory_cases(*, query: str, top_k: int, task_type: str, deps: Dict[str, Any]) -> List[Dict[str, Any]]:
    return memory_pipeline_ops.search_memory_cases(
        query=query,
        top_k=top_k,
        task_type=task_type,
        deps={
            "db_connect_fn": deps["db_connect_fn"],
            "normalize_text_fn": deps["normalize_text_fn"],
            "extract_match_fields_fn": deps["extract_match_fields_fn"],
            "match_required_fields_fn": deps["match_required_fields_fn"],
            "json_loads_or_default_fn": deps["json_loads_or_default_fn"],
            "infer_task_type_fn": deps["infer_task_type_fn"],
            "build_semantic_profile_fn": deps["build_semantic_profile_fn"],
            "score_semantic_similarity_fn": deps["score_semantic_similarity_fn"],
            "list_validated_dynamic_methods_fn": deps.get("list_validated_dynamic_methods_fn", lambda: []),
            "list_validated_dynamic_component_aliases_fn": deps.get("list_validated_dynamic_component_aliases_fn", lambda: {}),
        },
    )


def build_resume_prompt(*, rollout_id: str, resume_message: str, deps: Dict[str, Any]) -> Dict[str, Any]:
    return memory_core_ops.build_resume_prompt(
        rollout_id=rollout_id,
        resume_message=resume_message,
        deps={
            "db_connect_fn": deps["db_connect_fn"],
            "json_loads_or_default_fn": deps["json_loads_or_default_fn"],
            "query_spans_sqlite_fn": deps["query_spans_sqlite_fn"],
            "extract_config_snippet_from_spans_fn": deps["extract_config_snippet_from_spans_fn"],
            "extract_strategy_from_spans_fn": deps["extract_strategy_from_spans_fn"],
            "extract_pitfalls_from_spans_fn": deps["extract_pitfalls_from_spans_fn"],
            "extract_reward_and_tool_count_fn": deps["extract_reward_and_tool_count_fn"],
            "safe_str_fn": deps["safe_str_fn"],
        },
    )


def build_memory_from_rollouts(*, min_reward: float, limit: int, deps: Dict[str, Any]) -> Dict[str, Any]:
    return memory_pipeline_ops.build_memory_from_rollouts(
        min_reward=min_reward,
        limit=limit,
        deps={
            "db_connect_fn": deps["db_connect_fn"],
            "json_loads_or_default_fn": deps["json_loads_or_default_fn"],
            "query_spans_sqlite_fn": deps["query_spans_sqlite_fn"],
            "extract_reward_and_tool_count_fn": deps["extract_reward_and_tool_count_fn"],
            "infer_task_type_fn": deps["infer_task_type_fn"],
            "extract_strategy_from_spans_fn": deps["extract_strategy_from_spans_fn"],
            "extract_config_snippet_from_spans_fn": deps["extract_config_snippet_from_spans_fn"],
            "extract_pitfall_details_from_spans_fn": deps["extract_pitfall_details_from_spans_fn"],
            "extract_pitfalls_from_spans_fn": deps["extract_pitfalls_from_spans_fn"],
            "upsert_case_fn": lambda **kwargs: memory_storage_ops.upsert_memory_case(
                deps={
                    "db_connect_fn": deps["db_connect_fn"],
                    "json_dumps_fn": deps["json_dumps_fn"],
                    "normalize_text_fn": deps["normalize_text_fn"],
                    "memory_docs_dir": deps["memory_docs_dir"],
                    "list_validated_dynamic_methods_fn": deps.get("list_validated_dynamic_methods_fn", lambda: []),
                    "list_validated_dynamic_component_aliases_fn": deps.get("list_validated_dynamic_component_aliases_fn", lambda: {}),
                },
                **kwargs,
            ),
        },
    )


def build_memory_context_for_task(*, user_message: str, top_k: int, deps: Dict[str, Any]) -> Dict[str, Any]:
    return memory_core_ops.build_memory_context_for_task(
        user_message=user_message,
        top_k=top_k,
        deps={
            "infer_task_type_fn": deps["infer_task_type_fn"],
            "search_memory_cases_fn": deps["search_memory_cases_fn"],
            "safe_str_fn": deps["safe_str_fn"],
        },
    )


def collect_simulation_metrics(*, spans: List[Dict[str, Any]], deps: Dict[str, Any]) -> Dict[str, int]:
    return reward_engine.collect_simulation_metrics_from_spans(
        spans,
        extract_error_type_fn=lambda result_obj, fallback_text="": memory_extractors.extract_error_type_from_payload(
            result_obj,
            fallback_text,
            classify_run_simulation_error_fn=lambda err: reward_engine.classify_run_simulation_error(
                err,
                normalize_text_fn=deps["normalize_text_fn"],
            ),
        ),
    )


def build_semantic_profile(
    *,
    texts: List[str],
    task_type: str = "",
    dynamic_methods: List[str] | None = None,
    dynamic_component_aliases: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    return memory_matching.build_semantic_profile(
        texts,
        task_type=task_type,
        dynamic_methods=dynamic_methods,
        dynamic_component_aliases=dynamic_component_aliases,
    )


def score_semantic_similarity(*, query_profile: Dict[str, Any], memory_profile: Dict[str, Any]) -> Dict[str, Any]:
    score, details = memory_matching.score_semantic_similarity(query_profile, memory_profile)
    return {"score": score, "details": details}
