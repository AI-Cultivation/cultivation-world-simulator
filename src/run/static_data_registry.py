from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class StaticGameDataRegistry:
    generation: int
    sects_by_id: dict[int, Any]
    races_by_id: dict[str, Any]
    personas_by_id: dict[int, Any]
    techniques_by_id: dict[int, Any]
    weapons_by_id: dict[int, Any]
    auxiliaries_by_id: dict[int, Any]
    goldfingers_by_id: dict[int, Any]
    celestial_phenomena_by_id: dict[int, Any]


def build_static_game_data_registry(*, generation: int = 0) -> StaticGameDataRegistry:
    from src.classes.celestial_phenomenon import celestial_phenomena_by_id
    from src.classes.core.sect import sects_by_id
    from src.classes.goldfinger import goldfingers_by_id
    from src.classes.items.auxiliary import auxiliaries_by_id
    from src.classes.items.weapon import weapons_by_id
    from src.classes.persona import personas_by_id
    from src.classes.race import races_by_id
    from src.classes.technique import techniques_by_id

    return StaticGameDataRegistry(
        generation=generation,
        sects_by_id=sects_by_id,
        races_by_id=races_by_id,
        personas_by_id=personas_by_id,
        techniques_by_id=techniques_by_id,
        weapons_by_id=weapons_by_id,
        auxiliaries_by_id=auxiliaries_by_id,
        goldfingers_by_id=goldfingers_by_id,
        celestial_phenomena_by_id=celestial_phenomena_by_id,
    )
