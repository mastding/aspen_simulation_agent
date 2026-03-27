# Backend Architecture Guide

## Overview

The backend is now organized as:

- `main_with_rl.py`: composition root only.
- `app/runtime/*`: endpoint factories and layer assembly.
- `app/memory/*`: memory extraction, matching, storage, and pipeline.
- `app/rl/*`: reward and RL-related logic.
- `app/services/*`: execution services and orchestration primitives.

`main_with_rl.py` should not contain business logic functions anymore.

## Runtime Modules

- `app/runtime/persistence_runtime.py`
  - SQLite connect/json helper builders and DB init.
- `app/runtime/text_utils.py`
  - text normalize, task type infer, safe text clipping.
- `app/runtime/memory_endpoints.py`
  - memory search/get/context/build endpoint factories.
- `app/runtime/agent_runtime.py`
  - `get_agent` builder (model client + assistant agent).
- `app/runtime/public_endpoints.py`
  - public API endpoint factories.
- `app/runtime/state_endpoints.py`
  - SSE and RL job state endpoint factories.
- `app/runtime/rl_pipeline_endpoints.py`
  - collection/training subprocess and RL worker endpoint factories.
- `app/runtime/api_endpoints.py`
  - RL + memory API endpoint factories.
- `app/runtime/chat_endpoints.py`
  - SSE chat stream/stop/resume endpoint factories.
- `app/runtime/execution_endpoints.py`
  - `execute_user_task` endpoint factory.

## Layer Assembly

- `app/runtime/assembly_public.py`: build public APIs.
- `app/runtime/assembly_state.py`: build state helpers.
- `app/runtime/assembly_rl.py`: build RL pipeline pieces.
- `app/runtime/assembly_api.py`: build RL/memory APIs.
- `app/runtime/assembly_chat.py`: build chat endpoints.
- `app/runtime/assembly_router.py`: final handler map for router registration.

## Where To Change (Quick Map)

1. Add a new public API
   - `app/runtime/public_endpoints.py`
   - `app/runtime/assembly_public.py`
   - `app/runtime/assembly_router.py`

2. Change reward rules
   - `app/rl/reward.py`
   - if execution flow impacted: `app/runtime/execution_endpoints.py`

3. Change memory matching rules
   - `app/memory/matching.py`
   - wiring side: `app/runtime/memory_endpoints.py`

4. Change memory accumulation/upsert strategy
   - `app/memory/pipeline_ops.py`
   - wiring side: `app/runtime/memory_endpoints.py`

5. Change SSE chat behavior
   - `app/runtime/chat_endpoints.py`
   - state interaction: `app/runtime/state_endpoints.py`

6. Change training/collection subprocess args
   - `app/runtime/assembly_rl.py`
   - endpoint contract: `app/runtime/rl_pipeline_endpoints.py`

7. Add/remove Agent tools
   - `main_with_rl.py` tools assembly section
   - corresponding tool files under `tools/`

8. Change route path binding
   - `app/api/router_factory.py` (path definitions)
   - `app/runtime/assembly_router.py` (handler mapping)

## Rules For Future Changes

- Put business logic in `app/memory`, `app/rl`, `app/services`.
- Keep runtime files focused on dependency injection and assembly.
- Avoid adding new business helpers into `main_with_rl.py`.
- Keep handler mapping explicit (no dynamic globals injection).
