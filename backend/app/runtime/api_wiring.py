from __future__ import annotations

from typing import Any, Callable, Dict


def build_rl_task_history_deps(*, query_task_history_sqlite_fn: Callable[..., Any]) -> Dict[str, Any]:
    return {"query_task_history_sqlite_fn": query_task_history_sqlite_fn}


def build_memory_build_deps(*, build_memory_from_rollouts_fn: Callable[..., Any], get_memory_stats_fn: Callable[..., Any]) -> Dict[str, Any]:
    return {
        "build_memory_from_rollouts_fn": build_memory_from_rollouts_fn,
        "get_memory_stats_fn": get_memory_stats_fn,
    }


def build_memory_search_deps(*, search_memory_cases_fn: Callable[..., Any]) -> Dict[str, Any]:
    return {"search_memory_cases_fn": search_memory_cases_fn}


def build_memory_stats_deps(*, get_memory_stats_fn: Callable[..., Any]) -> Dict[str, Any]:
    return {"get_memory_stats_fn": get_memory_stats_fn}


def build_memory_backfill_deps(*, backfill_memory_documents_fn: Callable[..., Any]) -> Dict[str, Any]:
    return {"backfill_memory_documents_fn": backfill_memory_documents_fn}


def build_memory_clear_deps(*, clear_all_memory_fn: Callable[..., Any]) -> Dict[str, Any]:
    return {"clear_all_memory_fn": clear_all_memory_fn}


def build_memory_usages_deps(*, query_memory_usage_summary_fn: Callable[..., Any]) -> Dict[str, Any]:
    return {"query_memory_usage_summary_fn": query_memory_usage_summary_fn}


def build_memory_usage_events_deps(*, query_memory_usage_events_fn: Callable[..., Any]) -> Dict[str, Any]:
    return {"query_memory_usage_events_fn": query_memory_usage_events_fn}


def build_memory_quality_deps(*, query_memory_quality_metrics_fn: Callable[..., Any]) -> Dict[str, Any]:
    return {"query_memory_quality_metrics_fn": query_memory_quality_metrics_fn}


def build_memory_aliases_deps(*, query_memory_aliases_fn: Callable[..., Any]) -> Dict[str, Any]:
    return {"query_memory_aliases_fn": query_memory_aliases_fn}


def build_memory_alias_review_deps(*, review_memory_alias_fn: Callable[..., Any]) -> Dict[str, Any]:
    return {"review_memory_alias_fn": review_memory_alias_fn}


def build_chat_resume_context_deps(*, build_resume_prompt_fn: Callable[..., Any], safe_str_fn: Callable[..., Any]) -> Dict[str, Any]:
    return {
        "build_resume_prompt_fn": build_resume_prompt_fn,
        "safe_str_fn": safe_str_fn,
    }




