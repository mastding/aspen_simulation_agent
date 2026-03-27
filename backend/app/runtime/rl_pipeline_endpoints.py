from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict


def build_run_training_subprocess_fn(
    *,
    training_process_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[str, str, str, Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    async def endpoint(job_id: str, mode: str, train_algo: str, apo_config: Dict[str, Any]) -> Dict[str, Any]:
        return await training_process_service.run_training_subprocess(
            job_id=job_id,
            mode=mode,
            train_algo=train_algo,
            apo_config=apo_config,
            deps=deps_builder_fn(),
        )

    return endpoint


def build_run_collection_subprocess_fn(
    *,
    training_process_service: Any,
    deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    async def endpoint(job_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        return await training_process_service.run_collection_subprocess(
            job_id=job_id,
            config=config,
            deps=deps_builder_fn(),
        )

    return endpoint


def build_run_rl_job_fn(
    *,
    rl_worker_service: Any,
    job_deps_builder_fn: Callable[[], Dict[str, Any]],
) -> Callable[[str], Awaitable[None]]:
    async def endpoint(job_id: str) -> None:
        await rl_worker_service.run_rl_job(job_id, deps=job_deps_builder_fn())

    return endpoint
