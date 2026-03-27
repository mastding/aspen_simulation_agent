from __future__ import annotations

from typing import Any, Dict


def build_training_subprocess_deps(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "python_exec": deps["python_exec"],
        "script_path": deps["script_path"],
        "db_path": deps["db_path"],
        "prompt_dir": deps["prompt_dir"],
        "schema_dir": deps["schema_dir"],
        "training_runs_dir": deps["training_runs_dir"],
        "append_log_fn": deps["append_log_fn"],
        "set_job_fn": deps["set_job_fn"],
        "extract_run_id_fn": deps["extract_run_id_fn"],
        "cwd": deps["cwd"],
    }


def build_collection_subprocess_deps(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "python_exec": deps["python_exec"],
        "script_path": deps["script_path"],
        "db_path": deps["db_path"],
        "default_host": deps["default_host"],
        "default_port": deps["default_port"],
        "output_dir": deps["output_dir"],
        "append_log_fn": deps["append_log_fn"],
        "set_job_fn": deps["set_job_fn"],
        "extract_collection_file_fn": deps["extract_collection_file_fn"],
        "cwd": deps["cwd"],
    }


def build_rl_worker_deps(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "rl_jobs_lock": deps["rl_jobs_lock"],
        "rl_jobs": deps["rl_jobs"],
        "rl_set_job_fn": deps["rl_set_job_fn"],
        "rl_append_log_fn": deps["rl_append_log_fn"],
        "reset_rollouts_db_fn": deps["reset_rollouts_db_fn"],
        "run_collection_subprocess_fn": deps["run_collection_subprocess_fn"],
        "execute_user_task_fn": deps["execute_user_task_fn"],
        "db_connect_fn": deps["db_connect_fn"],
        "run_training_subprocess_fn": deps["run_training_subprocess_fn"],
        "build_training_overview_fn": deps["build_training_overview_fn"],
        "logger": deps["logger"],
        "CancellationToken": deps["CancellationToken"],
        "time_mod": deps["time_mod"],
        "rl_root": deps.get("rl_root", "/run/code/dinglei/aspen_simulation_new/backend/rl"),
        "prompt_dir": deps.get("prompt_dir", "/run/code/dinglei/aspen_simulation_new/backend/app/prompts"),
    }


