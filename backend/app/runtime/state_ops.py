from __future__ import annotations

import json
from typing import Any, Dict


async def set_sse_control(
    *,
    runtime_state,
    session_id: str,
    running: bool | None = None,
    cancel_token: Any = None,
    rollout_id: str | None = None,
) -> None:
    async with runtime_state.sse_controls_lock:
        control = runtime_state.sse_controls.setdefault(session_id, {})
        if running is not None:
            control["running"] = running
            if running is False:
                control["cancel_token"] = None
        if cancel_token is not None:
            control["cancel_token"] = cancel_token
        if rollout_id is not None:
            control["rollout_id"] = rollout_id
        elif rollout_id is None and "rollout_id" in control and running is False:
            control["rollout_id"] = None


async def get_sse_control(*, runtime_state, session_id: str) -> Dict[str, Any]:
    async with runtime_state.sse_controls_lock:
        return dict(runtime_state.sse_controls.get(session_id, {}))


async def rl_append_log(
    *,
    runtime_state,
    job_id: str,
    message: str,
    level: str,
    now_iso_fn,
    trim_logs_fn,
) -> None:
    async with runtime_state.rl_jobs_lock:
        job = runtime_state.rl_jobs.get(job_id)
        if not job:
            return
        job.setdefault("logs", []).append(
            {
                "ts": now_iso_fn(),
                "level": level,
                "message": str(message),
            }
        )
        trim_logs_fn(job["logs"])


async def rl_set_job(*, runtime_state, job_id: str, updates: Dict[str, Any]) -> None:
    async with runtime_state.rl_jobs_lock:
        job = runtime_state.rl_jobs.get(job_id)
        if not job:
            return
        job.update(updates)


async def rl_get_job(*, runtime_state, job_id: str) -> Dict[str, Any]:
    async with runtime_state.rl_jobs_lock:
        job = runtime_state.rl_jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        return json.loads(json.dumps(job, ensure_ascii=False, default=str))


