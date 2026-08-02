from __future__ import annotations
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

class OpportunityTargetType(StrEnum):
    REGION = "region"
    AVATAR = "avatar"


class OpportunityOutcome(StrEnum):
    EQUIPMENT = "equipment"
    BOON = "boon"
    EMPTY = "empty"
    INJURY = "injury"


@dataclass
class OpportunityRecord:
    id: str
    avatar_id: str
    target_type: OpportunityTargetType
    target_id: str
    hint_text: str
    created_month: int
    expires_month: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "avatar_id": self.avatar_id,
            "target_type": self.target_type.value,
            "target_id": self.target_id,
            "hint_text": self.hint_text,
            "created_month": int(self.created_month),
            "expires_month": int(self.expires_month),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OpportunityRecord":
        return cls(
            id=str(data.get("id") or uuid.uuid4()),
            avatar_id=str(data.get("avatar_id") or ""),
            target_type=OpportunityTargetType(str(data.get("target_type") or OpportunityTargetType.REGION.value)),
            target_id=str(data.get("target_id") or ""),
            hint_text=str(data.get("hint_text") or ""),
            created_month=int(data.get("created_month", 0) or 0),
            expires_month=int(data.get("expires_month", 0) or 0),
        )


class OpportunityManager:
    def __init__(self) -> None:
        self.active: dict[str, OpportunityRecord] = {}
        self.cooldowns: dict[str, int] = {}

    def get_for_avatar(self, avatar_id: str) -> OpportunityRecord | None:
        return self.active.get(str(avatar_id))

    def has_active(self, avatar_id: str) -> bool:
        return str(avatar_id) in self.active

    def add(self, record: OpportunityRecord) -> None:
        self.active[str(record.avatar_id)] = record

    def clear(self, avatar_id: str, *, cooldown_until: int | None = None) -> None:
        avatar_key = str(avatar_id)
        self.active.pop(avatar_key, None)
        if cooldown_until is not None:
            self.cooldowns[avatar_key] = int(cooldown_until)

    def is_in_cooldown(self, avatar_id: str, current_month: int) -> bool:
        return int(current_month) < int(self.cooldowns.get(str(avatar_id), 0) or 0)

    def to_save_dict(self) -> dict[str, Any]:
        return {
            "active": {
                avatar_id: record.to_dict()
                for avatar_id, record in self.active.items()
            },
            "cooldowns": {avatar_id: int(month) for avatar_id, month in self.cooldowns.items()},
        }

    def load_from_dict(self, data: dict[str, Any] | None) -> None:
        payload = data if isinstance(data, dict) else {}
        self.active = {}
        for avatar_id, raw_record in (payload.get("active") or {}).items():
            if not isinstance(raw_record, dict):
                continue
            record = OpportunityRecord.from_dict(raw_record)
            if not record.avatar_id:
                record.avatar_id = str(avatar_id)
            self.active[str(record.avatar_id)] = record
        self.cooldowns = {
            str(avatar_id): int(month)
            for avatar_id, month in (payload.get("cooldowns") or {}).items()
            if _can_int(month)
        }


def _can_int(value: object) -> bool:
    try:
        int(value)  # noqa: B018
        return True
    except (TypeError, ValueError):
        return False
