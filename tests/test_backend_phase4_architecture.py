from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.config.providers import RunConfigProvider, StaticConfigProvider
from src.server.loop import TickPayloadBuilder
from src.server.runtime import GameSessionRuntime
from src.server.services.roleplay_state import RoleplayStatus
from src.server.services.roleplay_state_machine import require_status, set_observing
from src.sim.simulator_engine.phase_registry import get_simulation_phases
from src.sim.simulator_engine.phase_runner import SimulationPhaseRunner


def test_simulation_phase_runner_has_handler_for_every_registered_phase(base_world):
    simulator = SimpleNamespace(world=base_world)
    runner = SimulationPhaseRunner(simulator)

    for phase in get_simulation_phases():
        assert phase.handler_name
        assert callable(phase.handler)
        assert phase.handler_name in runner.handlers
        assert runner.handlers[phase.handler_name] is phase.handler


def test_roleplay_state_machine_rejects_illegal_status():
    session = {"status": RoleplayStatus.OBSERVING.value}

    with pytest.raises(HTTPException) as exc_info:
        require_status(session, RoleplayStatus.AWAITING_CHOICE, "bad transition")

    assert exc_info.value.status_code == 409


def test_roleplay_state_machine_sets_observing_and_clears_runtime_pause():
    runtime = GameSessionRuntime({"roleplay_auto_paused": True})

    set_observing(runtime, avatar_id="avatar-1", prompt_context={"a": 1})

    session = runtime.get_roleplay_session()
    assert session["controlled_avatar_id"] == "avatar-1"
    assert session["status"] == RoleplayStatus.OBSERVING.value
    assert session["pending_request"] is None
    assert runtime.get("roleplay_auto_paused") is False


def test_config_providers_read_current_config_and_run_snapshot(monkeypatch):
    config = SimpleNamespace(
        paths=SimpleNamespace(templates="templates"),
        world=SimpleNamespace(max_action_rounds_per_turn=7, can_interrupt_major_events=True),
    )
    provider = StaticConfigProvider(lambda: config)

    assert provider.templates_path == "templates"
    assert provider.max_action_rounds_per_turn() == 7
    assert provider.can_interrupt_major_events() is True

    world = SimpleNamespace(run_config_snapshot={"content_locale": "zh-CN"})
    assert RunConfigProvider(world).get("content_locale") == "zh-CN"
    assert RunConfigProvider(world).get("missing", "fallback") == "fallback"


def test_tick_payload_builder_combines_avatar_updates_and_tick_state():
    builder = TickPayloadBuilder(
        build_avatar_updates=lambda: [{"id": "a"}],
        build_tick_state=lambda avatar_updates, events, world: {
            "avatars": avatar_updates,
            "events": events,
            "world": world,
        },
    )

    assert builder.build(events=["e"], world="w") == {
        "avatars": [{"id": "a"}],
        "events": ["e"],
        "world": "w",
    }
