from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, Optional

from autogen_core import CancellationToken
from fastapi import HTTPException
from fastapi.responses import StreamingResponse


_HEARTBEAT_INTERVAL_SEC = 15.0
_MAX_SSE_EVENT_CHARS = 32000


def _compact_large_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        rendered = json.dumps(payload, ensure_ascii=False)
    except Exception:
        return payload
    if len(rendered) <= _MAX_SSE_EVENT_CHARS:
        return payload

    compact = dict(payload)
    if isinstance(compact.get("content"), str) and len(compact["content"]) > 12000:
        compact["content"] = compact["content"][:12000] + "\n...(truncated)"
        compact["content_truncated"] = True

    tool_results = compact.get("tool_results")
    if isinstance(tool_results, list):
        compact_results = []
        for item in tool_results:
            if not isinstance(item, dict):
                compact_results.append(item)
                continue
            result_item = dict(item)
            result_value = result_item.get("result")
            if isinstance(result_value, str) and len(result_value) > 4000:
                result_item["result"] = result_value[:4000] + "\n...(truncated)"
                result_item["result_truncated"] = True
            elif isinstance(result_value, (dict, list)):
                try:
                    result_json = json.dumps(result_value, ensure_ascii=False)
                except Exception:
                    result_json = str(result_value)
                if len(result_json) > 4000:
                    result_item["result"] = result_json[:4000] + "\n...(truncated)"
                    result_item["result_truncated"] = True
            compact_results.append(result_item)
        compact["tool_results"] = compact_results

    try:
        rendered = json.dumps(compact, ensure_ascii=False)
    except Exception:
        rendered = ""
    if len(rendered) <= _MAX_SSE_EVENT_CHARS:
        return compact

    return {
        "type": compact.get("type", "update"),
        "status": compact.get("status", "update"),
        "rollout_id": compact.get("rollout_id"),
        "message": "event payload truncated",
        "truncated": True,
    }


async def stop_chat_stream(*, payload: Dict[str, Any], deps: Dict[str, Any]) -> Dict[str, Any]:
    get_sse_control_fn = deps["get_sse_control_fn"]
    session_id = str(payload.get("session_id", "")).strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    control = await get_sse_control_fn(session_id)
    cancel_token = control.get("cancel_token")
    rollout_id = control.get("rollout_id")
    running = bool(control.get("running"))
    if running and isinstance(cancel_token, CancellationToken):
        cancel_token.cancel()
        return {"type": "stop_ack", "status": "stopping", "rollout_id": rollout_id}
    return {"type": "stop_ack", "status": "idle", "rollout_id": rollout_id}


async def _stream_queue(
    *,
    queue: asyncio.Queue[Optional[Dict[str, Any]]],
    worker_task: asyncio.Task,
    cancel_token: CancellationToken,
    get_sse_control_fn,
    set_sse_control_fn,
    session_id: str,
    heartbeat_interval: float = _HEARTBEAT_INTERVAL_SEC,
):
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
            except asyncio.TimeoutError:
                control = await get_sse_control_fn(session_id)
                yield f"data: {json.dumps({'type': 'heartbeat', 'session_id': session_id, 'rollout_id': control.get('rollout_id'), 'ts': round(time.time(), 3)}, ensure_ascii=False)}\n\n"
                continue
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
    finally:
        if not worker_task.done():
            cancel_token.cancel()
            worker_task.cancel()
        await set_sse_control_fn(session_id, running=False, rollout_id=None)


async def chat_resume_stream(*, payload: Dict[str, Any], deps: Dict[str, Any]) -> StreamingResponse:
    build_resume_prompt_fn = deps["build_resume_prompt_fn"]
    get_sse_control_fn = deps["get_sse_control_fn"]
    set_sse_control_fn = deps["set_sse_control_fn"]
    execute_user_task_fn = deps["execute_user_task_fn"]

    rollout_id = str(payload.get("rollout_id", "")).strip()
    session_id = str(payload.get("session_id", "")).strip()
    resume_message = str(payload.get("resume_message", "")).strip()
    user_id = str(payload.get("_user_id", "") or "").strip()
    user_phone = str(payload.get("_user_phone", "") or "").strip()
    if not rollout_id:
        raise HTTPException(status_code=400, detail="rollout_id is required")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    current = await get_sse_control_fn(session_id)
    if current.get("running"):
        raise HTTPException(status_code=409, detail="A task is already running. Send stop first.")

    try:
        resume_ctx = build_resume_prompt_fn(rollout_id, resume_message)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    cancel_token = CancellationToken()
    await set_sse_control_fn(session_id, running=True, cancel_token=cancel_token, rollout_id=None)
    queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()

    async def _send(payload_obj: Dict[str, Any]) -> None:
        if payload_obj.get("type") == "rollout_started":
            await set_sse_control_fn(session_id, rollout_id=str(payload_obj.get("rollout_id", "")))
        await queue.put(payload_obj)

    async def _worker() -> None:
        try:
            await execute_user_task_fn(
                user_message=str(resume_ctx.get("resume_prompt", "")),
                send_payload=_send,
                cancel_token=cancel_token,
                source="resume",
                extra_metadata={
                    "resume": True,
                    "parent_rollout_id": rollout_id,
                    "resume_original_message": str(resume_ctx.get("original_message", "")),
                    "resume_followup": resume_message,
                    "user_id": user_id,
                    "user_phone": user_phone,
                },
            )
        except asyncio.CancelledError:
            pass
        finally:
            await set_sse_control_fn(session_id, running=False, rollout_id=None)
            await queue.put({"type": "stream_end"})
            await queue.put(None)

    worker_task = asyncio.create_task(_worker())

    return StreamingResponse(
        _stream_queue(
            queue=queue,
            worker_task=worker_task,
            cancel_token=cancel_token,
            get_sse_control_fn=get_sse_control_fn,
            set_sse_control_fn=set_sse_control_fn,
            session_id=session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def chat_stream(*, payload: Dict[str, Any], deps: Dict[str, Any]) -> StreamingResponse:
    get_sse_control_fn = deps["get_sse_control_fn"]
    set_sse_control_fn = deps["set_sse_control_fn"]
    execute_user_task_fn = deps["execute_user_task_fn"]

    user_message = str(payload.get("message", "")).strip()
    session_id = str(payload.get("session_id", "")).strip()
    task_type_hint = str(payload.get("task_type", "")).strip().lower()
    if task_type_hint not in {"unit", "process"}:
        task_type_hint = ""
    equipment_type = str(payload.get("equipment_type", "")).strip()
    equipment_category = str(payload.get("equipment_category", "")).strip()
    process_example = str(payload.get("process_example", "")).strip()
    user_id = str(payload.get("_user_id", "") or "").strip()
    user_phone = str(payload.get("_user_phone", "") or "").strip()

    if not user_message:
        raise HTTPException(status_code=400, detail="message is required")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")

    current = await get_sse_control_fn(session_id)
    if current.get("running"):
        raise HTTPException(status_code=409, detail="A task is already running. Send stop first.")

    cancel_token = CancellationToken()
    await set_sse_control_fn(session_id, running=True, cancel_token=cancel_token, rollout_id=None)
    queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()

    async def _send(payload_obj: Dict[str, Any]) -> None:
        if payload_obj.get("type") == "rollout_started":
            await set_sse_control_fn(session_id, rollout_id=str(payload_obj.get("rollout_id", "")))
        await queue.put(payload_obj)

    async def _worker() -> None:
        try:
            extra_metadata: Dict[str, Any] = {}
            if task_type_hint:
                extra_metadata["task_type"] = task_type_hint
            if equipment_type:
                extra_metadata["equipment_type"] = equipment_type
            if equipment_category:
                extra_metadata["equipment_category"] = equipment_category
            if process_example:
                extra_metadata["process_example"] = process_example
            if user_id:
                extra_metadata["user_id"] = user_id
            if user_phone:
                extra_metadata["user_phone"] = user_phone
            if payload.get("disable_memory", False):
                extra_metadata["disable_memory"] = True
            await execute_user_task_fn(
                user_message=user_message,
                send_payload=_send,
                cancel_token=cancel_token,
                source="sse",
                extra_metadata=extra_metadata or None,
            )
        except asyncio.CancelledError:
            pass
        finally:
            await set_sse_control_fn(session_id, running=False, rollout_id=None)
            await queue.put({"type": "stream_end"})
            await queue.put(None)

    worker_task = asyncio.create_task(_worker())

    return StreamingResponse(
        _stream_queue(
            queue=queue,
            worker_task=worker_task,
            cancel_token=cancel_token,
            get_sse_control_fn=get_sse_control_fn,
            set_sse_control_fn=set_sse_control_fn,
            session_id=session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
