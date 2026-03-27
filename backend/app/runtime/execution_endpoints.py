from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional


def build_execute_user_task_endpoint(
    *,
    chat_execution_service: Any,
    chat_wiring: Any,
    runtime_state: Any,
    deps: Dict[str, Any],
) -> Callable[..., Awaitable[str]]:
    async def endpoint(
        *,
        user_message: str,
        send_payload: Callable[[Dict[str, Any]], Awaitable[None]],
        cancel_token: Any,
        source: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        return await chat_execution_service.execute_user_task(
            user_message=user_message,
            send_payload=send_payload,
            cancel_token=cancel_token,
            source=source,
            extra_metadata=extra_metadata,
            deps=chat_wiring.build_chat_execution_deps(
                runtime_state=runtime_state,
                deps=deps,
            ),
        )

    return endpoint
