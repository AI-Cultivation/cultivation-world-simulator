"""Application boundary for roleplay commands.

This keeps API-level mutation policy outside the roleplay domain flows while
keeping those flows free to release the session lock during LLM I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RoleplayCommandDependencies:
    runtime: Any
    get_roleplay_session: Any
    clear_roleplay_session: Any
    start_roleplay: Any
    stop_roleplay: Any
    submit_roleplay_decision: Any
    submit_roleplay_choice: Any
    submit_roleplay_conversation_turn: Any
    end_roleplay_conversation: Any


class RoleplayCommandService:
    def __init__(self, dependencies: RoleplayCommandDependencies):
        self._deps = dependencies

    def get_session(self) -> dict:
        return self._deps.get_roleplay_session(self._deps.runtime)

    def clear_session(self) -> None:
        self._deps.clear_roleplay_session(self._deps.runtime)

    async def start(self, *, avatar_id: str) -> dict:
        return await self._deps.runtime.run_mutation(
            self._deps.start_roleplay, self._deps.runtime, avatar_id=avatar_id
        )

    async def stop(self, *, avatar_id: str | None) -> dict:
        return await self._deps.runtime.run_mutation(
            self._deps.stop_roleplay, self._deps.runtime, avatar_id=avatar_id
        )

    async def submit_decision(self, *, avatar_id: str, request_id: str, command_text: str) -> dict:
        return await self._deps.submit_roleplay_decision(
            self._deps.runtime,
            avatar_id=avatar_id,
            request_id=request_id,
            command_text=command_text,
        )

    async def submit_choice(self, *, avatar_id: str, request_id: str, selected_key: str) -> dict:
        return await self._deps.runtime.run_mutation(
            self._deps.submit_roleplay_choice,
            self._deps.runtime,
            avatar_id=avatar_id,
            request_id=request_id,
            selected_key=selected_key,
        )

    async def send_conversation(self, *, avatar_id: str, request_id: str, message: str) -> dict:
        return await self._deps.submit_roleplay_conversation_turn(
            self._deps.runtime,
            avatar_id=avatar_id,
            request_id=request_id,
            message=message,
        )

    async def end_conversation(self, *, avatar_id: str, request_id: str) -> dict:
        return await self._deps.end_roleplay_conversation(
            self._deps.runtime,
            avatar_id=avatar_id,
            request_id=request_id,
        )
