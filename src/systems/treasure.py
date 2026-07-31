from __future__ import annotations

import random
import uuid
from collections.abc import Mapping
from typing import Any

from src.classes.event import Event
from src.classes.items.auxiliary import get_random_auxiliary_by_realm
from src.classes.items.weapon import get_random_weapon_by_realm
from src.classes.poi import TreasurePOI, build_equipment_payload
from src.classes.poi.treasure import TREASURE_ICON_IDS
from src.i18n import t
from src.systems.cultivation import Realm
from src.utils.config import CONFIG


TREASURE_REALMS = (
    Realm.Foundation_Establishment,
    Realm.Core_Formation,
    Realm.Nascent_Soul,
)
DEFAULT_SOURCE_WEIGHTS = {
    "ancient_cultivator_relic": 20,
    "spirit_vein_treasure": 20,
    "demon_king_relic": 15,
    "demonic_artifact": 15,
    "meteorite_relic": 15,
    "lost_sect_artifact": 15,
}


def get_treasure_config() -> Any:
    return getattr(getattr(CONFIG, "world", None), "treasure", None)


def _config_value(name: str, default: Any) -> Any:
    return getattr(get_treasure_config(), name, default)


def _active_treasures(world: Any) -> list[TreasurePOI]:
    manager = getattr(world, "poi_manager", None)
    if manager is None:
        return []
    current_month = int(world.month_stamp)
    return [
        poi for poi in manager.get_all_active(current_month)
        if isinstance(poi, TreasurePOI)
    ]


def _pick_realm() -> Realm:
    configured = list(_config_value("realms", [realm.value for realm in TREASURE_REALMS]) or [])
    realms = []
    for value in configured:
        realm = Realm.from_str(str(value))
        if realm in TREASURE_REALMS:
            realms.append(realm)
    return random.choice(realms or list(TREASURE_REALMS))


def _pick_source() -> str:
    source_weights = _config_value("source_weights", DEFAULT_SOURCE_WEIGHTS) or DEFAULT_SOURCE_WEIGHTS
    if isinstance(source_weights, Mapping):
        source_weights = dict(source_weights)
    elif hasattr(source_weights, "__dict__"):
        source_weights = dict(vars(source_weights))
    else:
        source_weights = DEFAULT_SOURCE_WEIGHTS
    sources = list(source_weights)
    weights = [max(0.0, float(source_weights[source])) for source in sources]
    if not sources:
        return "ancient_cultivator_relic"
    return random.choices(sources, weights=weights if any(weights) else None, k=1)[0]


def _pick_payload(realm: Realm) -> dict[str, Any] | None:
    factories = [get_random_weapon_by_realm, get_random_auxiliary_by_realm]
    random.shuffle(factories)
    for factory in factories:
        payload = build_equipment_payload(factory(realm))
        if payload is not None:
            return payload
    return None


def _pick_coordinate(world: Any) -> tuple[int, int] | None:
    game_map = getattr(world, "map", None)
    tiles = getattr(game_map, "tiles", {}) or {}
    occupied = {(poi.x, poi.y) for poi in _active_treasures(world)}
    candidates = [
        (int(x), int(y))
        for x, y in tiles.keys()
        if (int(x), int(y)) not in occupied and game_map.is_in_bounds(int(x), int(y))
    ]
    return random.choice(candidates) if candidates else None


def try_spawn_treasure(world: Any) -> TreasurePOI | None:
    manager = getattr(world, "poi_manager", None)
    if manager is None:
        return None
    if len(_active_treasures(world)) >= int(_config_value("max_active_count", 3)):
        return None
    if random.random() >= float(_config_value("spawn_probability_per_month", 0.005)):
        return None

    realm = _pick_realm()
    payload = _pick_payload(realm)
    coordinate = _pick_coordinate(world)
    if payload is None or coordinate is None:
        return None
    current_month = int(world.month_stamp)
    icon_key = random.choice(TREASURE_ICON_IDS)
    treasure = TreasurePOI(
        id=f"treasure:{current_month}:{uuid.uuid4().hex[:8]}",
        x=coordinate[0],
        y=coordinate[1],
        name=t("{realm} treasure", realm=str(realm)),
        desc=t("An ancient treasure shines with a restrained spiritual radiance."),
        created_month=current_month,
        expires_month=current_month + int(_config_value("duration_months", 240)),
        icon_key=icon_key,
        treasure_icon_id=icon_key,
        treasure_source=_pick_source(),
        treasure_realm=realm.value,
        treasure_payload=payload,
    )
    manager.add(treasure)
    return treasure


def phase_treasure_lifecycle(world: Any) -> list[Event]:
    manager = getattr(world, "poi_manager", None)
    if manager is None:
        return []
    events: list[Event] = []
    current_month = int(world.month_stamp)
    for treasure in manager.pop_expired(current_month, kind="treasure"):
        events.append(Event(
            world.month_stamp,
            t("The spiritual radiance of a treasure faded away before anyone could claim it."),
            is_major=False,
        ))

    treasure = try_spawn_treasure(world)
    if treasure is not None:
        events.append(Event(
            world.month_stamp,
            t("A strange spiritual radiance appeared somewhere in the world. A {realm} treasure seems to have emerged.", realm=str(Realm.from_str(treasure.treasure_realm))),
            is_major=False,
        ))
    return events
