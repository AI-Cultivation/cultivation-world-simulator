from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.classes.poi.poi import PointOfInterest
from src.i18n import t
from src.systems.cultivation import Realm


TREASURE_ICON_IDS = tuple(f"treasure_{index:02d}" for index in range(1, 10))


@dataclass(kw_only=True)
class TreasurePOI(PointOfInterest):
    kind: str = "treasure"
    treasure_source: str = ""
    treasure_realm: str = ""
    treasure_payload: dict[str, Any] | None = None
    treasure_icon_id: str = "treasure_01"
    attempt_count: int = 0

    @classmethod
    def from_save_dict(cls, data: dict[str, Any]) -> "TreasurePOI":
        icon_key = str(data.get("icon_key") or data.get("treasure_icon_id") or "treasure_01")
        return cls(
            id=str(data["id"]),
            kind="treasure",
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            name=str(data.get("name", "")),
            desc=str(data.get("desc", "")),
            created_month=int(data.get("created_month", 0) or 0),
            expires_month=int(data["expires_month"]) if data.get("expires_month") is not None else None,
            discovered_by={str(item) for item in data.get("discovered_by", []) or []},
            icon_key=icon_key,
            is_clickable=bool(data.get("is_clickable", True)),
            treasure_source=str(data.get("treasure_source", "")),
            treasure_realm=str(data.get("treasure_realm", "")),
            treasure_payload=dict(data["treasure_payload"]) if data.get("treasure_payload") else None,
            treasure_icon_id=str(data.get("treasure_icon_id") or icon_key),
            attempt_count=int(data.get("attempt_count", 0) or 0),
        )

    def get_detail_payload(self, world: Any) -> dict[str, Any]:
        item = dict(self.treasure_payload) if self.treasure_payload else None
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "desc": self.desc,
            "x": int(self.x),
            "y": int(self.y),
            "icon_key": self.icon_key,
            "treasure": {
                "source": self.treasure_source,
                "source_label": t(f"treasure_source_{self.treasure_source}"),
                "realm": self.treasure_realm,
                "realm_name": str(Realm.from_str(self.treasure_realm)),
                "item": item,
                "attempt_count": int(self.attempt_count),
                "expires_month": int(self.expires_month) if self.expires_month is not None else None,
            },
        }

    def to_save_dict(self) -> dict[str, Any]:
        data = self._base_save_dict()
        data.update(
            {
                "treasure_source": self.treasure_source,
                "treasure_realm": self.treasure_realm,
                "treasure_payload": self.treasure_payload,
                "treasure_icon_id": self.treasure_icon_id,
                "attempt_count": int(self.attempt_count),
            }
        )
        return data
