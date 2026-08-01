from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from src.i18n import t


class DecisionBoundaryResult(StrEnum):
    CONTINUE = "continue"
    WAITING_FOR_PLAYER = "waiting_for_player"
    NO_CONTROLLED_AVATAR = "no_controlled_avatar"
    CONTROLLED_AVATAR_CLEARED = "controlled_avatar_cleared"


class DecisionBoundaryGateway(Protocol):
    def get_controlled_avatar_id(self) -> str: ...

    def controls_avatar(self, avatar_id: str) -> bool: ...

    def before_ai_decision(self, world: Any) -> DecisionBoundaryResult: ...

    def begin_conversation(self, *, avatar: Any, target_avatar: Any) -> dict[str, Any]: ...


@dataclass(slots=True)
class RuntimeDecisionBoundaryGateway:
    """Domain-facing roleplay adapter backed by a session runtime.

    This intentionally knows only the runtime session shape.  HTTP validation,
    LLM prompting, and response DTOs remain in the server application layer.
    """

    runtime: Any

    def get_session(self) -> dict[str, Any]:
        return self.runtime.get_roleplay_session()

    def get_controlled_avatar_id(self) -> str:
        return str(self.get_session().get("controlled_avatar_id") or "")

    def controls_avatar(self, avatar_id: str) -> bool:
        return self.get_controlled_avatar_id() == str(avatar_id)

    def clear_session(self) -> None:
        self.runtime.clear_roleplay_session()

    def before_ai_decision(self, world: Any) -> DecisionBoundaryResult:
        session = self.get_session()
        controlled_avatar_id = self.get_controlled_avatar_id()
        if not controlled_avatar_id:
            return DecisionBoundaryResult.NO_CONTROLLED_AVATAR

        status = str(session.get("status") or "")
        if status in {"awaiting_decision", "awaiting_choice", "conversing", "submitting"}:
            return DecisionBoundaryResult.WAITING_FOR_PLAYER

        avatar = world.avatar_manager.get_avatar(controlled_avatar_id)
        if avatar is None or bool(getattr(avatar, "is_dead", False)):
            self.clear_session()
            return DecisionBoundaryResult.CONTROLLED_AVATAR_CLEARED

        if avatar.current_action is not None or avatar.has_plans():
            return DecisionBoundaryResult.CONTINUE

        session["controlled_avatar_id"] = str(avatar.id)
        session["status"] = "awaiting_decision"
        session["pending_request"] = {
            "request_id": f"roleplay-decision-{avatar.id}-{int(time.time() * 1000)}",
            "type": "decision",
            "avatar_id": str(avatar.id),
            "title": t("{avatar_name} needs a new command", avatar_name=avatar.name),
            "description": t("World paused and waiting for your roleplay command."),
            "created_at": time.time(),
        }
        self.runtime.set_roleplay_auto_paused(True)
        return DecisionBoundaryResult.WAITING_FOR_PLAYER

    def begin_conversation(self, *, avatar: Any, target_avatar: Any) -> dict[str, Any]:
        session = self.get_session()
        existing = session.get("conversation_session")
        if isinstance(existing, dict) and (
            str(existing.get("avatar_id") or "") == str(avatar.id)
            and str(existing.get("target_avatar_id") or "") == str(target_avatar.id)
            and str(existing.get("status") or "") in {"awaiting_player", "awaiting_continue", "completed"}
        ):
            return dict(session)

        request_id = f"roleplay-conversation-{avatar.id}-{target_avatar.id}-{int(time.time() * 1000)}"
        title = t("{avatar_name} is talking with {target_avatar_name}", avatar_name=avatar.name, target_avatar_name=target_avatar.name)
        description = t(
            "World paused and waiting for you to continue speaking as {avatar_name} with {target_avatar_name}.",
            avatar_name=avatar.name,
            target_avatar_name=target_avatar.name,
        )
        session["controlled_avatar_id"] = str(avatar.id)
        session["status"] = "conversing"
        session["pending_request"] = {
            "request_id": request_id,
            "type": "conversation",
            "avatar_id": str(avatar.id),
            "target_avatar_id": str(target_avatar.id),
            "title": title,
            "description": description,
            "messages": [],
            "can_end": True,
            "created_at": time.time(),
        }
        session["conversation_session"] = {
            "session_id": request_id,
            "request_id": request_id,
            "avatar_id": str(avatar.id),
            "target_avatar_id": str(target_avatar.id),
            "initiator_avatar_id": str(avatar.id),
            "status": "awaiting_player",
            "messages": [],
            "started_at": time.time(),
            "last_summary": None,
            "last_ai_thinking": "",
        }
        self.runtime.set_roleplay_auto_paused(True)
        return dict(session)


def get_decision_boundary_gateway(world: Any) -> DecisionBoundaryGateway | None:
    runtime = getattr(world, "runtime", None)
    if runtime is None or not hasattr(runtime, "get_roleplay_session"):
        return None
    return RuntimeDecisionBoundaryGateway(runtime)
