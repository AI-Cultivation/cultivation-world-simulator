"""Member-status calculations kept outside the Sect aggregate."""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.systems.cultivation import Realm

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar
    from src.classes.core.sect import Sect


class SectMemberStatusService:
    @staticmethod
    def normalization(sect: "Sect") -> dict[str, float]:
        from src.systems.battle import get_base_strength
        living = [avatar for avatar in sect.members.values() if not getattr(avatar, "is_dead", False)]
        return {
            "max_contribution": float(max(1, max((int(getattr(a, "sect_contribution", 0) or 0) for a in living), default=0))),
            "max_battle_strength": float(max(1.0, max((float(get_base_strength(a)) for a in living), default=0.0))),
        }

    @staticmethod
    def score(avatar: "Avatar", *, max_contribution: float, max_battle_strength: float) -> float:
        from src.systems.battle import get_base_strength
        contribution = max(0, int(getattr(avatar, "sect_contribution", 0) or 0))
        strength = max(0.0, float(get_base_strength(avatar)))
        return (contribution / max_contribution if max_contribution else 0.0) * 70.0 + (
            strength / max_battle_strength if max_battle_strength else 0.0
        ) * 30.0

    @classmethod
    def snapshot(cls, sect: "Sect", avatar: "Avatar", *, normalization: dict[str, float] | None = None) -> dict[str, float | int]:
        from src.systems.battle import get_base_strength
        normalization = normalization or cls.normalization(sect)
        strength = max(0.0, float(get_base_strength(avatar)))
        return {
            "sect_contribution": max(0, int(getattr(avatar, "sect_contribution", 0) or 0)),
            "base_battle_strength": int(strength),
            "status_score": round(cls.score(avatar, **normalization), 2),
        }

    @classmethod
    def snapshot_map(cls, sect: "Sect") -> dict[str, dict[str, float | int]]:
        normalization = cls.normalization(sect)
        return {
            str(avatar.id): cls.snapshot(sect, avatar, normalization=normalization)
            for avatar in sect.members.values() if not getattr(avatar, "is_dead", False)
        }

    @classmethod
    def living_members_sorted(cls, sect: "Sect") -> list["Avatar"]:
        normalization = cls.normalization(sect)
        living = [avatar for avatar in sect.members.values() if not getattr(avatar, "is_dead", False)]
        return sorted(living, key=lambda avatar: (
            -cls.score(avatar, **normalization),
            -max(0, int(getattr(avatar, "sect_contribution", 0) or 0)),
            str(getattr(avatar, "name", "") or ""),
        ))


def get_member_upkeep_by_realm() -> dict[Realm, int]:
    """Read sect upkeep at call time so settings reloads are observed."""
    from src.utils.config import CONFIG

    defaults = {
        Realm.Qi_Refinement: 15,
        Realm.Foundation_Establishment: 30,
        Realm.Core_Formation: 60,
        Realm.Nascent_Soul: 120,
    }
    configured = getattr(getattr(CONFIG, "sect", None), "member_upkeep_by_realm", None)
    if not configured:
        return defaults
    mapping = {
        "QI_REFINEMENT": Realm.Qi_Refinement,
        "FOUNDATION_ESTABLISHMENT": Realm.Foundation_Establishment,
        "CORE_FORMATION": Realm.Core_Formation,
        "NASCENT_SOUL": Realm.Nascent_Soul,
    }
    result = dict(defaults)
    for key, value in configured.items():
        realm = mapping.get(str(key).strip().upper())
        if realm is None:
            continue
        try:
            result[realm] = max(0, int(value))
        except (TypeError, ValueError):
            continue
    return result
