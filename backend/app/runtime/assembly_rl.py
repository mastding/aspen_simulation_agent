from __future__ import annotations

from typing import Any, Dict


def build_rl_pipeline(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    rlp = deps["rl_pipeline_endpoints"]
    rl_wiring = deps["rl_wiring"]
    tp_service = deps["training_process_service"]
    artifacts = deps["training_artifacts"]
    telemetry_repo = deps["telemetry_repo"]
    _rl_append_log = deps["_rl_append_log"]
    _rl_set_job = deps["_rl_set_job"]
    return {
        "_run_training_subprocess": rlp.build_run_training_subprocess_fn(
            training_process_service=tp_service,
            deps_builder_fn=lambda: rl_wiring.build_training_subprocess_deps(
                deps={
                    "python_exec": deps["python_exec"],
                    "script_path": deps["RL_DIR"] / "src" / "train_offline_and_generate_prompts.py",
                    "db_path": deps["DB_PATH"],
                    "prompt_dir": deps["PROMPT_DIR"],
                    "schema_dir": deps["SCHEMA_DIR"],
                    "training_runs_dir": deps["TRAINING_RUNS_DIR"],
                    "append_log_fn": _rl_append_log,
                    "set_job_fn": _rl_set_job,
                    "extract_run_id_fn": artifacts.extract_run_id_from_training_stdout,
                    "cwd": deps["CWD"],
                }
            ),
        ),
        "_run_collection_subprocess": rlp.build_run_collection_subprocess_fn(
            training_process_service=tp_service,
            deps_builder_fn=lambda: rl_wiring.build_collection_subprocess_deps(
                deps={
                    "python_exec": deps["python_exec"],
                    "script_path": deps["RL_DIR"] / "src" / "collect_online_trajectories.py",
                    "db_path": deps["DB_PATH"],
                    "default_host": deps["default_host"],
                    "default_port": deps["default_port"],
                    "output_dir": deps["RL_DIR"] / "outputs" / "online_collection",
                    "append_log_fn": _rl_append_log,
                    "set_job_fn": _rl_set_job,
                    "extract_collection_file_fn": artifacts.extract_collection_file_from_stdout,
                    "cwd": deps["CWD"],
                }
            ),
        ),
        "_run_rl_job_builder": lambda run_collection_subprocess_fn, execute_user_task_fn, run_training_subprocess_fn: rlp.build_run_rl_job_fn(
            rl_worker_service=deps["rl_worker_service"],
            job_deps_builder_fn=lambda: rl_wiring.build_rl_worker_deps(
                deps={
                    "rl_jobs_lock": deps["runtime_state"].rl_jobs_lock,
                    "rl_jobs": deps["runtime_state"].rl_jobs,
                    "rl_set_job_fn": _rl_set_job,
                    "rl_append_log_fn": _rl_append_log,
                    "reset_rollouts_db_fn": lambda: telemetry_repo.reset_rollouts_db(db_path=deps["DB_PATH"]),
                    "run_collection_subprocess_fn": run_collection_subprocess_fn,
                    "execute_user_task_fn": execute_user_task_fn,
                    "db_connect_fn": deps["_db_connect"],
                    "run_training_subprocess_fn": run_training_subprocess_fn,
                    "build_training_overview_fn": lambda *, run_training, training_result, task_total, succeeded, failed: artifacts.build_training_overview(
                        run_training=run_training,
                        training_result=training_result,
                        task_total=task_total,
                        succeeded=succeeded,
                        failed=failed,
                        training_runs_dir=deps["TRAINING_RUNS_DIR"],
                        prompt_dir=deps["PROMPT_DIR"],
                        schema_default_target=deps["SCHEMA_DEFAULT_TARGET"],
                    ),
                    "logger": deps["logger"],
                    "CancellationToken": deps["CancellationToken"],
                    "time_mod": deps["time_mod"],
                }
            ),
        ),
    }
