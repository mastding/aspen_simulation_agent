from __future__ import annotations

from typing import Any, Dict, List

from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import ModelFamily
from autogen_ext.models.openai import OpenAIChatCompletionClient


def create_model_client(
    *,
    model_api_key: str,
    model_api_url: str,
    model: str,
    temperature: float = 0.2,
    max_tokens: int = 8192,
    timeout: int = 120,
    max_retries: int = 3,
) -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        api_key=model_api_key,
        base_url=model_api_url,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries,
        model_info={
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "family": ModelFamily.UNKNOWN,
            "structured_output": True,
            "multiple_system_messages": False,
        },
    )


def create_assistant_agent(
    *,
    model_client,
    system_prompt: str,
    tools: List[Any],
    safe_operation_context_fn,
    logger,
    model: str,
) -> AssistantAgent:
    with safe_operation_context_fn("create_agent", {"model": model}):
        agent = AssistantAgent(
            name="aspen_expert",
            model_client=model_client,
            system_message=system_prompt,
            tools=tools,
            reflect_on_tool_use=True,
            model_client_stream=True,
            max_tool_iterations=100,
        )
    logger.info("AssistantAgent initialized")
    return agent
