from __future__ import annotations

import ast
import json
from typing import Any, Callable, Dict, List, Optional, Tuple


def extract_config_snippet_from_spans(spans: List[Dict[str, Any]], *, safe_str_fn: Callable[[Any, int], str]) -> str:
    for span in reversed(spans):
        if span.get("name") != "tool_call_request":
            continue
        attrs = span.get("attributes", {})
        calls = attrs.get("tool_calls")
        if not isinstance(calls, list):
            continue
        for call in calls:
            if not isinstance(call, dict):
                continue
            if str(call.get("function_name", "")).strip() != "run_simulation":
                continue
            args = call.get("args")
            if isinstance(args, str):
                try:
                    parsed = json.loads(args)
                except Exception:
                    return safe_str_fn(args, 3000)
            elif isinstance(args, dict):
                parsed = args
            else:
                parsed = {}
            config = parsed.get("config", parsed)
            try:
                return safe_str_fn(json.dumps(config, ensure_ascii=False, indent=2), 5000)
            except Exception:
                return safe_str_fn(str(config), 3000)
    return ""


def extract_strategy_from_spans(spans: List[Dict[str, Any]], *, safe_str_fn: Callable[[Any, int], str]) -> str:
    thoughts: List[str] = []
    assistant_text: List[str] = []
    for span in spans:
        name = str(span.get("name", ""))
        attrs = span.get("attributes", {})
        if name == "thought":
            text = safe_str_fn(attrs.get("content", ""), 600)
            if text:
                thoughts.append(text)
        elif name == "assistant_response":
            text = safe_str_fn(attrs.get("content", ""), 1200)
            if text:
                assistant_text.append(text)
    blocks: List[str] = []
    if thoughts:
        blocks.append("Thoughts:\n" + "\n".join(thoughts[-2:]))
    if assistant_text:
        blocks.append("Response:\n" + "\n".join(assistant_text[-1:]))
    return safe_str_fn("\n\n".join(blocks), 2000)


def extract_error_type_from_payload(
    result_obj: Any,
    fallback_text: str = "",
    *,
    classify_run_simulation_error_fn: Optional[Callable[[str], str]] = None,
) -> str:
    if isinstance(result_obj, dict):
        raw = str(result_obj.get("error_type", "")).strip()
        if raw:
            low = raw.lower()
            if "config" in low or "配置" in raw:
                return "模拟配置错误"
            if "runtime" in low or "process" in low or "运行过程" in raw:
                return "模拟运行错误"
            return raw
    if callable(classify_run_simulation_error_fn):
        return classify_run_simulation_error_fn(fallback_text)
    return "未知"


def extract_run_simulation_attempts_from_spans(
    spans: List[Dict[str, Any]],
    *,
    safe_str_fn: Callable[[Any, int], str],
    classify_run_simulation_error_fn: Optional[Callable[[str], str]] = None,
) -> List[Dict[str, Any]]:
    attempts: List[Dict[str, Any]] = []
    call_to_tool: Dict[str, str] = {}

    for span in spans:
        if span.get("name") != "tool_call_request":
            continue
        attrs = span.get("attributes", {})
        calls = attrs.get("tool_calls")
        if not isinstance(calls, list):
            continue
        for c in calls:
            if not isinstance(c, dict):
                continue
            call_id = str(c.get("id", "")).strip()
            fn_name = str(c.get("function_name", "")).strip()
            if not fn_name:
                fn = c.get("function")
                if isinstance(fn, dict):
                    fn_name = str(fn.get("name", "")).strip()
            if call_id and fn_name:
                call_to_tool[call_id] = fn_name

    seq = 0
    for span in spans:
        if span.get("name") != "tool_execution":
            continue
        attrs = span.get("attributes", {})
        tool_results = attrs.get("tool_results")
        if not isinstance(tool_results, list):
            continue
        for item in tool_results:
            if not isinstance(item, dict):
                continue
            call_id = str(item.get("call_id", "")).strip()
            tool_name = str(item.get("tool_name", "")).strip() or call_to_tool.get(call_id, "")
            if tool_name != "run_simulation":
                continue

            seq += 1
            is_error = bool(item.get("is_error"))
            raw_result = item.get("result", "")
            parsed: Any = raw_result
            result_text = ""
            if isinstance(raw_result, str):
                result_text = raw_result
                try:
                    parsed = ast.literal_eval(raw_result)
                except Exception:
                    parsed = raw_result
            elif isinstance(raw_result, dict):
                parsed = raw_result
                result_text = json.dumps(raw_result, ensure_ascii=False)

            if isinstance(parsed, dict):
                error_msg = parsed.get("error_message", "") or parsed.get("error", "") or parsed.get("message", "") or parsed.get("detail", "") or ""
                # Extract content after ERROR keyword for runtime errors
                if "ERROR" in str(error_msg):
                    err_parts = str(error_msg).split("ERROR")
                    last_err = err_parts[-1].strip()
                    first_line = last_err.split(chr(10))[0].strip() if last_err else ""
                    error_match = bool(first_line)
                    if error_match:
                        result_text = first_line
                    else:
                        result_text = str(error_msg)
                elif error_msg:
                    result_text = str(error_msg)

            err_type = "none"
            if is_error:
                err_type = extract_error_type_from_payload(
                    parsed,
                    result_text,
                    classify_run_simulation_error_fn=classify_run_simulation_error_fn,
                )

            attempts.append(
                {
                    "seq": seq,
                    "is_error": is_error,
                    "error_type": err_type,
                    "error_text": safe_str_fn(result_text, 500),
                    "raw_result": safe_str_fn(str(raw_result), 800),
                }
            )

    thought_texts: List[str] = []
    for span in spans:
        if span.get("name") == "thought":
            t = safe_str_fn(span.get("attributes", {}).get("content", ""), 600)
            if t:
                thought_texts.append(t)
    last_thought = thought_texts[-1] if thought_texts else ""
    for att in attempts:
        att["fix_hint"] = last_thought if att.get("is_error") else ""

    return attempts


def build_pitfall_summary(attempts: List[Dict[str, Any]], *, safe_str_fn: Callable[[Any, int], str]) -> Dict[str, str]:
    failed = [a for a in attempts if bool(a.get("is_error"))]
    if not failed:
        return {"summary": "", "failure_reason": "", "fix_action": "", "lesson": ""}

    lines = []
    for a in failed:
        lines.append(
            f"第{a.get('seq')}次尝试: 错误类型={a.get('error_type')} 错误信息={safe_str_fn(a.get('error_text', ''), 180)}"
        )
    failure_reason = safe_str_fn(failed[-1].get("error_text", ""), 500)
    fix_action = safe_str_fn(failed[-1].get("fix_hint", ""), 600) or "根据错误类型调整配置参数后重新调用 run_simulation。"
    lesson = "优先复用已知的配置/运行错误修复方案，避免重复踩坑。"
    summary = "run_simulation 失败链路\n" + "\n".join(lines)
    return {
        "summary": safe_str_fn(summary, 1800),
        "failure_reason": failure_reason,
        "fix_action": fix_action,
        "lesson": lesson,
    }


def extract_pitfall_details_from_spans(
    spans: List[Dict[str, Any]],
    *,
    safe_str_fn: Callable[[Any, int], str],
) -> Dict[str, str]:
    call_to_tool: Dict[str, str] = {}
    for span in spans:
        if span.get("name") != "tool_call_request":
            continue
        attrs = span.get("attributes", {})
        calls = attrs.get("tool_calls")
        if not isinstance(calls, list):
            continue
        for c in calls:
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id", "")).strip()
            fn = c.get("function")
            tool_name = ""
            if isinstance(fn, dict):
                tool_name = str(fn.get("name", "")).strip()
            if cid and tool_name:
                call_to_tool[cid] = tool_name

    failures: List[Tuple[int, str]] = []
    success_idx: Optional[int] = None
    for idx, span in enumerate(spans):
        if span.get("name") != "tool_execution":
            continue
        attrs = span.get("attributes", {})
        tool_name = str(attrs.get("tool_name", "")).strip()
        call_id = str(attrs.get("call_id", "")).strip() or str(attrs.get("tool_call_id", "")).strip()
        if not tool_name and call_id:
            tool_name = call_to_tool.get(call_id, "")
        if tool_name != "run_simulation":
            continue
        result = attrs.get("result")
        result_obj: Any = result
        if isinstance(result, str):
            try:
                result_obj = json.loads(result)
            except Exception:
                result_obj = result
        is_error = False
        err_text = ""
        if isinstance(result_obj, dict):
            is_error = bool(result_obj.get("is_error"))
            if is_error:
                err_text = safe_str_fn(
                    result_obj.get("error")
                    or result_obj.get("message")
                    or result_obj.get("detail")
                    or str(result_obj),
                    500,
                )
        elif isinstance(result_obj, str):
            lowered = result_obj.lower()
            if "error" in lowered or "failed" in lowered or "traceback" in lowered:
                is_error = True
                err_text = safe_str_fn(result_obj, 500)
        if is_error:
            failures.append((idx, err_text))
        elif failures:
            success_idx = idx

    if not failures:
        return {"failure_reason": "", "fix_action": "", "lesson": "", "summary": ""}

    last_fail_idx, last_fail_text = failures[-1]
    fix_action = ""
    thought_candidates: List[str] = []
    right_bound = success_idx if success_idx is not None else len(spans) - 1
    for idx in range(last_fail_idx + 1, right_bound + 1):
        span = spans[idx]
        if span.get("name") != "thought":
            continue
        attrs = span.get("attributes", {})
        text = safe_str_fn(attrs.get("content", ""), 600)
        if text:
            thought_candidates.append(text)
    if thought_candidates:
        fix_action = thought_candidates[-1]

    recovered = success_idx is not None
    lesson = "run_simulation 执行失败后通过修正配置重试成功，后续类似任务可复用此恢复路径。"
    if not recovered:
        lesson = "run_simulation 执行出错未恢复，需检查 schema 和配置参数后重试。"
    if not fix_action:
        fix_action = "根据错误信息调整模拟配置参数，然后重新调用 run_simulation。"

    summary_lines = [
        f"run_simulation 恢复摘要：失败次数={len(failures)}，最终状态={'已恢复' if recovered else '未恢复'}",
        f"失败原因：{last_fail_text or '未知'}",
        f"修复方法：{fix_action}",
        f"经验总结：{lesson}",
    ]
    return {
        "failure_reason": safe_str_fn(last_fail_text, 500),
        "fix_action": safe_str_fn(fix_action, 800),
        "lesson": safe_str_fn(lesson, 500),
        "summary": safe_str_fn("\n".join(summary_lines), 1500),
    }


def extract_pitfalls_from_spans(spans: List[Dict[str, Any]], *, safe_str_fn: Callable[[Any, int], str]) -> str:
    details = extract_pitfall_details_from_spans(spans, safe_str_fn=safe_str_fn)
    if details.get("summary"):
        return safe_str_fn(str(details["summary"]), 1500)
    errors: List[str] = []
    for span in spans:
        if span.get("name") != "error":
            continue
        attrs = span.get("attributes", {})
        text = safe_str_fn(attrs.get("error", ""), 500)
        if text:
            errors.append(text)
    return safe_str_fn("\n".join(errors[-3:]), 1500)


def extract_reward_and_tool_count(spans: List[Dict[str, Any]]) -> Tuple[float, int]:
    reward = 0.0
    tool_count = 0
    for span in spans:
        name = str(span.get("name", ""))
        attrs = span.get("attributes", {})
        if name == "reward":
            try:
                reward = float(attrs.get("reward", reward))
            except Exception:
                pass
        elif name == "tool_call_request":
            calls = attrs.get("tool_calls")
            if isinstance(calls, list):
                tool_count += len(calls)
    return reward, tool_count
