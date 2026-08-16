import sys
import os

# 确保可以导入 src 模块，并尽早修复跨语言环境下的标准流编码。
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.server.encoding_runtime import configure_process_encoding

configure_process_encoding()

import asyncio
import uvicorn

from src.sim.simulator import Simulator
from src.classes.core.world import World
from src.classes.world_lore import WorldLoreManager
from src.classes.world_lore_snapshot import build_world_lore_snapshot
from src.systems.time import Month, Year, create_month_stamp
from src.server.assemblers.sect_detail import build_sect_detail
from src.server.assemblers.mortal_overview import build_mortal_overview
from src.server.assemblers.dynasty_detail import build_dynasty_detail
from src.server.assemblers.dynasty_overview import build_dynasty_overview
from src.server.services.avatar_adjustment import apply_avatar_adjustment, build_avatar_adjust_options
from src.server.services.avatar_control import (
    clear_long_term_objective_for_avatar,
    create_avatar_in_world,
    delete_avatar_in_world,
    set_long_term_objective_for_avatar,
    update_avatar_adjustment_in_world,
    update_avatar_portrait_in_world,
)
from src.server.services.custom_content_control import (
    create_custom_content as create_custom_content_command,
    generate_custom_content as generate_custom_content_command,
)
from src.server.services.custom_content_service import (
    create_custom_content_from_draft,
    generate_custom_content_draft,
)
from src.server.services.custom_goldfinger_service import (
    create_custom_goldfinger_from_draft,
    generate_custom_goldfinger_draft,
)
from src.server.services.game_lifecycle import reinit_game_lifecycle, start_game_lifecycle
from src.server.services.game_queries import (
    get_detail as get_detail_query,
    get_deceased_list,
    get_events_page,
    get_game_data as get_game_data_query,
    get_rankings as get_rankings_query,
    get_runtime_status,
    get_avatar_assets_meta as get_avatar_assets_meta_query,
    get_sect_relations as get_sect_relations_query,
    get_sect_territories_summary as get_sect_territories_summary_query,
    get_avatar_list as get_avatar_list_query,
    get_phenomena_list as get_phenomena_list_query,
    get_mortal_overview as get_mortal_overview_query,
    get_dynasty_overview as get_dynasty_overview_query,
    get_dynasty_detail as get_dynasty_detail_query,
    get_avatar_overview as get_avatar_overview_query,
    get_world_secret_meta as get_world_secret_meta_query,
    get_world_secret_overview as get_world_secret_overview_query,
    get_world_map,
    get_world_state,
)
from src.server.services.roleplay_service import (
    end_roleplay_conversation as end_roleplay_conversation_service,
    clear_roleplay_session as clear_roleplay_session_service,
    get_roleplay_session as get_roleplay_session_query,
    start_roleplay as start_roleplay_service,
    stop_roleplay as stop_roleplay_service,
    submit_roleplay_conversation_turn as submit_roleplay_conversation_turn_service,
    submit_roleplay_choice as submit_roleplay_choice_service,
    submit_roleplay_decision as submit_roleplay_decision_service,
)
from src.server.services.event_control import cleanup_events as cleanup_events_command
from src.server.api.public_v1 import (
    create_public_command_router,
    create_public_query_router,
)
from src.server.api.public_v1.command import GameStartRequest, LoadGameRequest
from src.server.api.settings import create_settings_router
from src.server.api.websocket import create_websocket_router
from src.server.services.save_load_control import (
    delete_save_file,
    list_saves_query,
    load_game_into_runtime,
    save_current_game,
)
from src.server.services.world_control import set_world_phenomenon
from src.run.load_map import load_cultivation_world_map
from src.run.map_presets import get_map_presets_query
from src.sim.avatar_init import make_avatars as _new_make_random, create_avatar_from_request
from src.systems.dynasty_generator import generate_dynasty, generate_emperor
from src.utils.config import CONFIG
from src.classes.appearance import get_appearance_by_level
from src.systems.cultivation import REALM_ORDER, Realm
from src.classes.alignment import Alignment
from src.classes.event import Event
from src.classes.long_term_objective import set_user_long_term_objective, clear_user_long_term_objective
from src.sim import save_game, list_saves, load_game, get_events_db_path
from src.utils.llm.client import register_llm_failure_handler, test_connectivity as _test_connectivity
from src.utils.llm.connectivity import check_llm_profile_connectivity
from src.run.data_loader import reload_all_static_data
from src.run.static_data_registry import build_static_game_data_registry
from src.classes.language import language_manager
from src.systems.sect_relations import compute_sect_relations
from src.i18n import t
from src.config import get_settings_service
from src.config.data_paths import get_data_paths
from src.i18n.locale_registry import uses_space_separated_names
from src.server.runtime import GameSessionRuntime, create_default_game_state
from src.server.host_runtime import (
    ConnectionManager,
    EndpointFilter,
    patch_sys_streams,
    trigger_process_shutdown,
)
from src.server.app_factory import HostDependencies, create_configured_app
from src.server.app_context import create_server_context
from src.server.services.game_command_service import GameCommandDependencies
from src.server.services.game_query_service import GameQueryDependencies
from src.server.services.roleplay_command_service import (
    RoleplayCommandDependencies,
    RoleplayCommandService,
)
from src.server.auto_save import trigger_auto_save as _trigger_auto_save
from src.server.bootstrap import (
    is_browser_auto_open_disabled,
    prepare_browser_target,
    print_startup_diagnostics,
    resolve_runtime_paths,
    resolve_server_binding,
)
from src.server.dev_runtime import start_frontend_dev_server, stop_frontend_dev_server
from src.server.host_app import (
    configure_routes_and_mounts,
    create_app,
    create_lifespan,
    create_llm_updated_handler,
    start_server,
)
from src.server.init_flow import perform_game_initialization
from src.server.init_runtime import (
    INIT_PHASE_NAMES,
    check_llm_connectivity,
    update_init_progress as _update_init_progress,
)
from src.server.loop_runtime import (
    build_auto_save_toast,
    build_avatar_updates,
    build_tick_state,
    run_game_loop_forever,
    should_trigger_auto_save,
)
from src.server.llm_runtime_handlers import create_llm_runtime_handlers
from src.server.runtime_hooks import create_runtime_hooks
from src.server.settings_handlers import SettingsServiceProxy, create_settings_handlers
from src.server.public_helpers import (
    apply_runtime_content_locale as _apply_runtime_content_locale,
    get_runtime_run_config as _get_runtime_run_config,
    model_to_dict as _model_to_dict,
    reset_runtime_custom_content,
    resolve_avatar_action_emoji,
    resolve_avatar_pic_id,
    scan_avatar_assets,
    validate_save_name,
)
from src.server.serialization import (
    serialize_active_domains,
    serialize_events_for_client,
    serialize_phenomenon,
)

# 全局游戏实例
game_instance = create_default_game_state()
runtime = GameSessionRuntime(game_instance)

# Cache for available avatar portrait asset IDs by race and gender.
AVATAR_ASSETS = {
    "human": {
        "male": [],
        "female": [],
    }
}

# 简易的命令行参数检查 (不使用 argparse 以避免冲突和时序问题)
IS_DEV_MODE = "--dev" in sys.argv


def apply_runtime_content_locale(lang_code: str) -> None:
    """兼容保留：按当前主运行时切换内容语言。"""
    _apply_runtime_content_locale(
        runtime=runtime,
        language_manager=language_manager,
        lang_code=lang_code,
    )


def get_current_config():
    """返回当前配置模块中的最新 CONFIG，避免 reload 后持有陈旧引用。"""
    from src.utils.config import CONFIG as current_config

    return current_config


def get_fallback_saves_dirs():
    """收集可能有效的存档目录，兼容 main.CONFIG 与 reload 后的新 CONFIG。"""
    candidates = []
    seen = set()

    for config_obj in (get_current_config(), CONFIG):
        saves_dir = getattr(getattr(config_obj, "paths", None), "saves", None)
        if saves_dir is None:
            continue
        key = str(saves_dir)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(saves_dir)

    return candidates


def is_idle_shutdown_enabled() -> bool:
    """Return whether the server should exit after the last client disconnects."""
    if IS_DEV_MODE:
        return False

    raw = os.environ.get("CWS_DISABLE_AUTO_SHUTDOWN", "")
    return raw.strip().lower() not in {"1", "true", "yes", "on"}

manager = ConnectionManager(runtime=runtime, is_idle_shutdown_enabled=is_idle_shutdown_enabled)
static_data = build_static_game_data_registry()
sects_by_id = static_data.sects_by_id
races_by_id = static_data.races_by_id
personas_by_id = static_data.personas_by_id
techniques_by_id = static_data.techniques_by_id
weapons_by_id = static_data.weapons_by_id
auxiliaries_by_id = static_data.auxiliaries_by_id
goldfingers_by_id = static_data.goldfingers_by_id
celestial_phenomena_by_id = static_data.celestial_phenomena_by_id

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

WEB_DIST_PATH, ASSETS_PATH = resolve_runtime_paths(
    server_file=__file__,
    is_frozen=getattr(sys, "frozen", False),
    executable=getattr(sys, "executable", None),
    meipass=getattr(sys, "_MEIPASS", None),
)

print(f"Runtime mode: {'Frozen/Packaged' if getattr(sys, 'frozen', False) else 'Development'}")
print(f"Assets path: {ASSETS_PATH}")
print(f"Web dist path: {WEB_DIST_PATH}")

query_dependencies = GameQueryDependencies(
    static_data=static_data,
    runtime=runtime,
    avatar_assets=AVATAR_ASSETS,
    config=CONFIG,
    model_to_dict=_model_to_dict,
    get_runtime_run_config=_get_runtime_run_config,
    resolve_avatar_action_emoji=resolve_avatar_action_emoji,
    resolve_avatar_pic_id=resolve_avatar_pic_id,
    serialize_events_for_client=serialize_events_for_client,
    serialize_active_domains=serialize_active_domains,
    serialize_phenomenon=serialize_phenomenon,
    get_world_state=get_world_state,
    get_world_map=get_world_map,
    get_map_presets_query=get_map_presets_query,
    get_runtime_status=get_runtime_status,
    get_events_page=get_events_page,
    get_game_data_query=get_game_data_query,
    realm_order=REALM_ORDER,
    alignment_enum=Alignment,
    get_detail_query=get_detail_query,
    build_sect_detail=build_sect_detail,
    language_manager=language_manager,
    build_avatar_adjust_options=build_avatar_adjust_options,
    get_avatar_assets_meta_query=get_avatar_assets_meta_query,
    get_avatar_list_query=get_avatar_list_query,
    get_phenomena_list_query=get_phenomena_list_query,
    get_sect_territories_summary_query=get_sect_territories_summary_query,
    list_saves_query=list_saves_query,
    get_list_saves=lambda: (
        lambda: next(
            (
                saves
                for saves in (
                    list_saves(saves_dir=saves_dir)
                    for saves_dir in get_fallback_saves_dirs()
                )
                if saves
            ),
            [],
        )
    ),
    get_rankings_query=get_rankings_query,
    get_sect_relations_query=get_sect_relations_query,
    compute_sect_relations=compute_sect_relations,
    get_mortal_overview_query=get_mortal_overview_query,
    build_mortal_overview=build_mortal_overview,
    get_dynasty_overview_query=get_dynasty_overview_query,
    build_dynasty_overview=build_dynasty_overview,
    get_dynasty_detail_query=get_dynasty_detail_query,
    build_dynasty_detail=build_dynasty_detail,
    get_avatar_overview_query=get_avatar_overview_query,
    get_deceased_list_query=get_deceased_list,
    get_roleplay_session_query=get_roleplay_session_query,
    get_world_secret_meta_query=get_world_secret_meta_query,
    get_world_secret_overview_query=get_world_secret_overview_query,
)
settings_service = SettingsServiceProxy(get_settings_service)

roleplay_command_service = RoleplayCommandService(RoleplayCommandDependencies(
    runtime=runtime,
    get_roleplay_session=get_roleplay_session_query,
    clear_roleplay_session=clear_roleplay_session_service,
    start_roleplay=start_roleplay_service,
    stop_roleplay=stop_roleplay_service,
    submit_roleplay_decision=submit_roleplay_decision_service,
    submit_roleplay_choice=submit_roleplay_choice_service,
    submit_roleplay_conversation_turn=submit_roleplay_conversation_turn_service,
    end_roleplay_conversation=end_roleplay_conversation_service,
))

command_dependencies = GameCommandDependencies(
    static_data=static_data,
    runtime=runtime,
    manager=manager,
    avatar_assets=AVATAR_ASSETS,
    assets_path=ASSETS_PATH,
    model_to_dict=_model_to_dict,
    validate_save_name=validate_save_name,
    get_init_game_async=lambda: init_game_async,
    get_apply_runtime_content_locale=lambda: apply_runtime_content_locale,
    scan_avatar_assets=scan_avatar_assets,
    start_game_lifecycle=start_game_lifecycle,
    reinit_game_lifecycle=reinit_game_lifecycle,
    cleanup_events_command=cleanup_events_command,
    set_world_phenomenon=set_world_phenomenon,
    create_avatar_in_world=create_avatar_in_world,
    create_avatar_from_request=create_avatar_from_request,
    uses_space_separated_names=uses_space_separated_names,
    language_manager=language_manager,
    alignment_from_str=Alignment.from_str,
    get_appearance_by_level=get_appearance_by_level,
    resolve_avatar_pic_id=resolve_avatar_pic_id,
    resolve_avatar_action_emoji=resolve_avatar_action_emoji,
    delete_avatar_in_world=delete_avatar_in_world,
    update_avatar_adjustment_in_world=update_avatar_adjustment_in_world,
    apply_avatar_adjustment=apply_avatar_adjustment,
    update_avatar_portrait_in_world=update_avatar_portrait_in_world,
    generate_custom_content_command=generate_custom_content_command,
    get_generate_custom_goldfinger_draft=lambda: generate_custom_goldfinger_draft,
    get_generate_custom_content_draft=lambda: generate_custom_content_draft,
    realm_from_str=Realm.from_str,
    create_custom_content_command=create_custom_content_command,
    create_custom_goldfinger_from_draft=create_custom_goldfinger_from_draft,
    create_custom_content_from_draft=create_custom_content_from_draft,
    set_long_term_objective_for_avatar=set_long_term_objective_for_avatar,
    clear_long_term_objective_for_avatar=clear_long_term_objective_for_avatar,
    set_user_long_term_objective=set_user_long_term_objective,
    clear_user_long_term_objective=clear_user_long_term_objective,
    save_current_game=save_current_game,
    save_game_impl=save_game,
    delete_save_file=delete_save_file,
    get_config=get_current_config,
    get_fallback_saves_dirs=get_fallback_saves_dirs,
    get_load_game_into_runtime=lambda: load_game_into_runtime,
    get_load_game=lambda: load_game,
    get_events_db_path=get_events_db_path,
    roleplay_commands=roleplay_command_service,
)

server_context = create_server_context(
    runtime=runtime,
    manager=manager,
    game_state=game_instance,
    avatar_assets=AVATAR_ASSETS,
    settings_service=settings_service,
    static_data=static_data,
    query_dependencies=query_dependencies,
    command_dependencies=command_dependencies,
    version=str(getattr(CONFIG.meta, "version", "")),
)
query_service = server_context.query_service
command_service = server_context.command_service


settings_handlers = create_settings_handlers(
    runtime=runtime,
    language_manager=language_manager,
    settings_service=settings_service,
    model_to_dict=_model_to_dict,
    apply_runtime_content_locale_impl=_apply_runtime_content_locale,
)
apply_runtime_content_locale = settings_handlers.apply_runtime_content_locale


def _get_logger():
    from src.run.log import get_logger

    return get_logger()


runtime_hooks = create_runtime_hooks(
    game_state=game_instance,
    runtime=runtime,
    manager=manager,
    avatar_assets=AVATAR_ASSETS,
    assets_path=ASSETS_PATH,
    static_data=static_data,
    config=CONFIG,
    update_init_progress_impl=_update_init_progress,
    perform_game_initialization=perform_game_initialization,
    trigger_auto_save_impl=_trigger_auto_save,
    run_game_loop_forever=run_game_loop_forever,
    build_avatar_updates=build_avatar_updates,
    build_tick_state=build_tick_state,
    should_trigger_auto_save=should_trigger_auto_save,
    build_auto_save_toast=build_auto_save_toast,
    reset_runtime_custom_content=reset_runtime_custom_content,
    reload_all_static_data=reload_all_static_data,
    scan_avatar_assets=scan_avatar_assets,
    load_cultivation_world_map=load_cultivation_world_map,
    get_events_db_path=get_events_db_path,
    get_runtime_run_config=_get_runtime_run_config,
    world_cls=World,
    create_month_stamp=create_month_stamp,
    year_cls=Year,
    month_enum=Month,
    generate_dynasty=generate_dynasty,
    generate_emperor=generate_emperor,
    event_cls=Event,
    translate=t,
    simulator_cls=Simulator,
    model_to_dict=_model_to_dict,
    world_lore_manager_cls=WorldLoreManager,
    build_world_lore_snapshot=build_world_lore_snapshot,
    make_random_avatars=_new_make_random,
    check_llm_connectivity=check_llm_connectivity,
    resolve_avatar_pic_id=resolve_avatar_pic_id,
    resolve_avatar_action_emoji=resolve_avatar_action_emoji,
    serialize_events_for_client=serialize_events_for_client,
    serialize_phenomenon=serialize_phenomenon,
    serialize_active_domains=serialize_active_domains,
    get_logger=_get_logger,
)
def update_init_progress(phase: int, phase_name: str = ""):
    """兼容保留：更新初始化进度。"""
    _update_init_progress(runtime=runtime, phase=phase, phase_name=phase_name)


async def init_game_async():
    """兼容保留：调用时读取 main 模块上的可 patch 依赖。"""
    await perform_game_initialization(
        runtime=runtime,
        avatar_assets=AVATAR_ASSETS,
        assets_path=ASSETS_PATH,
        config=CONFIG,
        update_init_progress=update_init_progress,
        reset_runtime_custom_content=reset_runtime_custom_content,
        reload_all_static_data=reload_all_static_data,
        scan_avatar_assets=scan_avatar_assets,
        load_cultivation_world_map=load_cultivation_world_map,
        get_events_db_path=get_events_db_path,
        get_runtime_run_config=_get_runtime_run_config,
        world_cls=World,
        create_month_stamp=create_month_stamp,
        year_cls=Year,
        month_enum=Month,
        generate_dynasty=generate_dynasty,
        generate_emperor=generate_emperor,
        event_cls=Event,
        translate=t,
        simulator_cls=Simulator,
        model_to_dict=_model_to_dict,
        world_lore_manager_cls=WorldLoreManager,
        build_world_lore_snapshot=build_world_lore_snapshot,
        sects_by_id=sects_by_id,
        make_random_avatars=_new_make_random,
        check_llm_connectivity=check_llm_connectivity,
    )


def trigger_auto_save(world, sim):
    """兼容保留：触发当前对局自动存档。"""
    _trigger_auto_save(world=world, sim=sim, sects_by_id=sects_by_id)


async def game_loop():
    """兼容保留：后台自动运行游戏循环。"""
    await run_game_loop_forever(
        game_instance=game_instance,
        runtime=runtime,
        manager=manager,
        build_avatar_updates=lambda: build_avatar_updates(
            world=runtime.get("world"),
            resolve_avatar_pic_id=lambda avatar: resolve_avatar_pic_id(
                avatar_assets=AVATAR_ASSETS,
                avatar=avatar,
            ),
            resolve_avatar_action_emoji=resolve_avatar_action_emoji,
        ),
        build_tick_state=lambda avatar_updates, events, world: build_tick_state(
            world=world,
            events=events,
            avatar_updates=avatar_updates,
            serialize_events_for_client=serialize_events_for_client,
            serialize_phenomenon=serialize_phenomenon,
            serialize_active_domains=serialize_active_domains,
            world_revision=runtime.world_revision,
        ),
        should_trigger_auto_save=lambda world: should_trigger_auto_save(world=world),
        trigger_auto_save=trigger_auto_save,
        build_auto_save_toast=build_auto_save_toast,
        get_logger=_get_logger,
    )

def get_settings() -> dict:
    """兼容保留：返回当前应用设置视图。"""
    return settings_handlers.get_settings()


def _patch_settings_model(req):
    updated = settings_service.patch_settings(req)
    next_locale = str(updated.new_game_defaults.content_locale)
    current_locale = str(language_manager)

    if next_locale and next_locale != current_locale:
        apply_runtime_content_locale(next_locale)

    run_config = game_instance.get("run_config")
    if isinstance(run_config, dict):
        run_config["content_locale"] = next_locale

    return updated


def patch_settings(req) -> dict:
    """兼容保留：更新应用设置。"""
    return _model_to_dict(_patch_settings_model(req))


def _reset_settings_model():
    updated = settings_service.reset_settings()
    next_locale = str(updated.new_game_defaults.content_locale)
    current_locale = str(language_manager)

    if next_locale and next_locale != current_locale:
        apply_runtime_content_locale(next_locale)

    run_config = game_instance.get("run_config")
    if isinstance(run_config, dict):
        run_config["content_locale"] = next_locale

    return updated


def reset_settings() -> dict:
    """兼容保留：重置应用设置，并同步全局语言。"""
    return _model_to_dict(_reset_settings_model())


async def start_game(req: GameStartRequest) -> dict:
    """兼容保留：启动游戏初始化流程。"""
    return await command_service.start_game(req)


async def api_load_game(req: LoadGameRequest) -> dict:
    """兼容保留：加载指定存档。"""
    return await command_service.load_game(filename=req.filename)


def get_runtime_run_config() -> object:
    """兼容保留：获取当前运行配置。"""
    return _get_runtime_run_config(runtime)


llm_handlers = create_llm_runtime_handlers(
    runtime=runtime,
    manager=manager,
    settings_service=settings_service,
    create_llm_updated_handler=create_llm_updated_handler,
    test_connectivity_impl=_test_connectivity,
)
def test_connectivity(config):
    """兼容保留：转发到底层 LLM 连通性测试。"""
    return _test_connectivity(config=config)


def test_llm_connection(req) -> dict:
    """兼容保留：使用当前保存的密钥测试 LLM 配置。"""
    profile, api_key, fast_api_key = settings_service.get_llm_test_payload(req)
    success, error_msg = check_llm_profile_connectivity(
        profile=profile,
        api_key=api_key,
        fast_api_key=fast_api_key,
        test_connectivity=lambda *, config: test_connectivity(config),
    )
    if success:
        return {"status": "ok", "message": "连接成功"}
    return {"status": "error", "message": error_msg}

handle_llm_updated = llm_handlers.handle_llm_updated
handle_global_llm_failure = llm_handlers.handle_global_llm_failure
llm_handlers.test_connectivity = lambda *, config: test_connectivity(config)
register_llm_failure_handler(handle_global_llm_failure)


def get_runtime_mode_label() -> str:
    return "Frozen/Packaged" if getattr(sys, "frozen", False) else "Development"

host_dependencies = HostDependencies(
    endpoint_filter=EndpointFilter,
    apply_runtime_content_locale=apply_runtime_content_locale,
    language_manager=language_manager,
    game_loop=game_loop,
    is_dev_mode=IS_DEV_MODE,
    project_root=PROJECT_ROOT,
    start_frontend_dev_server=start_frontend_dev_server,
    stop_frontend_dev_server=stop_frontend_dev_server,
    create_lifespan=create_lifespan,
    create_app=create_app,
    configure_routes_and_mounts=configure_routes_and_mounts,
    create_websocket_router=create_websocket_router,
    create_settings_router=create_settings_router,
    model_to_dict=_model_to_dict,
    patch_settings_model=_patch_settings_model,
    reset_settings_model=_reset_settings_model,
    llm_handlers=llm_handlers,
    create_public_query_router=create_public_query_router,
    create_public_command_router=create_public_command_router,
    trigger_process_shutdown=lambda: trigger_process_shutdown(is_dev_mode=IS_DEV_MODE),
    assets_path=ASSETS_PATH,
    web_dist_path=WEB_DIST_PATH,
)
app, lifespan = create_configured_app(context=server_context, host=host_dependencies)

def start():
    """启动服务的入口函数"""
    start_server(
        patch_sys_streams=patch_sys_streams,
        resolve_server_binding=resolve_server_binding,
        prepare_browser_target=prepare_browser_target,
        is_browser_auto_open_disabled=is_browser_auto_open_disabled,
        print_startup_diagnostics=print_startup_diagnostics,
        get_data_paths=get_data_paths,
        get_runtime_mode=get_runtime_mode_label,
        get_web_dist_path=lambda: WEB_DIST_PATH,
        get_assets_path=lambda: ASSETS_PATH,
        is_idle_shutdown_enabled=is_idle_shutdown_enabled,
        is_dev_mode=IS_DEV_MODE,
        app=app,
        uvicorn_module=uvicorn,
    )

if __name__ == "__main__":
    start()
