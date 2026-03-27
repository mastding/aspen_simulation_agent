from __future__ import annotations

from typing import Any, Callable, Dict


def build_api_handler_map(*, handlers: Dict[str, Callable[..., Any]]) -> Dict[str, Callable[..., Any]]:
    # Keep a shallow copy so caller mutations do not affect router binding.
    return dict(handlers)
