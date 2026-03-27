from __future__ import annotations

import asyncio
import importlib
import sys
from typing import Any, Dict, List, Optional


async def _auto_publish_prompts(job_id: str, run_id: str, *, deps: Dict[str, Any]) -> bool:
    """Auto-publish prompt candidates after training."""
    import subprocess
    from pathlib import Path

    rl_append_log = deps["rl_append_log_fn"]

    try:
        await rl_append_log(job_id, f"Auto-publishing prompts from run {run_id}...")

        # Build paths
        rl_root = Path(deps.get("rl_root", "/run/code/dinglei/aspen_simulation_new/backend/rl"))
        apply_script = rl_root / "src" / "apply_prompt_candidates.py"
        run_dir = rl_root / "training_runs" / f"run_{run_id}"
        prompt_dir = Path(deps.get("prompt_dir", "/run/code/dinglei/aspen_simulation_new/backend/prompt"))

        if not apply_script.exists():
            await rl_append_log(job_id, f"Warning: apply script not found at {apply_script}", "warning")
            return False

        if not run_dir.exists():
            await rl_append_log(job_id, f"Warning: run dir not found at {run_dir}", "warning")
            return False

        cmd = [
            "python3",
            str(apply_script),
            "--run-dir",
            str(run_dir),
            "--prompt-dir",
            str(prompt_dir),
            "--apply",
            "--emit-json",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            await rl_append_log(job_id, f"Auto-publish failed: {result.stderr}", "error")
            return False

        import json
        try:
            output = json.loads(result.stdout)
            updated_files = output.get("updated_files", [])
            if updated_files:
                await rl_append_log(job_id, f"Auto-published {len(updated_files)} prompt files")
                for item in updated_files:
                    await rl_append_log(job_id, f"  Updated: {item['path']}")
                return True
            else:
                await rl_append_log(job_id, "No prompt changes to publish")
                return False
        except json.JSONDecodeError:
            await rl_append_log(job_id, f"Auto-publish output: {result.stdout[:200]}")
            return True

    except subprocess.TimeoutExpired:
        await rl_append_log(job_id, "Auto-publish timeout", "error")
        return False
    except Exception as exc:
        await rl_append_log(job_id, f"Auto-publish exception: {exc}", "error")
        return False


def _reload_prompt_modules() -> str:
    """Force-reload prompt modules so the running process picks up disk changes.

    Returns the new system_prompt text.
    """
    # The import chain: llm_prompt imports schema_check, thought_process, etc.
    # We must reload in dependency order: leaves first, then the root.
    prompt_modules = [
        "prompt.schema_get",
        "prompt.result_get",
        "prompt.thought_process",
        "prompt.schema_check",
        "prompt.llm_prompt",
    ]
    for mod_name in prompt_modules:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])

    # Return the freshly loaded system_prompt
    from backend.app.prompts.llm_prompt import system_prompt
    return system_prompt


async def _run_collection_phase(
    job_id: str,
    task_messages: List[str],
    config: Dict[str, Any],
    iteration: int,
    is_online: bool,
    *,
    deps: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], bool]:
    """Run collection phase for one iteration. Returns (task_results, stopped)."""
    rl_jobs_lock = deps["rl_jobs_lock"]
    rl_jobs = deps["rl_jobs"]
    rl_set_job = deps["rl_set_job_fn"]
    rl_append_log = deps["rl_append_log_fn"]
    run_collection_subprocess = deps["run_collection_subprocess_fn"]
    execute_user_task = deps["execute_user_task_fn"]
    db_connect = deps["db_connect_fn"]
    CancellationToken = deps["CancellationToken"]

    task_results: List[Dict[str, Any]] = []
    collector_backend = str(config.get("collection_backend", "internal")).strip() or "internal"

    if collector_backend == "script_sse":
        collection_result = await run_collection_subprocess(job_id, config)
        await rl_set_job(job_id, collection_result=collection_result)
        task_results = list(collection_result.get("task_results", []))
        await rl_set_job(job_id, task_results=task_results)
        if int(collection_result.get("returncode", 1)) != 0:
            await rl_append_log(job_id, "Collection script failed", "error")
            return task_results, True
    else:
        msgs = list(task_messages)
        max_tasks = int(config.get("max_tasks", len(msgs)))
        if max_tasks > 0:
            msgs = msgs[:max_tasks]

        for index, msg in enumerate(msgs, start=1):
            async with rl_jobs_lock:
                running_job = rl_jobs.get(job_id, {})
                if running_job.get("stop_requested"):
                    await rl_append_log(job_id, "Stop requested before next task", "warning")
                    return task_results, True

            cancel_token = CancellationToken()
            await rl_set_job(job_id, current_task_index=index, current_cancel_token_id=id(cancel_token))
            rollout_id_holder = {"rollout_id": ""}

            _iter = iteration
            _idx = index

            async def _capture(payload_obj: Dict[str, Any]) -> None:
                ptype = str(payload_obj.get("type", ""))
                if ptype == "rollout_started":
                    rollout_id_holder["rollout_id"] = str(payload_obj.get("rollout_id", ""))
                    await rl_append_log(job_id, f"[iter{_iter}][{_idx}] rollout_started {rollout_id_holder['rollout_id']}")
                elif ptype == "error":
                    err = str(payload_obj.get("error_message") or payload_obj.get("error") or "unknown")
                    await rl_append_log(job_id, f"[iter{_iter}][{_idx}] error: {err}", "error")
                elif ptype == "done":
                    await rl_append_log(job_id, f"[iter{_iter}][{_idx}] done reward={payload_obj.get('reward')}")
                elif ptype == "stopped":
                    await rl_append_log(job_id, f"[iter{_iter}][{_idx}] stopped", "warning")

            await rl_append_log(job_id, f"[iter{iteration}][{index}/{len(msgs)}] start task")

            # Build extra_metadata for online training
            extra_meta: Dict[str, Any] = {}
            if is_online and iteration > 1:
                # Disable memory for iteration 2+ so we purely test new prompts
                extra_meta["disable_memory"] = True

            try:
                rollout_id = await execute_user_task(
                    user_message=msg,
                    send_payload=_capture,
                    cancel_token=cancel_token,
                    source="rl_lab",
                    extra_metadata=extra_meta if extra_meta else None,
                )
            except Exception as exc:
                await rl_append_log(job_id, f"[iter{iteration}][{index}] exception: {exc}", "error")
                rollout_id = rollout_id_holder["rollout_id"]

            if not rollout_id:
                rollout_id = rollout_id_holder["rollout_id"]

            rollout_status = "unknown"
            if rollout_id:
                try:
                    with db_connect() as conn:
                        row = conn.execute(
                            "SELECT status, start_time, end_time FROM rollouts WHERE rollout_id = ?",
                            (rollout_id,),
                        ).fetchone()
                    if row:
                        rollout_status = str(row["status"])
                except Exception:
                    pass

            task_results.append(
                {
                    "index": index,
                    "iteration": iteration,
                    "message": msg,
                    "rollout_id": rollout_id,
                    "status": rollout_status,
                }
            )
            await rl_set_job(job_id, task_results=task_results)

    return task_results, False


async def run_rl_job(job_id: str, *, deps: Dict[str, Any]) -> None:
    rl_jobs_lock = deps["rl_jobs_lock"]
    rl_jobs = deps["rl_jobs"]
    rl_set_job = deps["rl_set_job_fn"]
    rl_append_log = deps["rl_append_log_fn"]
    reset_rollouts_db = deps["reset_rollouts_db_fn"]
    run_training_subprocess = deps["run_training_subprocess_fn"]
    build_training_overview = deps["build_training_overview_fn"]
    logger = deps["logger"]
    time_mod = deps["time_mod"]

    try:
        async with rl_jobs_lock:
            job = rl_jobs[job_id]
            config = dict(job.get("config", {}))

        task_messages = [str(x).strip() for x in config.get("tasks", []) if str(x).strip()]
        if not task_messages:
            await rl_set_job(job_id, status="failed", ended_at=time_mod.time(), error="No tasks provided")
            await rl_append_log(job_id, "No tasks provided", "error")
            return

        if bool(config.get("reset_db", False)):
            reset_rollouts_db()
            await rl_append_log(job_id, "Trajectory DB reset completed")

        # Extract training config
        run_training = bool(config.get("run_training", True))
        train_algo = str(config.get("train_algo", "rgo")).strip().lower() or "rgo"
        apo_config = config.get("apo_config", {}) if isinstance(config.get("apo_config", {}), dict) else {}
        training_mode = str(config.get("training_mode", "test")).strip() or "test"
        online_iterations = int(config.get("online_iterations", 1))
        if train_algo not in {"rgo", "apo"}:
            train_algo = "rgo"
        if online_iterations < 1:
            online_iterations = 1

        is_online = training_mode == "online" and online_iterations > 1

        if is_online:
            await rl_append_log(job_id, f"Online training mode: {online_iterations} iterations (memory disabled for iter 2+)")
        else:
            await rl_append_log(job_id, f"Offline training mode: single pass")

        await rl_set_job(job_id, status="running", stage="collecting", started_at=time_mod.time())

        all_task_results: List[Dict[str, Any]] = []
        all_training_results: List[Dict[str, Any]] = []
        stopped = False

        iterations_to_run = online_iterations if is_online else 1

        for iteration in range(1, iterations_to_run + 1):
            if stopped:
                break

            async with rl_jobs_lock:
                running_job = rl_jobs.get(job_id, {})
                if running_job.get("stop_requested"):
                    await rl_append_log(job_id, f"Stop requested before iteration {iteration}", "warning")
                    stopped = True
                    break

            await rl_append_log(job_id, f"=== Iteration {iteration}/{iterations_to_run} ===")

            # Collection phase
            await rl_set_job(job_id, stage=f"collecting_iter{iteration}")
            await rl_append_log(job_id, f"Collection started (iteration {iteration}). task_count={len(task_messages)}")

            task_results, collection_stopped = await _run_collection_phase(
                job_id, task_messages, config, iteration, is_online, deps=deps
            )
            all_task_results.extend(task_results)

            if collection_stopped:
                stopped = True
                break

            # Training phase
            if run_training:
                await rl_set_job(job_id, stage=f"training_iter{iteration}")
                await rl_append_log(job_id, f"Training started (iteration {iteration})")

                training_result = await run_training_subprocess(job_id, training_mode, train_algo, apo_config)
                all_training_results.append(training_result)
                await rl_set_job(job_id, training_result=training_result)

                if int(training_result.get("returncode", 1)) != 0:
                    await rl_set_job(
                        job_id,
                        status="failed",
                        stage="failed",
                        ended_at=time_mod.time(),
                        error=f"Training failed at iteration {iteration}",
                    )
                    await rl_append_log(job_id, f"Training failed at iteration {iteration}", "error")
                    return

                # Auto-publish + reload prompts for online mode
                if is_online:
                    run_id = training_result.get("run_id")
                    if run_id:
                        await rl_set_job(job_id, stage=f"publishing_iter{iteration}")
                        published = await _auto_publish_prompts(job_id, run_id, deps=deps)
                        if published:
                            await rl_append_log(job_id, f"Prompts published for iteration {iteration}")
                            # Reload prompt modules so next iteration uses updated prompts
                            try:
                                new_prompt = _reload_prompt_modules()
                                await rl_append_log(job_id, f"Prompt modules reloaded (len={len(new_prompt)})")
                            except Exception as exc:
                                await rl_append_log(job_id, f"Warning: prompt reload failed: {exc}", "warning")
                        else:
                            await rl_append_log(job_id, f"No prompts to publish for iteration {iteration}")

            await rl_append_log(job_id, f"=== Iteration {iteration}/{iterations_to_run} completed ===")

        # Final summary
        succeeded = sum(1 for item in all_task_results if item.get("status") == "succeeded")
        failed = sum(1 for item in all_task_results if item.get("status") == "failed")
        final_status = "stopped" if stopped else "completed"

        last_training_result = all_training_results[-1] if all_training_results else None

        training_overview = build_training_overview(
            run_training=run_training,
            training_result=last_training_result,
            task_total=len(all_task_results),
            succeeded=succeeded,
            failed=failed,
        )

        await rl_set_job(
            job_id,
            status=final_status,
            stage="done" if not stopped else "stopped",
            ended_at=time_mod.time(),
            summary={
                "task_total": len(all_task_results),
                "succeeded": succeeded,
                "failed": failed,
                "training_algo": train_algo,
                "training_run_id": (last_training_result or {}).get("run_id"),
                "training_overview": training_overview,
                "iterations_completed": len(all_training_results),
                "iterations_requested": iterations_to_run,
            },
            current_task_index=None,
            current_cancel_token_id=None,
            current_process_pid=None,
        )
        await rl_append_log(job_id, f"Job finished status={final_status}")

    except asyncio.CancelledError:
        await rl_set_job(
            job_id,
            status="stopped",
            stage="stopped",
            ended_at=time_mod.time(),
            error=None,
            current_task_index=None,
            current_cancel_token_id=None,
            current_process_pid=None,
        )
        await rl_append_log(job_id, "Job cancelled by user", "warning")
        return
    except Exception as exc:
        logger.exception("rl job failed")
        await rl_set_job(
            job_id,
            status="failed",
            stage="failed",
            ended_at=time_mod.time(),
            error=str(exc),
            current_task_index=None,
            current_cancel_token_id=None,
            current_process_pid=None,
        )
        await rl_append_log(job_id, f"Job failed: {exc}", "error")
