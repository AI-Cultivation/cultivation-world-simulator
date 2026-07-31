from __future__ import annotations

import copy
from typing import Any


def build_equipment_payload(item: Any) -> dict[str, Any] | None:
    if item is None:
        return None

    from src.classes.items.auxiliary import Auxiliary
    from src.classes.items.weapon import Weapon

    if isinstance(item, Weapon):
        kind = "weapon"
    elif isinstance(item, Auxiliary):
        kind = "auxiliary"
    else:
        return None
    return {
        "kind": kind,
        "item_id": int(item.id),
        "name": str(item.name),
        "realm": str(getattr(item.realm, "value", item.realm)),
        "special_data": dict(getattr(item, "special_data", {}) or {}),
    }


def restore_equipment_item(payload: dict[str, Any] | None) -> Any | None:
    if not payload:
        return None
    try:
        item_id = int(payload.get("item_id"))
    except (TypeError, ValueError):
        return None

    kind = str(payload.get("kind", ""))
    if kind == "weapon":
        from src.classes.items.weapon import weapons_by_id

        prototype = weapons_by_id.get(item_id)
    elif kind == "auxiliary":
        from src.classes.items.auxiliary import auxiliaries_by_id

        prototype = auxiliaries_by_id.get(item_id)
    else:
        prototype = None
    if prototype is None:
        return None
    item = copy.copy(prototype)
    item.special_data = dict(payload.get("special_data", {}) or {})
    return item
