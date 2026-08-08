from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.server.mounts import mount_static_apps


def create_lifespan(
    *,
    endpoint_filter,
    get_settings_view,
    apply_runtime_content_locale,
    language_manager,
    game_loop,
    is_dev_mode: bool,
    project_root: str,
    start_frontend_dev_server,
    stop_frontend_dev_server,
):
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        logging.getLogger("uvicorn.access").addFilter(endpoint_filter())

        settings = get_settings_view()
        apply_runtime_content_locale(settings.new_game_defaults.content_locale)
        print(f"Current Language: {language_manager}")
        print("Server started, waiting for start game command...")

        asyncio.create_task(game_loop())

        npm_process = None
        if is_dev_mode:
            print("🚀 Starting Development Mode (Dev Mode)...")
            try:
                npm_process = start_frontend_dev_server(project_root=project_root)
            except Exception as exc:
                print(f"Failed to start frontend server: {exc}")

        yield

        stop_frontend_dev_server(npm_process)

    return lifespan


def create_llm_updated_handler(*, runtime, manager):
    async def handle_llm_updated() -> None:
        failed, _ = runtime.get_llm_failure_state()
        if not failed:
            return

        print("Detected previous LLM connection failure, resuming Simulator...")
        runtime.set_llm_check_state(failed=False, error_message="")
        runtime.set_paused(False)
        print("Simulator resumed")
        await manager.broadcast(
            {
                "type": "game_reinitialized",
                "message": "LLM 配置成功，游戏已恢复运行",
            }
        )

    return handle_llm_updated


def create_app(*, lifespan) -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


def configure_routes_and_mounts(
    *,
    app,
    context=None,
    create_websocket_router,
    manager=None,
    create_settings_router,
    model_to_dict,
    get_settings_view,
    patch_settings,
    reset_settings,
    get_llm_view,
    get_llm_runtime_config,
    get_llm_failure_state,
    get_llm_test_payload,
    test_connectivity,
    update_llm,
    on_llm_updated,
    create_public_query_router,
    build_runtime_status=None,
    build_world_state=None,
    build_world_map=None,
    build_map_presets=None,
    build_current_run=None,
    build_events_page=None,
    build_rankings=None,
    build_sect_relations=None,
    build_game_data=None,
    build_avatar_adjust_options=None,
    build_avatar_meta=None,
    build_avatar_list=None,
    build_phenomena=None,
    build_sect_territories=None,
    build_mortal_overview=None,
    build_dynasty_overview=None,
    build_dynasty_detail=None,
    build_avatar_overview=None,
    build_saves=None,
    build_detail=None,
    build_deceased_list=None,
    build_roleplay_session=None,
    build_world_secret_meta=None,
    build_world_secret_overview=None,
    create_public_command_router,
    run_start_game=None,
    run_reinit_game=None,
    run_reset_game=None,
    trigger_process_shutdown,
    run_pause_game=None,
    run_pause_game_and_drain=None,
    run_resume_game=None,
    run_set_long_term_objective=None,
    run_clear_long_term_objective=None,
    run_create_avatar=None,
    run_delete_avatar=None,
    run_update_avatar_adjustment=None,
    run_update_avatar_portrait=None,
    run_generate_custom_content=None,
    run_create_custom_content=None,
    run_set_phenomenon=None,
    run_cleanup_events=None,
    run_save_game=None,
    run_delete_save=None,
    run_load_game=None,
    run_start_roleplay=None,
    run_stop_roleplay=None,
    run_submit_roleplay_decision=None,
    run_submit_roleplay_choice=None,
    run_send_roleplay_conversation=None,
    run_end_roleplay_conversation=None,
    assets_path: str,
    web_dist_path: str,
    is_dev_mode: bool,
    version: str = "",
):
    manager = manager if manager is not None else context.manager
    query_service = getattr(context, "query_service", None) if context is not None else None
    command_service = getattr(context, "command_service", None) if context is not None else None
    if not version and context is not None:
        version = getattr(context, "version", "")

    @app.get("/api/health")
    def health():
        return {
            "ok": True,
            "status": "ready",
            "version": version,
        }

    app.include_router(create_websocket_router(manager=manager, runtime=context.runtime))

    app.include_router(
        create_settings_router(
            model_to_dict=model_to_dict,
            get_settings_view=get_settings_view,
            patch_settings=patch_settings,
            reset_settings=reset_settings,
            get_llm_view=get_llm_view,
            get_llm_runtime_config=get_llm_runtime_config,
            get_llm_failure_state=get_llm_failure_state,
            get_llm_test_payload=get_llm_test_payload,
            test_connectivity=test_connectivity,
            update_llm=update_llm,
            on_llm_updated=on_llm_updated,
        )
    )

    app.include_router(
        create_public_query_router(
            query_service=query_service,
            build_runtime_status=build_runtime_status,
            build_world_state=build_world_state,
            build_world_map=build_world_map,
            build_map_presets=build_map_presets,
            build_current_run=build_current_run,
            build_events_page=build_events_page,
            build_rankings=build_rankings,
            build_sect_relations=build_sect_relations,
            build_game_data=build_game_data,
            build_avatar_adjust_options=build_avatar_adjust_options,
            build_avatar_meta=build_avatar_meta,
            build_avatar_list=build_avatar_list,
            build_phenomena=build_phenomena,
            build_sect_territories=build_sect_territories,
            build_mortal_overview=build_mortal_overview,
            build_dynasty_overview=build_dynasty_overview,
            build_dynasty_detail=build_dynasty_detail,
            build_avatar_overview=build_avatar_overview,
            build_saves=build_saves,
            build_detail=build_detail,
            build_deceased_list=build_deceased_list,
            build_roleplay_session=build_roleplay_session,
            build_world_secret_meta=build_world_secret_meta,
            build_world_secret_overview=build_world_secret_overview,
        )
    )

    app.include_router(
        create_public_command_router(
            command_service=command_service,
            run_start_game=run_start_game,
            run_reinit_game=run_reinit_game,
            run_reset_game=run_reset_game,
            trigger_process_shutdown=trigger_process_shutdown,
            run_pause_game=run_pause_game,
            run_pause_game_and_drain=run_pause_game_and_drain,
            run_resume_game=run_resume_game,
            run_set_long_term_objective=run_set_long_term_objective,
            run_clear_long_term_objective=run_clear_long_term_objective,
            run_create_avatar=run_create_avatar,
            run_delete_avatar=run_delete_avatar,
            run_update_avatar_adjustment=run_update_avatar_adjustment,
            run_update_avatar_portrait=run_update_avatar_portrait,
            run_generate_custom_content=run_generate_custom_content,
            run_create_custom_content=run_create_custom_content,
            run_set_phenomenon=run_set_phenomenon,
            run_cleanup_events=run_cleanup_events,
            run_save_game=run_save_game,
            run_delete_save=run_delete_save,
            run_load_game=run_load_game,
            run_start_roleplay=run_start_roleplay,
            run_stop_roleplay=run_stop_roleplay,
            run_submit_roleplay_decision=run_submit_roleplay_decision,
            run_submit_roleplay_choice=run_submit_roleplay_choice,
            run_send_roleplay_conversation=run_send_roleplay_conversation,
            run_end_roleplay_conversation=run_end_roleplay_conversation,
        )
    )

    mount_static_apps(
        app,
        assets_path=assets_path,
        web_dist_path=web_dist_path,
        is_dev_mode=is_dev_mode,
    )


def start_server(
    *,
    patch_sys_streams,
    resolve_server_binding,
    prepare_browser_target,
    is_browser_auto_open_disabled,
    print_startup_diagnostics,
    get_data_paths,
    get_runtime_mode,
    get_web_dist_path,
    get_assets_path,
    is_idle_shutdown_enabled,
    is_dev_mode: bool,
    app,
    uvicorn_module,
):
    patch_sys_streams()
    import webbrowser

    host, port = resolve_server_binding()
    target_url = prepare_browser_target(is_dev_mode=is_dev_mode, host=host, port=port)
    browser_disabled = is_browser_auto_open_disabled()

    try:
        print_startup_diagnostics(
            runtime_mode=get_runtime_mode(),
            data_paths=get_data_paths(),
            host=host,
            port=port,
            web_dist_path=get_web_dist_path(),
            assets_path=get_assets_path(),
            browser_disabled=browser_disabled,
            idle_shutdown_enabled=is_idle_shutdown_enabled(),
        )
    except Exception as exc:
        print(f"Warning: failed to print startup diagnostics: {exc}")

    if browser_disabled:
        print(f"Browser auto open disabled. Web UI available at {target_url}")
    else:
        print(f"Opening browser at {target_url}...")
        try:
            webbrowser.open(target_url)
        except Exception as exc:
            print(f"Failed to open browser: {exc}")

    uvicorn_module.run(app, host=host, port=port, log_level="info")
