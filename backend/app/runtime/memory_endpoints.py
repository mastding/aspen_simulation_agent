from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List


def build_search_memory_cases_fn(
    *,
    runtime_wiring: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[str, int, str], List[Dict[str, Any]]]:
    def endpoint(query: str, top_k: int = 5, task_type: str = "") -> List[Dict[str, Any]]:
        return runtime_wiring.search_memory_cases(
            query=query,
            top_k=top_k,
            task_type=task_type,
            deps=deps_builder_fn(),
        )

    return endpoint


def build_memory_search_experience_tool_endpoint(
    *,
    memory_api_service: Any,
    search_memory_cases_fn: Callable[[str, int, str], List[Dict[str, Any]]],
    safe_str_fn: Callable[[Any], str],
    json_dumps_fn: Callable[[Any], str],
) -> Callable[[str, int, str], Awaitable[str]]:
    async def endpoint(query: str, top_k: int = 5, task_type: str = "") -> str:
        return await memory_api_service.memory_search_experience_tool(
            query=query,
            top_k=top_k,
            task_type=task_type,
            deps={
                "search_memory_cases_fn": search_memory_cases_fn,
                "safe_str_fn": safe_str_fn,
                "json_dumps_fn": json_dumps_fn,
            },
        )

    endpoint.__name__ = "memory_search_experience"
    return endpoint


def build_memory_get_experience_tool_endpoint(
    *,
    memory_api_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[str, bool], Awaitable[str]]:
    async def endpoint(memory_id: str, include_markdown: bool = True) -> str:
        return await memory_api_service.memory_get_experience_tool(
            memory_id=memory_id,
            include_markdown=include_markdown,
            deps=deps_builder_fn(),
        )

    endpoint.__name__ = "memory_get_experience"
    return endpoint


def build_resume_prompt_fn(
    *,
    runtime_wiring: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[str, str], Dict[str, Any]]:
    def endpoint(rollout_id: str, resume_message: str = "") -> Dict[str, Any]:
        return runtime_wiring.build_resume_prompt(
            rollout_id=rollout_id,
            resume_message=resume_message,
            deps=deps_builder_fn(),
        )

    return endpoint


def build_memory_from_rollouts_fn(
    *,
    runtime_wiring: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[float, int], Dict[str, Any]]:
    def endpoint(min_reward: float = 0.8, limit: int = 200) -> Dict[str, Any]:
        return runtime_wiring.build_memory_from_rollouts(
            min_reward=min_reward,
            limit=limit,
            deps=deps_builder_fn(),
        )

    return endpoint


def build_memory_context_for_task_fn(
    *,
    runtime_wiring: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[str, int], Dict[str, Any]]:
    def endpoint(user_message: str, top_k: int = 5) -> Dict[str, Any]:
        return runtime_wiring.build_memory_context_for_task(
            user_message=user_message,
            top_k=top_k,
            deps=deps_builder_fn(),
        )

    return endpoint


def build_collect_simulation_metrics_fn(
    *,
    runtime_wiring: Any,
    normalize_text_fn: Callable[[str], str],
) -> Callable[[List[Dict[str, Any]]], Dict[str, int]]:
    def endpoint(spans: List[Dict[str, Any]]) -> Dict[str, int]:
        return runtime_wiring.collect_simulation_metrics(
            spans=spans,
            deps={"normalize_text_fn": normalize_text_fn},
        )

    return endpoint
