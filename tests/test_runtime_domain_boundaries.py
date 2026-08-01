from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from src.classes.sect_diplomacy_state import SectDiplomacyState
from src.classes.war import STATUS_WAR
from src.server.runtime.session import GameSessionRuntime, create_default_game_state
from src.sim.runtime_capabilities import DecisionBoundaryResult, get_decision_boundary_gateway


def test_domain_and_simulation_modules_do_not_depend_on_server_implementation():
    root = Path(__file__).parents[1] / "src"
    offenders: list[str] = []
    for directory in (root / "classes", root / "sim"):
        for path in directory.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = getattr(node, "module", "") or ""
                if module.startswith("src.server"):
                    offenders.append(f"{path.relative_to(root)}:{node.lineno}:{module}")
    assert offenders == []


def test_runtime_gateway_marks_a_controlled_avatar_at_a_decision_boundary():
    class Avatar:
        id = "avatar-1"
        name = "Tester"
        current_action = None

        @staticmethod
        def has_plans() -> bool:
            return False

    avatar = Avatar()
    runtime = GameSessionRuntime(create_default_game_state())
    session = runtime.get_roleplay_session()
    session["controlled_avatar_id"] = avatar.id
    session["status"] = "observing"

    class Manager:
        @staticmethod
        def get_avatar(avatar_id: str):
            return avatar if avatar_id == avatar.id else None

    world = SimpleNamespace(avatar_manager=Manager(), runtime=runtime)
    gateway = get_decision_boundary_gateway(world)
    assert gateway is not None
    assert gateway.before_ai_decision(world) == DecisionBoundaryResult.WAITING_FOR_PLAYER
    assert runtime.get_roleplay_session()["status"] == "awaiting_decision"
    assert runtime.is_effectively_paused() is True


def test_sect_diplomacy_state_owns_war_and_relation_records():
    state = SectDiplomacyState()
    state.add_relation_modifier(
        sect_a_id=2,
        sect_b_id=1,
        delta=8,
        duration=12,
        reason="test",
        current_month=100,
    )
    state.declare_war(sect_a_id=1, sect_b_id=2, current_month=101, reason="test")

    assert state.relation_modifiers[0]["sect_a_id"] == 1
    assert state.get_war(1, 2)["status"] == STATUS_WAR
    assert state.diplomacy_breakdown(current_month=101, start_year=0)[(1, 2)][0]["reason"] == "WAR_STATE"
