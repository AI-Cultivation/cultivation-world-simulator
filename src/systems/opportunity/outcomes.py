from __future__ import annotations
import random
from typing import Any, TYPE_CHECKING
from src.classes.death import handle_death
from src.classes.death_reason import DeathReason, DeathType
from src.classes.items.auxiliary import Auxiliary, get_random_auxiliary_by_realm
from src.classes.items.weapon import Weapon, get_random_weapon_by_realm
from src.classes.story_event_service import StoryEventKind, StoryEventService
from src.i18n import t
from src.systems.cultivation import Realm
from src.systems.single_choice import ItemExchangeKind, ItemExchangeRequest, RejectMode, resolve_item_exchange
from src.utils.df import game_configs, get_float, get_int, get_str
from .config import _get_cfg_value, _weighted_choice_from_mapping
from .events import _event
from .models import OpportunityOutcome, OpportunityRecord, OpportunityTargetType
from .targeting import _resolve_target_avatar
if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar

def _pick_outcome() -> OpportunityOutcome:
    value = _weighted_choice_from_mapping(
        _get_cfg_value("outcome_weights", None),
        {
            OpportunityOutcome.EQUIPMENT.value: 35,
            OpportunityOutcome.BOON.value: 35,
            OpportunityOutcome.EMPTY.value: 20,
            OpportunityOutcome.INJURY.value: 10,
        },
    )
    try:
        return OpportunityOutcome(value)
    except ValueError:
        return OpportunityOutcome.EMPTY


def _next_realm(realm: Realm) -> Realm:
    realms = list(Realm)
    idx = realms.index(realm)
    return realms[min(idx + 1, len(realms) - 1)]


def _equipment_realm(avatar: "Avatar") -> Realm:
    return _next_realm(avatar.cultivation_progress.realm)


def _item_is_below_current_realm(item: object | None, avatar: "Avatar") -> bool:
    if item is None:
        return True
    realm = getattr(item, "realm", None)
    return bool(realm is not None and realm < avatar.cultivation_progress.realm)


def _pick_equipment(avatar: "Avatar") -> tuple[Weapon | Auxiliary | None, ItemExchangeKind | None]:
    target_realm = _equipment_realm(avatar)
    weapon_weight = 1.0
    auxiliary_weight = 1.0
    if _item_is_below_current_realm(getattr(avatar, "weapon", None), avatar):
        weapon_weight += 2.0
    if _item_is_below_current_realm(getattr(avatar, "auxiliary", None), avatar):
        auxiliary_weight += 2.0
    kind = random.choices(
        [ItemExchangeKind.WEAPON, ItemExchangeKind.AUXILIARY],
        weights=[weapon_weight, auxiliary_weight],
        k=1,
    )[0]
    if kind == ItemExchangeKind.WEAPON:
        return get_random_weapon_by_realm(target_realm), kind
    return get_random_auxiliary_by_realm(target_realm), kind


async def _apply_equipment(owner: "Avatar") -> tuple[str, bool]:
    from . import _pick_equipment as pick_equipment

    item, kind = pick_equipment(owner)
    if item is None or kind is None:
        return await _apply_boon(owner)
    intro = t(
        "{avatar_name} followed the opportunity and found an ancient treasure: {item_name}.",
        avatar_name=owner.name,
        item_name=item.name,
    )
    outcome = await resolve_item_exchange(
        ItemExchangeRequest(
            avatar=owner,
            new_item=item,
            kind=kind,
            scene_intro=intro,
            reject_mode=RejectMode.ABANDON_NEW,
            auto_accept_when_empty=True,
        )
    )
    return t(
        "{avatar_name} followed the opportunity and obtained {item_name}. {exchange_text}",
        avatar_name=owner.name,
        item_name=item.name,
        exchange_text=outcome.result_text,
    ), True


def _load_boon_records(owner: "Avatar") -> list[dict[str, Any]]:
    records = []
    for row in game_configs.get("opportunity_boon", []):
        min_realm = Realm.from_str(get_str(row, "min_realm", "QI_REFINEMENT"))
        max_realm = Realm.from_str(get_str(row, "max_realm", "NASCENT_SOUL"))
        if min_realm <= owner.cultivation_progress.realm <= max_realm:
            records.append(row)
    return records


async def _apply_boon(owner: "Avatar") -> tuple[str, bool]:
    from src.classes.effect import load_effect_from_str

    from . import _load_boon_records as load_boon_records

    records = load_boon_records(owner)
    if not records:
        return t("{avatar_name} followed the opportunity, but the spiritual trace faded away.", avatar_name=owner.name), False
    record = random.choices(records, weights=[max(0.0, get_float(row, "weight", 10.0)) for row in records], k=1)[0]
    effects = load_effect_from_str(get_str(record, "effects"))
    duration = get_int(record, "duration_months", 0)
    source = get_str(record, "source", "effect_source_opportunity")
    if duration > 0:
        owner.temporary_effects.append(
            {
                "source": source,
                "effects": effects,
                "start_month": int(owner.world.month_stamp),
                "duration": duration,
            }
        )
    else:
        owner.add_persistent_effect(source, effects)
    owner.recalc_effects()
    title = get_str(record, "title") or t("opportunity_boon")
    return t(
        "{avatar_name} followed the opportunity and gained a boon: {boon_title}.",
        avatar_name=owner.name,
        boon_title=title,
    ), True


def _apply_empty(owner: "Avatar") -> tuple[str, bool]:
    return t(
        "{avatar_name} followed the feeling, but only found the spiritual trace already gone.",
        avatar_name=owner.name,
    ), False


def _apply_injury(owner: "Avatar") -> tuple[str, bool]:
    from . import _get_cfg_value as get_cfg_value

    min_ratio = float(get_cfg_value("injury_min_hp_ratio", 0.2) or 0.2)
    max_ratio = float(get_cfg_value("injury_max_hp_ratio", 0.8) or 0.8)
    if max_ratio < min_ratio:
        min_ratio, max_ratio = max_ratio, min_ratio
    damage = max(1, int(owner.hp.max * random.uniform(min_ratio, max_ratio)))
    owner.hp.cur -= damage
    if owner.hp.cur <= 0:
        handle_death(owner.world, owner, DeathReason(DeathType.SERIOUS_INJURY))
        return t(
            "{avatar_name} followed the opportunity, but suffered backlash and perished.",
            avatar_name=owner.name,
        ), True
    return t(
        "{avatar_name} followed the opportunity, but suffered backlash and was injured for {damage} HP.",
        avatar_name=owner.name,
        damage=damage,
    ), False


async def _resolve_opportunity(owner: "Avatar", record: OpportunityRecord, related_avatars: list[str]) -> list[Event]:
    from . import _pick_outcome as pick_outcome

    outcome = pick_outcome()
    if outcome == OpportunityOutcome.EQUIPMENT:
        result_text, is_major = await _apply_equipment(owner)
    elif outcome == OpportunityOutcome.BOON:
        result_text, is_major = await _apply_boon(owner)
    elif outcome == OpportunityOutcome.INJURY:
        result_text, is_major = _apply_injury(owner)
    else:
        result_text, is_major = _apply_empty(owner)

    base_event = _event(owner, result_text, related_avatars=related_avatars, is_major=is_major)
    story_event = await StoryEventService.maybe_create_story(
        kind=StoryEventKind.OPPORTUNITY,
        month_stamp=owner.world.month_stamp,
        start_text=record.hint_text,
        result_text=result_text,
        actors=[owner, _resolve_target_avatar(owner.world, record.target_id) if record.target_type == OpportunityTargetType.AVATAR else None],
        related_avatar_ids=related_avatars,
        prompt=t("opportunity_story_prompt"),
        allow_relation_changes=False,
    )
    events = [base_event]
    if story_event is not None:
        events.append(story_event)
    return events
