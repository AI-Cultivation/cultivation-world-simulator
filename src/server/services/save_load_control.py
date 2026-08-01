from __future__ import annotations

import asyncio
import os
import time
from typing import Any, Callable

from fastapi import HTTPException
from src.i18n import t


def validate_save_filename(filename: str) -> None:
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail=t("Invalid filename"))


def resolve_existing_save_path(filename: str, *, candidate_dirs) -> Any:
    validate_save_filename(filename)
    for saves_dir in candidate_dirs:
        target_path = saves_dir / filename
        if target_path.exists():
            return target_path
    return None


def list_saves_query(*, list_saves) -> dict[str, Any]:
    saves_list = list_saves()
    result: list[dict[str, Any]] = []
    for path, meta in saves_list:
        result.append(
            {
                "filename": path.name,
                "save_time": meta.get("save_time", ""),
                "game_time": meta.get("game_time", ""),
                "version": meta.get("version", ""),
                "language": meta.get("language", ""),
                "avatar_count": meta.get("avatar_count", 0),
                "alive_count": meta.get("alive_count", 0),
                "dead_count": meta.get("dead_count", 0),
                "custom_name": meta.get("custom_name"),
                "event_count": meta.get("event_count", 0),
                "playthrough_id": meta.get("playthrough_id", ""),
                "is_auto_save": meta.get("is_auto_save", False),
                "map_id": meta.get("map_id", ""),
                "map_name": meta.get("map_name", ""),
            }
        )
    return {"saves": result}


def save_current_game(
    runtime,
    *,
    custom_name: str | None,
    validate_save_name: Callable[[str], bool],
    save_game,
    sects_by_id,
) -> dict[str, Any]:
    world = runtime.get("world")
    sim = runtime.get("sim")
    if not world or not sim:
        raise HTTPException(status_code=503, detail=t("Game not initialized"))

    existed_sects = getattr(world, "existed_sects", []) or list(sects_by_id.values())
    if custom_name and not validate_save_name(custom_name):
        raise HTTPException(status_code=400, detail=t("Invalid save name"))

    success, filename = save_game(world, sim, existed_sects, custom_name=custom_name)
    if not success:
        raise HTTPException(status_code=500, detail=t("Save failed"))
    return {"status": "ok", "filename": filename}


def delete_save_file(
    *,
    filename: str,
    saves_dir,
    fallback_saves_dirs=None,
    get_events_db_path,
) -> dict[str, Any]:
    validate_save_filename(filename)

    target_path = resolve_existing_save_path(
        filename,
        candidate_dirs=[saves_dir, *(fallback_saves_dirs or [])],
    ) or (saves_dir / filename)
    if target_path.exists():
        os.remove(target_path)

    events_db_path = get_events_db_path(target_path)
    if os.path.exists(events_db_path):
        try:
            os.remove(events_db_path)
        except Exception as exc:
            print(f"[Warning] Failed to delete db file {events_db_path}: {exc}")

    return {"status": "ok", "message": t("Save deleted")}


async def load_game_into_runtime(
    runtime,
    *,
    filename: str,
    saves_dir,
    fallback_saves_dirs=None,
    get_save_info,
    language_manager,
    manager,
    t,
    apply_runtime_content_locale,
    scan_avatar_assets,
    load_game,
    get_settings_service,
    _model_to_dict,
) -> dict[str, Any]:
    validate_save_filename(filename)
    target_path = resolve_existing_save_path(
        filename,
        candidate_dirs=[saves_dir, *(fallback_saves_dirs or [])],
    )
    if target_path is None or not target_path.exists():
        raise HTTPException(status_code=404, detail=t("File not found"))

    async def _do_load():
        runtime.clear_roleplay_session()
        save_meta = get_save_info(target_path)
        if save_meta:
            save_lang = save_meta.get("language")
            current_lang = str(language_manager)
            print(f"[Debug] Load Game - Save Lang: {save_lang}, Current Lang: {current_lang}")
            if save_lang:
                print(f"[Auto-Switch] Enforcing language sync to {save_lang}...")
                await manager.broadcast(
                    {
                        "type": "toast",
                        "level": "info",
                        "message": t("Syncing language setting: {lang}...", lang=save_lang),
                    }
                )
                await asyncio.sleep(0.2)
                if save_lang != current_lang:
                    print(f"[Auto-Switch] Switching backend language from {current_lang} to {save_lang}...")
                    await asyncio.to_thread(apply_runtime_content_locale, save_lang)

        runtime.begin_initialization()
        runtime.set_initialization_progress(phase=0, phase_name="scanning_assets", progress=0)
        await asyncio.to_thread(scan_avatar_assets)
        runtime.set_initialization_progress(phase_name="loading_save", progress=10)
        runtime.set_paused(True)
        await asyncio.sleep(0)

        runtime.set_initialization_progress(phase_name="parsing_data", progress=30)
        await asyncio.sleep(0)

        old_world = runtime.get("world")
        if old_world and hasattr(old_world, "event_manager"):
            old_world.event_manager.close()

        new_world, new_sim, new_sects = load_game(target_path)
        new_world.runtime = runtime
        runtime.set_initialization_progress(phase_name="restoring_state", progress=70)
        await asyncio.sleep(0)

        new_world.existed_sects = new_sects
        runtime.set_world_and_sim(new_world, new_sim)
        runtime.set_current_save_path(target_path)
        runtime.set_run_config(
            getattr(
                new_world,
                "run_config_snapshot",
                _model_to_dict(get_settings_service().get_default_run_config()),
            )
        )
        runtime.set_initialization_progress(phase_name="finalizing", progress=90)
        await asyncio.sleep(0)
        runtime.finish_initialization(phase_name="complete")
        runtime.set_initialization_progress(progress=100)
        return {"status": "ok", "message": t("Game loaded")}

    try:
        return await runtime.run_mutation(_do_load)
    except HTTPException:
        raise
    except Exception as exc:
        import traceback

        traceback.print_exc()
        runtime.fail_initialization(str(exc))
        raise HTTPException(status_code=500, detail=t("Load failed: {error}", error=str(exc)))
