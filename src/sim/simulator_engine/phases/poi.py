from __future__ import annotations

from src.classes.event import Event
from src.i18n import t


def phase_discover_pois(world, living_avatars) -> list[Event]:
    poi_manager = getattr(world, "poi_manager", None)
    if poi_manager is None:
        return []

    events: list[Event] = []
    current_month = int(getattr(world, "month_stamp", 0))
    for avatar in living_avatars:
        for poi in poi_manager.discover_nearby(avatar, current_month=current_month):
            if poi.kind == "grave":
                content = t(
                    "{avatar} discovered a grave at {location}: {poi}",
                    avatar=avatar.name,
                    location=f"({poi.x}, {poi.y})",
                    poi=poi.name,
                )
            elif poi.kind == "treasure":
                content = t(
                    "{avatar} discovered a treasure at {location}: {poi}",
                    avatar=avatar.name,
                    location=f"({poi.x}, {poi.y})",
                    poi=poi.name,
                )
            else:
                content = t(
                    "{avatar} discovered a point of interest at {location}: {poi}",
                    avatar=avatar.name,
                    location=f"({poi.x}, {poi.y})",
                    poi=poi.name,
                )
            events.append(Event(world.month_stamp, content, related_avatars=[avatar.id]))
    return events
