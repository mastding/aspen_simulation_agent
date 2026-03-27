# Aspen Process Simulation Agent

## Overview
This repository implements an AI-driven chemical process simulation platform.

It combines:
- A Vue 3 frontend (workspace, run history, memory, artifacts, metrics, training, RL lab)
- A FastAPI backend (AutoGen + AgentLightning + SQLite persistence)
- Aspen simulator integration through HTTP tools
- Offline training and prompt-candidate generation workflows

The backend is modularized. `backend/main_with_rl.py` is now the composition root, and business logic is split into `backend/app/*` modules.

## Core Capabilities

### 1. Task execution (unit + process simulation)
- Users submit natural-language simulation requirements.
- The agent calls tools (`get_schema`, `run_simulation`, `get_result`, memory tools).
- Frontend streams thoughts, tool calls/results, final response, and downloadable outputs.

### 2. Persistence and observability
- Rollouts, spans, rewards, and task metadata are persisted in SQLite.
- Frontend pages support run-level and span-level inspection.

### 3. Long-term memory
- Successful trajectories can be converted to reusable experience entries.
- New tasks can retrieve historical experience before tool execution.
- Usage events and quality stats are queryable.

### 4. RL data collection and offline training
- RL Lab supports online collection + optional training.
- Two modes are supported:
  - `RGO`: rule-guided offline optimization
  - `APO`: preference-style candidate search over prompt increments
- Generated training artifacts can be reviewed and published from UI.

### 5. Artifact management
- Files are grouped by task in Artifacts page.
- Backend `/download` proxies file content from Aspen server.

## Repository Structure

```text
aspen_simulation_new/
|-- frontend/
|   |-- src/
|   |   |-- views/                # workspace/runs/memory/artifacts/metrics/training/rl-lab/help
|   |   |-- services/             # API wrappers
|   |   |-- router.js
|   |   `-- App.vue
|   `-- package.json
|-- backend/
|   |-- main_with_rl.py           # composition root
|   |-- app/
|   |   |-- api/                  # route factory + handlers
|   |   |-- runtime/              # endpoint factories + layer assembly
|   |   |-- services/             # chat/rl/training process services
|   |   |-- memory/               # extraction/matching/storage/pipeline
|   |   |-- rl/                   # reward engine
|   |   |-- training/             # training artifact helpers
|   |   `-- config/               # settings
|   |-- prompt/                   # prompt files
|   |-- tools/                    # get_schema/run_simulation/get_result/download_aspen_file
|   `-- rl_data/                  # sqlite db + memory docs
|-- reinforcement_learning/
|   |-- src/                      # collection/training/publish scripts
|   `-- outputs/training_runs/    # training outputs
|-- aspen/schema/                 # schema source files
|-- .env
`-- requirements.txt
```

See `backend/ARCHITECTURE.md` for backend split details.

## Requirements

### Python
Install from repository root:

```bash
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Environment Variables

Root `.env` example:

```env
MODEL=qwen3-max
MODEL_API_URL=http://openai.dicp.sixseven.ltd:5924/v1
MODEL_API_KEY=sk-xxxx

HOST=192.168.3.202
PORT=38843
BACKEND_URL=http://${HOST}:${PORT}

ASPEN_SIMULATOR_PORT=7777
ASPEN_SIMULATOR_URL=https://119.3.160.243:${ASPEN_SIMULATOR_PORT}
```

Notes:
- `MODEL_*`: LLM provider settings
- `HOST/PORT`: FastAPI bind address
- `ASPEN_SIMULATOR_URL`: remote Aspen service used by backend tools

## Run

### Backend

```bash
cd backend
python3 main_with_rl.py
```

### Frontend

```bash
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173
```

## Typical Nginx Mapping

- Frontend domain: `aspen.dicp.sixseven.ltd:5924 -> 192.168.3.202:5173`
- Backend domain: `aspenback.dicp.sixseven.ltd:5924 -> 192.168.3.202:38843`

## Main API Endpoints

Defined in `backend/app/api/router_factory.py`.

### Basic
- `GET /`
- `GET /health`
- `GET /download?file_path=...`

### Rollouts / telemetry
- `GET /api/rollouts`
- `POST /api/rollouts/clear`
- `GET /api/rollouts/{rollout_id}/spans`
- `GET /api/statistics`
- `GET /api/artifacts`
- `GET /api/metrics/overview`

### Training publish
- `GET /api/training/runs`
- `POST /api/training/runs/clear`
- `GET /api/training/runs/{run_id}/files/{file_name}`
- `POST /api/training/publish`

### RL jobs
- `POST /api/rl/jobs/start`
- `POST /api/rl/jobs/{job_id}/stop`
- `GET /api/rl/jobs`
- `GET /api/rl/jobs/{job_id}`
- `GET /api/rl/task-history`

### Memory
- `POST /api/memory/build`
- `GET /api/memory/search`
- `GET /api/memory/stats`
- `POST /api/memory/backfill`
- `POST /api/memory/clear`
- `GET /api/memory/usages`
- `GET /api/memory/usages/{memory_id}`
- `GET /api/memory/quality`

### Chat stream (SSE)
- `POST /api/chat/stream`
- `POST /api/chat/resume/stream`
- `POST /api/chat/stop`
- `POST /api/chat/resume-context`

## Training Workflow

### Online collection
RL Lab can collect trajectories via:
- `internal`: backend-internal execution path
- `script_sse`: external collector script via SSE/HTTP

### Offline training script
Main script:
- `reinforcement_learning/src/train_offline_and_generate_prompts.py`

Inputs:
- trajectory DB
- prompt directory
- schema directory

Outputs:
- `training_result.json`
- `training_report.md`
- prompt candidate increments
- optional schema candidate increment file

### RGO vs APO
- `RGO`: deterministic rule-driven prompt increment generation from error/success stats
- `APO`: multi-iteration sampled candidate search over increment pool (no model weight update)

## Data and Artifacts

### SQLite
- `backend/rl_data/aspen_trajectories.db`
- stores rollouts, spans, memory usage events, and related telemetry

### Memory docs
- `backend/rl_data/memory_docs/`
- markdown-readable memory entries

### Training outputs
- `reinforcement_learning/outputs/training_runs/run_<run_id>/`
- typical files:
  - `training_result.json`
  - `training_report.md`
  - `system_prompt_candidate-run_<run_id>.txt`
  - `schema_check_prompt_candidate-run_<run_id>.txt`
  - `thought_process_prompt_candidate-run_<run_id>.txt`
  - `schema_descriptions_candidate-<run_id>.json` (when schema delta exists)

## Troubleshooting

### Frontend 502 / blank page
- verify frontend process is listening on `5173`
- verify nginx frontend upstream points to `5173`

### Backend unavailable
- verify backend process is listening on `38843`
- check logs: `backend/app_with_rl.log`, `logs/backend_38843.log`

### Artifact download returns empty file
- ensure request hits backend domain (`aspenback...`) instead of frontend domain
- verify `/download` response has non-empty body
- verify remote path exists on Aspen server and `ASPEN_SIMULATOR_URL` is reachable

### Training produces no increment
- inspect `training_result.json` -> `summary`, `top_errors`, `error_type_count`
- verify enough window signal exists for increment generation

## Development Notes
- Keep new business logic in `backend/app/*`, not in `main_with_rl.py`.
- Keep `main_with_rl.py` as composition and wiring only.
- Exclude runtime artifacts from commits (`dist/`, `node_modules/`, `__pycache__/`, `*.bak_*`, `logs/`, DB/output artifacts).
