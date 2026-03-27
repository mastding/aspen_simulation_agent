from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List


async def run_training_subprocess(*, job_id: str, mode: str, train_algo: str, apo_config: Dict[str, Any], deps: Dict[str, Any]) -> Dict[str, Any]:
    cmd = [
        deps["python_exec"],
        str(deps["script_path"]),
        "--db-path",
        str(deps["db_path"]),
        "--mode",
        mode,
        "--prompt-dir",
        str(deps["prompt_dir"]),
        "--schema-dir",
        str(deps["schema_dir"]),
        "--output-root",
        str(deps["training_runs_dir"]),
        "--tag",
        job_id.replace("rl-", ""),
        "--algo",
        train_algo,
    ]
    if train_algo == "apo":
        cmd.extend(
            [
                "--apo-iters",
                str(int(apo_config.get("iters", 4))),
                "--apo-sample-size",
                str(int(apo_config.get("sample_size", 6))),
                "--apo-exploration",
                str(float(apo_config.get("exploration", 0.35))),
            ]
        )
    await deps["append_log_fn"](job_id, "Start training: " + " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(deps["cwd"]),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    await deps["set_job_fn"](job_id, current_process_pid=proc.pid)
    stdout_lines: List[str] = []
    if proc.stdout is not None:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            stdout_lines.append(text)
            await deps["append_log_fn"](job_id, text)
    returncode = await proc.wait()
    await deps["set_job_fn"](job_id, current_process_pid=None)
    run_id = deps["extract_run_id_fn"](stdout_lines)
    return {"command": cmd, "returncode": returncode, "run_id": run_id, "algo": train_algo, "stdout_tail": stdout_lines[-80:]}


async def run_collection_subprocess(*, job_id: str, config: Dict[str, Any], deps: Dict[str, Any]) -> Dict[str, Any]:
    tasks = [str(x).strip() for x in config.get("tasks", []) if str(x).strip()]
    max_tasks = int(config.get("max_tasks", len(tasks)))
    if max_tasks <= 0:
        max_tasks = len(tasks)
    tasks = tasks[:max_tasks]
    api_host = str(config.get("collector_api_host") or deps["default_host"]).strip() or deps["default_host"]
    api_port = int(config.get("collector_api_port") or deps["default_port"])
    api_base = str(config.get("collector_api_base") or f"http://{api_host}:{api_port}").strip()
    timeout_sec = float(config.get("collect_timeout", 120.0))

    payload = {"tasks": [{"name": f"task_{i+1}", "msg": msg} for i, msg in enumerate(tasks)]}
    temp_dir: Path = deps["output_dir"]
    temp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False, dir=str(temp_dir)) as tf:
        json.dump(payload, tf, ensure_ascii=False)
        task_file = tf.name

    cmd = [
        deps["python_exec"],
        str(deps["script_path"]),
        "--api-base",
        api_base,
        "--db-path",
        str(deps["db_path"]),
        "--tasks-file",
        task_file,
        "--max-tasks",
        str(max_tasks),
        "--timeout",
        str(timeout_sec),
        "--output-dir",
        str(temp_dir),
    ]
    await deps["append_log_fn"](job_id, "Start collection(script_sse): " + " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(deps["cwd"]),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    await deps["set_job_fn"](job_id, current_process_pid=proc.pid)
    stdout_lines: List[str] = []
    if proc.stdout is not None:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            stdout_lines.append(text)
            await deps["append_log_fn"](job_id, text)
    returncode = await proc.wait()
    await deps["set_job_fn"](job_id, current_process_pid=None)
    summary_path = deps["extract_collection_file_fn"](stdout_lines)
    summary_obj: Dict[str, Any] = {}
    task_results: List[Dict[str, Any]] = []
    if summary_path and summary_path.exists():
        try:
            summary_obj = json.loads(summary_path.read_text(encoding="utf-8"))
            for item in summary_obj.get("results", []):
                if not isinstance(item, dict):
                    continue
                task_results.append(
                    {
                        "index": item.get("index"),
                        "message": "",
                        "rollout_id": item.get("rollout_id", ""),
                        "status": item.get("status", "unknown"),
                        "name": item.get("name", ""),
                        "error": item.get("error", ""),
                    }
                )
        except Exception as exc:
            await deps["append_log_fn"](job_id, f"parse collection summary failed: {exc}", "error")
    try:
        Path(task_file).unlink(missing_ok=True)
    except Exception:
        pass
    return {
        "command": cmd,
        "returncode": returncode,
        "summary_path": str(summary_path) if summary_path else "",
        "summary": summary_obj,
        "task_results": task_results,
        "stdout_tail": stdout_lines[-80:],
    }
