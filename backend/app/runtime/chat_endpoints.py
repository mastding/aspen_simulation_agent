from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from fastapi import Body
from fastapi.responses import StreamingResponse


def build_stop_chat_stream_endpoint(
    *,
    chat_stream_service: Any,
    get_sse_control_fn: Callable[[str], Any],
) -> Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    async def endpoint(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        return await chat_stream_service.stop_chat_stream(
            payload=payload,
            deps={
                "get_sse_control_fn": get_sse_control_fn,
            },
        )

    return endpoint


def build_chat_resume_stream_endpoint(
    *,
    chat_stream_service: Any,
    build_resume_prompt_fn: Callable[..., Any],
    get_sse_control_fn: Callable[[str], Any],
    set_sse_control_fn: Callable[[str, Any], None],
    execute_user_task_fn: Callable[..., Awaitable[str]],
) -> Callable[[Dict[str, Any]], Awaitable[StreamingResponse]]:
    async def endpoint(payload: Dict[str, Any] = Body(...)) -> StreamingResponse:
        return await chat_stream_service.chat_resume_stream(
            payload=payload,
            deps={
                "build_resume_prompt_fn": build_resume_prompt_fn,
                "get_sse_control_fn": get_sse_control_fn,
                "set_sse_control_fn": set_sse_control_fn,
                "execute_user_task_fn": execute_user_task_fn,
            },
        )

    return endpoint


def build_chat_stream_endpoint(
    *,
    chat_stream_service: Any,
    get_sse_control_fn: Callable[[str], Any],
    set_sse_control_fn: Callable[[str, Any], None],
    execute_user_task_fn: Callable[..., Awaitable[str]],
) -> Callable[[Dict[str, Any]], Awaitable[StreamingResponse]]:
    async def endpoint(payload: Dict[str, Any] = Body(...)) -> StreamingResponse:
        return await chat_stream_service.chat_stream(
            payload=payload,
            deps={
                "get_sse_control_fn": get_sse_control_fn,
                "set_sse_control_fn": set_sse_control_fn,
                "execute_user_task_fn": execute_user_task_fn,
            },
        )

    return endpoint
