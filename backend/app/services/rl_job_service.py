from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import HTTPException


async def start_rl_job(*, payload: Dict[str, Any], deps: Dict[str, Any]) -> Dict[str, Any]:
    rl_jobs_lock = deps["rl_jobs_lock"]
    rl_jobs = deps["rl_jobs"]
    now_iso = deps["now_iso_fn"]
    run_rl_job_fn = deps["run_rl_job_fn"]

    async with rl_jobs_lock:
        active = [job for job in rl_jobs.values() if str(job.get("status")) in {"queued", "running"}]
        if active:
            raise HTTPException(status_code=409, detail="An RL job is already running")

    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        raise HTTPException(status_code=400, detail="tasks must be a list")
    clean_tasks = [str(item).strip() for item in tasks if str(item).strip()]
    if not clean_tasks:
        raise HTTPException(status_code=400, detail="tasks is empty")

    job_id = f"rl-{uuid.uuid4().hex[:12]}"
    config = {
        "tasks": clean_tasks,
        "max_tasks": int(payload.get("max_tasks", len(clean_tasks))),
        "reset_db": bool(payload.get("reset_db", False)),
        "run_training": bool(payload.get("run_training", True)),
        "training_mode": str(payload.get("training_mode", "test")),
        "online_iterations": max(1, int(payload.get("online_iterations", 1))),
        "train_algo": str(payload.get("train_algo", "rgo")).strip().lower() or "rgo",
        "apo_config": payload.get("apo_config", {}) if isinstance(payload.get("apo_config", {}), dict) else {},
        "collection_backend": str(payload.get("collection_backend", "internal")).strip() or "internal",
        "collect_timeout": float(payload.get("collect_timeout", 120.0)),
        "label": str(payload.get("label", "")).strip(),
    }
    if config["collection_backend"] not in {"internal", "script_sse"}:
        raise HTTPException(status_code=400, detail="collection_backend must be internal or script_sse")
    if config["train_algo"] not in {"rgo", "apo"}:
        raise HTTPException(status_code=400, detail="train_algo must be rgo or apo")
    if config["train_algo"] == "apo":
        apo_cfg = config["apo_config"]
        try:
            config["apo_config"] = {
                "iters": max(1, int(apo_cfg.get("iters", 4))),
                "sample_size": max(1, int(apo_cfg.get("sample_size", 6))),
                "exploration": max(0.05, min(1.0, float(apo_cfg.get("exploration", 0.35)))),
            }
        except Exception:
            raise HTTPException(status_code=400, detail="invalid apo_config")
    else:
        config["apo_config"] = {}
    if config["max_tasks"] <= 0:
        config["max_tasks"] = len(clean_tasks)

    async with rl_jobs_lock:
        rl_jobs[job_id] = {
            "job_id": job_id,
            "username": payload.pop("_username", "unknown"),
            "status": "queued",
            "stage": "queued",
            "created_at": time.time(),
            "started_at": None,
            "ended_at": None,
            "config": config,
            "logs": [{"ts": now_iso(), "level": "info", "message": "Job queued"}],
            "task_results": [],
            "training_result": None,
            "summary": None,
            "error": None,
            "stop_requested": False,
            "current_task_index": None,
            "current_cancel_token_id": None,
            "current_process_pid": None,
        }
    job_task = asyncio.create_task(run_rl_job_fn(job_id))
    async with rl_jobs_lock:
        rl_jobs[job_id]["_task"] = job_task
    return {"job_id": job_id, "status": "queued"}


async def stop_rl_job(*, job_id: str, deps: Dict[str, Any]) -> Dict[str, Any]:
    rl_jobs_lock = deps["rl_jobs_lock"]
    rl_jobs = deps["rl_jobs"]
    append_log_fn = deps["append_log_fn"]

    async with rl_jobs_lock:
        job = rl_jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        job["stop_requested"] = True
        if str(job.get("status")) in {"queued", "running"}:
            job["status"] = "stopping"
            job["stage"] = "stopping"
        task_ref = job.get("_task")
        proc_pid = job.get("current_process_pid")

    if isinstance(task_ref, asyncio.Task):
        task_ref.cancel()
    if proc_pid:
        try:
            os.kill(int(proc_pid), 15)
        except Exception:
            pass
    await append_log_fn(job_id, "Stop requested by user", "warning")
    return {"job_id": job_id, "status": "stopping"}


async def list_rl_jobs(*, limit: int, deps: Dict[str, Any]) -> Dict[str, Any]:
    rl_jobs_lock = deps["rl_jobs_lock"]
    rl_jobs = deps["rl_jobs"]
    async with rl_jobs_lock:
        rows = sorted(list(rl_jobs.values()), key=lambda x: float(x.get("created_at") or 0), reverse=True)[: max(1, min(limit, 100))]
        items = []
        for row in rows:
            items.append(
                {
                    "job_id": row.get("job_id"),
                    "status": row.get("status"),
                    "stage": row.get("stage"),
                    "created_at": row.get("created_at"),
                    "started_at": row.get("started_at"),
                    "ended_at": row.get("ended_at"),
                    "summary": row.get("summary"),
                    "label": (row.get("config") or {}).get("label", ""),
                    "username": row.get("username", "unknown"),
                }
            )
    return {"jobs": items}


async def list_rl_task_history(
    *,
    limit: int,
    status: Optional[str],
    q: str,
    label: str,
    start_time_from: Optional[float],
    start_time_to: Optional[float],
    deps: Dict[str, Any],
) -> Dict[str, Any]:
    query_task_history_sqlite_fn = deps["query_task_history_sqlite_fn"]
    items = query_task_history_sqlite_fn(
        limit=limit,
        status=status,
        q=q,
        label=label,
        start_time_from=start_time_from,
        start_time_to=start_time_to,
    )
    return {"total": len(items), "items": items}


async def get_rl_job(*, job_id: str, log_offset: int, deps: Dict[str, Any]) -> Dict[str, Any]:
    get_job_fn = deps["get_job_fn"]
    try:
        job = await get_job_fn(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found")

    logs = job.get("logs", [])
    offset = max(0, int(log_offset))
    sliced_logs = logs[offset:]
    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "stage": job.get("stage"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "ended_at": job.get("ended_at"),
        "config": job.get("config"),
        "summary": job.get("summary"),
        "error": job.get("error"),
        "task_results": job.get("task_results", []),
        "training_result": job.get("training_result"),
        "logs": sliced_logs,
        "log_total": len(logs),
        "next_log_offset": offset + len(sliced_logs),
    }
