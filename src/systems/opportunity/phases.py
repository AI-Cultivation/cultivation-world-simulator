from __future__ import annotations
import random
from typing import TYPE_CHECKING
from src.classes.event import Event
from src.i18n import t
from .config import _cooldown_after_dissipated, _cooldown_after_resolved, _opportunity_probability
from .events import _event
from .manager import _get_manager
from .outcomes import _resolve_opportunity
from .targeting import _build_record, _target_is_invalid, _target_is_reached
if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar
    from src.classes.core.world import World

async def try_generate_opportunity(avatar: "Avatar", world: "World") -> list[Event]:
    manager = _get_manager(world)
    current_month = int(world.month_stamp)
    if manager.has_active(avatar.id):
        return []
    if manager.is_in_cooldown(avatar.id, current_month):
        return []
    if not getattr(avatar, "can_trigger_world_event", True):
        return []
    from . import _opportunity_probability as get_opportunity_probability

    prob = get_opportunity_probability(avatar)
    if prob <= 0.0 or random.random() >= prob:
        return []

    record = _build_record(avatar, world)
    if record is None:
        return []
    manager.add(record)
    return [_event(avatar, record.hint_text)]

async def phase_generate_opportunities(world: "World", living_avatars: list["Avatar"]) -> list[Event]:
    events: list[Event] = []
    for avatar in living_avatars:
        events.extend(await try_generate_opportunity(avatar, world))
    return events


async def phase_check_opportunities(world: "World", living_avatars: list["Avatar"]) -> list[Event]:
    manager = _get_manager(world)
    current_month = int(world.month_stamp)
    living_by_id = {str(avatar.id): avatar for avatar in living_avatars if not getattr(avatar, "is_dead", False)}
    events: list[Event] = []

    for avatar_id, record in list(manager.active.items()):
        owner = living_by_id.get(str(avatar_id))
        if owner is None:
            manager.clear(avatar_id)
            continue

        if current_month >= record.expires_month:
            manager.clear(avatar_id, cooldown_until=current_month + _cooldown_after_dissipated())
            events.append(
                _event(
                    owner,
                    t("{avatar_name}'s opportunity sense gradually faded away.", avatar_name=owner.name),
                )
            )
            continue

        if _target_is_invalid(world, record):
            manager.clear(avatar_id, cooldown_until=current_month + _cooldown_after_dissipated())
            events.append(
                _event(
                    owner,
                    t("{avatar_name}'s opportunity sense suddenly broke, leaving nowhere to seek.", avatar_name=owner.name),
                )
            )
            continue

        if current_month <= record.created_month:
            continue

        reached, related_avatars = _target_is_reached(owner, record)
        if not reached:
            continue

        manager.clear(avatar_id, cooldown_until=current_month + _cooldown_after_resolved())
        events.extend(await _resolve_opportunity(owner, record, related_avatars))

    return events
