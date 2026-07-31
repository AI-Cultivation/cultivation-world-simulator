from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from src.classes.poi.poi import PointOfInterest
from src.classes.poi.item_payload import build_equipment_payload, restore_equipment_item

GRAVE_RETENTION_YEARS = 50
GRAVE_ICON_IDS = tuple(f"grave_{idx:02d}" for idx in range(1, 10))


def restore_grave_item(payload: dict[str, Any] | None) -> Any | None:
    return restore_equipment_item(payload)


@dataclass(kw_only=True)
class GravePOI(PointOfInterest):
    kind: str = "grave"
    deceased_avatar_id: str = ""
    deceased_name: str = ""
    death_reason: str = ""
    death_month: int = 0
    realm_at_death: str = ""
    stage_at_death: str = ""
    sect_name_at_death: str = ""
    alignment_at_death: str = ""
    grave_icon_id: str = "grave_01"
    weapon_payload: dict[str, Any] | None = None
    auxiliary_payload: dict[str, Any] | None = None
    weapon_looted: bool = False
    auxiliary_looted: bool = False
    dig_attempt_count: int = 0

    def get_summary_payload(self) -> dict[str, Any]:
        payload = super().get_summary_payload()
        payload["deceased_avatar_id"] = self.deceased_avatar_id
        return payload

    @classmethod
    def from_avatar(cls, avatar: Any, current_month: int) -> "GravePOI":
        death_info = getattr(avatar, "death_info", None) or {}
        death_location = death_info.get("location") or (getattr(avatar, "pos_x", 0), getattr(avatar, "pos_y", 0))
        x, y = int(death_location[0]), int(death_location[1])
        death_month = int(death_info.get("time", current_month) or current_month)
        icon_id = random.choice(GRAVE_ICON_IDS)
        deceased_name = str(getattr(avatar, "name", ""))
        return cls(
            id=f"grave:{getattr(avatar, 'id')}:{death_month}",
            kind="grave",
            x=x,
            y=y,
            name=f"{deceased_name}之墓",
            desc="一方古旧墓碑，碑面仍残留淡淡灵光。",
            created_month=int(current_month),
            expires_month=int(current_month) + GRAVE_RETENTION_YEARS * 12,
            icon_key=icon_id,
            grave_icon_id=icon_id,
            deceased_avatar_id=str(getattr(avatar, "id", "")),
            deceased_name=deceased_name,
            death_reason=str(death_info.get("reason", "")),
            death_month=death_month,
            realm_at_death=str(getattr(getattr(getattr(avatar, "cultivation_progress", None), "realm", ""), "value", "")),
            stage_at_death=str(getattr(getattr(getattr(avatar, "cultivation_progress", None), "stage", ""), "value", "")),
            sect_name_at_death=str(death_info.get("sect_name_at_death", "")),
            alignment_at_death=str(death_info.get("alignment_at_death", "")),
            weapon_payload=build_equipment_payload(getattr(avatar, "weapon", None)),
            auxiliary_payload=build_equipment_payload(getattr(avatar, "auxiliary", None)),
        )

    @classmethod
    def from_save_dict(cls, data: dict[str, Any]) -> "GravePOI":
        return cls(
            id=str(data["id"]),
            kind="grave",
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            name=str(data.get("name", "")),
            desc=str(data.get("desc", "")),
            created_month=int(data.get("created_month", 0) or 0),
            expires_month=int(data["expires_month"]) if data.get("expires_month") is not None else None,
            discovered_by={str(item) for item in data.get("discovered_by", []) or []},
            icon_key=str(data.get("icon_key") or data.get("grave_icon_id") or "grave_01"),
            is_clickable=bool(data.get("is_clickable", True)),
            deceased_avatar_id=str(data.get("deceased_avatar_id", "")),
            deceased_name=str(data.get("deceased_name", "")),
            death_reason=str(data.get("death_reason", "")),
            death_month=int(data.get("death_month", data.get("created_month", 0)) or 0),
            realm_at_death=str(data.get("realm_at_death", "")),
            stage_at_death=str(data.get("stage_at_death", "")),
            sect_name_at_death=str(data.get("sect_name_at_death", "")),
            alignment_at_death=str(data.get("alignment_at_death", "")),
            grave_icon_id=str(data.get("grave_icon_id") or data.get("icon_key") or "grave_01"),
            weapon_payload=dict(data["weapon_payload"]) if data.get("weapon_payload") else None,
            auxiliary_payload=dict(data["auxiliary_payload"]) if data.get("auxiliary_payload") else None,
            weapon_looted=bool(data.get("weapon_looted", False)),
            auxiliary_looted=bool(data.get("auxiliary_looted", False)),
            dig_attempt_count=int(data.get("dig_attempt_count", 0) or 0),
        )

    def get_available_item_payloads(self) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        if self.weapon_payload and not self.weapon_looted:
            payloads.append(self.weapon_payload)
        if self.auxiliary_payload and not self.auxiliary_looted:
            payloads.append(self.auxiliary_payload)
        return payloads

    def mark_item_looted(self, payload: dict[str, Any]) -> None:
        kind = str(payload.get("kind", ""))
        if kind == "weapon":
            self.weapon_looted = True
            self.weapon_payload = None
        elif kind == "auxiliary":
            self.auxiliary_looted = True
            self.auxiliary_payload = None

    def _deceased_payload(self, world: Any) -> dict[str, Any]:
        record = getattr(getattr(world, "deceased_manager", None), "get_record", lambda _id: None)(self.deceased_avatar_id)
        if record is not None:
            return record.to_dict()
        return {
            "id": self.deceased_avatar_id,
            "name": self.deceased_name,
            "age_at_death": None,
            "realm_at_death": self.realm_at_death,
            "stage_at_death": self.stage_at_death,
            "death_reason": self.death_reason,
            "death_time": self.death_month,
            "sect_name_at_death": self.sect_name_at_death,
            "alignment_at_death": self.alignment_at_death,
            "backstory": None,
            "custom_pic_id": None,
        }

    def get_detail_payload(self, world: Any) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "desc": self.desc,
            "x": int(self.x),
            "y": int(self.y),
            "icon_key": self.icon_key,
            "deceased": self._deceased_payload(world),
            "grave_goods": {
                "weapon": None if self.weapon_looted else self.weapon_payload,
                "auxiliary": None if self.auxiliary_looted else self.auxiliary_payload,
            },
            "dig_attempt_count": int(self.dig_attempt_count),
        }

    def to_save_dict(self) -> dict[str, Any]:
        data = self._base_save_dict()
        data.update(
            {
                "deceased_avatar_id": self.deceased_avatar_id,
                "deceased_name": self.deceased_name,
                "death_reason": self.death_reason,
                "death_month": int(self.death_month),
                "realm_at_death": self.realm_at_death,
                "stage_at_death": self.stage_at_death,
                "sect_name_at_death": self.sect_name_at_death,
                "alignment_at_death": self.alignment_at_death,
                "grave_icon_id": self.grave_icon_id,
                "weapon_payload": self.weapon_payload,
                "auxiliary_payload": self.auxiliary_payload,
                "weapon_looted": bool(self.weapon_looted),
                "auxiliary_looted": bool(self.auxiliary_looted),
                "dig_attempt_count": int(self.dig_attempt_count),
            }
        )
        return data
