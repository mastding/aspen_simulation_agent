from __future__ import annotations

from typing import Any, Dict


def build_chat_layer(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    chat_endpoints = deps["chat_endpoints"]
    return {
        "stop_chat_stream": chat_endpoints.build_stop_chat_stream_endpoint(
            chat_stream_service=deps["chat_stream_service"],
            get_sse_control_fn=deps["_get_sse_control"],
        ),
        "chat_resume_stream": chat_endpoints.build_chat_resume_stream_endpoint(
            chat_stream_service=deps["chat_stream_service"],
            build_resume_prompt_fn=deps["_build_resume_prompt"],
            get_sse_control_fn=deps["_get_sse_control"],
            set_sse_control_fn=deps["_set_sse_control"],
            execute_user_task_fn=deps["execute_user_task"],
        ),
        "chat_stream": chat_endpoints.build_chat_stream_endpoint(
            chat_stream_service=deps["chat_stream_service"],
            get_sse_control_fn=deps["_get_sse_control"],
            set_sse_control_fn=deps["_set_sse_control"],
            execute_user_task_fn=deps["execute_user_task"],
        ),
    }
