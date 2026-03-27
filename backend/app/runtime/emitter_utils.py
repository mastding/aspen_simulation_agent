from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import Any, Dict, Optional


def safe_emit_message(message: str, *, emit_message_fn, logger) -> None:
    try:
        emit_message_fn(message)
    except RuntimeError as exc:
        if "No active tracer found" in str(exc):
            logger.warning("emit_message fallback (no active tracer)")
        else:
            raise


def safe_emit_annotation(payload: Dict[str, Any], *, emit_annotation_fn, logger) -> None:
    try:
        emit_annotation_fn(payload)
    except RuntimeError as exc:
        if "No active tracer found" in str(exc):
            logger.warning("emit_annotation fallback (no active tracer)")
        else:
            raise


def safe_emit_reward(
    *,
    reward: float,
    dimensions: Optional[Dict[str, float]] = None,
    emit_reward_fn,
    logger,
) -> None:
    try:
        _ = dimensions
        emit_reward_fn(reward=reward)
    except RuntimeError as exc:
        if "No active tracer found" in str(exc):
            logger.warning("emit_reward fallback (no active tracer)")
        else:
            raise


@contextmanager
def safe_operation_context(name: str, attrs: Dict[str, Any], *, OperationContextCls, logger):
    try:
        with OperationContextCls(name, attrs):
            yield
    except RuntimeError as exc:
        if "No active tracer found" in str(exc):
            logger.warning("OperationContext fallback (no active tracer): %s", name)
            with nullcontext():
                yield
        else:
            raise
