from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from autogen_agentchat.messages import (
    ModelClientStreamingChunkEvent,
    TextMessage,
    ThoughtEvent,
    ToolCallExecutionEvent,
    ToolCallRequestEvent,
)
from autogen_core import CancellationToken


def _safe_parse_tool_result(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            import ast
            return ast.literal_eval(raw)
        except Exception:
            try:
                import json
                return json.loads(raw)
            except Exception:
                return raw
    return raw


def _classify_failure_text(text: str) -> str:
    lowered = str(text or '').lower()
    if not lowered:
        return 'unknown'
    if any(tok in lowered for tok in ['timed out', 'timeout']):
        return 'timeout'
    if any(tok in lowered for tok in ['connect', 'connection', 'refused', 'unreachable']):
        return 'connection'
    if any(tok in lowered for tok in ['schema', 'config', 'parameter', 'field', 'validation', 'invalid', 'keyerror']):
        return 'config'
    if any(tok in lowered for tok in ['remote', 'http ', 'status_code', 'response_body']):
        return 'remote_service'
    if any(tok in lowered for tok in ['converge', 'solver', 'numerical', 'calculation', 'run failed', 'simulation failed']):
        return 'runtime'
    if any(tok in lowered for tok in ['non json', 'json', 'decode']):
        return 'result_format'
    return 'unknown'


def _classify_tool_failure(tool_name: str, result_payload: Dict[str, Any]) -> str:
    if not bool(result_payload.get('is_error')):
        return ''
    raw_result = result_payload.get('result', '')
    parsed = _safe_parse_tool_result(raw_result)
    error_text = ''
    if isinstance(parsed, dict):
        error_text = str(parsed.get('error') or parsed.get('message') or parsed.get('detail') or parsed)
    else:
        error_text = str(raw_result)
    base = _classify_failure_text(error_text)
    if tool_name == 'get_result':
        if base == 'remote_service':
            return 'result_remote_error'
        if base == 'timeout':
            return 'result_timeout'
        if base == 'connection':
            return 'result_connection_error'
        if base == 'result_format':
            return 'result_format_error'
        return 'result_fetch_error'
    if tool_name == 'run_simulation':
        # 优先读取 run_simulation 返回的 error_type 字段（与高频错误统计逻辑一致）
        if isinstance(parsed, dict):
            error_type_field = str(parsed.get('error_type', ''))
            if '运行过程' in error_type_field:
                return 'simulation_runtime_error'
            elif '配置' in error_type_field:
                return 'simulation_config_error'
        # 回退到文本关键词匹配
        if base == 'config':
            return 'simulation_config_error'
        if base == 'runtime':
            return 'simulation_runtime_error'
        if base == 'timeout':
            return 'simulation_timeout'
        if base == 'connection':
            return 'simulation_connection_error'
        if base == 'remote_service':
            return 'simulation_remote_error'
        return 'simulation_unknown_error'
    if tool_name == 'get_schema':
        if base == 'timeout':
            return 'schema_timeout'
        if base == 'connection':
            return 'schema_connection_error'
        return 'schema_generation_error'
    if tool_name.startswith('memory_'):
        return 'memory_tool_error'
    return f'{tool_name or "tool"}_error'


def _progress_stage_for_request(tool_name: str) -> str:
    mapping = {
        'memory_search_experience': 'memory_search_started',
        'memory_get_experience': 'memory_fetch_started',
        'get_schema': 'schema_generation_started',
        'run_simulation': 'simulation_started',
        'get_result': 'result_fetch_started',
    }
    return mapping.get(tool_name, '')


def _progress_stage_for_result(tool_name: str, result_payload: Dict[str, Any]) -> str:
    success = not bool(result_payload.get('is_error'))
    mapping = {
        'memory_search_experience': ('memory_search_succeeded', 'memory_search_failed'),
        'memory_get_experience': ('memory_fetch_succeeded', 'memory_fetch_failed'),
        'get_schema': ('schema_generation_succeeded', 'schema_generation_failed'),
        'run_simulation': ('simulation_succeeded', 'simulation_failed'),
        'get_result': ('result_fetch_succeeded', 'result_fetch_failed'),
    }
    pair = mapping.get(tool_name)
    if not pair:
        return ''
    return pair[0] if success else pair[1]


def _compact_tool_result_payload(tool_name: str, result_payload: Dict[str, Any], safe_str: Callable[[str, int], str]) -> Dict[str, Any]:
    compact = dict(result_payload)
    raw_result = result_payload.get('result')
    if tool_name == 'memory_get_experience' and not bool(result_payload.get('is_error')):
        parsed = _safe_parse_tool_result(raw_result)
        if isinstance(parsed, dict):
            item = parsed.get('item') if isinstance(parsed.get('item'), dict) else parsed
            markdown = str(item.get('markdown', '') or '')
            compact['result'] = {
                'memory_id': item.get('memory_id'),
                'task_type': item.get('task_type'),
                'reward': item.get('reward'),
                'tool_call_count': item.get('tool_call_count'),
                'has_markdown': bool(markdown),
                'markdown_chars': len(markdown),
                'markdown_preview': safe_str(markdown, 1200),
            }
            compact['result_truncated'] = True
            return compact
    if isinstance(raw_result, str) and len(raw_result) > 4000:
        compact['result'] = safe_str(raw_result, 4000)
        compact['result_truncated'] = True
    return compact


async def execute_user_task(
    *,
    user_message: str,
    send_payload: Callable[[Dict[str, Any]], Awaitable[None]],
    cancel_token: CancellationToken,
    source: str,
    extra_metadata: Optional[Dict[str, Any]] = None,
    deps: Dict[str, Any],
) -> str:
    get_state_fn = deps["get_state_fn"]
    set_state_fn = deps["set_state_fn"]
    AspenTask = deps["AspenTask"]
    get_agent_fn = deps["get_agent_fn"]
    reset_agent_fn = deps["reset_agent_fn"]
    store = deps["store"]
    persist_rollout_start = deps["persist_rollout_start_fn"]
    safe_emit_message = deps["safe_emit_message_fn"]
    safe_emit_annotation = deps["safe_emit_annotation_fn"]
    persist_span = deps["persist_span_fn"]
    infer_task_type = deps["infer_task_type_fn"]
    build_memory_context_for_task = deps["build_memory_context_for_task_fn"]
    log_memory_usage_events = deps["log_memory_usage_events_fn"]
    safe_str = deps["safe_str_fn"]
    estimate_prompt_tokens = deps["estimate_prompt_tokens_fn"]
    build_auto_resume_prompt = deps["build_auto_resume_prompt_fn"]
    safe_operation_context = deps["safe_operation_context_fn"]
    extract_tool_result_payload = deps["extract_tool_result_payload_fn"]
    is_context_overflow_error = deps["is_context_overflow_error_fn"]
    query_spans_sqlite = deps["query_spans_sqlite_fn"]
    collect_simulation_metrics = deps["collect_simulation_metrics_fn"]
    calculate_reward = deps["calculate_reward_fn"]
    safe_emit_reward = deps["safe_emit_reward_fn"]
    persist_rollout_status = deps["persist_rollout_status_fn"]
    finalize_memory_usage_events = deps["finalize_memory_usage_events_fn"]
    auto_upsert_memory_from_rollout = deps["auto_upsert_memory_from_rollout_fn"]
    build_user_friendly_error = deps["build_user_friendly_error_fn"]
# REMOVED:     policy_suggest = deps.get("policy_suggest_fn")
# REMOVED:     build_policy_guidance = deps.get("build_policy_guidance_fn")
# REMOVED:     policy_mode = str(deps.get("policy_mode", "off") or "off")
    select_prompt_assignment = deps.get("select_prompt_assignment_fn")
    build_effective_system_prompt = deps.get("build_effective_system_prompt_fn")
    record_prompt_assignment = deps.get("record_prompt_assignment_fn")
    prompt_version_mode = str(deps.get("prompt_version_mode", "off") or "off")
    logger = deps["logger"]
    settings_mem_min_reward = deps["memory_min_reward"]

    state = dict(get_state_fn())
    task_counter = int(state.get("task_counter", 0)) + 1
    set_state_fn(task_counter=task_counter)
    task = AspenTask(task_id=f"online_{task_counter}", user_requirement=user_message)

    metadata_obj = {
        "source": source,
        "user_message": user_message,
        "timestamp": time.time(),
        "is_online": True,
    }
    if isinstance(extra_metadata, dict):
        metadata_obj.update(extra_metadata)

    rollout = await store.start_rollout(
        input=task.to_dict(),
        mode="test",
        resources_id=None,
        metadata=metadata_obj,
    )
    attempt_id = None
    try:
        attempt_id = rollout.attempt.attempt_id  # type: ignore[attr-defined]
    except Exception:
        attempt_id = f"attempt_{task.task_id}"

    request_task_type = str(metadata_obj.get("task_type", "")).strip().lower()
    if request_task_type not in {"unit", "process"}:
        request_task_type = ""
    task_type = request_task_type or infer_task_type(user_message)

    prompt_assignment: Dict[str, Any] = {}
    effective_system_prompt: Optional[str] = None
    if callable(select_prompt_assignment):
        try:
            prompt_assignment = select_prompt_assignment(
                rollout_id=rollout.rollout_id,
                user_message=user_message,
                task_type=task_type,
                mode=prompt_version_mode,
            ) or {}
        except Exception as exc:
            prompt_assignment = {
                "selection_error": str(exc),
                "bucket": "selection_error",
                "prompt_version_id": "published_static",
                "applied_version_id": "published_static",
            }
        if isinstance(prompt_assignment, dict):
            metadata_obj["prompt_version_id"] = prompt_assignment.get("prompt_version_id")
            metadata_obj["prompt_applied_version_id"] = prompt_assignment.get("applied_version_id")
            metadata_obj["prompt_bucket"] = prompt_assignment.get("bucket")
            metadata_obj["prompt_assignment_mode"] = prompt_assignment.get("assignment_mode")
            if callable(build_effective_system_prompt):
                try:
                    effective_system_prompt = build_effective_system_prompt(assignment=prompt_assignment)
                except Exception as exc:
                    prompt_assignment["build_error"] = str(exc)
                    effective_system_prompt = None

    persist_rollout_start(
        rollout_id=rollout.rollout_id,
        attempt_id=attempt_id,
        status="running",
        mode="online" if metadata_obj.get("is_online") else "test",
        start_time=float(getattr(rollout, "start_time", time.time())),
        input_obj=task.to_dict(),
        metadata_obj=metadata_obj,
        user_id=str(metadata_obj.get("user_id", "") or "").strip() or None,
    )
    if prompt_assignment:
        persist_span(rollout.rollout_id, "prompt_assignment", dict(prompt_assignment))
        if callable(record_prompt_assignment):
            try:
                record_prompt_assignment(
                    rollout_id=rollout.rollout_id,
                    assignment=prompt_assignment,
                )
            except Exception as exc:
                persist_span(rollout.rollout_id, "prompt_assignment_error", {"error": str(exc)})
    await send_payload({"type": "rollout_started", "rollout_id": rollout.rollout_id, "attempt_id": attempt_id, "task_id": task.task_id})

    safe_emit_message(f"task_started: {task.task_id}")
    safe_emit_annotation(
        {
            "task_id": task.task_id,
            "user_message": user_message,
            "mode": "test",
            "is_online": True,
            "rollout_id": rollout.rollout_id,
            "attempt_id": attempt_id,
            "source": source,
        }
    )
    persist_span(rollout.rollout_id, "task_started", {"task_id": task.task_id, "message": user_message})

    reset_agent_fn()
    agent = get_agent_fn(system_prompt_override=effective_system_prompt)
    memory_hits: List[Dict[str, Any]] = []
    memory_context = ""
    memory_usage_count = 0
    disable_memory = bool((extra_metadata or {}).get("disable_memory", False))
    if source != "resume" and not disable_memory:
        memory_pack = build_memory_context_for_task(user_message, top_k=5)
        memory_hits = memory_pack.get("hits", [])
        memory_context = str(memory_pack.get("context_text", "")).strip()
    if memory_hits:
        memory_usage_count = log_memory_usage_events(
            rollout_id=rollout.rollout_id,
            query_text=user_message,
            task_type=task_type,
            source=source,
            hits=memory_hits,
        )
        persist_span(
            rollout.rollout_id,
            "memory_retrieval",
            {
                "hit_count": len(memory_hits),
                "memory_ids": [x.get("memory_id") for x in memory_hits if isinstance(x, dict)],
                "scores": [
                    {"memory_id": x.get("memory_id"), "score": x.get("score"), "match": x.get("match", {})}
                    for x in memory_hits
                    if isinstance(x, dict)
                ],
            },
        )

    await send_payload(
        {
            "type": "memory_hits",
            "count": len(memory_hits),
            "items": [
                {"memory_id": x.get("memory_id"), "task_type": x.get("task_type"), "task_text": safe_str(str(x.get("task_text", "")), 120), "score": x.get("score")}
                for x in memory_hits
                if isinstance(x, dict)
            ],
        }
    )
    if memory_context:
        await send_payload(
            {
                "type": "memory_context",
                "hit_count": len(memory_hits),
                "context_text": safe_str(memory_context, 8000),
                "items": [
                    {
                        "memory_id": x.get("memory_id"),
                        "task_type": x.get("task_type"),
                        "task_text": safe_str(str(x.get("task_text", "")), 160),
                        "score": x.get("score"),
                        "strategy_summary": x.get("strategy_summary", x.get("strategy", "")),
                        "config_deltas": x.get("config_deltas", x.get("config", "")),
                        "failure_avoidance": x.get("failure_avoidance", x.get("pitfalls", "")),
                    }
                    for x in memory_hits
                    if isinstance(x, dict)
                ],
            }
        )


# REMOVED:     policy_hint_text = ""
# REMOVED:     try:
# REMOVED:         if callable(policy_suggest):
# REMOVED:             policy_info = policy_suggest(
# REMOVED:                 user_message=user_message,
# REMOVED:                 task_type=task_type,
# REMOVED:                 memory_hit_count=len(memory_hits),
# REMOVED:                 tool_call_count=0,
# REMOVED:                 rollout_id=rollout.rollout_id,
# REMOVED:                 policy_mode=policy_mode,
# REMOVED:             )
# REMOVED:             persist_span(
# REMOVED:                 rollout.rollout_id,
# REMOVED:                 "policy_suggestion",
# REMOVED:                 {
# REMOVED:                     "mode": policy_info.get("mode"),
# REMOVED:                     "policy_version": policy_info.get("policy_version"),
# REMOVED:                     "state_key": policy_info.get("state_key"),
# REMOVED:                     "actions": policy_info.get("actions", []),
# REMOVED:                     "enforce": bool(policy_info.get("enforce", False)),
# REMOVED:                     "latency_ms": policy_info.get("latency_ms"),
# REMOVED:                 },
# REMOVED:             )
# REMOVED:             await send_payload(
# REMOVED:                 {
# REMOVED:                     "type": "policy_hint",
# REMOVED:                     "mode": policy_info.get("mode"),
# REMOVED:                     "policy_version": policy_info.get("policy_version"),
# REMOVED:                     "state_key": policy_info.get("state_key"),
# REMOVED:                     "actions": policy_info.get("actions", []),
# REMOVED:                     "enforce": bool(policy_info.get("enforce", False)),
# REMOVED:                 }
# REMOVED:             )
# REMOVED:             if callable(build_policy_guidance):
# REMOVED:                 policy_hint_text = build_policy_guidance(
# REMOVED:                     list(policy_info.get("actions", []) or []),
# REMOVED:                     enforce=bool(policy_info.get("enforce", False)),
# REMOVED:                 )
# REMOVED:     except Exception as policy_exc:
# REMOVED:         persist_span(rollout.rollout_id, "policy_suggestion_error", {"error": str(policy_exc)})
# REMOVED: 
    memory_tool_guide = (
        "[经验检索策略] 在开始流程设计前，先调用 memory_search_experience(query=当前任务, top_k=3, task_type=可选)。\n"
        "若命中高分经验，再调用 memory_get_experience(memory_id) 获取完整经验步骤、关键配置与避坑要点。\n"
        "若主要设备、物流流向、关键操作、物性方法、组分基本一致，优先复用历史配置并最小改动后先执行 run_simulation。\n"
        "仅当经验信息不足、匹配差异较大或配置不完整时，再调用 get_schema 重新生成配置。\n"
    )
    effective_user_message = memory_tool_guide + "\n[当前任务]\n" + user_message
# REMOVED:     if policy_hint_text:
# REMOVED:         effective_user_message = policy_hint_text + "\n\n" + effective_user_message

    accumulated_content = ""
    tool_call_count = 0
    task_started_monotonic = time.time()
    final_file_paths: List[Dict[str, str]] = []
    executed_tool_snapshots: List[Dict[str, Any]] = []
    failure_categories: List[str] = []
    progress_events: List[str] = []
    auto_resume_count = 0
    before_resume_tool_calls = 0

    estimated_tokens = estimate_prompt_tokens(effective_user_message)
    if estimated_tokens > 14000:
        auto_resume_count = 1
        persist_span(
            rollout.rollout_id,
            "auto_resume_triggered",
            {
                "reason": "preflight_budget",
                "estimated_prompt_tokens": estimated_tokens,
                "tool_call_count_before_resume": 0,
                "partial_response_len": 0,
            },
        )
        effective_user_message = build_auto_resume_prompt(
            original_message=user_message,
            partial_response="",
            tool_call_count_before_resume=0,
            executed_tool_snapshots=[],
            safe_str_fn=safe_str,
        )

    try:
        loop_idx = 0
        while True:
            try:
                with safe_operation_context("execute_task", {"task_id": task.task_id, "source": source, "loop_idx": loop_idx}):
                    async for chunk in agent.on_messages_stream([TextMessage(content=effective_user_message, source="user")], cancel_token):
                        payload: Dict[str, Any] = {"role": "assistant", "type": "update"}
                        if isinstance(chunk, ThoughtEvent):
                            payload["thought"] = chunk.content
                            safe_emit_message(f"thought: {chunk.content}")
                            persist_span(rollout.rollout_id, "thought", {"content": chunk.content})
                        elif isinstance(chunk, ModelClientStreamingChunkEvent):
                            accumulated_content += chunk.content
                            continue
                        elif isinstance(chunk, ToolCallRequestEvent):
                            tool_calls = []
                            for idx, tc in enumerate(chunk.content):
                                tool_name = tc.name
                                tool_calls.append({"id": tc.id if hasattr(tc, "id") else f"call_{idx}", "function_name": tool_name, "args": tc.arguments})
                                stage = _progress_stage_for_request(str(tool_name or ""))
                                if stage:
                                    progress_events.append(stage)
                                    persist_span(rollout.rollout_id, "task_progress", {"stage": stage, "tool_name": tool_name, "status": "started"})
                                    # await send_payload({"type": "task_progress", "stage": stage, "tool_name": tool_name, "status": "started", "rollout_id": rollout.rollout_id})
                            tool_call_count += len(tool_calls)
                            payload.update({"status": "tool_calling", "tool_calls": tool_calls})
                            safe_emit_annotation({"event": "tool_call_request", "tools": tool_calls})
                            persist_span(rollout.rollout_id, "tool_call_request", {"tool_calls": tool_calls})
                        elif isinstance(chunk, ToolCallExecutionEvent):
                            tool_results = []
                            for res in chunk.content:
                                result_payload = extract_tool_result_payload(res.content, res.call_id)
                                tool_name = str(getattr(res, "name", "") or result_payload.get("tool_name") or "tool")
                                result_payload["tool_name"] = tool_name
                                failure_category = _classify_tool_failure(tool_name, result_payload)
                                if failure_category:
                                    result_payload["failure_category"] = failure_category
                                    failure_categories.append(failure_category)
                                compact_payload = _compact_tool_result_payload(tool_name, result_payload, safe_str)
                                tool_results.append(compact_payload)
                                executed_tool_snapshots.append(
                                    {
                                        "call_id": result_payload.get("call_id", ""),
                                        "tool_name": tool_name,
                                        "result": safe_str(str(result_payload.get("result", "")), 500),
                                    }
                                )
                                stage = _progress_stage_for_result(tool_name, result_payload)
                                if stage:
                                    progress_events.append(stage)
                                    progress_payload = {"type": "task_progress", "stage": stage, "tool_name": tool_name, "status": "failed" if result_payload.get("is_error") else "succeeded", "rollout_id": rollout.rollout_id}
                                    if failure_category:
                                        progress_payload["failure_category"] = failure_category
                                    persist_span(rollout.rollout_id, "task_progress", {k: v for k, v in progress_payload.items() if k != "type"})
                                    # await send_payload(progress_payload)
                                incoming_files = result_payload.get("file_paths")
                                if isinstance(incoming_files, list) and incoming_files:
                                    if len(incoming_files) >= 3:
                                        final_file_paths = incoming_files
                                    else:
                                        existing_paths = {str(item.get("path")) for item in final_file_paths if isinstance(item, dict)}
                                        for item in incoming_files:
                                            if not isinstance(item, dict):
                                                continue
                                            fp = str(item.get("path", ""))
                                            if fp and fp not in existing_paths:
                                                final_file_paths.append(item)
                                                existing_paths.add(fp)
                            payload.update({"status": "tool_executed", "tool_results": tool_results})
                            safe_emit_annotation(
                                {
                                    "event": "tool_execution",
                                    "tool_names": [str(item.get("tool_name", "")) for item in tool_results],
                                    "tool_count": len(tool_results),
                                    "error_count": sum(1 for item in tool_results if item.get("is_error")),
                                    "truncated_count": sum(1 for item in tool_results if item.get("result_truncated")),
                                    "failure_categories": [
                                        str(item.get("failure_category"))
                                        for item in tool_results
                                        if item.get("failure_category")
                                    ],
                                }
                            )
                            persist_span(rollout.rollout_id, "tool_execution", {"tool_results": tool_results})
                        await send_payload(payload)
                break
            except Exception as loop_exc:
                if cancel_token.is_cancelled():
                    raise
                if auto_resume_count >= 1 or (not is_context_overflow_error(loop_exc)):
                    raise
                auto_resume_count += 1
                before_resume_tool_calls = tool_call_count
                persist_span(
                    rollout.rollout_id,
                    "auto_resume_triggered",
                    {
                        "reason": "context_overflow",
                        "error": str(loop_exc),
                        "tool_call_count_before_resume": before_resume_tool_calls,
                        "partial_response_len": len(accumulated_content),
                    },
                )
                effective_user_message = build_auto_resume_prompt(
                    original_message=user_message,
                    partial_response=accumulated_content,
                    tool_call_count_before_resume=before_resume_tool_calls,
                    executed_tool_snapshots=executed_tool_snapshots,
                    safe_str_fn=safe_str,
                )
                accumulated_content = ""
                reset_agent_fn()
                agent = get_agent_fn(system_prompt_override=effective_system_prompt)
                loop_idx += 1
                continue

        if accumulated_content:
            await send_payload({"role": "assistant", "type": "update", "content": accumulated_content})
            persist_span(rollout.rollout_id, "assistant_response", {"content": accumulated_content})

        if final_file_paths:
            await send_payload({"type": "file_download", "rollout_id": rollout.rollout_id, "file_paths": final_file_paths})
            persist_span(rollout.rollout_id, "file_download", {"file_paths": final_file_paths})

        spans_for_reward = query_spans_sqlite(rollout.rollout_id)
        sim_metrics = collect_simulation_metrics(spans_for_reward)
        elapsed_seconds = max(0.0, time.time() - task_started_monotonic)
        reward_info = calculate_reward(
            response_content=accumulated_content,
            tool_call_count=tool_call_count,
            file_download_count=len(final_file_paths),
            task_type=task_type,
            simulation_metrics=sim_metrics,
            user_message=user_message,
            elapsed_seconds=elapsed_seconds,
            memory_hit_count=len(memory_hits),
            memory_usage_count=memory_usage_count,
            spans=spans_for_reward,
        )
        if failure_categories:
            reward_info["failure_categories"] = sorted(set(failure_categories))
        if progress_events:
            reward_info["progress_events"] = progress_events[-12:]
        safe_emit_reward(reward=reward_info["reward"], dimensions=reward_info)
        persist_span(rollout.rollout_id, "reward", reward_info)
        if auto_resume_count > 0:
            persist_span(
                rollout.rollout_id,
                "auto_resume_result",
                {
                    "auto_resume_count": auto_resume_count,
                    "success": True,
                    "tool_call_count_before_resume": before_resume_tool_calls,
                    "tool_call_count_total": tool_call_count,
                    "step_delta": max(0, tool_call_count - before_resume_tool_calls),
                },
            )

        await store.update_rollout(rollout_id=rollout.rollout_id, status="succeeded")
        persist_rollout_status(rollout.rollout_id, "succeeded")
        if memory_usage_count > 0:
            finalize_memory_usage_events(
                rollout_id=rollout.rollout_id,
                status="succeeded",
                reward=float(reward_info.get("reward", 0.0)),
                tool_call_count=tool_call_count,
            )
        memory_task_text = user_message
        if source == "resume":
            memory_task_text = str(metadata_obj.get("resume_original_message", "")).strip() or user_message
        if not disable_memory:
            auto_upsert_memory_from_rollout(
                rollout_id=rollout.rollout_id,
                task_text=memory_task_text,
                reward=float(reward_info.get("reward", 0.0)),
                tool_call_count=tool_call_count,
                min_reward=float(settings_mem_min_reward),
                task_type_hint=task_type,
                equipment_type_hint=str(metadata_obj.get("equipment_type", "")),
                deps=deps,
            )
        await send_payload({"type": "done", "rollout_id": rollout.rollout_id, "reward": reward_info["reward"], "status": "succeeded"})
    except asyncio.CancelledError:
        persist_span(rollout.rollout_id, "cancelled", {"reason": "user_stop"})
        safe_emit_reward(reward=0.0)
        persist_span(rollout.rollout_id, "reward", {"reward": 0.0, "cancelled": True})
        await store.update_rollout(rollout_id=rollout.rollout_id, status="failed")
        persist_rollout_status(rollout.rollout_id, "failed")
        if memory_usage_count > 0:
            finalize_memory_usage_events(rollout_id=rollout.rollout_id, status="cancelled", reward=0.0, tool_call_count=tool_call_count)
        await send_payload({"type": "stopped", "rollout_id": rollout.rollout_id, "status": "stopped"})
        raise
    except Exception as exc:
        if cancel_token.is_cancelled():
            persist_span(rollout.rollout_id, "cancelled", {"reason": "user_stop"})
            safe_emit_reward(reward=0.0)
            persist_span(rollout.rollout_id, "reward", {"reward": 0.0, "cancelled": True})
            await store.update_rollout(rollout_id=rollout.rollout_id, status="failed")
            persist_rollout_status(rollout.rollout_id, "failed")
            if memory_usage_count > 0:
                finalize_memory_usage_events(rollout_id=rollout.rollout_id, status="cancelled", reward=0.0, tool_call_count=tool_call_count)
            await send_payload({"type": "stopped", "rollout_id": rollout.rollout_id, "status": "stopped"})
        else:
            logger.exception("Task execution failed")
            safe_emit_message(f"task_failed: {exc}")
            safe_emit_reward(reward=-1.0)
            if auto_resume_count > 0:
                persist_span(
                    rollout.rollout_id,
                    "auto_resume_result",
                    {
                        "auto_resume_count": auto_resume_count,
                        "success": False,
                        "tool_call_count_before_resume": before_resume_tool_calls,
                        "tool_call_count_total": tool_call_count,
                        "step_delta": max(0, tool_call_count - before_resume_tool_calls),
                        "error": str(exc),
                    },
                )
            error_attrs = {"error": str(exc)}
            if failure_categories:
                error_attrs["failure_categories"] = sorted(set(failure_categories))
                error_attrs["failure_category"] = sorted(set(failure_categories))[0]
            persist_span(rollout.rollout_id, "error", error_attrs)
            reward_attrs = {"reward": -1.0}
            if failure_categories:
                reward_attrs["failure_categories"] = sorted(set(failure_categories))
            persist_span(rollout.rollout_id, "reward", reward_attrs)
            await store.update_rollout(rollout_id=rollout.rollout_id, status="failed")
            persist_rollout_status(rollout.rollout_id, "failed")
            if memory_usage_count > 0:
                finalize_memory_usage_events(rollout_id=rollout.rollout_id, status="failed", reward=-1.0, tool_call_count=tool_call_count)
            friendly = build_user_friendly_error(exc)
            await send_payload(
                {
                    "type": "error",
                    "rollout_id": rollout.rollout_id,
                    "error": str(exc),
                    "error_code": friendly["code"],
                    "error_message": friendly["message"],
                    "status": "failed",
                }
            )
    return rollout.rollout_id
