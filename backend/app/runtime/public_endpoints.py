from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import Body, Query
from fastapi.responses import StreamingResponse


def build_root_endpoint(*, api_handlers: Any, model: str) -> Callable[[], Awaitable[Dict[str, Any]]]:
    async def endpoint() -> Dict[str, Any]:
        return api_handlers.root_handler(model=model)

    return endpoint


def build_health_endpoint(
    *,
    api_handlers: Any,
    model: str,
    data_dir: Any,
    query_statistics_sqlite_fn: Callable[[], Dict[str, Any]],
) -> Callable[[], Awaitable[Dict[str, Any]]]:
    async def endpoint() -> Dict[str, Any]:
        return api_handlers.health_handler(
            model=model,
            data_dir=data_dir,
            query_statistics_sqlite_fn=query_statistics_sqlite_fn,
        )

    return endpoint


def build_history_endpoint() -> Callable[[], Awaitable[List[Dict[str, Any]]]]:
    async def endpoint() -> List[Dict[str, Any]]:
        return []

    return endpoint


def build_download_file_endpoint(
    *,
    api_handlers: Any,
    download_aspen_file_fn: Callable[..., Any],
    logger: Any,
) -> Callable[..., Awaitable[StreamingResponse]]:
    async def endpoint(file_path: str = Query(..., description="Absolute result file path")) -> StreamingResponse:
        return api_handlers.download_handler(
            file_path=file_path,
            download_aspen_file_fn=download_aspen_file_fn,
            logger=logger,
        )

    return endpoint


def build_rollouts_endpoint(
    *,
    api_handlers: Any,
    query_rollouts_sqlite_fn: Callable[..., Dict[str, Any]],
    logger: Any,
) -> Callable[..., Awaitable[Dict[str, Any]]]:
    async def endpoint(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        return api_handlers.rollouts_handler(
            limit=limit,
            offset=offset,
            query_rollouts_sqlite_fn=query_rollouts_sqlite_fn,
            logger=logger,
        )

    return endpoint


def build_clear_rollouts_endpoint(
    *,
    api_handlers: Any,
    reset_rollouts_db_fn: Callable[[], None],
    logger: Any,
) -> Callable[[], Awaitable[Dict[str, Any]]]:
    async def endpoint() -> Dict[str, Any]:
        return api_handlers.clear_rollouts_handler(
            reset_rollouts_db_fn=reset_rollouts_db_fn,
            logger=logger,
        )

    return endpoint


def build_rollout_spans_endpoint(
    *,
    api_handlers: Any,
    query_spans_sqlite_fn: Callable[[str], Dict[str, Any]],
    logger: Any,
) -> Callable[[str], Awaitable[Dict[str, Any]]]:
    async def endpoint(rollout_id: str) -> Dict[str, Any]:
        return api_handlers.rollout_spans_handler(
            rollout_id=rollout_id,
            query_spans_sqlite_fn=query_spans_sqlite_fn,
            logger=logger,
        )

    return endpoint


def build_statistics_endpoint(
    *,
    api_handlers: Any,
    query_statistics_sqlite_fn: Callable[[], Dict[str, Any]],
    logger: Any,
) -> Callable[[], Awaitable[Dict[str, Any]]]:
    async def endpoint() -> Dict[str, Any]:
        return api_handlers.statistics_handler(
            query_statistics_sqlite_fn=query_statistics_sqlite_fn,
            logger=logger,
        )

    return endpoint


def build_artifacts_endpoint(
    *,
    api_handlers: Any,
    query_artifacts_sqlite_fn: Callable[..., Dict[str, Any]],
    logger: Any,
) -> Callable[..., Awaitable[Dict[str, Any]]]:
    async def endpoint(
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        return api_handlers.artifacts_handler(
            limit=limit,
            offset=offset,
            status=status,
            query_artifacts_sqlite_fn=query_artifacts_sqlite_fn,
            logger=logger,
        )

    return endpoint


def build_metrics_overview_endpoint(
    *,
    api_handlers: Any,
    query_metrics_overview_sqlite_fn: Callable[[], Dict[str, Any]],
    logger: Any,
) -> Callable[[], Awaitable[Dict[str, Any]]]:
    async def endpoint() -> Dict[str, Any]:
        return api_handlers.metrics_overview_handler(
            query_metrics_overview_sqlite_fn=query_metrics_overview_sqlite_fn,
            logger=logger,
        )

    return endpoint


def build_list_training_runs_endpoint(
    *,
    api_handlers: Any,
    training_runs_dir: Any,
    training_exports_dir: Any,
    logger: Any,
) -> Callable[[int], Awaitable[Dict[str, Any]]]:
    async def endpoint(limit: int = 30) -> Dict[str, Any]:
        return api_handlers.list_training_runs_handler(
            limit=limit,
            training_runs_dir=training_runs_dir,
            training_exports_dir=training_exports_dir,
            logger=logger,
        )

    return endpoint


def build_clear_training_runs_endpoint(
    *,
    api_handlers: Any,
    training_runs_dir: Any,
    training_exports_dir: Any,
    logger: Any,
) -> Callable[[], Awaitable[Dict[str, Any]]]:
    async def endpoint() -> Dict[str, Any]:
        return api_handlers.clear_training_runs_handler(
            training_runs_dir=training_runs_dir,
            training_exports_dir=training_exports_dir,
            logger=logger,
        )

    return endpoint


def build_get_training_file_endpoint(
    *,
    api_handlers: Any,
    safe_run_id_fn: Callable[[str], str],
    training_runs_dir: Any,
    read_small_text_fn: Callable[[Any], str],
    logger: Any,
) -> Callable[[str, str], Awaitable[Dict[str, Any]]]:
    async def endpoint(run_id: str, file_name: str) -> Dict[str, Any]:
        return api_handlers.get_training_file_handler(
            run_id=run_id,
            file_name=file_name,
            safe_run_id_fn=safe_run_id_fn,
            training_runs_dir=training_runs_dir,
            read_small_text_fn=read_small_text_fn,
            logger=logger,
        )

    return endpoint


def build_publish_training_result_endpoint(
    *,
    api_handlers: Any,
    safe_run_id_fn: Callable[[str], str],
    schema_default_target: Any,
    training_runs_dir: Any,
    rl_dir: Any,
    prompt_dir: Any,
    base_parent_dir: Any,
    prompt_version_file: Any,
    prompt_version_service: Any,
    upsert_prompt_version_fn: Callable[..., Any],
    logger: Any,
) -> Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    async def endpoint(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return api_handlers.publish_training_result_handler(
            payload=payload,
            safe_run_id_fn=safe_run_id_fn,
            schema_default_target=schema_default_target,
            training_runs_dir=training_runs_dir,
            rl_dir=rl_dir,
            prompt_dir=prompt_dir,
            base_parent_dir=base_parent_dir,
            prompt_version_file=prompt_version_file,
            prompt_version_service=prompt_version_service,
            upsert_prompt_version_fn=upsert_prompt_version_fn,
            logger=logger,
        )

    return endpoint


def build_get_prompt_versions_endpoint(
    *,
    api_handlers: Any,
    prompt_version_file: Any,
    prompt_version_service: Any,
    logger: Any,
) -> Callable[[], Awaitable[Dict[str, Any]]]:
    async def endpoint() -> Dict[str, Any]:
        return api_handlers.get_prompt_versions_handler(
            prompt_version_file=prompt_version_file,
            prompt_version_service=prompt_version_service,
            logger=logger,
        )

    return endpoint


def build_update_prompt_versions_endpoint(
    *,
    api_handlers: Any,
    prompt_version_file: Any,
    prompt_version_service: Any,
    logger: Any,
) -> Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    async def endpoint(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return api_handlers.update_prompt_versions_handler(
            payload=payload,
            prompt_version_file=prompt_version_file,
            prompt_version_service=prompt_version_service,
            logger=logger,
        )

    return endpoint


def build_get_current_prompts_endpoint(
    *,
    prompt_dir,
    logger,
):
    async def endpoint():
        from pathlib import Path

        prompt_path = Path(prompt_dir)
        prompts = {}

        # Read prompt files
        prompt_files = {
            "system_prompt": "llm_prompt.py",
            "schema_check_prompt": "schema_check.py",
            "thought_process_prompt": "thought_process.py",
            "schema_get_prompt": "schema_get.py",
            "result_get_prompt": "result_get.py",
        }

        for name, filename in prompt_files.items():
            file_path = prompt_path / filename
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    # For simplicity, just return the whole file content
                    prompts[name] = content
                except Exception as e:
                    logger.error(f"Failed to read {filename}: {e}")
                    prompts[name] = ""

        return {"ok": True, "prompts": prompts}

    return endpoint


def build_update_current_prompts_endpoint(
    *,
    prompt_dir,
    logger,
):
    async def endpoint(payload):
        from pathlib import Path

        prompt_path = Path(prompt_dir)
        prompts = payload.get("prompts", {})

        if not isinstance(prompts, dict):
            return {"ok": False, "error": "Invalid prompts format"}

        prompt_files = {
            "system_prompt": "llm_prompt.py",
            "schema_check_prompt": "schema_check.py",
            "thought_process_prompt": "thought_process.py",
            "schema_get_prompt": "schema_get.py",
            "result_get_prompt": "result_get.py",
        }

        updated = []
        for name, content in prompts.items():
            if name not in prompt_files:
                continue

            filename = prompt_files[name]
            file_path = prompt_path / filename

            try:
                # Write prompt content
                file_path.write_text(content, encoding="utf-8")
                updated.append(name)
                logger.info(f"Updated prompt: {name} in {filename}")
            except Exception as e:
                logger.error(f"Failed to update {filename}: {e}")
                return {"ok": False, "error": f"Failed to update {name}: {str(e)}"}

        return {"ok": True, "updated": updated}

    return endpoint


def build_list_schema_files_endpoint(
    *,
    schema_dir,
    logger,
):
    async def endpoint():
        from pathlib import Path

        schema_path = Path(schema_dir)
        
        if not schema_path.exists():
            return {"ok": False, "error": "Schema directory not found"}
        
        try:
            files = []
            for file_path in sorted(schema_path.glob("*.json")):
                stat = file_path.stat()
                files.append({
                    "name": file_path.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                })
            return {"ok": True, "files": files}
        except Exception as e:
            logger.error(f"Failed to list schema files: {e}")
            return {"ok": False, "error": str(e)}

    return endpoint


def build_get_schema_file_endpoint(
    *,
    schema_dir,
    logger,
):
    async def endpoint(filename: str):
        from pathlib import Path

        schema_path = Path(schema_dir)
        file_path = schema_path / filename
        
        # Security check: prevent path traversal
        if not file_path.resolve().is_relative_to(schema_path.resolve()):
            return {"ok": False, "error": "Invalid file path"}
        
        if not file_path.exists():
            return {"ok": False, "error": "File not found"}
        
        try:
            content = file_path.read_text(encoding="utf-8")
            return {"ok": True, "content": content}
        except Exception as e:
            logger.error(f"Failed to read schema file {filename}: {e}")
            return {"ok": False, "error": str(e)}

    return endpoint


def build_update_schema_file_endpoint(
    *,
    schema_dir,
    logger,
):
    async def endpoint(payload):
        from pathlib import Path

        schema_path = Path(schema_dir)
        filename = payload.get("filename")
        content = payload.get("content")
        
        if not filename or content is None:
            return {"ok": False, "error": "Missing filename or content"}
        
        file_path = schema_path / filename
        
        # Security check: prevent path traversal
        if not file_path.resolve().is_relative_to(schema_path.resolve()):
            return {"ok": False, "error": "Invalid file path"}
        
        try:
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"Updated schema file: {filename}")
            return {"ok": True, "message": f"File {filename} updated successfully"}
        except Exception as e:
            logger.error(f"Failed to update schema file {filename}: {e}")
            return {"ok": False, "error": str(e)}

    return endpoint
