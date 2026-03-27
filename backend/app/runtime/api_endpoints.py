from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import Body, Query


def build_start_rl_job_endpoint(
    *,
    rl_job_service: Any,
    runtime_state: Any,
    now_iso_fn: Callable[[], str],
    run_rl_job_fn: Callable[[str], Awaitable[None]],
) -> Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    async def endpoint(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await rl_job_service.start_rl_job(
            payload=payload,
            deps={
                "rl_jobs_lock": runtime_state.rl_jobs_lock,
                "rl_jobs": runtime_state.rl_jobs,
                "now_iso_fn": now_iso_fn,
                "run_rl_job_fn": run_rl_job_fn,
            },
        )

    return endpoint


def build_stop_rl_job_endpoint(
    *,
    rl_job_service: Any,
    runtime_state: Any,
    append_log_fn: Callable[[str, str], Any],
) -> Callable[[str], Awaitable[Dict[str, Any]]]:
    async def endpoint(job_id: str) -> Dict[str, Any]:
        return await rl_job_service.stop_rl_job(
            job_id=job_id,
            deps={
                "rl_jobs_lock": runtime_state.rl_jobs_lock,
                "rl_jobs": runtime_state.rl_jobs,
                "append_log_fn": append_log_fn,
            },
        )

    return endpoint


def build_list_rl_jobs_endpoint(
    *,
    rl_job_service: Any,
    runtime_state: Any,
) -> Callable[[int], Awaitable[Dict[str, Any]]]:
    async def endpoint(limit: int = 20) -> Dict[str, Any]:
        return await rl_job_service.list_rl_jobs(
            limit=limit,
            deps={
                "rl_jobs_lock": runtime_state.rl_jobs_lock,
                "rl_jobs": runtime_state.rl_jobs,
            },
        )

    return endpoint


def build_list_rl_task_history_endpoint(
    *,
    rl_job_service: Any,
    deps_builder_fn: Callable[..., Dict[str, Any]],
) -> Callable[..., Awaitable[Dict[str, Any]]]:
    async def endpoint(
        limit: int = 200,
        status: Optional[str] = Query(default=None),
        q: str = Query(default=""),
        label: str = Query(default=""),
        start_time_from: Optional[float] = Query(default=None),
        start_time_to: Optional[float] = Query(default=None),
    ) -> Dict[str, Any]:
        return await rl_job_service.list_rl_task_history(
            limit=limit,
            status=status,
            q=q,
            label=label,
            start_time_from=start_time_from,
            start_time_to=start_time_to,
            deps=deps_builder_fn(),
        )

    return endpoint


def build_memory_build_endpoint(
    *,
    memory_api_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    async def endpoint(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
        return await memory_api_service.api_memory_build(payload=payload, deps=deps_builder_fn())

    return endpoint


def build_memory_search_endpoint(
    *,
    memory_api_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[..., Awaitable[Dict[str, Any]]]:
    async def endpoint(
        q: str = Query(..., description="task query text"),
        top_k: int = Query(default=5),
        task_type: str = Query(default=""),
    ) -> Dict[str, Any]:
        return await memory_api_service.api_memory_search(
            q=q, top_k=top_k, task_type=task_type, deps=deps_builder_fn()
        )

    return endpoint


def build_memory_stats_endpoint(
    *,
    memory_api_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[], Awaitable[Dict[str, Any]]]:
    async def endpoint() -> Dict[str, Any]:
        return await memory_api_service.api_memory_stats(deps=deps_builder_fn())

    return endpoint


def build_memory_backfill_endpoint(
    *,
    memory_api_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    async def endpoint(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
        return await memory_api_service.api_memory_backfill(payload=payload, deps=deps_builder_fn())

    return endpoint


def build_memory_clear_endpoint(
    *,
    memory_api_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[], Awaitable[Dict[str, Any]]]:
    async def endpoint() -> Dict[str, Any]:
        return await memory_api_service.api_memory_clear(deps=deps_builder_fn())

    return endpoint


def build_memory_usages_endpoint(
    *,
    memory_api_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[..., Awaitable[Dict[str, Any]]]:
    async def endpoint(
        limit: int = Query(default=100),
        q: str = Query(default=""),
        task_type: str = Query(default=""),
    ) -> Dict[str, Any]:
        return await memory_api_service.api_memory_usages(
            limit=limit, q=q, task_type=task_type, deps=deps_builder_fn()
        )

    return endpoint


def build_memory_usage_events_endpoint(
    *,
    memory_api_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[..., Awaitable[Dict[str, Any]]]:
    async def endpoint(
        memory_id: str,
        limit: int = Query(default=100),
        offset: int = Query(default=0),
    ) -> Dict[str, Any]:
        return await memory_api_service.api_memory_usage_events(
            memory_id=memory_id, limit=limit, offset=offset, deps=deps_builder_fn()
        )

    return endpoint


def build_memory_quality_endpoint(
    *,
    memory_api_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[], Awaitable[Dict[str, Any]]]:
    async def endpoint() -> Dict[str, Any]:
        return await memory_api_service.api_memory_quality(deps=deps_builder_fn())

    return endpoint


def build_memory_aliases_endpoint(
    *,
    memory_api_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[..., Awaitable[Dict[str, Any]]]:
    async def endpoint(
        status: str = Query(default="validated"),
        limit: int = Query(default=20),
    ) -> Dict[str, Any]:
        return await memory_api_service.api_memory_aliases(
            status=status,
            limit=limit,
            deps=deps_builder_fn(),
        )

    return endpoint


def build_memory_alias_review_endpoint(
    *,
    memory_api_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    async def endpoint(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await memory_api_service.api_memory_alias_review(
            payload=payload,
            deps=deps_builder_fn(),
        )

    return endpoint


def build_chat_resume_context_endpoint(
    *,
    memory_api_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    async def endpoint(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await memory_api_service.chat_resume_context(payload=payload, deps=deps_builder_fn())

    return endpoint


def build_get_rl_job_endpoint(
    *,
    rl_job_service: Any,
    get_job_fn: Callable[[str], Awaitable[Dict[str, Any]]],
) -> Callable[[str, int], Awaitable[Dict[str, Any]]]:
    async def endpoint(job_id: str, log_offset: int = 0) -> Dict[str, Any]:
        return await rl_job_service.get_rl_job(
            job_id=job_id,
            log_offset=log_offset,
            deps={"get_job_fn": get_job_fn},
        )

    return endpoint


