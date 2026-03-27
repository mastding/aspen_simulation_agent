# -*- coding: utf-8 -*-
"""
Collect online trajectories from backend SSE endpoint (/api/chat/stream).

Features:
- Optional DB reset before collection (rollouts/spans clean).
- Task batch from JSON input or built-in fallback tasks.
- Per-task success/failure tracking and failure reason summary.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class TaskResult:
    index: int
    name: str
    status: str
    rollout_id: str
    start_time: float
    end_time: float
    duration_sec: float
    error: str
    file_download_count: int
    tool_call_count: int
    update_chars: int


def reset_db(db_path: Path) -> None:
    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM spans")
        cur.execute("DELETE FROM rollouts")
        conn.commit()
        try:
            cur.execute("VACUUM")
        except Exception:
            pass


def build_tasks() -> List[Dict[str, str]]:
    return [
        {
            "name": "sample_1",
            "message": "生成乙苯催化脱氢制苯乙烯的工艺流程，优先使用RStoic反应器。",
        }
    ]


def _extract_tasks_from_json_obj(obj: Any) -> List[Dict[str, str]]:
    tasks: List[Dict[str, str]] = []

    def append_item(item: Any, idx: int) -> None:
        if isinstance(item, str) and item.strip():
            tasks.append({"name": f"task_{idx}", "message": item.strip()})
            return
        if isinstance(item, dict):
            msg = str(item.get("msg") or item.get("message") or "").strip()
            if not msg:
                return
            name = str(item.get("name") or f"task_{idx}").strip() or f"task_{idx}"
            tasks.append({"name": name, "message": msg})

    if isinstance(obj, list):
        for i, item in enumerate(obj, start=1):
            append_item(item, i)
        return tasks

    if isinstance(obj, dict):
        if isinstance(obj.get("tasks"), list):
            for i, item in enumerate(obj["tasks"], start=1):
                append_item(item, i)
            return tasks
        if obj.get("msg") or obj.get("message"):
            append_item(obj, 1)
            return tasks
        i = 1
        for value in obj.values():
            append_item(value, i)
            i += 1
    return tasks


def load_tasks(tasks_file: str, tasks_json: str) -> List[Dict[str, str]]:
    if tasks_file:
        raw = Path(tasks_file).read_text(encoding="utf-8")
        parsed = json.loads(raw)
        tasks = _extract_tasks_from_json_obj(parsed)
        if tasks:
            return tasks
    if tasks_json:
        parsed = json.loads(tasks_json)
        tasks = _extract_tasks_from_json_obj(parsed)
        if tasks:
            return tasks
    return build_tasks()


def _iter_sse_events(api_base: str, session_id: str, message: str, timeout: float):
    url = api_base.rstrip("/") + "/api/chat/stream"
    payload = {"session_id": session_id, "message": message}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if not data_str:
                continue
            try:
                yield json.loads(data_str)
            except Exception:
                continue


def run_one_task_sse(api_base: str, idx: int, name: str, message: str, timeout: float) -> TaskResult:
    start = time.time()
    rollout_id = ""
    error = ""
    file_download_count = 0
    tool_call_count = 0
    update_chars = 0
    status = "failed"

    session_id = f"collect_{int(start)}_{idx}"

    for data in _iter_sse_events(api_base=api_base, session_id=session_id, message=message, timeout=timeout):
        t = str(data.get("type", ""))
        if t == "rollout_started":
            rollout_id = str(data.get("rollout_id", ""))
        elif t == "error":
            status = "failed"
            error = str(data.get("error_message") or data.get("error") or "unknown error")
            break
        elif t == "done":
            status = "succeeded" if str(data.get("status", "succeeded")) == "succeeded" else "failed"
            break
        elif t == "stopped":
            status = "failed"
            error = "stopped"
            break
        elif t == "file_download":
            fps = data.get("file_paths") or []
            if isinstance(fps, list):
                file_download_count += len(fps)
        elif data.get("status") == "tool_calling":
            calls = data.get("tool_calls") or []
            if isinstance(calls, list):
                tool_call_count += len(calls)
        elif "content" in data:
            update_chars += len(str(data.get("content", "")))

    end = time.time()
    return TaskResult(
        index=idx,
        name=name,
        status=status,
        rollout_id=rollout_id,
        start_time=start,
        end_time=end,
        duration_sec=round(end - start, 3),
        error=error,
        file_download_count=file_download_count,
        tool_call_count=tool_call_count,
        update_chars=update_chars,
    )


def collect(api_base: str, tasks: List[Dict[str, str]], timeout: float) -> List[TaskResult]:
    results: List[TaskResult] = []
    for i, task in enumerate(tasks, start=1):
        try:
            result = run_one_task_sse(api_base, i, task["name"], task["message"], timeout)
        except Exception as exc:
            now = time.time()
            result = TaskResult(
                index=i,
                name=task["name"],
                status="failed",
                rollout_id="",
                start_time=now,
                end_time=now,
                duration_sec=0.0,
                error=str(exc),
                file_download_count=0,
                tool_call_count=0,
                update_chars=0,
            )
        results.append(result)
        time.sleep(1.0)
    return results


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect online trajectories via SSE/HTTP")
    p.add_argument("--api-base", default="http://127.0.0.1:38843")
    p.add_argument("--db-path", default="/run/code/dinglei/aspen_simulation_n../data/training/aspen_trajectories.db")
    p.add_argument("--reset-db", action="store_true")
    p.add_argument("--max-tasks", type=int, default=10)
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--tasks-file", default="")
    p.add_argument("--tasks-json", default="")
    p.add_argument("--output-dir", default="/run/code/dinglei/aspen_simulation_new/backend/rl/outputs/online_collection")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.reset_db:
        reset_db(db_path)

    tasks = load_tasks(args.tasks_file, args.tasks_json)[: max(1, args.max_tasks)]
    started_at = time.time()
    results = collect(args.api_base, tasks, args.timeout)
    ended_at = time.time()

    succ = [r for r in results if r.status == "succeeded"]
    fail = [r for r in results if r.status != "succeeded"]
    summary = {
        "started_at": datetime.fromtimestamp(started_at).isoformat(timespec="seconds"),
        "ended_at": datetime.fromtimestamp(ended_at).isoformat(timespec="seconds"),
        "api_base": args.api_base,
        "db_path": str(db_path),
        "task_count": len(results),
        "succeeded": len(succ),
        "failed": len(fail),
        "failed_tasks": [{"index": r.index, "name": r.name, "error": r.error} for r in fail],
        "results": [asdict(r) for r in results],
    }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = output_dir / f"online_collection_{stamp}.json"
    out_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved: {out_file}")
    print(json.dumps({"succeeded": len(succ), "failed": len(fail)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
