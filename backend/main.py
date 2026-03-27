"""
AutoGen Aspen backend with AgentLightning + SQLite persistence.

Goals:
- Keep original AutoGen agent/tool orchestration logic.
- Use AgentLightning framework primitives for online rollouts.
- Persist rollouts/spans to SQLite for cross-restart queryability.
"""

from __future__ import annotations

import io
import ntpath
import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from autogen_core import CancellationToken

from agentlightning import emit_annotation as _al_emit_annotation, emit_message as _al_emit_message, emit_reward as _al_emit_reward
from agentlightning.emitter.annotation import OperationContext
from agentlightning.store import InMemoryLightningStore

from app.prompts.llm_prompt import system_prompt

# Auth imports
from app.auth.auth_middleware import AuthMiddleware
from app.auth.auth_service import create_default_admin
from app.api.auth_handlers import router as auth_router, admin_router, init_auth_handlers
from app.api.session_handlers import router as session_router, init_session_handlers
from tools.get_result import get_result
from tools.get_schema import get_schema
from tools.run_simulation import run_simulation
from tools.download_aspen_file import download_aspen_file

from app.config.settings import load_settings
from app.utils.jsonx import json_dumps as _json_dumps_util, json_loads_or_default as _json_loads_or_default_util
from app.telemetry import repository as telemetry_repo
from app.memory import matching as memory_matching
from app.memory import extractors as memory_extractors
from app.memory import core_ops as memory_core_ops
from app.memory import pipeline_ops as memory_pipeline_ops
from app.memory import storage_ops as memory_storage_ops
from app.rl import reward as reward_engine
from app.training import artifacts as training_artifacts
from app.runtime import app_state
from app.runtime import state_ops
from app.runtime import state_endpoints
from app.runtime import text_utils
from app.runtime import memory_endpoints
from app.runtime import agent_runtime
from app.runtime import persistence_runtime
from app.runtime import assembly_public
from app.runtime import assembly_state
from app.runtime import assembly_rl
from app.runtime import assembly_api
from app.runtime import assembly_chat
from app.runtime import assembly_router
from app.runtime import wiring as runtime_wiring
from app.runtime import chat_wiring
from app.runtime import chat_endpoints
from app.runtime import api_endpoints
from app.runtime import public_endpoints
from app.runtime import execution_endpoints
from app.runtime import rl_pipeline_endpoints
from app.runtime import rl_wiring
from app.runtime import api_wiring
from app.runtime import router_wiring
from app.runtime import bootstrap as runtime_bootstrap
from app.runtime import emitter_utils
from app.api import handlers as api_handlers
from app.api import settings_handlers
from app.api import router_factory as api_router_factory
from app.services import rl_job_service, chat_stream_service, rl_worker_service, chat_execution_service, memory_api_service, training_process_service
from app.services import agent_factory
from app.services import chat_helpers
from app.services import prompt_version_service

load_dotenv()

# Ensure UTF-8 logs in mixed shell environments.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("app_with_rl.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

settings = load_settings(Path(__file__).resolve().parent)

MODEL = settings.model
MODEL_API_KEY = settings.model_api_key
MODEL_API_URL = settings.model_api_url
TEMPERATURE = settings.temperature
MAX_TOKENS = settings.max_tokens
TIMEOUT = settings.timeout
MAX_RETRIES = settings.max_retries

BASE_DIR = settings.base_dir
DATA_DIR = settings.data_dir
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DOCS_DIR = settings.memory_docs_dir
MEMORY_DOCS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = settings.db_path
RL_DIR = settings.rl_dir
TRAINING_RUNS_DIR = settings.training_runs_dir
TRAINING_EXPORTS_DIR = settings.training_exports_dir
PROMPT_DIR = settings.prompt_dir
SCHEMA_DEFAULT_TARGET = settings.schema_default_target
# REMOVED: POLICY_MODE = settings.policy_mode
# REMOVED: POLICY_CANARY_RATIO = settings.policy_canary_ratio
# REMOVED: POLICY_FILE = settings.policy_file
# REMOVED: POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
PROMPT_VERSION_MODE = settings.prompt_version_mode
PROMPT_CANARY_RATIO = settings.prompt_canary_ratio
PROMPT_VERSION_FILE = settings.prompt_version_file
PROMPT_VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
MAX_TEXT_FILE_SIZE = settings.max_text_file_size

# AgentLightning store for rollout/span lifecycle (runtime memory).
store = InMemoryLightningStore(thread_safe=True)

app = FastAPI(title="Aspen Simulation Backend (RL)", version="2.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_db_connect = persistence_runtime.build_db_connect_fn(telemetry_repo=telemetry_repo, db_path=DB_PATH)
_json_dumps = persistence_runtime.build_json_dumps_fn(json_dumps_util_fn=_json_dumps_util)
_json_loads_or_default = persistence_runtime.build_json_loads_or_default_fn(
    json_loads_or_default_util_fn=_json_loads_or_default_util
)

# Auth middleware and routes
_auth_deps = {
    "db_connect_fn": _db_connect,
    "jwt_secret": os.getenv("JWT_SECRET", "aspen-default-secret"),
    "jwt_algorithm": "HS256",
}
app.add_middleware(AuthMiddleware, deps=_auth_deps)
init_auth_handlers(_auth_deps)
init_session_handlers({"db_connect_fn": _db_connect})
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(session_router)



def _list_validated_dynamic_methods() -> list[str]:
    with _db_connect() as conn:
        rows = conn.execute(
            "SELECT normalized_value FROM dynamic_method_aliases WHERE status = 'validated' ORDER BY normalized_value"
        ).fetchall()
    return [str(r["normalized_value"] or "").strip().upper() for r in rows if str(r["normalized_value"] or "").strip()]


def _list_validated_dynamic_component_aliases() -> dict[str, str]:
    with _db_connect() as conn:
        rows = conn.execute(
            "SELECT raw_text, normalized_value FROM dynamic_component_aliases WHERE status = 'validated' ORDER BY raw_text"
        ).fetchall()
    return {
        str(r["raw_text"] or "").strip(): str(r["normalized_value"] or "").strip().upper()
        for r in rows
        if str(r["raw_text"] or "").strip() and str(r["normalized_value"] or "").strip()
    }


def _select_prompt_assignment(*, rollout_id: str, user_message: str, task_type: str, mode: str = PROMPT_VERSION_MODE) -> dict:
    runtime_mode = str(mode or "").strip().lower()
    if runtime_mode in {"", "off"}:
        runtime_mode = None
    return prompt_version_service.select_prompt_assignment(
        registry_path=PROMPT_VERSION_FILE,
        rollout_id=rollout_id,
        user_message=user_message,
        task_type=task_type,
        mode=runtime_mode,
        canary_ratio=PROMPT_CANARY_RATIO,
    )


def _build_effective_system_prompt(*, assignment: dict) -> str:
    # Read from module dynamically so prompt reloads (online training) take effect
    import backend.app.prompts.llm_prompt as _llm_mod
    current_prompt = getattr(_llm_mod, "system_prompt", system_prompt)
    return prompt_version_service.build_effective_system_prompt(
        base_system_prompt=current_prompt,
        assignment=assignment,
        training_runs_dir=TRAINING_RUNS_DIR,
    )






_search_memory_cases = memory_endpoints.build_search_memory_cases_fn(
    runtime_wiring=runtime_wiring,
    deps_builder_fn=lambda: {
        "db_connect_fn": _db_connect,
        "normalize_text_fn": text_utils.normalize_text,
        "extract_match_fields_fn": memory_matching.extract_match_fields,
        "match_required_fields_fn": memory_matching.match_required_fields,
        "json_loads_or_default_fn": _json_loads_or_default,
        "infer_task_type_fn": text_utils.infer_task_type,
        "build_semantic_profile_fn": runtime_wiring.build_semantic_profile,
        "score_semantic_similarity_fn": runtime_wiring.score_semantic_similarity,
        "list_validated_dynamic_methods_fn": _list_validated_dynamic_methods,
        "list_validated_dynamic_component_aliases_fn": _list_validated_dynamic_component_aliases,
    },
)


persistence_runtime.init_sqlite(
    telemetry_repo=telemetry_repo,
    db_path=DB_PATH,
    json_dumps_fn=_json_dumps,
)
create_default_admin(deps=_auth_deps)
try:
    memory_storage_ops.backfill_memory_documents(
        limit=2000,
        deps={
            "db_connect_fn": _db_connect,
            "json_dumps_fn": _json_dumps,
            "json_loads_or_default_fn": _json_loads_or_default,
            "normalize_text_fn": text_utils.normalize_text,
            "memory_docs_dir": MEMORY_DOCS_DIR,
        },
    )
except Exception as exc:
    logger.warning("memory backfill skipped: %s", exc)


runtime_state = app_state.RuntimeState()


memory_search_experience = memory_endpoints.build_memory_search_experience_tool_endpoint(
    memory_api_service=memory_api_service,
    search_memory_cases_fn=_search_memory_cases,
    safe_str_fn=text_utils.safe_str,
    json_dumps_fn=_json_dumps,
)

memory_get_experience = memory_endpoints.build_memory_get_experience_tool_endpoint(
    memory_api_service=memory_api_service,
    deps_builder_fn=lambda: {
        "db_connect_fn": _db_connect,
        "json_loads_or_default_fn": _json_loads_or_default,
        "json_dumps_fn": _json_dumps,
        "safe_str_fn": text_utils.safe_str,
        "memory_docs_dir": MEMORY_DOCS_DIR,
        "list_validated_dynamic_methods_fn": _list_validated_dynamic_methods,
        "list_validated_dynamic_component_aliases_fn": _list_validated_dynamic_component_aliases,
    },
)


get_agent = agent_runtime.build_get_agent_fn(
    runtime_state=runtime_state,
    create_model_client_fn=agent_factory.create_model_client,
    create_assistant_agent_fn=agent_factory.create_assistant_agent,
    model_api_key=MODEL_API_KEY,
    model_api_url=MODEL_API_URL,
    model=MODEL,
    system_prompt=system_prompt,
    tools=[memory_search_experience, memory_get_experience, get_schema, run_simulation, get_result],
    safe_operation_context_fn=lambda name, attrs: emitter_utils.safe_operation_context(
        name, attrs, OperationContextCls=OperationContext, logger=logger
    ),
    logger=logger,
    temperature=TEMPERATURE,
    max_tokens=MAX_TOKENS,
    timeout=TIMEOUT,
    max_retries=MAX_RETRIES,
)


_build_resume_prompt = memory_endpoints.build_resume_prompt_fn(
    runtime_wiring=runtime_wiring,
    deps_builder_fn=lambda: {
        "db_connect_fn": _db_connect,
        "json_loads_or_default_fn": _json_loads_or_default,
        "query_spans_sqlite_fn": lambda rid: telemetry_repo.query_spans(
            db_path=DB_PATH,
            json_loads_or_default=_json_loads_or_default,
            rollout_id=rid,
        ),
        "extract_config_snippet_from_spans_fn": lambda spans: memory_extractors.extract_config_snippet_from_spans(
            spans, safe_str_fn=text_utils.safe_str
        ),
        "extract_strategy_from_spans_fn": lambda spans: memory_extractors.extract_strategy_from_spans(
            spans, safe_str_fn=text_utils.safe_str
        ),
        "extract_pitfalls_from_spans_fn": lambda spans: memory_extractors.extract_pitfalls_from_spans(
            spans, safe_str_fn=text_utils.safe_str
        ),
        "extract_reward_and_tool_count_fn": memory_extractors.extract_reward_and_tool_count,
        "safe_str_fn": text_utils.safe_str,
    },
)

_build_memory_from_rollouts = memory_endpoints.build_memory_from_rollouts_fn(
    runtime_wiring=runtime_wiring,
    deps_builder_fn=lambda: {
        "db_connect_fn": _db_connect,
        "json_loads_or_default_fn": _json_loads_or_default,
        "query_spans_sqlite_fn": lambda rid: telemetry_repo.query_spans(
            db_path=DB_PATH,
            json_loads_or_default=_json_loads_or_default,
            rollout_id=rid,
        ),
        "extract_reward_and_tool_count_fn": memory_extractors.extract_reward_and_tool_count,
        "infer_task_type_fn": text_utils.infer_task_type,
        "extract_strategy_from_spans_fn": lambda spans: memory_extractors.extract_strategy_from_spans(
            spans, safe_str_fn=text_utils.safe_str
        ),
        "extract_config_snippet_from_spans_fn": lambda spans: memory_extractors.extract_config_snippet_from_spans(
            spans, safe_str_fn=text_utils.safe_str
        ),
        "extract_pitfall_details_from_spans_fn": lambda spans: memory_extractors.extract_pitfall_details_from_spans(
            spans, safe_str_fn=text_utils.safe_str
        ),
        "extract_pitfalls_from_spans_fn": lambda spans: memory_extractors.extract_pitfalls_from_spans(
            spans, safe_str_fn=text_utils.safe_str
        ),
        "json_dumps_fn": _json_dumps,
        "normalize_text_fn": text_utils.normalize_text,
        "memory_docs_dir": MEMORY_DOCS_DIR,
    },
)

_build_memory_context_for_task = memory_endpoints.build_memory_context_for_task_fn(
    runtime_wiring=runtime_wiring,
    deps_builder_fn=lambda: {
        "infer_task_type_fn": text_utils.infer_task_type,
        "search_memory_cases_fn": _search_memory_cases,
        "safe_str_fn": text_utils.safe_str,
    },
)

_collect_simulation_metrics = memory_endpoints.build_collect_simulation_metrics_fn(
    runtime_wiring=runtime_wiring,
    normalize_text_fn=text_utils.normalize_text,
)


def _query_metrics_overview_with_policy() -> dict:
    base = telemetry_repo.query_metrics_overview(
        db_path=DB_PATH,
        json_loads_or_default=_json_loads_or_default,
        query_statistics_fn=lambda: telemetry_repo.query_statistics(
            db_path=DB_PATH, json_loads_or_default=_json_loads_or_default
        ),
        query_memory_quality_metrics_fn=lambda: memory_core_ops.query_memory_quality_metrics(
            deps={"db_connect_fn": _db_connect, "json_loads_or_default_fn": _json_loads_or_default}
        ),
    )
# REMOVED:     policy_overview = policy_service.get_policy_overview(
# REMOVED:         db_connect_fn=_db_connect,
# REMOVED:         json_loads_or_default_fn=_json_loads_or_default,
# REMOVED:         policy_path=POLICY_FILE,
# REMOVED:         policy_mode=POLICY_MODE,
# REMOVED:     )
# REMOVED:     return {**base, "policy_overview": policy_overview}
    return base


public_layer = assembly_public.build_public_api_endpoints(
    deps={
        "public_endpoints": public_endpoints,
        "api_handlers": api_handlers,
        "telemetry_repo": telemetry_repo,
        "training_artifacts": training_artifacts,
        "memory_core_ops": memory_core_ops,
        "MODEL": MODEL,
        "DATA_DIR": DATA_DIR,
        "DB_PATH": DB_PATH,
        "query_metrics_overview_with_policy_fn": _query_metrics_overview_with_policy,
        "_json_loads_or_default": _json_loads_or_default,
        "download_aspen_file": download_aspen_file,
        "logger": logger,
        "ntpath": ntpath,
        "MAX_TEXT_FILE_SIZE": MAX_TEXT_FILE_SIZE,
        "TRAINING_RUNS_DIR": TRAINING_RUNS_DIR,
        "TRAINING_EXPORTS_DIR": TRAINING_EXPORTS_DIR,
        "SCHEMA_DEFAULT_TARGET": SCHEMA_DEFAULT_TARGET,
        "RL_DIR": RL_DIR,
        "PROMPT_DIR": PROMPT_DIR,
        "SCHEMA_DIR": BASE_DIR / "aspen" / "schema",
        "BASE_PARENT_DIR": BASE_DIR.parent,
        "PROMPT_VERSION_FILE": PROMPT_VERSION_FILE,
        "prompt_version_service": prompt_version_service,
        "upsert_prompt_version_fn": lambda prompt_version_id, source_run_id, status, assignment_mode, canary_ratio, manifest_obj: telemetry_repo.upsert_prompt_version(
            db_path=DB_PATH,
            json_dumps=_json_dumps,
            prompt_version_id=prompt_version_id,
            source_run_id=source_run_id,
            status=status,
            assignment_mode=assignment_mode,
            canary_ratio=canary_ratio,
            manifest_obj=manifest_obj,
        ),
        "_db_connect": _db_connect,
    }
)
root = public_layer["root"]
health = public_layer["health"]
history = public_layer["history"]
download_file = public_layer["download_file"]
get_rollouts = public_layer["get_rollouts"]
clear_rollouts = public_layer["clear_rollouts"]
get_rollout_spans = public_layer["get_rollout_spans"]

async def _delete_rollout(rollout_id: str):
    return telemetry_repo.delete_single_rollout(db_path=DB_PATH, rollout_id=rollout_id)

async def _delete_memory(memory_id: str):
    return memory_core_ops.delete_single_memory(memory_id=memory_id, deps={"db_connect_fn": _db_connect})
get_statistics = public_layer["get_statistics"]
get_artifacts = public_layer["get_artifacts"]
get_metrics_overview = public_layer["get_metrics_overview"]
list_training_runs = public_layer["list_training_runs"]
clear_training_runs = public_layer["clear_training_runs"]
get_training_file = public_layer["get_training_file"]
publish_training_result = public_layer["publish_training_result"]
get_prompt_versions = public_layer["get_prompt_versions"]
update_prompt_versions = public_layer["update_prompt_versions"]
get_current_prompts = public_layer["get_current_prompts"]
update_current_prompts = public_layer["update_current_prompts"]
list_schema_files = public_layer["list_schema_files"]
get_schema_file = public_layer["get_schema_file"]
update_schema_file = public_layer["update_schema_file"]

state_layer = assembly_state.build_state_helpers(
    deps={
        "state_endpoints": state_endpoints,
        "state_ops": state_ops,
        "runtime_state": runtime_state,
        "training_artifacts": training_artifacts,
    }
)
_set_sse_control = state_layer["_set_sse_control"]
_get_sse_control = state_layer["_get_sse_control"]
_rl_append_log = state_layer["_rl_append_log"]
_rl_set_job = state_layer["_rl_set_job"]
_rl_get_job = state_layer["_rl_get_job"]

rl_pipeline_layer = assembly_rl.build_rl_pipeline(
    deps={
        "rl_pipeline_endpoints": rl_pipeline_endpoints,
        "rl_wiring": rl_wiring,
        "training_process_service": training_process_service,
        "training_artifacts": training_artifacts,
        "telemetry_repo": telemetry_repo,
        "_rl_append_log": _rl_append_log,
        "_rl_set_job": _rl_set_job,
        "python_exec": sys.executable or "python3",
        "RL_DIR": RL_DIR,
        "DB_PATH": DB_PATH,
        "PROMPT_DIR": PROMPT_DIR,
        "SCHEMA_DIR": BASE_DIR / "aspen" / "schema",
        "TRAINING_RUNS_DIR": TRAINING_RUNS_DIR,
        "CWD": BASE_DIR.parent,
        "default_host": os.getenv("HOST", "192.168.3.202"),
        "default_port": int(os.getenv("PORT", "38843") or 38843),
        "rl_worker_service": rl_worker_service,
        "runtime_state": runtime_state,
        "_db_connect": _db_connect,
        "SCHEMA_DEFAULT_TARGET": SCHEMA_DEFAULT_TARGET,
        "logger": logger,
        "CancellationToken": CancellationToken,
        "time_mod": time,
    }
)
_run_training_subprocess = rl_pipeline_layer["_run_training_subprocess"]
_run_collection_subprocess = rl_pipeline_layer["_run_collection_subprocess"]


execute_user_task = execution_endpoints.build_execute_user_task_endpoint(
    chat_execution_service=chat_execution_service,
    chat_wiring=chat_wiring,
    runtime_state=runtime_state,
    deps={
        "AspenTaskCls": app_state.AspenTask,
        "get_agent_fn": get_agent,
        "store": store,
        "db_path": DB_PATH,
        "db_connect_fn": _db_connect,
        "json_dumps_fn": _json_dumps,
        "json_loads_or_default_fn": _json_loads_or_default,
        "infer_task_type_fn": text_utils.infer_task_type,
        "build_memory_context_for_task_fn": _build_memory_context_for_task,
        "safe_str_fn": text_utils.safe_str,
        "collect_simulation_metrics_fn": _collect_simulation_metrics,
        "extract_run_attempts_fn": lambda spans: memory_extractors.extract_run_simulation_attempts_from_spans(
            spans, safe_str_fn=text_utils.safe_str
        ),
        "extract_strategy_from_spans_fn": lambda spans: memory_extractors.extract_strategy_from_spans(
            spans, safe_str_fn=text_utils.safe_str
        ),
        "extract_config_snippet_from_spans_fn": lambda spans: memory_extractors.extract_config_snippet_from_spans(
            spans, safe_str_fn=text_utils.safe_str
        ),
        "extract_pitfall_details_from_spans_fn": lambda spans: memory_extractors.extract_pitfall_details_from_spans(
            spans, safe_str_fn=text_utils.safe_str
        ),
        "build_pitfall_summary_fn": lambda attempts: memory_extractors.build_pitfall_summary(
            attempts, safe_str_fn=text_utils.safe_str
        ),
        "extract_pitfalls_from_spans_fn": lambda spans: memory_extractors.extract_pitfalls_from_spans(
            spans, safe_str_fn=text_utils.safe_str
        ),
        "memory_tags_fn": memory_storage_ops.memory_tags,
        "upsert_case_fn": lambda **kwargs: memory_storage_ops.upsert_memory_case(
            **kwargs,
            deps={
                "db_connect_fn": _db_connect,
                "json_dumps_fn": _json_dumps,
                "normalize_text_fn": text_utils.normalize_text,
                "memory_docs_dir": MEMORY_DOCS_DIR,
                "list_validated_dynamic_methods_fn": _list_validated_dynamic_methods,
                "list_validated_dynamic_component_aliases_fn": _list_validated_dynamic_component_aliases,
            },
        ),
        "auto_upsert_memory_from_rollout_fn": memory_pipeline_ops.auto_upsert_memory_from_rollout,
        "memory_core_ops": memory_core_ops,
        "telemetry_repo": telemetry_repo,
        "emitter_utils": emitter_utils,
        "reward_engine": reward_engine,
        "chat_helpers": chat_helpers,
# REMOVED:         "policy_suggest_fn": lambda user_message, task_type, memory_hit_count, tool_call_count, rollout_id, policy_mode=POLICY_MODE: policy_service.suggest_policy(
# REMOVED:             policy_path=POLICY_FILE,
# REMOVED:             policy_mode=policy_mode,
# REMOVED:             canary_ratio=POLICY_CANARY_RATIO,
# REMOVED:             user_message=user_message,
# REMOVED:             task_type=task_type,
# REMOVED:             memory_hit_count=memory_hit_count,
# REMOVED:             tool_call_count=tool_call_count,
# REMOVED:             rollout_id=rollout_id,
# REMOVED:         ),
# REMOVED:         "build_policy_guidance_fn": lambda actions, enforce=False: policy_service.build_policy_guidance(actions, enforce=enforce),
# REMOVED:         "policy_mode": POLICY_MODE,
        "select_prompt_assignment_fn": _select_prompt_assignment,
        "build_effective_system_prompt_fn": _build_effective_system_prompt,
        "record_prompt_assignment_fn": lambda rollout_id, assignment: telemetry_repo.record_prompt_assignment(
            db_path=DB_PATH,
            json_dumps=_json_dumps,
            rollout_id=rollout_id,
            prompt_version_id=assignment.get("selected_version_id"),
            bucket=str(assignment.get("bucket") or ""),
            assignment_obj=assignment,
        ),
        "prompt_version_mode": PROMPT_VERSION_MODE,
        "al_emit_message_fn": _al_emit_message,
        "al_emit_annotation_fn": _al_emit_annotation,
        "al_emit_reward_fn": _al_emit_reward,
        "OperationContextCls": OperationContext,
        "logger": logger,
        "memory_min_reward": os.getenv("MEMORY_MIN_REWARD", "0.0"),
    },
)

_run_rl_job = rl_pipeline_layer["_run_rl_job_builder"](
    _run_collection_subprocess,
    execute_user_task,
    _run_training_subprocess,
)

api_layer = assembly_api.build_api_layer(
    deps={
        "api_endpoints": api_endpoints,
        "api_wiring": api_wiring,
        "telemetry_repo": telemetry_repo,
        "memory_core_ops": memory_core_ops,
        "memory_storage_ops": memory_storage_ops,
        "rl_job_service": rl_job_service,
        "runtime_state": runtime_state,
        "training_artifacts": training_artifacts,
        "_run_rl_job": _run_rl_job,
        "_rl_append_log": _rl_append_log,
        "DB_PATH": DB_PATH,
        "_json_loads_or_default": _json_loads_or_default,
        "_build_memory_from_rollouts": _build_memory_from_rollouts,
        "_db_connect": _db_connect,
        "memory_api_service": memory_api_service,
        "_search_memory_cases": _search_memory_cases,
        "_json_dumps": _json_dumps,
        "MEMORY_DOCS_DIR": MEMORY_DOCS_DIR,
        "_build_resume_prompt": _build_resume_prompt,
        "safe_str_fn": text_utils.safe_str,
        "_rl_get_job": _rl_get_job,
    }
)
start_rl_job = api_layer["start_rl_job"]
stop_rl_job = api_layer["stop_rl_job"]
list_rl_jobs = api_layer["list_rl_jobs"]
list_rl_task_history = api_layer["list_rl_task_history"]
api_memory_build = api_layer["api_memory_build"]
api_memory_search = api_layer["api_memory_search"]
api_memory_stats = api_layer["api_memory_stats"]
api_memory_backfill = api_layer["api_memory_backfill"]
api_memory_clear = api_layer["api_memory_clear"]
api_memory_usages = api_layer["api_memory_usages"]
api_memory_usage_events = api_layer["api_memory_usage_events"]
api_memory_quality = api_layer["api_memory_quality"]
api_memory_aliases = api_layer["api_memory_aliases"]
api_memory_alias_review = api_layer["api_memory_alias_review"]
chat_resume_context = api_layer["chat_resume_context"]
get_rl_job = api_layer["get_rl_job"]

chat_layer = assembly_chat.build_chat_layer(
    deps={
        "chat_endpoints": chat_endpoints,
        "chat_stream_service": chat_stream_service,
        "_get_sse_control": _get_sse_control,
        "_set_sse_control": _set_sse_control,
        "_build_resume_prompt": _build_resume_prompt,
        "execute_user_task": execute_user_task,
    }
)
stop_chat_stream = chat_layer["stop_chat_stream"]
chat_resume_stream = chat_layer["chat_resume_stream"]
chat_stream = chat_layer["chat_stream"]


runtime_bootstrap.include_api_router(
    app=app,
    build_router_fn=api_router_factory.build_router,
    handler_map=router_wiring.build_api_handler_map(
        handlers=assembly_router.build_handler_map(
            deps={
                "root": root,
                "health": health,
                "history": history,
                "download_file": download_file,
                "get_rollouts": get_rollouts,
                "clear_rollouts": clear_rollouts,
                "delete_rollout": _delete_rollout,
                "get_rollout_spans": get_rollout_spans,
                "get_statistics": get_statistics,
                "get_artifacts": get_artifacts,
                "get_metrics_overview": get_metrics_overview,
                "list_training_runs": list_training_runs,
                "clear_training_runs": clear_training_runs,
                "get_training_file": get_training_file,
                "publish_training_result": publish_training_result,
                "get_prompt_versions": get_prompt_versions,
                "update_prompt_versions": update_prompt_versions,
                "get_current_prompts": get_current_prompts,
                "update_current_prompts": update_current_prompts,
                "list_schema_files": list_schema_files,
                "get_schema_file": get_schema_file,
                "update_schema_file": update_schema_file,
                "start_rl_job": start_rl_job,
                "stop_rl_job": stop_rl_job,
                "list_rl_jobs": list_rl_jobs,
                "list_rl_task_history": list_rl_task_history,
                "api_memory_build": api_memory_build,
                "api_memory_search": api_memory_search,
                "api_memory_stats": api_memory_stats,
                "api_memory_backfill": api_memory_backfill,
                "api_memory_clear": api_memory_clear,
                "delete_memory": _delete_memory,
                "api_memory_usages": api_memory_usages,
                "api_memory_usage_events": api_memory_usage_events,
                "api_memory_quality": api_memory_quality,
                "api_memory_aliases": api_memory_aliases,
                "api_memory_alias_review": api_memory_alias_review,
                "chat_resume_context": chat_resume_context,
                "get_rl_job": get_rl_job,
                "stop_chat_stream": stop_chat_stream,
                "chat_resume_stream": chat_resume_stream,
                "chat_stream": chat_stream,
                "get_model_config": settings_handlers.get_model_config_handler,
                "save_model_config": settings_handlers.save_model_config_handler,
                "test_model_config": settings_handlers.test_model_config_handler,
                "get_system_config": settings_handlers.get_system_config_handler,
                "save_system_config": settings_handlers.save_system_config_handler,
                "test_system_config": settings_handlers.test_system_config_handler,
                "restart_service": lambda: settings_handlers.restart_service_handler(logger=logger),
            }
        )
    ),
)


if __name__ == "__main__":
    import uvicorn

    runtime_bootstrap.run_server_main(
        app=app,
        logger=logger,
        model=MODEL,
        db_path=DB_PATH,
        uvicorn_module=uvicorn,
    )








