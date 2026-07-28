"""Per-execution LLM mode propagation for a single game run."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator


_TEST_MODE_ENABLED: ContextVar[bool] = ContextVar("llm_test_mode_enabled", default=False)


def is_test_mode_enabled() -> bool:
    return _TEST_MODE_ENABLED.get()


@contextmanager
def llm_test_mode_scope(enabled: bool) -> Iterator[None]:
    token = _TEST_MODE_ENABLED.set(bool(enabled))
    try:
        yield
    finally:
        _TEST_MODE_ENABLED.reset(token)


def is_world_test_mode(world: Any) -> bool:
    snapshot = getattr(world, "run_config_snapshot", None) or {}
    return bool(snapshot.get("test_mode", False))
