from __future__ import annotations

from typing import Any, Dict


def build_state_helpers(*, deps: Dict[str, Any]) -> Dict[str, Any]:
    se = deps["state_endpoints"]
    training_artifacts = deps["training_artifacts"]
    return {
        "_set_sse_control": se.build_set_sse_control_fn(state_ops=deps["state_ops"], runtime_state=deps["runtime_state"]),
        "_get_sse_control": se.build_get_sse_control_fn(state_ops=deps["state_ops"], runtime_state=deps["runtime_state"]),
        "_rl_append_log": se.build_rl_append_log_fn(
            state_ops=deps["state_ops"],
            runtime_state=deps["runtime_state"],
            now_iso_fn=training_artifacts.now_iso,
            trim_logs_fn=training_artifacts.trim_logs,
        ),
        "_rl_set_job": se.build_rl_set_job_fn(state_ops=deps["state_ops"], runtime_state=deps["runtime_state"]),
        "_rl_get_job": se.build_rl_get_job_fn(state_ops=deps["state_ops"], runtime_state=deps["runtime_state"]),
    }
