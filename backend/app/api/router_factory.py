from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import StreamingResponse


def build_router(deps: Dict[str, Any]) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def root() -> Dict[str, Any]:
        return await deps["root"]()

    @router.get("/health")
    async def health() -> Dict[str, Any]:
        return await deps["health"]()

    @router.get("/history")
    async def history() -> List[Dict[str, Any]]:
        return await deps["history"]()

    @router.get("/download")
    async def download_file(file_path: str = Query(..., description="Absolute result file path")) -> StreamingResponse:
        return await deps["download_file"](file_path=file_path)

    @router.get("/api/rollouts")
    async def get_rollouts(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        return await deps["get_rollouts"](limit=limit, offset=offset)

    @router.post("/api/rollouts/clear")
    async def clear_rollouts() -> Dict[str, Any]:
        return await deps["clear_rollouts"]()

    @router.delete("/api/rollouts/{rollout_id}")
    async def delete_rollout(rollout_id: str) -> Dict[str, Any]:
        return await deps["delete_rollout"](rollout_id=rollout_id)

    @router.get("/api/rollouts/{rollout_id}/spans")
    async def get_rollout_spans(rollout_id: str) -> Dict[str, Any]:
        return await deps["get_rollout_spans"](rollout_id=rollout_id)

    @router.get("/api/statistics")
    async def get_statistics() -> Dict[str, Any]:
        return await deps["get_statistics"]()

    @router.get("/api/artifacts")
    async def get_artifacts(
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await deps["get_artifacts"](limit=limit, offset=offset, status=status)

    @router.get("/api/metrics/overview")
    async def get_metrics_overview() -> Dict[str, Any]:
        return await deps["get_metrics_overview"]()

    @router.get("/api/training/runs")
    async def list_training_runs(limit: int = 30) -> Dict[str, Any]:
        return await deps["list_training_runs"](limit=limit)

    @router.post("/api/training/runs/clear")
    async def clear_training_runs() -> Dict[str, Any]:
        return await deps["clear_training_runs"]()

    @router.get("/api/training/runs/{run_id}/files/{file_name}")
    async def get_training_file(run_id: str, file_name: str) -> Dict[str, Any]:
        return await deps["get_training_file"](run_id=run_id, file_name=file_name)

    @router.post("/api/training/publish")
    async def publish_training_result(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await deps["publish_training_result"](payload=payload)

    @router.get("/api/prompt/versions")
    async def get_prompt_versions() -> Dict[str, Any]:
        return await deps["get_prompt_versions"]()

    @router.post("/api/prompt/versions")
    async def update_prompt_versions(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await deps["update_prompt_versions"](payload=payload)
    @router.get("/api/prompt/current")
    async def get_current_prompts() -> Dict[str, Any]:
        return await deps["get_current_prompts"]()

    @router.post("/api/prompt/update")
    async def update_current_prompts(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await deps["update_current_prompts"](payload=payload)

    @router.get("/api/schema/files")
    async def list_schema_files() -> Dict[str, Any]:
        return await deps["list_schema_files"]()

    @router.get("/api/schema/file")
    async def get_schema_file(filename: str) -> Dict[str, Any]:
        return await deps["get_schema_file"](filename=filename)

    @router.post("/api/schema/file")
    async def update_schema_file(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await deps["update_schema_file"](payload=payload)


    @router.post("/api/rl/jobs/start")
    async def start_rl_job(request: Request, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        payload["_username"] = getattr(request.state, "user_phone", None) or "unknown"
        return await deps["start_rl_job"](payload=payload)

    @router.post("/api/rl/jobs/{job_id}/stop")
    async def stop_rl_job(job_id: str) -> Dict[str, Any]:
        return await deps["stop_rl_job"](job_id=job_id)

    @router.get("/api/rl/jobs")
    async def list_rl_jobs(limit: int = 20) -> Dict[str, Any]:
        return await deps["list_rl_jobs"](limit=limit)

    @router.get("/api/rl/task-history")
    async def list_rl_task_history(
        limit: int = 200,
        status: Optional[str] = Query(default=None),
        q: str = Query(default=""),
        label: str = Query(default=""),
        start_time_from: Optional[float] = Query(default=None),
        start_time_to: Optional[float] = Query(default=None),
    ) -> Dict[str, Any]:
        return await deps["list_rl_task_history"](
            limit=limit,
            status=status,
            q=q,
            label=label,
            start_time_from=start_time_from,
            start_time_to=start_time_to,
        )

    @router.post("/api/memory/build")
    async def api_memory_build(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
        return await deps["api_memory_build"](payload=payload)

    @router.get("/api/memory/search")
    async def api_memory_search(
        q: str = Query(..., description="task query text"),
        top_k: int = Query(default=5),
        task_type: str = Query(default=""),
    ) -> Dict[str, Any]:
        return await deps["api_memory_search"](q=q, top_k=top_k, task_type=task_type)

    @router.get("/api/memory/stats")
    async def api_memory_stats() -> Dict[str, Any]:
        return await deps["api_memory_stats"]()

    @router.post("/api/memory/backfill")
    async def api_memory_backfill(payload: Dict[str, Any] = Body(default={})) -> Dict[str, Any]:
        return await deps["api_memory_backfill"](payload=payload)

    @router.post("/api/memory/clear")
    async def api_memory_clear() -> Dict[str, Any]:
        return await deps["api_memory_clear"]()

    @router.delete("/api/memory/{memory_id}")
    async def delete_memory(memory_id: str) -> Dict[str, Any]:
        return await deps["delete_memory"](memory_id=memory_id)

    @router.get("/api/memory/usages")
    async def api_memory_usages(
        limit: int = Query(default=100),
        q: str = Query(default=""),
        task_type: str = Query(default=""),
    ) -> Dict[str, Any]:
        return await deps["api_memory_usages"](limit=limit, q=q, task_type=task_type)

    @router.get("/api/memory/usages/{memory_id}")
    async def api_memory_usage_events(
        memory_id: str,
        limit: int = Query(default=100),
        offset: int = Query(default=0),
    ) -> Dict[str, Any]:
        return await deps["api_memory_usage_events"](memory_id=memory_id, limit=limit, offset=offset)

    @router.get("/api/memory/quality")
    async def api_memory_quality() -> Dict[str, Any]:
        return await deps["api_memory_quality"]()

    # REMOVED:     @router.get("/api/memory/aliases")
    # REMOVED:     async def api_memory_aliases(
    # REMOVED:         status: str = Query(default="validated"),
    # REMOVED:         limit: int = Query(default=20),
    # REMOVED:     ) -> Dict[str, Any]:
    # REMOVED:         return await deps["api_memory_aliases"](status=status, limit=limit)
    # REMOVED: 
    # REMOVED:     @router.post("/api/memory/aliases/review")
    # REMOVED:     async def api_memory_alias_review(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    # REMOVED:         return await deps["api_memory_alias_review"](payload=payload)

    @router.post("/api/chat/resume-context")
    async def chat_resume_context(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await deps["chat_resume_context"](payload=payload)

    @router.get("/api/rl/jobs/{job_id}")
    async def get_rl_job(job_id: str, log_offset: int = 0) -> Dict[str, Any]:
        return await deps["get_rl_job"](job_id=job_id, log_offset=log_offset)

    @router.post("/api/chat/stop")
    async def stop_chat_stream(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await deps["stop_chat_stream"](payload=payload)

    @router.post("/api/chat/resume/stream")
    async def chat_resume_stream(request: Request, payload: Dict[str, Any] = Body(...)) -> StreamingResponse:
        payload["_user_id"] = getattr(request.state, "user_id", None)
        payload["_user_phone"] = getattr(request.state, "user_phone", None)
        return await deps["chat_resume_stream"](payload=payload)

    @router.post("/api/chat/stream")
    async def chat_stream(request: Request, payload: Dict[str, Any] = Body(...)) -> StreamingResponse:
        payload["_user_id"] = getattr(request.state, "user_id", None)
        payload["_user_phone"] = getattr(request.state, "user_phone", None)
        return await deps["chat_stream"](payload=payload)


    # Settings API routes
    @router.get("/api/settings/model")
    async def get_model_config() -> Dict[str, Any]:
        return await deps["get_model_config"]()

    @router.post("/api/settings/model")
    async def save_model_config(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await deps["save_model_config"](config=payload)

    @router.post("/api/settings/model/test")
    async def test_model_config(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await deps["test_model_config"](config=payload)


    @router.get("/api/settings/system")
    async def get_system_config() -> Dict[str, Any]:
        return await deps["get_system_config"]()

    @router.post("/api/settings/system")
    async def save_system_config(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await deps["save_system_config"](config=payload)

    @router.post("/api/settings/system/test")
    async def test_system_config(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await deps["test_system_config"](config=payload)


    @router.post("/api/settings/restart")
    async def restart_service() -> Dict[str, Any]:
        return await deps["restart_service"]()





    return router
