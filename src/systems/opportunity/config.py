from __future__ import annotations
import random
from typing import Any, TYPE_CHECKING
from src.utils.config import CONFIG
if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar

def _get_cfg_value(name: str, default: Any) -> Any:
    cfg = getattr(getattr(CONFIG.world, "opportunity", None), name, None)
    return default if cfg is None else cfg


def _get_manager(world: "World") -> OpportunityManager:
    manager = getattr(world, "opportunity_manager", None)
    if manager is None:
        manager = OpportunityManager()
        setattr(world, "opportunity_manager", manager)
    return manager


def _cooldown_after_dissipated() -> int:
    return int(_get_cfg_value("cooldown_months_after_dissipated", 12) or 12)


def _cooldown_after_resolved() -> int:
    return int(_get_cfg_value("cooldown_months_after_resolved", 60) or 60)


def _duration_months() -> int:
    return int(_get_cfg_value("duration_months", 60) or 60)


def _opportunity_probability(avatar: "Avatar") -> float:
    base = float(_get_cfg_value("probability", 0.0) or 0.0)
    extra = float(getattr(avatar, "effects", {}).get("extra_opportunity_probability", 0.0) or 0.0)
    return max(0.0, min(1.0, base + extra))


def _weighted_choice_from_mapping(mapping: Any, defaults: dict[str, float]) -> str:
    weights: dict[str, float] = dict(defaults)
    if isinstance(mapping, dict):
        for key, value in mapping.items():
            try:
                weights[str(key)] = max(0.0, float(value))
            except (TypeError, ValueError):
                continue
    choices = [(key, weight) for key, weight in weights.items() if weight > 0]
    if not choices:
        return next(iter(defaults))
    keys, values = zip(*choices)
    return str(random.choices(keys, weights=values, k=1)[0])
