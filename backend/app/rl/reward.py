from __future__ import annotations

import ast
import json
import os
from typing import Any, Callable, Dict, List, Optional, Sequence, Set


def estimate_prompt_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, int(len(text) / 2.2))


def classify_run_simulation_error(error_text: str, *, normalize_text_fn: Callable[[str], str]) -> str:
    text = normalize_text_fn(error_text)
    if not text:
        return "unknown"
    config_markers = [
        "schema", "config", "parameter", "field", "missing", "required",
        "invalid", "validation", "json", "keyerror", "block_types", "type mismatch",
    ]
    runtime_markers = [
        "runtime", "run failed", "converge", "solver", "numerical", "flash",
        "simulation failed", "timeout", "timed out", "calculation",
    ]
    if any(m in text for m in config_markers):
        return "config"
    if any(m in text for m in runtime_markers):
        return "runtime"
    return "unknown"


def collect_simulation_metrics_from_spans(
    spans: List[Dict[str, Any]],
    *,
    extract_error_type_fn: Callable[[Any, str], str],
) -> Dict[str, int]:
    metrics: Dict[str, int] = {
        "get_schema_calls": 0,
        "get_schema_success": 0,
        "get_schema_fail": 0,
        "run_simulation_calls": 0,
        "run_simulation_success": 0,
        "run_simulation_fail_total": 0,
        "run_simulation_fail_config": 0,
        "run_simulation_fail_runtime": 0,
        "run_simulation_fail_unknown": 0,
        "get_result_calls": 0,
        "get_result_success": 0,
        "get_result_fail": 0,
        "rounds_completed": 0,
    }

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
            if not fn_name:
                continue
            if call_id:
                call_to_tool[call_id] = fn_name
            if fn_name == "get_schema":
                metrics["get_schema_calls"] += 1
            elif fn_name == "run_simulation":
                metrics["run_simulation_calls"] += 1
            elif fn_name == "get_result":
                metrics["get_result_calls"] += 1

    for span in spans:
        if span.get("name") != "tool_execution":
            continue
        attrs = span.get("attributes", {})
        results = attrs.get("tool_results")
        if not isinstance(results, list):
            continue
        for item in results:
            if not isinstance(item, dict):
                continue
            call_id = str(item.get("call_id", "")).strip()
            tool_name = str(item.get("tool_name", "")).strip() or call_to_tool.get(call_id, "")
            if not tool_name:
                continue
            is_error = bool(item.get("is_error"))
            raw_result = item.get("result", "")
            parsed_obj: Any = raw_result
            error_text = ""
            if isinstance(raw_result, str):
                error_text = raw_result
                try:
                    parsed = ast.literal_eval(raw_result)
                    parsed_obj = parsed
                    if isinstance(parsed, dict):
                        error_text = str(parsed.get("error") or parsed.get("message") or parsed.get("detail") or raw_result)
                except Exception:
                    parsed_obj = raw_result
            elif isinstance(raw_result, dict):
                parsed_obj = raw_result
                error_text = str(raw_result.get("error") or raw_result.get("message") or raw_result.get("detail") or raw_result)

            if tool_name == "get_schema":
                metrics["get_schema_fail" if is_error else "get_schema_success"] += 1
                continue
            if tool_name == "run_simulation":
                if is_error:
                    metrics["run_simulation_fail_total"] += 1
                    err_type = extract_error_type_fn(parsed_obj, error_text)
                    if err_type == "config":
                        metrics["run_simulation_fail_config"] += 1
                    elif err_type == "runtime":
                        metrics["run_simulation_fail_runtime"] += 1
                    else:
                        metrics["run_simulation_fail_unknown"] += 1
                else:
                    metrics["run_simulation_success"] += 1
                continue
            if tool_name == "get_result":
                metrics["get_result_fail" if is_error else "get_result_success"] += 1

    metrics["rounds_completed"] = min(metrics["run_simulation_success"], metrics["get_result_success"])
    return metrics


def exp_decay(value: float, alpha: float) -> float:
    value = max(0.0, float(value))
    return float(pow(2.718281828459045, -alpha * value))


def infer_expected_process_rounds(user_message: str) -> int:
    text = str(user_message or "")
    if any(k in text for k in ["T3", "stage 3", "third"]):
        return 3
    if any(k in text for k in ["T2", "stage 2", "second"]):
        return 2
    return 2


def _resolve_task_mode(task_type: str, user_message: str, response_content: str, infer_task_type_fn: Callable[[str], str]) -> str:
    mode = (task_type or "unknown").strip().lower()
    if mode not in {"unit", "process"}:
        mode = infer_task_type_fn(user_message or response_content or "")
        if mode not in {"unit", "process"}:
            mode = "unit"
    return mode


def _has_output_marker(text: str, file_download_count: int) -> bool:
    return any(k in text for k in ["result", "success", "file", "path", ".xlsx", ".bkp", "config"]) or file_download_count > 0


def _safe_load_result_obj(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return ast.literal_eval(raw)
        except Exception:
            try:
                return json.loads(raw)
            except Exception:
                return raw
    return raw


def _extract_result_texts(spans: Sequence[Dict[str, Any]]) -> List[str]:
    texts: List[str] = []
    for span in spans:
        if span.get("name") != "tool_execution":
            continue
        attrs = span.get("attributes", {})
        results = attrs.get("tool_results")
        if not isinstance(results, list):
            continue
        for item in results:
            if not isinstance(item, dict):
                continue
            if bool(item.get("is_error")):
                continue
            tool_name = str(item.get("tool_name", "") or "").strip()
            if tool_name != "get_result":
                continue
            raw = item.get("result", "")
            obj = _safe_load_result_obj(raw)
            if isinstance(obj, dict):
                try:
                    texts.append(json.dumps(obj, ensure_ascii=False))
                except Exception:
                    texts.append(str(obj))
            else:
                texts.append(str(obj))
    return texts


def infer_requested_outputs(user_message: str) -> Set[str]:
    text = str(user_message or "").lower()
    requested: Set[str] = set()
    if any(k in text for k in ["温度", "temperature", "temp"]):
        requested.add("temperature")
    if any(k in text for k in ["压力", "pressure", "pres"]):
        requested.add("pressure")
    if any(k in text for k in ["流量", "flow", "kmol", "mol flow"]):
        requested.add("flowrate")
    if any(k in text for k in ["组成", "组分", "composition", "mole frac", "mass frac", "摩尔分数", "纯度"]):
        requested.add("composition")
    if any(k in text for k in ["气相分数", "vapor frac", "vfrac"]):
        requested.add("vapor_fraction")
    if any(k in text for k in ["液相分数", "liquid frac"]):
        requested.add("liquid_fraction")
    if any(k in text for k in ["结果", "result", "文件", "file"]):
        requested.add("file_artifact")
    return requested


def calculate_requested_output_coverage(
    *,
    user_message: str,
    response_content: str,
    spans: Sequence[Dict[str, Any]],
    file_download_count: int,
) -> Optional[float]:
    del file_download_count
    requested = infer_requested_outputs(user_message)
    if not requested:
        return None

    result_blob = "\n".join(_extract_result_texts(spans)).lower()
    response_blob = str(response_content or "").lower()
    combined = result_blob + "\n" + response_blob

    signal_map = {
        "temperature": ["temperature", "temp", "温度", "b_temp", "temperature c"],
        "pressure": ["pressure", "pres", "压力", "b_pres", "pressure bar"],
        "flowrate": ["flow", "流量", "total flow", "mole flow", "mass flow", "kmol/hr"],
        "composition": ["composition", "组成", "组分", "mole frac", "mass frac", "摩尔分数", "纯度"],
        "vapor_fraction": ["vapor frac", "vfrac", "气相分数"],
        "liquid_fraction": ["liquid frac", "液相分数"],
        "file_artifact": ["file_path", ".xlsx", ".bkp", "file_name", "结果文件"],
    }

    matched = 0
    for key in requested:
        markers = signal_map.get(key, [])
        if any(marker in combined for marker in markers):
            matched += 1
    return matched / max(1, len(requested))


def _contains_any(text: str, markers: Sequence[str]) -> bool:
    return any(marker in text for marker in markers)


def infer_task_validator_profile(user_message: str, *, mode: str) -> Dict[str, Any]:
    text = str(user_message or "").lower()
    requested = infer_requested_outputs(user_message)

    change_markers = [
        "modify", "change", "set ", "update", "adjust",
        "\u4fee\u6539", "\u8c03\u6574", "\u8bbe\u4e3a", "\u66f4\u6539",
    ]
    query_markers = [
        "query", "show", "check", "report", "list",
        "\u67e5\u8be2", "\u67e5\u770b", "\u83b7\u53d6", "\u8f93\u51fa",
    ]
    calc_markers = [
        "calculate", "compute", "solve",
        "\u8ba1\u7b97", "\u6c42\u89e3", "\u8ba1\u7b97\u51fa",
    ]
    separation_markers = [
        "separate", "separator", "flash", "distill", "radfrac", "dstwu",
        "\u5206\u79bb", "\u5206\u79bb\u5668", "\u95ea\u84b8", "\u7cbe\u998f", "\u5854\u9876", "\u5854\u5e95",
    ]
    mixing_markers = [
        "mix", "mixer",
        "\u6df7\u5408", "\u6df7\u5408\u5668",
    ]
    heat_markers = [
        "heat", "heater", "cooler", "heatx",
        "\u52a0\u70ed", "\u6362\u70ed", "\u51b7\u5374", "\u6362\u70ed\u5668",
    ]
    pressure_markers = [
        "pump", "compressor", "valve", "pressure drop", "discharge pressure",
        "\u6cf5", "\u538b\u7f29\u673a", "\u9600", "\u51fa\u53e3\u538b\u529b", "\u538b\u964d",
    ]
    process_markers = [
        "process", "flowsheet", "full plant",
        "\u6d41\u7a0b", "\u5168\u6d41\u7a0b", "\u6574\u4e2a\u6d41\u7a0b",
    ]

    families: List[str] = []
    if _contains_any(text, separation_markers):
        families.append("separation")
    if _contains_any(text, mixing_markers):
        families.append("mixing")
    if _contains_any(text, heat_markers):
        families.append("heat_exchange")
    asks_change = _contains_any(text, change_markers)
    asks_query = _contains_any(text, query_markers)
    asks_calculation = _contains_any(text, calc_markers) or bool(requested)
    query_only = asks_query and not asks_change and not _contains_any(text, calc_markers)
    if asks_change and _contains_any(text, pressure_markers):
        families.append("pressure_adjustment")
    if mode == "process" or _contains_any(text, process_markers):
        families.append("process")
    expects_simulation = mode == "process" or asks_change or (asks_calculation and not query_only) or (bool(families) and not query_only)
    expects_result = bool(requested) or asks_query or asks_calculation or mode == "process"
    task_templates: List[str] = []
    if mode == "process":
        task_templates.append("process_execution")
    if asks_change:
        task_templates.append("parameter_change")
    if query_only:
        task_templates.append("result_query")
    elif asks_calculation or bool(families):
        task_templates.append("unit_calculation")

    return {
        "mode": mode,
        "families": families,
        "task_templates": task_templates,
        "asks_change": asks_change,
        "asks_query": asks_query,
        "asks_calculation": asks_calculation,
        "query_only": query_only,
        "expects_simulation": expects_simulation,
        "expects_result": expects_result,
        "requested_outputs": sorted(requested),
    }


def calculate_task_specific_validation(
    *,
    profile: Dict[str, Any],
    metrics: Dict[str, int],
    requested_output_coverage: Optional[float],
    has_output_marker: bool,
    user_message: str,
) -> Dict[str, Any]:
    mode = str(profile.get("mode", "unit") or "unit")
    task_templates = set(profile.get("task_templates") or [])
    run_success = int(metrics.get("run_simulation_success", 0) or 0)
    get_result_success = int(metrics.get("get_result_success", 0) or 0)
    rounds_completed = int(metrics.get("rounds_completed", 0) or 0)
    validators: Dict[str, float] = {}

    if bool(profile.get("expects_simulation")):
        validators["simulation_execution"] = 1.0 if run_success > 0 else 0.0

    if bool(profile.get("expects_result")):
        if get_result_success > 0:
            validators["result_retrieval"] = 1.0
        elif run_success > 0 and has_output_marker:
            validators["result_retrieval"] = 0.45
        else:
            validators["result_retrieval"] = 0.0

    if "result_query" in task_templates:
        if get_result_success > 0:
            validators["query_result_delivery"] = 1.0
        elif has_output_marker:
            validators["query_result_delivery"] = 0.4
        else:
            validators["query_result_delivery"] = 0.0

    if "parameter_change" in task_templates:
        if run_success > 0 and get_result_success > 0:
            validators["change_closed_loop"] = 1.0
        elif run_success > 0:
            validators["change_closed_loop"] = 0.7
        else:
            validators["change_closed_loop"] = 0.0

    if mode == "process":
        expected = max(1, infer_expected_process_rounds(user_message))
        validators["process_round_completion"] = min(1.0, rounds_completed / expected)

    families = set(profile.get("families") or [])
    if "separation" in families:
        coverage = requested_output_coverage if requested_output_coverage is not None else (-1.0)
        if get_result_success > 0 and coverage >= 0.6:
            validators["separation_delivery"] = 1.0
        elif get_result_success > 0:
            validators["separation_delivery"] = 0.75
        elif run_success > 0 and has_output_marker:
            validators["separation_delivery"] = 0.35
        else:
            validators["separation_delivery"] = 0.0
    if "mixing" in families:
        coverage = requested_output_coverage if requested_output_coverage is not None else (-1.0)
        if get_result_success > 0 and coverage >= 0.6:
            validators["mixing_delivery"] = 1.0
        elif get_result_success > 0:
            validators["mixing_delivery"] = 0.75
        elif run_success > 0 and has_output_marker:
            validators["mixing_delivery"] = 0.35
        else:
            validators["mixing_delivery"] = 0.0
    if "heat_exchange" in families:
        requested = set(profile.get("requested_outputs") or [])
        expects_temp = "temperature" in requested or not requested
        if get_result_success > 0 and (not expects_temp or (requested_output_coverage is not None and requested_output_coverage >= 0.5)):
            validators["heat_exchange_delivery"] = 1.0
        elif get_result_success > 0:
            validators["heat_exchange_delivery"] = 0.7
        elif run_success > 0:
            validators["heat_exchange_delivery"] = 0.3
        else:
            validators["heat_exchange_delivery"] = 0.0
    if "pressure_adjustment" in families:
        requested = set(profile.get("requested_outputs") or [])
        expects_pressure = "pressure" in requested or bool(profile.get("asks_change"))
        if run_success > 0 and get_result_success > 0 and (not expects_pressure or (requested_output_coverage is not None and requested_output_coverage >= 0.5)):
            validators["pressure_change_verification"] = 1.0
        elif run_success > 0 and get_result_success > 0:
            validators["pressure_change_verification"] = 0.7
        elif run_success > 0:
            validators["pressure_change_verification"] = 0.4
        else:
            validators["pressure_change_verification"] = 0.0
    if "unit_calculation" in task_templates and not families.intersection({"separation", "mixing", "heat_exchange", "pressure_adjustment"}) and mode == "unit":
        coverage = requested_output_coverage if requested_output_coverage is not None else (-1.0)
        if get_result_success > 0 and coverage >= 0.5:
            validators["unit_result_delivery"] = 1.0
        elif get_result_success > 0:
            validators["unit_result_delivery"] = 0.75
        elif run_success > 0 and has_output_marker:
            validators["unit_result_delivery"] = 0.35
        else:
            validators["unit_result_delivery"] = 0.0

    if not validators:
        return {"score": 0.0, "validators": {}}
    score = sum(validators.values()) / len(validators)
    return {
        "score": min(1.0, max(0.0, score)),
        "validators": {k: round(v, 4) for k, v in validators.items()},
    }


def calculate_reward_v1(
    response_content: str,
    tool_call_count: int,
    file_download_count: int,
    *,
    task_type: str = "unknown",
    simulation_metrics: Optional[Dict[str, int]] = None,
    user_message: str = "",
    infer_task_type_fn: Callable[[str], str],
) -> Dict[str, float]:
    del tool_call_count
    text = (response_content or "").lower()
    metrics = dict(simulation_metrics or {})
    run_calls = int(metrics.get("run_simulation_calls", 0) or 0)
    run_success = int(metrics.get("run_simulation_success", 0) or 0)
    run_fail_total = int(metrics.get("run_simulation_fail_total", 0) or 0)
    run_fail_config = int(metrics.get("run_simulation_fail_config", 0) or 0)
    run_fail_runtime = int(metrics.get("run_simulation_fail_runtime", 0) or 0)
    run_fail_unknown = int(metrics.get("run_simulation_fail_unknown", 0) or 0)
    get_schema_calls = int(metrics.get("get_schema_calls", 0) or 0)
    get_result_success = int(metrics.get("get_result_success", 0) or 0)
    rounds_completed = int(metrics.get("rounds_completed", 0) or 0)

    mode = _resolve_task_mode(task_type, user_message, response_content, infer_task_type_fn)
    has_output_marker = _has_output_marker(text, file_download_count)

    if mode == "unit":
        completion = 1.0 if (run_success >= 1 and get_result_success >= 1) else (0.7 if run_success >= 1 else (0.25 if has_output_marker else 0.1))
        retry_count = max(0, run_calls - 1)
        efficiency = exp_decay(retry_count, 0.35)
        recovery = 1.0 if (run_fail_total > 0 and run_success > 0) else 0.0
        pipeline = (0.5 if get_schema_calls >= 1 else 0.0) + (0.5 if get_result_success >= 1 else 0.0)
        penalty = run_fail_config * 0.10 + run_fail_runtime * 0.05 + run_fail_unknown * 0.03
        reward = completion * 0.55 + efficiency * 0.20 + recovery * 0.15 + pipeline * 0.10 - penalty
    else:
        expected_rounds = infer_expected_process_rounds(user_message)
        completion = 1.0 if rounds_completed >= expected_rounds else (0.75 if rounds_completed >= 1 else (0.3 if run_success > 0 else 0.1))
        progress = min(1.0, rounds_completed / max(1, expected_rounds))
        overhead = max(0, run_calls - max(1, rounds_completed))
        efficiency = exp_decay(overhead, 0.18)
        recovery = min(1.0, run_success / max(1, run_fail_total)) if run_fail_total > 0 else (1.0 if run_success > 0 else 0.0)
        pipeline = (0.4 if get_schema_calls >= 1 else 0.0) + (0.6 if get_result_success >= max(1, rounds_completed) else 0.0)
        penalty = run_fail_config * 0.12 + run_fail_runtime * 0.06 + run_fail_unknown * 0.04
        reward = completion * 0.45 + progress * 0.20 + efficiency * 0.20 + recovery * 0.10 + pipeline * 0.05 - penalty

    reward = max(0.0, min(reward, 1.0))
    return {
        "reward": round(reward, 4),
        "task_mode": mode,
        "task_completion": round(completion, 4),
        "tool_efficiency": round(efficiency, 4),
        "response_quality": round(pipeline, 4),
        "pipeline_quality": round(pipeline, 4),
        "reward_version": "v1",
        "run_simulation_calls": run_calls,
        "run_simulation_success": run_success,
        "run_simulation_fail_total": run_fail_total,
        "run_simulation_fail_config": run_fail_config,
        "run_simulation_fail_runtime": run_fail_runtime,
        "run_simulation_fail_unknown": run_fail_unknown,
        "get_schema_calls": get_schema_calls,
        "get_result_success": get_result_success,
        "rounds_completed": rounds_completed,
    }


def calculate_result_accuracy_score(
    *,
    mode: str,
    metrics: Dict[str, int],
    user_message: str,
    has_output_marker: bool,
    response_content: str,
    spans: Sequence[Dict[str, Any]],
    file_download_count: int,
) -> Dict[str, float]:
    run_success = int(metrics.get("run_simulation_success", 0) or 0)
    get_result_success = int(metrics.get("get_result_success", 0) or 0)
    rounds_completed = int(metrics.get("rounds_completed", 0) or 0)
    validator_profile = infer_task_validator_profile(user_message, mode=mode)
    requested_output_coverage = calculate_requested_output_coverage(
        user_message=user_message,
        response_content=response_content,
        spans=spans,
        file_download_count=file_download_count,
    )
    if mode == "unit":
        if run_success >= 1 and get_result_success >= 1:
            base_score = 1.0
        elif get_result_success >= 1:
            base_score = 0.85
        elif run_success >= 1 and has_output_marker:
            base_score = 0.65
        elif has_output_marker:
            base_score = 0.3
        else:
            base_score = 0.0
    else:
        expected_rounds = infer_expected_process_rounds(user_message)
        round_ratio = min(1.0, rounds_completed / max(1, expected_rounds))
        result_ratio = min(1.0, get_result_success / max(1, expected_rounds))
        base_score = round_ratio * 0.55 + result_ratio * 0.45
        if has_output_marker:
            base_score = max(base_score, 0.25)

    task_specific = calculate_task_specific_validation(
        profile=validator_profile,
        metrics=metrics,
        requested_output_coverage=requested_output_coverage,
        has_output_marker=has_output_marker,
        user_message=user_message,
    )
    task_specific_score = float(task_specific.get("score", 0.0) or 0.0)
    if requested_output_coverage is None:
        final_score = min(1.0, base_score * 0.7 + task_specific_score * 0.3)
    else:
        coverage_weight = 0.40 if get_result_success > 0 else 0.20
        task_weight = 0.20 if get_result_success > 0 else 0.30
        base_weight = max(0.0, 1.0 - coverage_weight - task_weight)
        final_score = min(
            1.0,
            base_score * base_weight + requested_output_coverage * coverage_weight + task_specific_score * task_weight,
        )
    return {
        "score": final_score,
        "base_score": min(1.0, base_score),
        "requested_output_coverage": round(requested_output_coverage if requested_output_coverage is not None else -1.0, 4),
        "task_specific_score": round(task_specific_score, 4),
        "validator_profile": validator_profile,
        "validator_scores": dict(task_specific.get("validators", {}) or {}),
    }


def extract_failure_categories(spans: Sequence[Dict[str, Any]]) -> List[str]:
    categories: List[str] = []
    for span in spans:
        name = str(span.get("name") or "")
        attrs = span.get("attributes", {})
        if name == "tool_execution":
            results = attrs.get("tool_results")
            if isinstance(results, list):
                for item in results:
                    if not isinstance(item, dict):
                        continue
                    category = str(item.get("failure_category") or "").strip()
                    if category:
                        categories.append(category)
        elif name in {"error", "reward"}:
            value = attrs.get("failure_categories")
            if isinstance(value, list):
                for item in value:
                    category = str(item or "").strip()
                    if category:
                        categories.append(category)
            single = str(attrs.get("failure_category") or "").strip()
            if single:
                categories.append(single)
    deduped: List[str] = []
    seen = set()
    for item in categories:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def calculate_failure_penalty(failure_categories: Sequence[str]) -> Dict[str, Any]:
    penalties = {
        "simulation_config_error": 0.18,
        "simulation_runtime_error": 0.12,
        "simulation_timeout": 0.16,
        "simulation_connection_error": 0.15,
        "simulation_remote_error": 0.14,
        "simulation_unknown_error": 0.10,
        "result_remote_error": 0.10,
        "result_timeout": 0.08,
        "result_connection_error": 0.08,
        "result_format_error": 0.06,
        "result_fetch_error": 0.06,
        "schema_timeout": 0.06,
        "schema_connection_error": 0.06,
        "schema_generation_error": 0.05,
        "memory_tool_error": 0.03,
    }
    categories = [str(x or "").strip() for x in failure_categories if str(x or "").strip()]
    if not categories:
        return {"penalty": 0.0, "dominant_failure_category": "", "failure_categories": []}
    weighted = [(penalties.get(cat, 0.04), cat) for cat in categories]
    weighted.sort(reverse=True)
    dominant_penalty, dominant_category = weighted[0]
    total_penalty = sum(val for val, _ in weighted[:3])
    total_penalty = min(0.25, total_penalty)
    return {
        "penalty": round(total_penalty, 4),
        "dominant_failure_category": dominant_category,
        "failure_categories": categories,
        "dominant_failure_penalty": round(dominant_penalty, 4),
    }


def calculate_memory_utilization_score(
    *,
    memory_hit_count: int,
    memory_usage_count: int,
    base_reward: float,
    get_result_success: int,
) -> float:
    if memory_hit_count <= 0:
        return 0.0
    if memory_usage_count <= 0:
        return 0.2
    if get_result_success > 0 and base_reward >= 0.75:
        return 1.0
    if base_reward >= 0.5:
        return 0.75
    if base_reward >= 0.25:
        return 0.5
    return 0.3


def calculate_reward_v2(
    response_content: str,
    tool_call_count: int,
    file_download_count: int,
    *,
    task_type: str = "unknown",
    simulation_metrics: Optional[Dict[str, int]] = None,
    user_message: str = "",
    infer_task_type_fn: Callable[[str], str],
    elapsed_seconds: float = 0.0,
    memory_hit_count: int = 0,
    memory_usage_count: int = 0,
    spans: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, float]:
    base_info = calculate_reward_v1(
        response_content,
        tool_call_count,
        file_download_count,
        task_type=task_type,
        simulation_metrics=simulation_metrics,
        user_message=user_message,
        infer_task_type_fn=infer_task_type_fn,
    )
    metrics = dict(simulation_metrics or {})
    mode = str(base_info.get("task_mode", "unit") or "unit")
    has_output_marker = _has_output_marker((response_content or "").lower(), file_download_count)
    result_accuracy_info = calculate_result_accuracy_score(
        mode=mode,
        metrics=metrics,
        user_message=user_message,
        has_output_marker=has_output_marker,
        response_content=response_content,
        spans=list(spans or []),
        file_download_count=file_download_count,
    )
    result_accuracy = float(result_accuracy_info.get("score", 0.0) or 0.0)
    time_alpha = 0.012 if mode == "process" else 0.018
    time_efficiency = exp_decay(elapsed_seconds, time_alpha)
    memory_utilization = calculate_memory_utilization_score(
        memory_hit_count=memory_hit_count,
        memory_usage_count=memory_usage_count,
        base_reward=float(base_info.get("reward", 0.0) or 0.0),
        get_result_success=int(metrics.get("get_result_success", 0) or 0),
    )

    failure_info = calculate_failure_penalty(extract_failure_categories(list(spans or [])))
    failure_penalty = float(failure_info.get("penalty", 0.0) or 0.0)

    base_reward = float(base_info.get("reward", 0.0) or 0.0)
    final_reward = base_reward * 0.70 + result_accuracy * 0.15 + time_efficiency * 0.10 + memory_utilization * 0.05 - failure_penalty
    final_reward = max(0.0, min(final_reward, 1.0))

    result = dict(base_info)
    result.update(
        {
            "reward": round(final_reward, 4),
            "reward_version": "v2",
            "base_reward": round(base_reward, 4),
            "result_accuracy": round(result_accuracy, 4),
            "result_accuracy_base": round(float(result_accuracy_info.get("base_score", 0.0) or 0.0), 4),
            "requested_output_coverage": round(float(result_accuracy_info.get("requested_output_coverage", -1.0) or -1.0), 4),
            "task_specific_score": round(float(result_accuracy_info.get("task_specific_score", 0.0) or 0.0), 4),
            "validator_profile": dict(result_accuracy_info.get("validator_profile", {}) or {}),
            "validator_scores": dict(result_accuracy_info.get("validator_scores", {}) or {}),
            "time_efficiency": round(time_efficiency, 4),
            "memory_utilization": round(memory_utilization, 4),
            "failure_penalty": round(failure_penalty, 4),
            "dominant_failure_category": str(failure_info.get("dominant_failure_category", "") or ""),
            "dominant_failure_penalty": round(float(failure_info.get("dominant_failure_penalty", 0.0) or 0.0), 4),
            "failure_categories": list(failure_info.get("failure_categories", []) or []),
            "elapsed_seconds": round(max(0.0, float(elapsed_seconds or 0.0)), 4),
            "memory_hit_count": int(memory_hit_count or 0),
            "memory_usage_count": int(memory_usage_count or 0),
            "response_quality": round(result_accuracy, 4),
        }
    )
    return result


def calculate_reward(
    response_content: str,
    tool_call_count: int,
    file_download_count: int,
    *,
    task_type: str = "unknown",
    simulation_metrics: Optional[Dict[str, int]] = None,
    user_message: str = "",
    infer_task_type_fn: Callable[[str], str],
    elapsed_seconds: float = 0.0,
    memory_hit_count: int = 0,
    memory_usage_count: int = 0,
    reward_version: Optional[str] = None,
    spans: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, float]:
    version = str(reward_version or os.getenv("REWARD_VERSION", "v2") or "v2").strip().lower()
    if version == "v1":
        return calculate_reward_v1(
            response_content,
            tool_call_count,
            file_download_count,
            task_type=task_type,
            simulation_metrics=simulation_metrics,
            user_message=user_message,
            infer_task_type_fn=infer_task_type_fn,
        )
    return calculate_reward_v2(
        response_content,
        tool_call_count,
        file_download_count,
        task_type=task_type,
        simulation_metrics=simulation_metrics,
        user_message=user_message,
        infer_task_type_fn=infer_task_type_fn,
        elapsed_seconds=elapsed_seconds,
        memory_hit_count=memory_hit_count,
        memory_usage_count=memory_usage_count,
        spans=spans,
    )
