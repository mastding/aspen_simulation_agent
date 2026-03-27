from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional


def build_set_sse_control_fn(
    *,
    state_ops: Any,
    runtime_state: Any,
) -> Callable[..., Awaitable[None]]:
    async def endpoint(
        session_id: str,
        *,
        running: Optional[bool] = None,
        cancel_token: Optional[Any] = None,
        rollout_id: Optional[str] = None,
    ) -> None:
        await state_ops.set_sse_control(
            runtime_state=runtime_state,
            session_id=session_id,
            running=running,
            cancel_token=cancel_token,
            rollout_id=rollout_id,
        )

    return endpoint


def build_get_sse_control_fn(
    *,
    state_ops: Any,
    runtime_state: Any,
) -> Callable[[str], Awaitable[Dict[str, Any]]]:
    async def endpoint(session_id: str) -> Dict[str, Any]:
        return await state_ops.get_sse_control(runtime_state=runtime_state, session_id=session_id)

    return endpoint


def build_rl_append_log_fn(
    *,
    state_ops: Any,
    runtime_state: Any,
    now_iso_fn: Callable[[], str],
    trim_logs_fn: Callable[[list], list],
) -> Callable[[str, str, str], Awaitable[None]]:
    async def endpoint(job_id: str, message: str, level: str = "info") -> None:
        await state_ops.rl_append_log(
            runtime_state=runtime_state,
            job_id=job_id,
            message=message,
            level=level,
            now_iso_fn=now_iso_fn,
            trim_logs_fn=trim_logs_fn,
        )

    return endpoint


def build_rl_set_job_fn(
    *,
    state_ops: Any,
    runtime_state: Any,
) -> Callable[..., Awaitable[None]]:
    async def endpoint(job_id: str, **updates: Any) -> None:
        await state_ops.rl_set_job(runtime_state=runtime_state, job_id=job_id, updates=updates)

    return endpoint


def build_rl_get_job_fn(
    *,
    state_ops: Any,
    runtime_state: Any,
) -> Callable[[str], Awaitable[Dict[str, Any]]]:
    async def endpoint(job_id: str) -> Dict[str, Any]:
        return await state_ops.rl_get_job(runtime_state=runtime_state, job_id=job_id)

    return endpoint
