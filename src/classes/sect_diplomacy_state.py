from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from src.classes.war import SectWar, STATUS_PEACE, STATUS_WAR


@dataclass
class SectDiplomacyState:
    """Runtime and persistence state for inter-sect diplomacy.

    The state owns its serialized records so World remains the aggregate root,
    not the implementation of the diplomacy state machine.
    """

    relation_modifiers: list[dict[str, Any]] = field(default_factory=list)
    wars: list[dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def normalize_pair(sect_a_id: int, sect_b_id: int) -> tuple[int, int]:
        a, b = int(sect_a_id), int(sect_b_id)
        return (a, b) if a <= b else (b, a)

    def set_relation_modifiers(self, items: Iterable[dict[str, Any]]) -> None:
        self.relation_modifiers = [dict(item) for item in items if isinstance(item, dict)]

    def set_wars(self, items: Iterable[dict[str, Any] | SectWar]) -> None:
        self.wars = [
            item.to_dict() if isinstance(item, SectWar) else dict(item)
            for item in items
            if isinstance(item, (dict, SectWar))
        ]

    def add_relation_modifier(self, *, sect_a_id: int, sect_b_id: int, delta: int, duration: int, reason: str, current_month: int, meta: dict | None = None) -> None:
        if int(duration) <= 0 or int(delta) == 0:
            return
        a, b = self.normalize_pair(sect_a_id, sect_b_id)
        self.relation_modifiers.append({"sect_a_id": a, "sect_b_id": b, "delta": int(delta), "reason": str(reason), "meta": dict(meta or {}), "start_month": int(current_month), "duration": int(duration)})

    def _iter_wars(self) -> list[SectWar]:
        records: list[SectWar] = []
        for item in self.wars:
            try:
                records.append(item if isinstance(item, SectWar) else SectWar.from_dict(item))
            except (TypeError, ValueError, KeyError):
                continue
        return records

    def _store_wars(self, wars: Iterable[SectWar]) -> None:
        self.wars = [war.to_dict() for war in wars]

    def get_war(self, sect_a_id: int, sect_b_id: int) -> dict[str, Any] | None:
        pair = SectWar.normalize_pair(sect_a_id, sect_b_id)
        for war in self._iter_wars():
            if (int(war.sect_a_id), int(war.sect_b_id)) == pair:
                return war.to_dict()
        return None

    def declare_war(self, *, sect_a_id: int, sect_b_id: int, current_month: int, reason: str = "") -> dict[str, Any]:
        pair = SectWar.normalize_pair(sect_a_id, sect_b_id)
        records = self._iter_wars()
        target = next((war for war in records if (int(war.sect_a_id), int(war.sect_b_id)) == pair), None)
        if target is None:
            target = SectWar.create(sect_a_id=pair[0], sect_b_id=pair[1], status=STATUS_WAR, current_month=current_month, reason=reason)
            records.append(target)
        else:
            target.status, target.start_month, target.peace_start_month = STATUS_WAR, int(current_month), None
            target.reason = str(reason or target.reason or "")
        self._store_wars(records)
        return target.to_dict()

    def make_peace(self, *, sect_a_id: int, sect_b_id: int, current_month: int, reason: str = "") -> dict[str, Any]:
        pair = SectWar.normalize_pair(sect_a_id, sect_b_id)
        records = self._iter_wars()
        target = next((war for war in records if (int(war.sect_a_id), int(war.sect_b_id)) == pair), None)
        if target is None:
            target = SectWar.create(sect_a_id=pair[0], sect_b_id=pair[1], status=STATUS_PEACE, current_month=current_month, reason=reason, peace_start_month=current_month)
            records.append(target)
        else:
            target.status, target.peace_start_month = STATUS_PEACE, int(current_month)
            target.reason = str(reason or target.reason or "")
        self._store_wars(records)
        return target.to_dict()

    def record_battle(self, sect_a_id: int, sect_b_id: int, *, current_month: int) -> None:
        pair = SectWar.normalize_pair(sect_a_id, sect_b_id)
        records = self._iter_wars()
        target = next((war for war in records if (int(war.sect_a_id), int(war.sect_b_id)) == pair), None)
        if target is None:
            records.append(SectWar.create(sect_a_id=pair[0], sect_b_id=pair[1], status=STATUS_WAR, current_month=current_month, last_battle_month=current_month))
        else:
            target.last_battle_month = int(current_month)
        self._store_wars(records)

    def get_state(self, sect_a_id: int, sect_b_id: int, *, current_month: int, start_year: int) -> dict[str, Any]:
        war = self.get_war(sect_a_id, sect_b_id)
        if war is None:
            peace_start = int(start_year) * 12
            return {"status": STATUS_PEACE, "start_month": peace_start, "peace_start_month": peace_start, "peace_months": max(0, current_month - peace_start), "war_months": 0, "last_battle_month": None, "reason": ""}
        status = str(war.get("status", STATUS_PEACE) or STATUS_PEACE)
        war_start = int(war.get("start_month", current_month) or current_month)
        if status == STATUS_WAR:
            return {"status": STATUS_WAR, "start_month": war_start, "peace_start_month": None, "peace_months": 0, "war_months": max(0, current_month - war_start), "last_battle_month": war.get("last_battle_month"), "reason": str(war.get("reason", "") or "")}
        peace_start = int(war.get("peace_start_month") if war.get("peace_start_month") is not None else war_start)
        return {"status": STATUS_PEACE, "start_month": war_start, "peace_start_month": peace_start, "peace_months": max(0, current_month - peace_start), "war_months": 0, "last_battle_month": war.get("last_battle_month"), "reason": str(war.get("reason", "") or "")}

    def prune_relation_modifiers(self, *, current_month: int) -> None:
        self.relation_modifiers = [item for item in self.relation_modifiers if current_month < int(item.get("start_month", 0)) + int(item.get("duration", 0))]

    def relation_breakdown(self, *, current_month: int) -> dict[tuple[int, int], list[dict[str, Any]]]:
        self.prune_relation_modifiers(current_month=current_month)
        result: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for item in self.relation_modifiers:
            pair = self.normalize_pair(int(item.get("sect_a_id", 0)), int(item.get("sect_b_id", 0)))
            if pair[0] > 0 and pair[1] > 0:
                result.setdefault(pair, []).append({"reason": str(item.get("reason", "")), "delta": int(item.get("delta", 0)), "meta": dict(item.get("meta", {}) or {})})
        return result

    def diplomacy_breakdown(self, *, current_month: int, start_year: int, sect_ids: Iterable[int] | None = None) -> dict[tuple[int, int], list[dict[str, Any]]]:
        result: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for war in self._iter_wars():
            pair = SectWar.normalize_pair(war.sect_a_id, war.sect_b_id)
            if pair[0] <= 0 or pair[1] <= 0:
                continue
            if war.status == STATUS_WAR:
                months = max(0, current_month - int(war.start_month))
                result[pair] = [{"reason": "WAR_STATE", "delta": -20 - min(20, (months // 12) * 2), "meta": {"status": STATUS_WAR, "war_months": months}}]
            else:
                self._append_peace_breakdown(result, pair, current_month, int(war.peace_start_month if war.peace_start_month is not None else war.start_month))
        ids = sorted({int(sid) for sid in (sect_ids or []) if int(sid) > 0})
        for index, first in enumerate(ids):
            for second in ids[index + 1:]:
                pair = (first, second)
                if pair not in result:
                    self._append_peace_breakdown(result, pair, current_month, int(start_year) * 12)
        return result

    @staticmethod
    def _append_peace_breakdown(result: dict[tuple[int, int], list[dict[str, Any]]], pair: tuple[int, int], current_month: int, peace_start: int) -> None:
        months = max(0, current_month - peace_start)
        entries = [{"reason": "PEACE_STATE", "delta": 0, "meta": {"status": STATUS_PEACE, "peace_months": months}}]
        bonus = min(20, months // 12)
        if bonus:
            entries.append({"reason": "LONG_PEACE", "delta": bonus, "meta": {"status": STATUS_PEACE, "peace_months": months, "capped": bonus >= 20}})
        result[pair] = entries
