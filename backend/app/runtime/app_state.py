from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from autogen_agentchat.agents import AssistantAgent


@dataclass
class AspenTask:
    task_id: str
    user_requirement: str
    difficulty: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "user_requirement": self.user_requirement,
            "difficulty": self.difficulty,
        }


@dataclass
class RuntimeState:
    agent_instance: Optional[AssistantAgent] = None
    task_counter: int = 0
    sse_controls: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    sse_controls_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    rl_jobs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    rl_jobs_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


