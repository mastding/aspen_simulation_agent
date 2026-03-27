from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict

import requests
from fastapi import HTTPException


# Configuration file paths
CONFIG_DIR = Path("./config")
MODEL_CONFIG_FILE = CONFIG_DIR / "model_config.json"
SYSTEM_CONFIG_FILE = CONFIG_DIR / "system_config.json"


def ensure_config_dir():
    """Ensure config directory exists"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config(config_file: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    """Load configuration from file or return default"""
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_config(config_file: Path, config: Dict[str, Any]):
    """Save configuration to file"""
    ensure_config_dir()
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def _parse_int(value: Any, default: int, *, minimum: int | None = None, maximum: int | None = None, field_name: str = "") -> int:
    try:
        if value in (None, ""):
            parsed = int(default)
        else:
            parsed = int(value)
    except Exception:
        raise HTTPException(status_code=400, detail=f"{field_name or '数值字段'}格式不正确")
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def _parse_float(value: Any, default: float, *, minimum: float | None = None, maximum: float | None = None, field_name: str = "") -> float:
    try:
        if value in (None, ""):
            parsed = float(default)
        else:
            parsed = float(value)
    except Exception:
        raise HTTPException(status_code=400, detail=f"{field_name or '数值字段'}格式不正确")
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


# Model Configuration Handlers
async def get_model_config_handler() -> Dict[str, Any]:
    """Get model configuration - merge JSON config with env vars"""
    default_config = {
        "model_name": os.getenv("MODEL", "deepseek-chat"),
        "api_base": os.getenv("MODEL_API_URL", ""),
        "api_key": os.getenv("MODEL_API_KEY", ""),
        "temperature": 0.7,
        "max_tokens": 4096,
        "timeout": 120,
        "max_retries": 3
    }
    saved = load_config(MODEL_CONFIG_FILE, {})
    merged = {**default_config, **{k: v for k, v in saved.items() if v}}
    return merged


async def save_model_config_handler(*, config: Dict[str, Any]) -> Dict[str, str]:
    """Save model configuration"""
    try:
        save_config(MODEL_CONFIG_FILE, config)
        return {"status": "success", "message": "Model configuration saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save model config: {str(e)}")


async def test_model_config_handler(*, config: Dict[str, Any]) -> Dict[str, Any]:
    """Test model configuration against an OpenAI-compatible endpoint"""
    model_name = str(config.get("model_name") or "").strip()
    api_base = str(config.get("api_base") or "").strip().rstrip("/")
    api_key = str(config.get("api_key") or "").strip()
    timeout = _parse_int(config.get("timeout"), 30, minimum=5, maximum=600, field_name="超时")
    max_tokens = _parse_int(config.get("max_tokens"), 16, minimum=1, maximum=64, field_name="最大Token数")
    temperature = _parse_float(config.get("temperature"), 0.0, minimum=0.0, maximum=2.0, field_name="Temperature")

    if not model_name:
        raise HTTPException(status_code=400, detail="模型名称不能为空")
    if not api_base:
        raise HTTPException(status_code=400, detail="API端点不能为空")
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key不能为空")

    endpoint = f"{api_base}/chat/completions"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a connectivity test assistant."},
            {"role": "user", "content": "Reply with OK only."},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    started_at = time.time()
    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
        elapsed_ms = round((time.time() - started_at) * 1000, 2)
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"模型连接失败: {str(exc)}")

    response_text = response.text or ""
    if not response.ok:
        detail = response_text[:300] if response_text else response.reason
        raise HTTPException(
            status_code=502,
            detail=f"模型连接失败: HTTP {response.status_code} - {detail}",
        )

    try:
        data = response.json()
    except Exception:
        raise HTTPException(status_code=502, detail="模型连接失败: 返回结果不是合法JSON")

    message = ""
    try:
        choices = data.get("choices") or []
        if choices:
            message = str(((choices[0] or {}).get("message") or {}).get("content") or "").strip()
    except Exception:
        message = ""

    return {
        "status": "success",
        "message": "模型连接测试成功",
        "model": model_name,
        "endpoint": endpoint,
        "latency_ms": elapsed_ms,
        "reply_preview": message[:120],
    }


# System Configuration Handlers
async def get_system_config_handler() -> Dict[str, Any]:
    """Get system configuration"""
    default_config = {
        "aspen_service_url": os.getenv("ASPEN_SIMULATOR_URL", "https://119.3.160.243:7777"),
    }
    saved = load_config(SYSTEM_CONFIG_FILE, {})
    merged = {**default_config, **{k: v for k, v in saved.items() if v}}
    return merged


async def save_system_config_handler(*, config: Dict[str, Any]) -> Dict[str, str]:
    """Save system configuration"""
    try:
        save_config(SYSTEM_CONFIG_FILE, config)
        return {"status": "success", "message": "System configuration saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save system config: {str(e)}")


async def test_system_config_handler(*, config: Dict[str, Any]) -> Dict[str, Any]:
    """Test Aspen simulator service connectivity"""
    aspen_service_url = str(config.get("aspen_service_url") or "").strip().rstrip("/")
    timeout = _parse_int(config.get("timeout"), 15, minimum=3, maximum=60, field_name="超时")

    if not aspen_service_url:
        raise HTTPException(status_code=400, detail="Aspen服务地址不能为空")

    test_candidates = [
        ("base", aspen_service_url),
        ("docs", f"{aspen_service_url}/docs"),
        ("result_endpoint", f"{aspen_service_url}/get-aspen-result"),
    ]

    last_error = ""
    started_at = time.time()
    for probe_name, probe_url in test_candidates:
        try:
            response = requests.get(probe_url, timeout=timeout, verify=False)
            elapsed_ms = round((time.time() - started_at) * 1000, 2)
            if response.status_code < 500:
                return {
                    "status": "success",
                    "message": "Aspen服务连接测试成功",
                    "endpoint": probe_url,
                    "probe": probe_name,
                    "latency_ms": elapsed_ms,
                    "status_code": response.status_code,
                }
            last_error = f"HTTP {response.status_code}"
        except requests.RequestException as exc:
            last_error = str(exc)

    raise HTTPException(status_code=502, detail=f"Aspen服务连接失败: {last_error or '未收到有效响应'}")


# Service Restart Handler
async def restart_service_handler(*, logger) -> Dict[str, str]:
    """Restart the backend service"""
    try:
        logger.info("Service restart requested")

        host = os.getenv("HOST", "0.0.0.0")
        port = os.getenv("PORT", "8000")
        workdir = str(Path.cwd())
        python_executable = sys.executable
        entry_script = sys.argv[0] if sys.argv and sys.argv[0] else "backend/main.py"
        restart_log = str(Path("/tmp/aspen_backend_restart.log"))

        relaunch_cmd = (
            f"cd {shlex.quote(workdir)} && "
            f"sleep 2 && "
            f"HOST={shlex.quote(host)} PORT={shlex.quote(str(port))} "
            f"nohup {shlex.quote(python_executable)} {shlex.quote(entry_script)} "
            f">{shlex.quote(restart_log)} 2>&1 < /dev/null &"
        )

        subprocess.Popen(
            ["/bin/sh", "-lc", relaunch_cmd],
            cwd=workdir,
            env=os.environ.copy(),
            start_new_session=True,
        )

        def _terminate_current_process() -> None:
            time.sleep(1.0)
            logger.info("Stopping current backend process for restart")
            os.kill(os.getpid(), signal.SIGTERM)

        threading.Thread(target=_terminate_current_process, daemon=True).start()
        return {
            "status": "success",
            "message": "服务重启中，请等待约5-10秒后刷新页面。"
        }
    except Exception as e:
        logger.error(f"Failed to restart service: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to restart service: {str(e)}")
