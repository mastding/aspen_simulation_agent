from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class Settings:
    model: str
    model_api_key: str | None
    model_api_url: str | None
    base_dir: Path
    data_dir: Path
    memory_docs_dir: Path
    db_path: Path
    rl_dir: Path
    training_runs_dir: Path
    training_exports_dir: Path
    prompt_dir: Path
    schema_default_target: Path
    policy_mode: str
    policy_canary_ratio: float
    policy_file: Path
    prompt_version_mode: str
    prompt_canary_ratio: float
    prompt_version_file: Path
    max_text_file_size: int = 400_000
    # Model config
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 4096
    timeout: int = 120
    max_retries: int = 3


def load_json_config(config_file: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    """Load configuration from JSON file or return default"""
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def load_settings(base_dir: Path) -> Settings:
    data_dir = base_dir / "rl_data"
    memory_docs_dir = data_dir / "memory_docs"
    rl_dir = base_dir / "rl"
    training_runs_dir = rl_dir / "outputs" / "training_runs"

    # Load model config from JSON file
    config_dir = base_dir / "config"
    model_config_file = config_dir / "model_config.json"
    model_config = load_json_config(model_config_file, {})

    # Model settings: prioritize JSON config, fallback to env vars, then defaults
    model_name = model_config.get("model_name") or os.getenv("MODEL", "deepseek-chat")
    model_api_url = model_config.get("api_base") or os.getenv("MODEL_API_URL")
    model_api_key = model_config.get("api_key") or os.getenv("MODEL_API_KEY")

    return Settings(
        model=model_name,
        model_api_key=model_api_key,
        model_api_url=model_api_url,
        base_dir=base_dir,
        data_dir=data_dir,
        memory_docs_dir=memory_docs_dir,
        db_path=data_dir / "aspen_trajectories.db",
        rl_dir=rl_dir,
        training_runs_dir=training_runs_dir,
        training_exports_dir=rl_dir / "exports",
        prompt_dir=base_dir / "app" / "prompts",
        schema_default_target=training_runs_dir / "schema_descriptions_0211.json",
        policy_mode=os.getenv("POLICY_MODE", "off"),
        policy_canary_ratio=float(os.getenv("POLICY_CANARY_RATIO", "0.1") or 0.1),
        policy_file=rl_dir / "outputs" / "policy" / "policy_latest.json",
        prompt_version_mode=os.getenv("PROMPT_VERSION_MODE", "off"),
        prompt_canary_ratio=float(os.getenv("PROMPT_CANARY_RATIO", os.getenv("POLICY_CANARY_RATIO", "0.1")) or 0.1),
        prompt_version_file=rl_dir / "outputs" / "policy" / "prompt_version_latest.json",
        # Model parameters from JSON config
        temperature=float(model_config.get("temperature", 0.7)),
        max_tokens=int(model_config.get("max_tokens", 4096)),
        timeout=int(model_config.get("timeout", 120)),
        max_retries=int(model_config.get("max_retries", 3)),
    )
