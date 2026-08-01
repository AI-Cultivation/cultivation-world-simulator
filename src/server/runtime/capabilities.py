from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.sim.runtime_capabilities import (
    DecisionBoundaryGateway,
    RuntimeDecisionBoundaryGateway,
    get_decision_boundary_gateway,
)


@dataclass(slots=True)
class CancellationToken:
    runtime: Any

    def is_cancelled(self) -> bool:
        return bool(getattr(self.runtime, "is_reset_requested", lambda: False)())


@dataclass(slots=True)
class RuntimePauseController:
    runtime: Any

    def set_roleplay_paused(self, paused: bool) -> None:
        self.runtime.set_roleplay_auto_paused(paused)

    def is_effectively_paused(self) -> bool:
        return bool(self.runtime.is_effectively_paused())


@dataclass(slots=True)
class RoleplayDecisionGateway(RuntimeDecisionBoundaryGateway):
    """Deprecated server alias for the domain-facing runtime gateway."""


def get_roleplay_gateway_from_world(world: Any) -> DecisionBoundaryGateway | None:
    return get_decision_boundary_gateway(world)
