from __future__ import annotations
import random
import uuid
from typing import TYPE_CHECKING
from src.classes.observe import get_avatar_observation_radius
from src.i18n import t
from .config import _duration_months, _get_cfg_value, _weighted_choice_from_mapping
from .models import OpportunityRecord, OpportunityTargetType, _can_int
if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar
    from src.classes.core.world import World
    from src.classes.environment.region import Region

def _relative_direction(from_x: int, from_y: int, to_x: int, to_y: int) -> str:
    dx = to_x - from_x
    dy = to_y - from_y
    horizontal = "east" if dx > 0 else "west"
    vertical = "south" if dy > 0 else "north"
    if abs(dx) >= abs(dy) * 2:
        return horizontal
    if abs(dy) >= abs(dx) * 2:
        return vertical
    if dx == 0 and dy == 0:
        return "nearby"
    return f"{vertical}_{horizontal}"


def _direction_label(direction: str) -> str:
    labels = {
        "north": t("north"),
        "south": t("south"),
        "east": t("east"),
        "west": t("west"),
        "nearby": t("nearby"),
        "north_east": t("northeast"),
        "north_west": t("northwest"),
        "south_east": t("southeast"),
        "south_west": t("southwest"),
    }
    return labels.get(direction, direction)


def _region_kind_label(region: "Region") -> str:
    from src.classes.environment.region import CityRegion, CultivateRegion, NormalRegion
    from src.classes.environment.sect_region import SectRegion

    if isinstance(region, CityRegion):
        return t("old city")
    if isinstance(region, SectRegion):
        return t("sect territory")
    if isinstance(region, CultivateRegion):
        return t("cave dwelling")
    if isinstance(region, NormalRegion):
        return t("wilderness place")
    return t("unknown place")


def _realm_hint(avatar: "Avatar") -> str:
    return str(getattr(getattr(avatar, "cultivation_progress", None), "realm", t("unknown realm")))


def _avatar_feature_hint(avatar: "Avatar") -> str:
    weapon = getattr(avatar, "weapon", None)
    if weapon is not None:
        weapon_type = getattr(weapon, "weapon_type", None)
        if weapon_type is not None:
            return t("{realm} {weapon_type} cultivator", realm=_realm_hint(avatar), weapon_type=str(weapon_type))
    sect = getattr(avatar, "sect", None)
    if sect is not None:
        return t("{realm} sect cultivator", realm=_realm_hint(avatar))
    return t("{realm} cultivator", realm=_realm_hint(avatar))


def _build_region_hint(avatar: "Avatar", region: "Region") -> str:
    center_x, center_y = getattr(region, "center_loc", (avatar.pos_x, avatar.pos_y))
    direction = _direction_label(_relative_direction(avatar.pos_x, avatar.pos_y, center_x, center_y))
    return t(
        "{avatar_name} felt a stir of fate, sensing a thread of opportunity tied to a {region_hint} in the {direction}.",
        avatar_name=avatar.name,
        region_hint=_region_kind_label(region),
        direction=direction,
    )


def _build_avatar_hint(avatar: "Avatar", target: "Avatar") -> str:
    direction = _direction_label(_relative_direction(avatar.pos_x, avatar.pos_y, target.pos_x, target.pos_y))
    return t(
        "{avatar_name} felt a stir of fate, sensing a thread of opportunity tied to a {target_hint} in the {direction}.",
        avatar_name=avatar.name,
        target_hint=_avatar_feature_hint(target),
        direction=direction,
    )


def _pick_region_target(avatar: "Avatar", world: "World") -> "Region | None":
    current_region_id = getattr(getattr(getattr(avatar, "tile", None), "region", None), "id", None)
    candidates = [
        region
        for region in getattr(getattr(world, "map", None), "regions", {}).values()
        if getattr(region, "id", None) is not None and getattr(region, "id", None) != current_region_id
    ]
    if not candidates:
        return None
    return random.choice(candidates)


def _pick_avatar_target(avatar: "Avatar", world: "World") -> "Avatar | None":
    candidates = [
        other
        for other in world.avatar_manager.get_living_avatars()
        if other.id != avatar.id and not getattr(other, "is_dead", False)
    ]
    if not candidates:
        return None
    return random.choice(candidates)


def _build_record(avatar: "Avatar", world: "World") -> OpportunityRecord | None:
    from . import _weighted_choice_from_mapping as choose_target_kind

    target_kind = choose_target_kind(
        _get_cfg_value("target_weights", None),
        {OpportunityTargetType.REGION.value: 70, OpportunityTargetType.AVATAR.value: 30},
    )
    if target_kind == OpportunityTargetType.AVATAR.value:
        target_avatar = _pick_avatar_target(avatar, world)
        if target_avatar is not None:
            current_month = int(world.month_stamp)
            return OpportunityRecord(
                id=str(uuid.uuid4()),
                avatar_id=str(avatar.id),
                target_type=OpportunityTargetType.AVATAR,
                target_id=str(target_avatar.id),
                hint_text=_build_avatar_hint(avatar, target_avatar),
                created_month=current_month,
                expires_month=current_month + _duration_months(),
            )

    target_region = _pick_region_target(avatar, world)
    if target_region is None:
        return None
    current_month = int(world.month_stamp)
    return OpportunityRecord(
        id=str(uuid.uuid4()),
        avatar_id=str(avatar.id),
        target_type=OpportunityTargetType.REGION,
        target_id=str(target_region.id),
        hint_text=_build_region_hint(avatar, target_region),
        created_month=current_month,
        expires_month=current_month + _duration_months(),
    )

def _resolve_target_avatar(world: "World", target_id: str) -> "Avatar | None":
    manager = getattr(world, "avatar_manager", None)
    if manager is None:
        return None
    if hasattr(manager, "get_avatar"):
        return manager.get_avatar(str(target_id))
    return getattr(manager, "avatars", {}).get(str(target_id))


def _is_avatar_observable(owner: "Avatar", target: "Avatar") -> bool:
    radius = get_avatar_observation_radius(owner)
    distance = abs(int(target.pos_x) - int(owner.pos_x)) + abs(int(target.pos_y) - int(owner.pos_y))
    return distance <= radius


def _target_is_reached(owner: "Avatar", record: OpportunityRecord) -> tuple[bool, list[str]]:
    world = owner.world
    if record.target_type == OpportunityTargetType.REGION:
        region = getattr(getattr(owner, "tile", None), "region", None)
        return bool(region is not None and str(getattr(region, "id", "")) == str(record.target_id)), [owner.id]

    target = _resolve_target_avatar(world, record.target_id)
    if target is None or getattr(target, "is_dead", False):
        return False, [owner.id]
    return _is_avatar_observable(owner, target), [owner.id, target.id]


def _target_is_invalid(world: "World", record: OpportunityRecord) -> bool:
    if record.target_type == OpportunityTargetType.REGION:
        regions = getattr(getattr(world, "map", None), "regions", {})
        return not (int(record.target_id) in regions if _can_int(record.target_id) else record.target_id in regions)
    target = _resolve_target_avatar(world, record.target_id)
    return target is None or getattr(target, "is_dead", False)
