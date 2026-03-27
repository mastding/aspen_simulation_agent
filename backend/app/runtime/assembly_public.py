from __future__ import annotations

from typing import Any, Dict


def build_public_api_endpoints(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    pe = deps["public_endpoints"]
    api_handlers = deps["api_handlers"]
    telemetry_repo = deps["telemetry_repo"]
    training_artifacts = deps["training_artifacts"]
    memory_core_ops = deps["memory_core_ops"]

    return {
        "root": pe.build_root_endpoint(api_handlers=api_handlers, model=deps["MODEL"]),
        "health": pe.build_health_endpoint(
            api_handlers=api_handlers,
            model=deps["MODEL"],
            data_dir=deps["DATA_DIR"],
            query_statistics_sqlite_fn=lambda: telemetry_repo.query_statistics(
                db_path=deps["DB_PATH"], json_loads_or_default=deps["_json_loads_or_default"]
            ),
        ),
        "history": pe.build_history_endpoint(),
        "download_file": pe.build_download_file_endpoint(
            api_handlers=api_handlers,
            download_aspen_file_fn=deps["download_aspen_file"],
            logger=deps["logger"],
        ),
        "get_rollouts": pe.build_rollouts_endpoint(
            api_handlers=api_handlers,
            query_rollouts_sqlite_fn=lambda limit, offset: telemetry_repo.query_rollouts(
                db_path=deps["DB_PATH"],
                json_loads_or_default=deps["_json_loads_or_default"],
                limit=limit,
                offset=offset,
            ),
            logger=deps["logger"],
        ),
        "clear_rollouts": pe.build_clear_rollouts_endpoint(
            api_handlers=api_handlers,
            reset_rollouts_db_fn=lambda: telemetry_repo.reset_rollouts_db(db_path=deps["DB_PATH"]),
            logger=deps["logger"],
        ),
        "get_rollout_spans": pe.build_rollout_spans_endpoint(
            api_handlers=api_handlers,
            query_spans_sqlite_fn=lambda rollout_id: telemetry_repo.query_spans(
                db_path=deps["DB_PATH"],
                json_loads_or_default=deps["_json_loads_or_default"],
                rollout_id=rollout_id,
            ),
            logger=deps["logger"],
        ),
        "get_statistics": pe.build_statistics_endpoint(
            api_handlers=api_handlers,
            query_statistics_sqlite_fn=lambda: telemetry_repo.query_statistics(
                db_path=deps["DB_PATH"], json_loads_or_default=deps["_json_loads_or_default"]
            ),
            logger=deps["logger"],
        ),
        "get_artifacts": pe.build_artifacts_endpoint(
            api_handlers=api_handlers,
            query_artifacts_sqlite_fn=lambda limit, offset, status=None: telemetry_repo.query_artifacts(
                db_path=deps["DB_PATH"],
                json_loads_or_default=deps["_json_loads_or_default"],
                ntpath_mod=deps["ntpath"],
                max_text_file_size=deps["MAX_TEXT_FILE_SIZE"],
                limit=limit,
                offset=offset,
                status=status,
            ),
            logger=deps["logger"],
        ),
        "get_metrics_overview": pe.build_metrics_overview_endpoint(
            api_handlers=api_handlers,
            query_metrics_overview_sqlite_fn=deps.get("query_metrics_overview_with_policy_fn")
            or (lambda: telemetry_repo.query_metrics_overview(
                db_path=deps["DB_PATH"],
                json_loads_or_default=deps["_json_loads_or_default"],
                query_statistics_fn=lambda: telemetry_repo.query_statistics(
                    db_path=deps["DB_PATH"], json_loads_or_default=deps["_json_loads_or_default"]
                ),
                query_memory_quality_metrics_fn=lambda: memory_core_ops.query_memory_quality_metrics(
                    deps={"db_connect_fn": deps["_db_connect"], "json_loads_or_default_fn": deps["_json_loads_or_default"]}
                ),
            )),
            logger=deps["logger"],
        ),
        "list_training_runs": pe.build_list_training_runs_endpoint(
            api_handlers=api_handlers,
            training_runs_dir=deps["TRAINING_RUNS_DIR"],
            training_exports_dir=deps["TRAINING_EXPORTS_DIR"],
            logger=deps["logger"],
        ),
        "clear_training_runs": pe.build_clear_training_runs_endpoint(
            api_handlers=api_handlers,
            training_runs_dir=deps["TRAINING_RUNS_DIR"],
            training_exports_dir=deps["TRAINING_EXPORTS_DIR"],
            logger=deps["logger"],
        ),
        "get_training_file": pe.build_get_training_file_endpoint(
            api_handlers=api_handlers,
            safe_run_id_fn=training_artifacts.safe_run_id,
            training_runs_dir=deps["TRAINING_RUNS_DIR"],
            read_small_text_fn=lambda p: training_artifacts.read_small_text(p, deps["MAX_TEXT_FILE_SIZE"]),
            logger=deps["logger"],
        ),
        "publish_training_result": pe.build_publish_training_result_endpoint(
            api_handlers=api_handlers,
            safe_run_id_fn=training_artifacts.safe_run_id,
            schema_default_target=deps["SCHEMA_DEFAULT_TARGET"],
            training_runs_dir=deps["TRAINING_RUNS_DIR"],
            rl_dir=deps["RL_DIR"],
            prompt_dir=deps["PROMPT_DIR"],
            base_parent_dir=deps["BASE_PARENT_DIR"],
            prompt_version_file=deps["PROMPT_VERSION_FILE"],
            prompt_version_service=deps["prompt_version_service"],
            upsert_prompt_version_fn=deps["upsert_prompt_version_fn"],
            logger=deps["logger"],
        ),
        "get_prompt_versions": pe.build_get_prompt_versions_endpoint(
            api_handlers=api_handlers,
            prompt_version_file=deps["PROMPT_VERSION_FILE"],
            prompt_version_service=deps["prompt_version_service"],
            logger=deps["logger"],
        ),
        "update_prompt_versions": pe.build_update_prompt_versions_endpoint(
            api_handlers=api_handlers,
            prompt_version_file=deps["PROMPT_VERSION_FILE"],
            prompt_version_service=deps["prompt_version_service"],
            logger=deps["logger"],
        ),
        "get_current_prompts": pe.build_get_current_prompts_endpoint(
            prompt_dir=deps["PROMPT_DIR"],
            logger=deps["logger"],
        ),
        "update_current_prompts": pe.build_update_current_prompts_endpoint(
            prompt_dir=deps["PROMPT_DIR"],
            logger=deps["logger"],
        ),
        "list_schema_files": pe.build_list_schema_files_endpoint(
            schema_dir=deps["SCHEMA_DIR"],
            logger=deps["logger"],
        ),
        "get_schema_file": pe.build_get_schema_file_endpoint(
            schema_dir=deps["SCHEMA_DIR"],
            logger=deps["logger"],
        ),
        "update_schema_file": pe.build_update_schema_file_endpoint(
            schema_dir=deps["SCHEMA_DIR"],
            logger=deps["logger"],
        ),
    }
