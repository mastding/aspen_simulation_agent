from __future__ import annotations

from typing import Any, Callable


def build_db_connect_fn(*, telemetry_repo: Any, db_path: Any) -> Callable[[], Any]:
    def endpoint() -> Any:
        return telemetry_repo.db_connect(db_path)

    return endpoint


def build_json_dumps_fn(*, json_dumps_util_fn: Callable[[Any], str]) -> Callable[[Any], str]:
    def endpoint(obj: Any) -> str:
        return json_dumps_util_fn(obj)

    return endpoint


def build_json_loads_or_default_fn(
    *, json_loads_or_default_util_fn: Callable[[Any, Any], Any]
) -> Callable[[Any, Any], Any]:
    def endpoint(raw: Any, default: Any) -> Any:
        return json_loads_or_default_util_fn(raw, default)

    return endpoint


def init_sqlite(*, telemetry_repo: Any, db_path: Any, json_dumps_fn: Callable[[Any], str]) -> None:
    telemetry_repo.init_app_tables(db_path=db_path, json_dumps=json_dumps_fn)
