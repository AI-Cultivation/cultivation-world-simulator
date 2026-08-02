from __future__ import annotations
from typing import TYPE_CHECKING
from .models import OpportunityManager
if TYPE_CHECKING:
    from src.classes.core.world import World

def _get_manager(world: "World") -> OpportunityManager:
    manager = getattr(world, "opportunity_manager", None)
    if manager is None:
        manager = OpportunityManager()
        setattr(world, "opportunity_manager", manager)
    return manager
