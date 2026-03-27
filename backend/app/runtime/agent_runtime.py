from __future__ import annotations

from typing import Any, Callable


def build_get_agent_fn(
    *,
    runtime_state: Any,
    create_model_client_fn: Callable[..., Any],
    create_assistant_agent_fn: Callable[..., Any],
    model_api_key: str,
    model_api_url: str,
    model: str,
    system_prompt: str,
    tools: list,
    safe_operation_context_fn: Callable[..., Any],
    logger: Any,
    temperature: float = 0.2,
    max_tokens: int = 8192,
    timeout: int = 120,
    max_retries: int = 3,
) -> Callable[[], Any]:
    def endpoint(*, system_prompt_override: str | None = None) -> Any:
        if runtime_state.agent_instance is None:
            model_client = create_model_client_fn(
                model_api_key=model_api_key,
                model_api_url=model_api_url,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                max_retries=max_retries,
            )
            runtime_state.agent_instance = create_assistant_agent_fn(
                model_client=model_client,
                system_prompt=system_prompt_override or system_prompt,
                tools=tools,
                safe_operation_context_fn=safe_operation_context_fn,
                logger=logger,
                model=model,
            )
        return runtime_state.agent_instance

    return endpoint
