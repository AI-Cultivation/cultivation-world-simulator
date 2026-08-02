from __future__ import annotations
from typing import TYPE_CHECKING
from src.classes.event import Event
if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar

def _event(owner: "Avatar", content: str, *, related_avatars: list[str] | None = None, is_major: bool = False) -> Event:
    return Event(
        owner.world.month_stamp,
        content,
        related_avatars=related_avatars or [owner.id],
        is_major=is_major,
        event_type="opportunity",
    )
