"""
Online comparison testing for trained prompts.
This module runs comparison tests when mode='online'.
"""

import asyncio
import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


def run_online_comparison(
    *,
    db_path: Path,
    rollouts: List[Dict[str, Any]],
    new_prompts: Dict[str, str],
    prompt_dir: Path,
    backend_url: str = "http://192.168.3.202:38843",
) -> Dict[str, Any]:
    """
    Run comparison test: re-execute tasks with new prompts and compare results.

    IMPORTANT: Memory system is disabled during comparison to ensure fair testing.

    Returns comparison report with:
    - tasks_tested
    - comparison (success_rate, avg_tool_calls, error_distribution)
    - task_details (per-task comparison)
    - memory_disabled: True
    """

    # Extract tasks from rollouts
    tasks = []
    old_results = {}
    for rollout in rollouts:
        task_msg = rollout.get("input", {}).get("user_requirement") or rollout.get("metadata", {}).get("user_message") or ""
        if not task_msg:
            continue
        tasks.append({"msg": task_msg})

        # Extract old results from rollout
        old_results[task_msg] = _extract_rollout_metrics(rollout, db_path)

    if not tasks:
        return {
            "tasks_tested": 0,
            "comparison": {},
            "task_details": [],
            "note": "No tasks to test",
            "memory_disabled": True,
        }

    # Limit tasks for comparison (avoid too long execution)
    max_comparison_tasks = 10
    if len(tasks) > max_comparison_tasks:
        print(f"Limiting comparison to first {max_comparison_tasks} tasks (total: {len(tasks)})")
        tasks = tasks[:max_comparison_tasks]
        # Also limit old_results
        old_results = {task["msg"]: old_results[task["msg"]] for task in tasks if task["msg"] in old_results}

    # Temporarily write new prompts to a test directory
    test_prompt_dir = prompt_dir.parent / "prompt_test_temp"
    test_prompt_dir.mkdir(exist_ok=True)

    try:
        # Write new prompts
        (test_prompt_dir / "llm_prompt.py").write_text(
            new_prompts.get("system_prompt_candidate", ""), encoding="utf-8"
        )
        (test_prompt_dir / "schema_check.py").write_text(
            new_prompts.get("schema_check_prompt_candidate", ""), encoding="utf-8"
        )
        (test_prompt_dir / "thought_process.py").write_text(
            new_prompts.get("thought_process_prompt_candidate", ""), encoding="utf-8"
        )

        # Execute tasks with new prompts using asyncio
        print(f"Executing {len(tasks)} tasks with new prompts (memory disabled)...")
        new_results = asyncio.run(_execute_tasks_with_new_prompts_async(
            tasks=tasks,
            test_prompt_dir=test_prompt_dir,
            db_path=db_path,
            backend_url=backend_url,
        ))

        # Compare results
        comparison_report = _build_comparison_report(tasks, old_results, new_results)
        comparison_report["memory_disabled"] = True
        comparison_report["comparison_note"] = "对比测试时已禁用经验系统，纯粹测试新提示词效果"

        return comparison_report

    finally:
        # Cleanup test directory
        import shutil
        if test_prompt_dir.exists():
            shutil.rmtree(test_prompt_dir)


def _extract_rollout_metrics(rollout: Dict[str, Any], db_path: Path) -> Dict[str, Any]:
    """Extract metrics from a rollout."""
    rollout_id = rollout.get("rollout_id")
    status = rollout.get("status", "unknown")

    # Query spans to get tool call count
    tool_calls = 0
    error_type = None

    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        # Count tool execution spans
        rows = conn.execute(
            "SELECT COUNT(*) as cnt FROM spans WHERE rollout_id = ? AND name = 'tool_execution'",
            (rollout_id,)
        ).fetchone()
        if rows:
            tool_calls = rows["cnt"]

        # Get error type if failed
        if status == "failed":
            error_row = conn.execute(
                "SELECT metadata_json FROM spans WHERE rollout_id = ? AND is_error = 1 LIMIT 1",
                (rollout_id,)
            ).fetchone()
            if error_row:
                try:
                    metadata = json.loads(error_row["metadata_json"] or "{}")
                    error_type = metadata.get("error_type", "unknown")
                except:
                    pass

        conn.close()
    except Exception as e:
        print(f"Warning: Failed to extract metrics for {rollout_id}: {e}")

    return {
        "status": status,
        "rollout_id": rollout_id,
        "tool_calls": tool_calls,
        "error_type": error_type,
    }


async def _execute_tasks_with_new_prompts_async(
    *,
    tasks: List[Dict],
    test_prompt_dir: Path,
    db_path: Path,
    backend_url: str = "http://192.168.3.202:38843",
) -> Dict[str, Dict]:
    """
    Execute tasks with new prompts via HTTP API.

    Calls the backend /api/chat/stream endpoint with disable_memory=True
    to ensure fair comparison without experience system interference.
    """
    import httpx

    results = {}

    for i, task in enumerate(tasks):
        task_msg = task["msg"]
        print(f"  [{i+1}/{len(tasks)}] Executing: {task_msg[:60]}...")

        try:
            session_id = f"comparison_test_{int(time.time())}_{i}"
            payload = {
                "message": task_msg,
                "session_id": session_id,
                "disable_memory": True,
            }

            rollout_id = None
            final_status = "unknown"

            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream(
                    "POST",
                    f"{backend_url}/api/chat/stream",
                    json=payload,
                ) as response:
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if not data_str:
                            continue
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        msg_type = data.get("type", "")
                        if msg_type == "rollout_started":
                            rollout_id = data.get("rollout_id")
                        elif msg_type == "stream_end":
                            break
                        status = data.get("status", "")
                        if status in ("succeeded", "failed"):
                            final_status = status

            if rollout_id:
                result = _extract_rollout_metrics(
                    {"rollout_id": rollout_id, "status": final_status}, db_path
                )
            else:
                result = {
                    "status": final_status,
                    "rollout_id": None,
                    "tool_calls": 0,
                    "error_type": "no_rollout_id",
                }

            results[task_msg] = result
            print(f"    Result: {result['status']}, tool_calls: {result['tool_calls']}")

        except Exception as e:
            print(f"    Error: {e}")
            import traceback
            traceback.print_exc()
            results[task_msg] = {
                "status": "failed",
                "tool_calls": 0,
                "error_type": "execution_error",
            }

    return results
def _build_comparison_report(
    tasks: List[Dict],
    old_results: Dict[str, Dict],
    new_results: Dict[str, Dict],
) -> Dict[str, Any]:
    """Build comparison report from old and new results."""

    task_details = []
    old_success = 0
    new_success = 0
    old_tool_calls = []
    new_tool_calls = []
    old_errors = {}
    new_errors = {}

    for task in tasks:
        task_msg = task["msg"]
        old = old_results.get(task_msg, {})
        new = new_results.get(task_msg, {})

        old_status = old.get("status", "unknown")
        new_status = new.get("status", "unknown")

        if old_status == "succeeded":
            old_success += 1
        if new_status == "succeeded":
            new_success += 1

        improvement = (old_status != "succeeded" and new_status == "succeeded")

        task_details.append({
            "task_msg": task_msg[:100] + "..." if len(task_msg) > 100 else task_msg,
            "old_status": old_status,
            "new_status": new_status,
            "improvement": improvement,
        })

        # Collect tool calls
        old_tool_calls.append(old.get("tool_calls", 0))
        new_tool_calls.append(new.get("tool_calls", 0))

        # Collect error types
        if old_status == "failed":
            err_type = old.get("error_type", "unknown")
            old_errors[err_type] = old_errors.get(err_type, 0) + 1
        if new_status == "failed":
            err_type = new.get("error_type", "unknown")
            new_errors[err_type] = new_errors.get(err_type, 0) + 1

    total = len(tasks)
    old_success_rate = old_success / total if total > 0 else 0
    new_success_rate = new_success / total if total > 0 else 0

    old_avg_tools = sum(old_tool_calls) / len(old_tool_calls) if old_tool_calls else 0
    new_avg_tools = sum(new_tool_calls) / len(new_tool_calls) if new_tool_calls else 0

    # Build error distribution comparison
    all_error_types = set(old_errors.keys()) | set(new_errors.keys())
    error_distribution = {}
    for err_type in all_error_types:
        error_distribution[err_type] = {
            "old": old_errors.get(err_type, 0),
            "new": new_errors.get(err_type, 0),
        }

    return {
        "tasks_tested": total,
        "comparison": {
            "success_rate": {
                "old": round(old_success_rate, 4),
                "new": round(new_success_rate, 4),
                "delta": round(new_success_rate - old_success_rate, 4),
            },
            "avg_tool_calls": {
                "old": round(old_avg_tools, 2),
                "new": round(new_avg_tools, 2),
                "delta": round(new_avg_tools - old_avg_tools, 2),
            },
            "error_distribution": error_distribution,
        },
        "task_details": task_details,
        "old_prompt_version": "current",
        "new_prompt_candidate": "trained",
    }
