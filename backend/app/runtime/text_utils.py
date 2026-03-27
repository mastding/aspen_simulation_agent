from __future__ import annotations

from typing import Any


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def infer_task_type(message: str) -> str:
    m = normalize_text(message)
    if any(k in m for k in ["distillation", "flowsheet", "process", "flowsheet", "radfrac", "dstwu"]):
        return "process"
    if any(k in m for k in ["mixer", "sep", "flash", "heater", "pump", "rcstr", "rplug", "radfrac"]):
        return "unit"
    return "unknown"


def safe_str(value: Any, max_len: int = 2000) -> str:
    text = str(value or "").strip()
    if len(text) > max_len:
        return text[:max_len] + "\n...[truncated]"
    return text
