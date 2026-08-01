from __future__ import annotations

import asyncio
from typing import Any, Callable

from fastapi import HTTPException


async def start_game_lifecycle(
    runtime,
    *,
    run_config: Any,
    apply_runtime_content_locale: Callable[[str], None],
    init_game_async: Callable[[], Any],
) -> dict[str, str]:
    current_status = runtime.get("init_status", "idle")
    if current_status == "in_progress":
        raise HTTPException(status_code=400, detail="Game is already initializing")

    apply_runtime_content_locale(run_config.content_locale)

    def _prepare_start() -> None:
        runtime.set_run_config(run_config.model_dump())
        runtime.mark_pending_initialization(clear_world=current_status == "ready")

    await runtime.run_mutation(_prepare_start)
    asyncio.create_task(init_game_async())
    return {"status": "ok", "message": "Game initialization started"}


async def reinit_game_lifecycle(runtime, *, init_game_async: Callable[[], Any]) -> dict[str, str]:
    await runtime.run_mutation(runtime.mark_pending_initialization, clear_world=True)
    asyncio.create_task(init_game_async())
    return {"status": "ok", "message": "Reinitialization started"}
