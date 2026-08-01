from __future__ import annotations

from typing import Any, Callable


def create_configured_app(
    *,
    context: Any,
    endpoint_filter: type,
    apply_runtime_content_locale: Callable[[str], None],
    language_manager: Any,
    game_loop: Callable[..., Any],
    is_dev_mode: bool,
    project_root: str,
    start_frontend_dev_server: Callable[..., Any],
    stop_frontend_dev_server: Callable[..., Any],
    create_lifespan: Callable[..., Any],
    create_app: Callable[..., Any],
    configure_routes_and_mounts: Callable[..., None],
    create_websocket_router: Callable[..., Any],
    create_settings_router: Callable[..., Any],
    model_to_dict: Callable[[Any], dict],
    patch_settings_model: Callable[[Any], Any],
    reset_settings_model: Callable[[], Any],
    llm_handlers: Any,
    create_public_query_router: Callable[..., Any],
    create_public_command_router: Callable[..., Any],
    trigger_process_shutdown: Callable[[], None],
    assets_path: str,
    web_dist_path: str,
):
    lifespan = create_lifespan(
        endpoint_filter=endpoint_filter,
        get_settings_view=context.settings_service.get_settings_view,
        apply_runtime_content_locale=apply_runtime_content_locale,
        game_instance=context.game_state,
        language_manager=language_manager,
        game_loop=game_loop,
        is_dev_mode=is_dev_mode,
        project_root=project_root,
        start_frontend_dev_server=start_frontend_dev_server,
        stop_frontend_dev_server=stop_frontend_dev_server,
    )
    app = create_app(lifespan=lifespan)
    configure_routes_and_mounts(
        app=app,
        context=context,
        create_websocket_router=create_websocket_router,
        create_settings_router=create_settings_router,
        model_to_dict=model_to_dict,
        get_settings_view=context.settings_service.get_settings_view,
        patch_settings=patch_settings_model,
        reset_settings=reset_settings_model,
        get_llm_view=context.settings_service.get_llm_view,
        get_llm_runtime_config=context.settings_service.get_llm_runtime_config,
        get_llm_failure_state=context.runtime.get_llm_failure_state,
        get_llm_test_payload=context.settings_service.get_llm_test_payload,
        test_connectivity=llm_handlers.test_connectivity,
        update_llm=context.settings_service.update_llm,
        on_llm_updated=llm_handlers.handle_llm_updated,
        create_public_query_router=create_public_query_router,
        create_public_command_router=create_public_command_router,
        trigger_process_shutdown=trigger_process_shutdown,
        assets_path=assets_path,
        web_dist_path=web_dist_path,
        is_dev_mode=is_dev_mode,
    )
    return app, lifespan
