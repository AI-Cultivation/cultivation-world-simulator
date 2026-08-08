"""Shared event-query vocabulary for persistent and in-memory backends."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar


EventT = TypeVar("EventT")


class EventAudience(str, Enum):
    DIRECT = "direct"
    OBSERVED = "observed"


class EventMemoryScope(str, Enum):
    ALL = "all"
    MAJOR = "major"
    MINOR = "minor"


@dataclass(frozen=True, slots=True)
class EventQuery:
    avatar_ids: tuple[str, ...] = ()
    audience: EventAudience = EventAudience.DIRECT
    sect_id: int | None = None
    memory_scope: EventMemoryScope = EventMemoryScope.ALL
    cursor: str | None = None
    limit: int = 100
    chronological: bool = False


@dataclass(frozen=True, slots=True)
class EventPage(Generic[EventT]):
    """A page returned by either event backend.

    The cursor is opaque to callers.  Query adapters may expose legacy tuple
    return values, but storage and in-memory implementations share this
    result contract.
    """

    events: list[EventT]
    next_cursor: str | None = None


def matches_memory_scope(event: object, scope: EventMemoryScope) -> bool:
    """Apply the long-/short-term memory rule without backend-specific SQL."""
    if scope is EventMemoryScope.ALL:
        return True
    is_major = bool(getattr(event, "is_major", False))
    is_story = bool(getattr(event, "is_story", False))
    return (is_major and not is_story) if scope is EventMemoryScope.MAJOR else (not is_major or is_story)
