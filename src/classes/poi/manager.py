from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.classes.poi.grave import GravePOI
from src.classes.poi.poi import PointOfInterest
from src.classes.poi.treasure import TreasurePOI


@dataclass
class POIManager:
    pois: dict[str, PointOfInterest] = field(default_factory=dict)
    _updates: list[dict[str, Any]] = field(default_factory=list, init=False, repr=False)

    def add(self, poi: PointOfInterest, *, track_update: bool = True) -> None:
        self.pois[str(poi.id)] = poi
        if track_update:
            self._updates.append({"op": "upsert", "poi": poi.get_summary_payload()})

    def get(self, poi_id: str) -> PointOfInterest | None:
        return self.pois.get(str(poi_id))

    def remove(self, poi_id: str, *, track_update: bool = True) -> None:
        pid = str(poi_id)
        if pid in self.pois:
            self.pois.pop(pid, None)
            if track_update:
                self._updates.append({"op": "remove", "id": pid})

    def pop_updates(self) -> list[dict[str, Any]]:
        updates = list(self._updates)
        self._updates.clear()
        return updates

    def get_all_active(self, current_month: int | None = None) -> list[PointOfInterest]:
        if current_month is None:
            return list(self.pois.values())
        return [poi for poi in self.pois.values() if not poi.is_expired(current_month)]

    def get_known_by(self, avatar: Any, *, kind: str | None = None) -> list[PointOfInterest]:
        result = [poi for poi in self.pois.values() if poi.is_known_by(avatar)]
        if kind is not None:
            result = [poi for poi in result if poi.kind == kind]
        return result

    def get_within_observation(self, avatar: Any) -> list[PointOfInterest]:
        from src.classes.observe import get_avatar_observation_radius

        radius = get_avatar_observation_radius(avatar)
        ax = int(getattr(avatar, "pos_x", 0))
        ay = int(getattr(avatar, "pos_y", 0))
        return [
            poi
            for poi in self.pois.values()
            if abs(int(poi.x) - ax) + abs(int(poi.y) - ay) <= radius
        ]

    def discover_nearby(self, avatar: Any, *, current_month: int | None = None) -> list[PointOfInterest]:
        discovered: list[PointOfInterest] = []
        for poi in self.get_within_observation(avatar):
            if current_month is not None and poi.is_expired(current_month):
                continue
            if poi.is_discoverable_by(avatar) and poi.discover(avatar):
                discovered.append(poi)
        return discovered

    def cleanup_expired(self, current_month: int) -> int:
        expired = [poi_id for poi_id, poi in self.pois.items() if poi.is_expired(current_month)]
        for poi_id in expired:
            self.remove(poi_id)
        return len(expired)

    def pop_expired(self, current_month: int, *, kind: str | None = None) -> list[PointOfInterest]:
        expired = [
            poi for poi in self.pois.values()
            if poi.is_expired(current_month) and (kind is None or poi.kind == kind)
        ]
        for poi in expired:
            self.remove(poi.id)
        return expired

    def create_grave_from_avatar(self, avatar: Any, current_month: int) -> GravePOI:
        grave = GravePOI.from_avatar(avatar, current_month)
        self.add(grave)
        return grave

    def to_save_list(self) -> list[dict[str, Any]]:
        return [poi.to_save_dict() for poi in self.pois.values()]

    def load_from_list(self, data: list[dict[str, Any]] | None) -> None:
        self.pois.clear()
        self._updates.clear()
        for item in data or []:
            if not isinstance(item, dict):
                continue
            loader = {
                "grave": GravePOI.from_save_dict,
                "treasure": TreasurePOI.from_save_dict,
            }.get(str(item.get("kind", "")))
            if loader is not None:
                self.add(loader(item), track_update=False)
