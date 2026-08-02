from __future__ import annotations
from typing import Any, TYPE_CHECKING
from .manager import _get_manager
if TYPE_CHECKING:
    from src.classes.core.world import World

def serialize_opportunities(world: "World") -> dict[str, Any]:
    return _get_manager(world).to_save_dict()


def load_opportunities(world: "World", data: dict[str, Any] | None) -> None:
    manager = _get_manager(world)
    manager.load_from_dict(data)
