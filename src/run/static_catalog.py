"""Single lifecycle owner for reloadable static game definitions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.run.static_data_registry import StaticGameDataRegistry, build_static_game_data_registry


@dataclass(frozen=True, slots=True)
class RebindReport:
    avatars_seen: int
    missing_references: tuple[str, ...]


class StaticCatalogService:
    """Reload static definitions atomically from the application's perspective."""

    def __init__(self) -> None:
        self._generation = 0
        self._current = build_static_game_data_registry(generation=self._generation)

    def current(self) -> StaticGameDataRegistry:
        return self._current

    def reload(self) -> StaticGameDataRegistry:
        # Imports are intentionally local: loading a catalog must not make
        # import time itself a reload boundary.
        from src.classes.animal import reload as reload_animals
        from src.classes.celestial_phenomenon import reload as reload_phenomena
        from src.classes.core.dynasty import reload as reload_dynasties
        from src.classes.core.sect import reload as reload_sects
        from src.classes.environment.lode import reload as reload_lodes
        from src.classes.environment.plant import reload as reload_plants
        from src.classes.goldfinger import reload as reload_goldfingers
        from src.classes.items.auxiliary import reload as reload_auxiliaries
        from src.classes.items.elixir import reload as reload_elixirs
        from src.classes.items.registry import ItemRegistry
        from src.classes.items.weapon import reload as reload_weapons
        from src.classes.material import reload as reload_materials
        from src.classes.persona import reload as reload_personas
        from src.classes.race import reload as reload_races
        from src.classes.technique import reload as reload_techniques
        from src.utils.name_generator import reload as reload_names

        ItemRegistry.reset()
        for loader in (
            reload_sects, reload_dynasties, reload_techniques, reload_weapons,
            reload_auxiliaries, reload_personas, reload_goldfingers, reload_races,
            reload_phenomena, reload_names, reload_animals, reload_plants,
            reload_materials, reload_lodes, reload_elixirs,
        ):
            loader()
        self._generation += 1
        self._current = build_static_game_data_registry(generation=self._generation)
        return self._current

    def rebind_world(self, world: Any) -> RebindReport:
        if not world or not getattr(world, "avatar_manager", None):
            return RebindReport(avatars_seen=0, missing_references=())
        catalog = self._current
        manager = world.avatar_manager
        avatars = list(getattr(manager, "avatars", {}).values())
        avatars.extend(list(getattr(manager, "dead_avatars", {}).values()))
        missing: list[str] = []
        for avatar in avatars:
            sect = getattr(avatar, "sect", None)
            if sect is not None:
                replacement = catalog.sects_by_id.get(sect.id)
                if replacement is None:
                    missing.append(f"sect:{sect.id}")
                else:
                    avatar.sect = replacement
                    replacement.add_member(avatar)
            for attr, registry in (
                ("technique", catalog.techniques_by_id),
                ("weapon", catalog.weapons_by_id),
                ("auxiliary", catalog.auxiliaries_by_id),
                ("goldfinger", catalog.goldfingers_by_id),
            ):
                value = getattr(avatar, attr, None)
                if value is not None and (replacement := registry.get(value.id)) is not None:
                    setattr(avatar, attr, replacement)
            if getattr(avatar, "personas", None):
                avatar.personas = [catalog.personas_by_id.get(item.id, item) for item in avatar.personas]
            race = getattr(avatar, "race", None)
            if race is not None:
                race_id = getattr(race, "id", race)
                avatar.race = catalog.races_by_id.get(str(race_id), catalog.races_by_id.get("human"))
        phenomenon = getattr(world, "current_phenomenon", None)
        if phenomenon is not None:
            world.current_phenomenon = catalog.celestial_phenomena_by_id.get(phenomenon.id, phenomenon)
        return RebindReport(avatars_seen=len(avatars), missing_references=tuple(missing))


static_catalog = StaticCatalogService()
