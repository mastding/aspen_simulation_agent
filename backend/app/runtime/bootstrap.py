from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable


def include_api_router(*, app: Any, build_router_fn: Callable[[dict], Any], handler_map: dict) -> None:
    app.include_router(build_router_fn(handler_map))


def run_server_main(*, app: Any, logger: Any, model: str, db_path: Path, uvicorn_module: Any) -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    logger.info("=" * 80)
    logger.info("Starting Aspen backend with AgentLightning + SQLite")
    logger.info("host=%s port=%s model=%s db=%s", host, port, model, db_path)
    logger.info("=" * 80)

    uvicorn_module.run(app, host=host, port=port, log_level="info", access_log=True)
