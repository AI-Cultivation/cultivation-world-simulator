from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from src.classes.core.world import World
from src.classes.event import Event
from src.classes.sect_effect import EXTRA_INCOME_PER_TILE
from src.classes.language import language_manager
from src.run.log import get_logger
from src.systems.sect_relations import SectRelationReason
from src.utils.config import CONFIG
from src.utils.df import game_configs, get_float, get_int, get_str
from src.utils.llm.client import call_llm_with_template
from src.utils.llm.runtime_mode import is_test_mode_enabled
from src.utils.llm.config import LLMMode
from src.i18n import t


EVENT_TYPE_RELATION_UP = "relation_up"
EVENT_TYPE_RELATION_DOWN = "relation_down"
EVENT_TYPE_MAGIC_STONE_UP = "magic_stone_up"
EVENT_TYPE_MAGIC_STONE_DOWN = "magic_stone_down"
EVENT_TYPE_INCOME_UP = "income_up"
EVENT_TYPE_INCOME_DOWN = "income_down"

RELATION_EVENT_TYPES = {EVENT_TYPE_RELATION_UP, EVENT_TYPE_RELATION_DOWN}
MAGIC_STONE_EVENT_TYPES = {EVENT_TYPE_MAGIC_STONE_UP, EVENT_TYPE_MAGIC_STONE_DOWN}
INCOME_EVENT_TYPES = {EVENT_TYPE_INCOME_UP, EVENT_TYPE_INCOME_DOWN}
ALL_EVENT_TYPES = RELATION_EVENT_TYPES | MAGIC_STONE_EVENT_TYPES | INCOME_EVENT_TYPES


@dataclass(frozen=True)
class SectRandomEventConfig:
    event_type: str
    value: float
    duration_months: int


def _pick_record(records: list[dict]) -> Optional[dict]:
    if not records:
        return None
    weights = [max(0.0, get_float(row, "weight", 1.0)) for row in records]
    if not any(weights):
        return random.choice(records)
    return random.choices(records, weights=weights, k=1)[0]


def _collect_active_sects(world: World) -> list:
    sects = getattr(world, "existed_sects", []) or []
    return [s for s in sects if getattr(s, "is_active", True)]


def _parse_event_config(record: dict) -> SectRandomEventConfig:
    legacy_relation_delta = get_str(record, "relation_delta")
    if legacy_relation_delta and legacy_relation_delta not in {"0", "0.0"}:
        raise ValueError(
            "Legacy field relation_delta is not supported in sect_random_event.csv. "
            "Use event_type=relation_up/relation_down with value instead."
        )

    event_type = get_str(record, "event_type").lower()
    if event_type not in ALL_EVENT_TYPES:
        raise ValueError(f"Invalid sect_random_event event_type={event_type!r}.")

    value = abs(get_float(record, "value", 0.0))
    if value <= 0:
        raise ValueError(f"Invalid sect_random_event value={value}, must be > 0.")

    duration = get_int(record, "duration_months", 0)
    if event_type in RELATION_EVENT_TYPES or event_type in INCOME_EVENT_TYPES:
        if duration <= 0:
            raise ValueError(
                f"Invalid sect_random_event duration_months={duration}, "
                f"event_type={event_type} requires duration_months > 0."
            )

    return SectRandomEventConfig(
        event_type=event_type,
        value=value,
        duration_months=duration,
    )


def _pick_participants(active_sects: list, event_type: str):
    if event_type in RELATION_EVENT_TYPES:
        if len(active_sects) < 2:
            return None, None
        return random.sample(active_sects, 2)
    if len(active_sects) < 1:
        return None, None
    return random.choice(active_sects), None


def _lang() -> str:
    return str(language_manager)


async def _generate_reason_fragment(
    *,
    event_type: str,
    sect_a_name: str,
    sect_b_name: str,
    sect_a_detail: str,
    sect_b_detail: str,
    value: float,
    duration_months: int,
) -> Optional[str]:
    if is_test_mode_enabled():
        return None

    infos = {
        "language": _lang(),
        "event_type": event_type,
        "sect_a_name": sect_a_name,
        "sect_b_name": sect_b_name,
        "sect_a_detail": sect_a_detail,
        "sect_b_detail": sect_b_detail,
        "value": value,
        "duration_months": duration_months,
        "target_chars": int(getattr(CONFIG.sect, "random_event_reason_max_chars", 20)),
    }

    try:
        result = await call_llm_with_template(
            template_path=CONFIG.paths.templates / "sect_random_event.txt",
            infos=infos,
            mode=LLMMode.FAST,
        )
    except Exception as exc:
        get_logger().logger.error(
            "Failed to generate sect random event reason for sects %s and %s: %s",
            sect_a_name,
            sect_b_name,
            exc,
        )
        return None

    if not isinstance(result, dict):
        get_logger().logger.error(
            "Invalid sect random event reason payload type for sects %s and %s: %s",
            sect_a_name,
            sect_b_name,
            type(result).__name__,
        )
        return None

    reason = str(result.get("reason_fragment", "")).strip()
    if not reason:
        get_logger().logger.error(
            "Empty sect random event reason for sects %s and %s.",
            sect_a_name,
            sect_b_name,
        )
        return None
    return reason


def _fmt_int(v: float) -> int:
    return int(round(v))


def _build_event_text(
    *,
    event_type: str,
    sect_a_name: str,
    sect_b_name: Optional[str],
    reason_fragment: str,
    value: float,
    duration_months: int,
) -> str:
    value_int = _fmt_int(value)
    value_str = f"{value:.1f}"

    if event_type == EVENT_TYPE_RELATION_UP:
        return t(
            "Because {reason_fragment}, relations between {sect_a_name} and {sect_b_name} improved (+{value_int} for {duration_months} months).",
            reason_fragment=reason_fragment,
            sect_a_name=sect_a_name,
            sect_b_name=sect_b_name or "",
            value_int=value_int,
            duration_months=duration_months,
        )
    if event_type == EVENT_TYPE_RELATION_DOWN:
        return t(
            "Because {reason_fragment}, relations between {sect_a_name} and {sect_b_name} worsened (-{value_int} for {duration_months} months).",
            reason_fragment=reason_fragment,
            sect_a_name=sect_a_name,
            sect_b_name=sect_b_name or "",
            value_int=value_int,
            duration_months=duration_months,
        )
    if event_type == EVENT_TYPE_MAGIC_STONE_UP:
        return t(
            "Because {reason_fragment}, {sect_a_name} gained +{value_int} magic stones.",
            reason_fragment=reason_fragment,
            sect_a_name=sect_a_name,
            value_int=value_int,
        )
    if event_type == EVENT_TYPE_MAGIC_STONE_DOWN:
        return t(
            "Because {reason_fragment}, {sect_a_name} lost -{value_int} magic stones.",
            reason_fragment=reason_fragment,
            sect_a_name=sect_a_name,
            value_int=value_int,
        )
    if event_type == EVENT_TYPE_INCOME_UP:
        return t(
            "Because {reason_fragment}, {sect_a_name} gained +{value} extra income per tile for {duration_months} months.",
            reason_fragment=reason_fragment,
            sect_a_name=sect_a_name,
            value=value_str,
            duration_months=duration_months,
        )
    return t(
        "Because {reason_fragment}, {sect_a_name} suffered -{value} income per tile for {duration_months} months.",
        reason_fragment=reason_fragment,
        sect_a_name=sect_a_name,
        value=value_str,
        duration_months=duration_months,
    )


async def try_trigger_sect_random_event(world: World) -> Optional[Event]:
    world.prune_expired_sect_relation_modifiers(int(world.month_stamp))

    base_prob = float(getattr(CONFIG.sect, "random_event_prob_per_month", 0.0))
    if base_prob <= 0.0:
        return None
    if random.random() >= base_prob:
        return None

    active_sects = _collect_active_sects(world)
    if not active_sects:
        return None

    record = _pick_record(game_configs.get("sect_random_event", []))
    if not record:
        return None

    cfg = _parse_event_config(record)

    sect_a, sect_b = _pick_participants(active_sects, cfg.event_type)
    if sect_a is None:
        return None
    if cfg.event_type in RELATION_EVENT_TYPES and sect_b is None:
        return None

    reason_fragment = await _generate_reason_fragment(
        event_type=cfg.event_type,
        sect_a_name=sect_a.name,
        sect_b_name=sect_b.name if sect_b else "",
        sect_a_detail=sect_a.get_detailed_info(),
        sect_b_detail=sect_b.get_detailed_info() if sect_b else "",
        value=cfg.value,
        duration_months=cfg.duration_months,
    )
    if not reason_fragment:
        return None

    if cfg.event_type == EVENT_TYPE_RELATION_UP and sect_b is not None:
        world.add_sect_relation_modifier(
            sect_a_id=sect_a.id,
            sect_b_id=sect_b.id,
            delta=_fmt_int(cfg.value),
            duration=cfg.duration_months,
            reason=SectRelationReason.RANDOM_EVENT.value,
            meta={"cause": reason_fragment},
        )
    elif cfg.event_type == EVENT_TYPE_RELATION_DOWN and sect_b is not None:
        world.add_sect_relation_modifier(
            sect_a_id=sect_a.id,
            sect_b_id=sect_b.id,
            delta=-_fmt_int(cfg.value),
            duration=cfg.duration_months,
            reason=SectRelationReason.RANDOM_EVENT.value,
            meta={"cause": reason_fragment},
        )
    elif cfg.event_type == EVENT_TYPE_MAGIC_STONE_UP:
        sect_a.magic_stone += _fmt_int(cfg.value)
    elif cfg.event_type == EVENT_TYPE_MAGIC_STONE_DOWN:
        sect_a.magic_stone -= _fmt_int(cfg.value)
    elif cfg.event_type == EVENT_TYPE_INCOME_UP:
        sect_a.add_temporary_sect_effect(
            effects={EXTRA_INCOME_PER_TILE: cfg.value},
            start_month=int(world.month_stamp),
            duration=cfg.duration_months,
            source="sect_random_event",
        )
    elif cfg.event_type == EVENT_TYPE_INCOME_DOWN:
        sect_a.add_temporary_sect_effect(
            effects={EXTRA_INCOME_PER_TILE: -cfg.value},
            start_month=int(world.month_stamp),
            duration=cfg.duration_months,
            source="sect_random_event",
        )

    related_sects = [sect_a.id]
    if sect_b is not None:
        related_sects.append(sect_b.id)

    event_text = _build_event_text(
        event_type=cfg.event_type,
        sect_a_name=sect_a.name,
        sect_b_name=sect_b.name if sect_b else None,
        reason_fragment=reason_fragment,
        value=cfg.value,
        duration_months=cfg.duration_months,
    )

    return Event(
        month_stamp=world.month_stamp,
        content=event_text,
        related_sects=related_sects,
        is_major=False,
        is_story=False,
    )
