from __future__ import annotations

import inspect

from src.run.static_data_registry import build_static_game_data_registry
from src.server.app_context import ServerAppContext
from src.server.app_factory import create_configured_app
from src.server.llm_runtime_handlers import create_llm_runtime_handlers
from src.server.runtime_hooks import create_runtime_hooks
from src.server.services.game_command_service import GameCommandService
from src.server.services.game_query_service import GameQueryService
from src.server.settings_handlers import SettingsServiceProxy, create_settings_handlers
from src.sim.save.sections import registry
from src.sim.save.sections.load_restore import LOAD_SECTIONS, restore_loaded_game


def test_phase3_server_composition_entrypoints_exist():
    assert callable(create_configured_app)
    assert callable(create_runtime_hooks)
    assert callable(create_settings_handlers)
    assert callable(create_llm_runtime_handlers)
    from src.server.app_context import create_server_context

    assert callable(create_server_context)
    assert callable(GameQueryService.from_dependencies)
    assert callable(GameCommandService.from_dependencies)


def test_server_context_carries_static_data_and_services():
    annotations = ServerAppContext.__annotations__

    assert "static_data" in annotations
    assert "query_service" in annotations
    assert "command_service" in annotations


def test_save_registry_is_only_section_order_and_dispatch():
    source = inspect.getsource(registry)

    assert "SAVE_SECTIONS" in source
    assert "def dump_save_data" in source
    assert "class WorldSection" not in source
    assert "def restore_loaded_game" not in source
    assert registry.restore_loaded_game is restore_loaded_game


def test_load_restore_is_section_orchestration_only():
    import inspect
    import src.sim.save.sections.load_restore as load_restore

    source = inspect.getsource(load_restore)

    assert "LOAD_SECTIONS" in source
    assert [section.key for section in LOAD_SECTIONS] == [
        "run_config",
        "world_core",
        "sect_runtime",
        "avatars",
        "region_runtime",
        "membership",
        "events",
        "simulator",
    ]
    assert "Avatar.from_save_dict" not in source
    assert "load_opportunities" not in source


def test_settings_service_proxy_reads_current_service_each_call():
    calls = []

    class Service:
        def __init__(self, token):
            self.token = token

        def get_settings_view(self):
            return self.token

    def get_service():
        token = object()
        calls.append(token)
        return Service(token)

    proxy = SettingsServiceProxy(get_service)

    first = proxy.get_settings_view()
    second = proxy.get_settings_view()

    assert first is calls[0]
    assert second is calls[1]
    assert first is not second


def test_static_data_registry_is_shared_phase3_dependency_source():
    static_data = build_static_game_data_registry()

    assert static_data.sects_by_id
    assert static_data.celestial_phenomena_by_id


def test_main_uses_context_factory_without_legacy_exports():
    import inspect
    import src.server.main as main

    source = inspect.getsource(main)

    assert "create_server_context(" in source
    assert "_install_legacy_query_exports" not in source
    assert "_install_legacy_command_exports" not in source
    assert "from src.server.public_query_builders" not in source
    assert "from src.server.command_handlers" not in source


def test_avatar_init_package_exposes_phase2_boundaries():
    from src.sim.avatar_init import AvatarFactory, PopulationPlanner, create_avatar_from_request, make_avatars
    from src.sim.avatar_init.factory import AvatarFactory as FactoryFromModule
    from src.sim.avatar_init.planning import PopulationPlanner as PlannerFromModule
    from src.sim.avatar_init.request_parser import create_avatar_from_request as RequestFactory

    assert AvatarFactory is FactoryFromModule
    assert PopulationPlanner is PlannerFromModule
    assert create_avatar_from_request is RequestFactory
    assert callable(make_avatars)


def test_opportunity_package_exposes_phase2_boundaries():
    from src.systems.opportunity import OpportunityManager, OpportunityRecord, phase_check_opportunities
    from src.systems.opportunity.manager import OpportunityManager as ManagerFromModule
    from src.systems.opportunity.models import OpportunityRecord as RecordFromModule
    from src.systems.opportunity.phases import phase_check_opportunities as PhaseFromModule

    assert OpportunityManager is ManagerFromModule
    assert OpportunityRecord is RecordFromModule
    assert phase_check_opportunities is PhaseFromModule
