from __future__ import annotations

import ast
from typing import Any, Callable, Dict, List


def extract_tool_result_payload(raw_content: str, call_id: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "call_id": call_id,
        "result": raw_content,
        "is_error": False,
    }

    try:
        parsed = ast.literal_eval(raw_content)
        if isinstance(parsed, dict):
            file_paths: List[Dict[str, str]] = []
            for key in ["aspen_file_path", "config_file_path", "result_file_path"]:
                if key in parsed:
                    file_paths.append({"path": str(parsed[key]), "type": key.split("_")[0]})
            if file_paths:
                payload["file_paths"] = file_paths
            if parsed.get("success") is False:
                payload["is_error"] = True
    except Exception:
        pass

    return payload


def build_user_friendly_error(exc: Exception) -> Dict[str, str]:
    raw = str(exc)
    lower = raw.lower()

    if "insufficient balance" in lower or "error code: 402" in lower or "402" in lower:
        return {
            "code": "MODEL_BALANCE_INSUFFICIENT",
            "message": "????????????????",
        }

    if "timed out" in lower or "timeout" in lower:
        return {
            "code": "MODEL_TIMEOUT",
            "message": "?????????????",
        }

    return {
        "code": "MODEL_RUNTIME_ERROR",
        "message": "????????????????????",
    }


def is_context_overflow_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = [
        "maximum context length",
        "context length exceeded",
        "context_length_exceeded",
        "too many tokens",
        "prompt is too long",
        "input is too long",
        "max token",
    ]
    return any(m in text for m in markers)


def build_auto_resume_prompt(
    *,
    original_message: str,
    partial_response: str,
    tool_call_count_before_resume: int,
    executed_tool_snapshots: List[Dict[str, Any]],
    safe_str_fn: Callable[[Any, int], str],
) -> str:
    lines: List[str] = [
        "??????????????????????????????????",
        "????????????????????????",
        "",
        "??????",
        safe_str_fn(original_message, 4000),
    ]
    if partial_response.strip():
        lines.extend(
            [
                "",
                "??????????????",
                safe_str_fn(partial_response, 2000),
            ]
        )
    if executed_tool_snapshots:
        lines.append("")
        lines.append("?????????")
        for idx, item in enumerate(executed_tool_snapshots[-8:], start=1):
            tool_name = str(item.get("tool_name", "tool"))
            call_id = str(item.get("call_id", ""))
            result_brief = safe_str_fn(str(item.get("result", "")), 240)
            lines.append(f"{idx}. {tool_name} call_id={call_id} result={result_brief}")
    lines.extend(
        [
            "",
            f"???????????{tool_call_count_before_resume}",
            "??????????????????????????????????",
        ]
    )
    return "\n".join(lines)
