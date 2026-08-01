from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Awaitable, Callable

from src.server.services.public_api_contract import raise_public_error
from src.server.services.roleplay_state import create_roleplay_session_dict


DEFAULT_GAME_STATE: dict[str, Any] = {
    "world": None,
    "sim": None,
    "is_paused": True,
    "roleplay_auto_paused": False,
    "init_status": "idle",
    "init_phase": 0,
    "init_phase_name": "",
    "init_progress": 0,
    "init_error": None,
    "init_start_time": None,
    "init_generation": 0,
    "reset_requested": False,
    "run_config": None,
    "current_save_path": None,
    "llm_check_failed": False,
    "llm_error_message": "",
    "llm_check_pending": False,
    "roleplay_session": create_roleplay_session_dict(),
}


def create_default_roleplay_session() -> dict[str, Any]:
    return create_roleplay_session_dict()


def create_default_game_state() -> dict[str, Any]:
    return {
        **DEFAULT_GAME_STATE,
        "roleplay_session": create_default_roleplay_session(),
    }


class GameSessionRuntime:
    """
    Unified access point for the in-memory game session state.

    Phase 1 keeps the underlying storage as a plain dict so existing code and
    tests can still interact with `game_instance`, while lifecycle mutations
    and simulator stepping are gradually routed through this runtime facade.
    """

    def __init__(self, state: dict[str, Any]):
        self._state = state
        self._mutation_lock = asyncio.Lock()
        self._world_revision = 0
        self._ensure_owned_roleplay_session()

    @property
    def state(self) -> dict[str, Any]:
        """Deprecated test compatibility access to the mutable backing state."""
        return self._state

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def update(self, values: dict[str, Any]) -> None:
        """Deprecated test compatibility helper; production code uses named methods."""
        self._state.update(values)

    def get_world(self) -> Any:
        return self._state.get("world")

    def require_world(self) -> Any:
        world = self.get_world()
        if world is None:
            raise_public_error(
                status_code=503,
                code="WORLD_NOT_READY",
                message="World not initialized",
            )
        return world

    def get_simulator(self) -> Any:
        return self._state.get("sim")

    def set_world_and_sim(self, world: Any, sim: Any) -> None:
        self._state["world"] = world
        self._state["sim"] = sim

    def set_run_config(self, run_config: dict[str, Any] | None) -> None:
        self._state["run_config"] = run_config

    def set_current_save_path(self, save_path: Any | None) -> None:
        self._state["current_save_path"] = save_path

    def set_initialization_progress(
        self,
        *,
        phase: int | None = None,
        phase_name: str | None = None,
        progress: int | None = None,
    ) -> None:
        if phase is not None:
            self._state["init_phase"] = int(phase)
        if phase_name is not None:
            self._state["init_phase_name"] = str(phase_name)
        if progress is not None:
            self._state["init_progress"] = int(progress)

    def set_llm_check_state(
        self,
        *,
        pending: bool | None = None,
        failed: bool | None = None,
        error_message: str | None = None,
    ) -> None:
        if pending is not None:
            self._state["llm_check_pending"] = bool(pending)
        if failed is not None:
            self._state["llm_check_failed"] = bool(failed)
        if error_message is not None:
            self._state["llm_error_message"] = str(error_message)

    def get_llm_failure_state(self) -> tuple[bool, str]:
        return (
            bool(self._state.get("llm_check_failed", False)),
            str(self._state.get("llm_error_message", "") or ""),
        )

    def replace_with_defaults(self) -> None:
        self._state.clear()
        self._state.update(create_default_game_state())

    def reset_to_idle(self, *, clear_run_config: bool = True) -> None:
        run_config = None if clear_run_config else self._state.get("run_config")
        self._state["init_generation"] = int(self._state.get("init_generation", 0) or 0) + 1
        self._state.update(
            {
                "world": None,
                "sim": None,
                "current_save_path": None,
                "run_config": run_config,
                "is_paused": True,
                "roleplay_auto_paused": False,
                "init_status": "idle",
                "init_phase": 0,
                "init_phase_name": "",
                "init_progress": 0,
                "init_error": None,
                "init_start_time": None,
                "llm_check_failed": False,
                "llm_error_message": "",
                "llm_check_pending": False,
                "reset_requested": False,
            }
        )
        self.clear_roleplay_session()

    def request_reset(self) -> None:
        self._state["reset_requested"] = True

    def clear_reset_request(self) -> None:
        self._state["reset_requested"] = False

    def is_reset_requested(self) -> bool:
        return bool(self._state.get("reset_requested", False))

    def mark_pending_initialization(self, *, clear_world: bool) -> None:
        self._state["init_generation"] = int(self._state.get("init_generation", 0) or 0) + 1
        if clear_world:
            self._state["world"] = None
            self._state["sim"] = None
            self._state["current_save_path"] = None
        self._state["is_paused"] = True
        self._state["roleplay_auto_paused"] = False
        self._state["init_status"] = "pending"
        self._state["init_phase"] = 0
        self._state["init_phase_name"] = ""
        self._state["init_progress"] = 0
        self._state["init_error"] = None
        self._state["llm_check_failed"] = False
        self._state["llm_error_message"] = ""
        self._state["llm_check_pending"] = False
        self._state["reset_requested"] = False
        self.clear_roleplay_session()

    def begin_initialization(self) -> None:
        self._state["init_status"] = "in_progress"
        self._state["init_start_time"] = time.time()
        self._state["init_error"] = None

    def finish_initialization(self, *, phase_name: str = "") -> None:
        self._state["init_status"] = "ready"
        self._state["init_progress"] = 100
        if phase_name:
            self._state["init_phase_name"] = phase_name

    def fail_initialization(self, error: str) -> None:
        self._state["init_status"] = "error"
        self._state["init_error"] = str(error)

    def set_paused(self, paused: bool) -> None:
        self._state["is_paused"] = bool(paused)

    def set_roleplay_auto_paused(self, paused: bool) -> None:
        self._state["roleplay_auto_paused"] = bool(paused)

    def is_effectively_paused(self) -> bool:
        return bool(self._state.get("is_paused", False) or self._state.get("roleplay_auto_paused", False))

    def get_pause_reason(self) -> str:
        if self._state.get("roleplay_auto_paused", False):
            session = self.get_roleplay_session()
            status = str(session.get("status", "") or "")
            if status == "awaiting_decision":
                return "roleplay_waiting_decision"
            if status == "awaiting_choice":
                return "roleplay_waiting_choice"
            if status == "conversing":
                return "roleplay_conversation"
            return "roleplay_waiting"
        if self._state.get("is_paused", False):
            return "paused"
        return ""

    def get_roleplay_session(self) -> dict[str, Any]:
        self._ensure_owned_roleplay_session()
        session = self._state.get("roleplay_session")
        if not isinstance(session, dict):
            session = create_default_roleplay_session()
            self._state["roleplay_session"] = session
        return session

    def _ensure_owned_roleplay_session(self) -> None:
        session = self._state.get("roleplay_session")
        if session is DEFAULT_GAME_STATE["roleplay_session"]:
            self._state["roleplay_session"] = create_default_roleplay_session()
            return

        if not isinstance(session, dict):
            return

        default_history = DEFAULT_GAME_STATE["roleplay_session"]["interaction_history"]
        if session.get("interaction_history") is default_history:
            session["interaction_history"] = []

    def clear_roleplay_session(self) -> None:
        existing = self._state.get("roleplay_session")
        if isinstance(existing, dict):
            choice_future = existing.get("_choice_future")
            try:
                if choice_future is not None and hasattr(choice_future, "done") and not choice_future.done():
                    choice_future.cancel()
            except Exception:
                pass
        self._state["roleplay_session"] = create_default_roleplay_session()
        self._state["roleplay_auto_paused"] = False

    async def run_mutation(
        self,
        operation: Callable[..., Any] | Awaitable[Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Serialize world mutations and simulator stepping through one lock.
        """
        result, _ = await self.run_mutation_measured(operation, *args, **kwargs)
        return result

    @property
    def world_revision(self) -> int:
        return self._world_revision

    async def run_mutation_measured(
        self,
        operation: Callable[..., Any] | Awaitable[Any],
        *args: Any,
        **kwargs: Any,
    ) -> tuple[Any, dict[str, int]]:
        requested_at = time.perf_counter()
        async with self._mutation_lock:
            acquired_at = time.perf_counter()
            if callable(operation):
                result = operation(*args, **kwargs)
            else:
                result = operation

            if inspect.isawaitable(result):
                result = await result
            completed_at = time.perf_counter()
            self._world_revision += 1
            return result, {
                "lock_wait_ms": round((acquired_at - requested_at) * 1000),
                "execution_ms": round((completed_at - acquired_at) * 1000),
            }
