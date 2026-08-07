"""
Tests for EventStorage and EventManager.

Covers:
- EventStorage: add_event, get_events, pagination, cursor handling, cleanup
- EventManager: all query methods, get_events_paginated
- Memory fallback mode
"""

import pytest
import tempfile
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock

from src.classes.event import Event, NULL_EVENT
from src.classes.event_storage import EventStorage, EventStorageError
from src.sim.managers.event_manager import EventManager
from src.systems.time import MonthStamp, Year, Month, create_month_stamp


# --- Fixtures ---

@pytest.fixture
def temp_db_path():
    """Create a temporary database file path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_events.db"


@pytest.fixture
def event_storage(temp_db_path):
    """Create an EventStorage instance with a temporary database."""
    storage = EventStorage(temp_db_path)
    yield storage
    storage.close()


@pytest.fixture
def event_manager(temp_db_path):
    """Create an EventManager with SQLite storage."""
    manager = EventManager.create_with_db(temp_db_path)
    yield manager
    manager.close()


@pytest.fixture
def memory_event_manager():
    """Create an EventManager in memory mode (no SQLite)."""
    return EventManager.create_in_memory()


def make_event(
    year: int,
    month: int,
    content: str,
    avatar_ids: list[str] | None = None,
    is_major: bool = False,
    is_story: bool = False,
    event_id: str | None = None,
) -> Event:
    """Helper to create an Event with the given parameters."""
    month_stamp = create_month_stamp(Year(year), Month(month))
    kwargs = {
        "month_stamp": month_stamp,
        "content": content,
        "related_avatars": avatar_ids,
        "is_major": is_major,
        "is_story": is_story,
    }
    if event_id is not None:
        kwargs["id"] = event_id
    return Event(**kwargs)
    
# --- EventStorage Tests ---

class TestEventStorageBasic:
    """Basic EventStorage functionality tests."""

    def test_init_creates_tables(self, temp_db_path):
        """Test that EventStorage creates necessary tables on init."""
        storage = EventStorage(temp_db_path)
        assert storage._conn is not None

        # Verify tables exist
        cursor = storage._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('events', 'event_avatars')"
        )
        tables = [row[0] for row in cursor.fetchall()]
        assert "events" in tables
        assert "event_avatars" in tables

        storage.close()

    def test_add_event_success(self, event_storage):
        """Test adding a single event."""
        event = make_event(100, 5, "Test event content", ["avatar_1", "avatar_2"])

        result = event_storage.add_event(event)

        assert result is True
        assert event_storage.count() == 1

    def test_add_event_duplicate_ignored(self, event_storage):
        """Test that duplicate events (same ID) are ignored."""
        event = make_event(100, 5, "Original content", event_id="fixed-id")
        event_storage.add_event(event)

        # Try to add with same ID but different content
        duplicate = make_event(100, 5, "Different content", event_id="fixed-id")
        result = event_storage.add_event(duplicate)

        assert result is True  # INSERT OR IGNORE doesn't fail
        assert event_storage.count() == 1

    def test_add_event_without_avatars(self, event_storage):
        """Test adding an event without related avatars."""
        event = make_event(100, 5, "World event", avatar_ids=None)

        result = event_storage.add_event(event)

        assert result is True
        assert event_storage.count() == 1

    def test_subject_snapshots_round_trip(self, event_storage):
        event = make_event(100, 5, "Alice acted", ["avatar_1"])
        event.subject_snapshots = {"avatar_1": "Alice"}

        event_storage.add_event(event)
        events, _ = event_storage.get_events()

        assert events[0].subject_snapshots == {"avatar_1": "Alice"}

    def test_count(self, event_storage):
        """Test event counting."""
        assert event_storage.count() == 0

        event_storage.add_event(make_event(100, 1, "Event 1"))
        assert event_storage.count() == 1

        event_storage.add_event(make_event(100, 2, "Event 2"))
        assert event_storage.count() == 2


class TestEventStorageQueries:
    """EventStorage query functionality tests."""

    def test_get_events_empty_db(self, event_storage):
        """Test querying an empty database."""
        events, cursor = event_storage.get_events()

        assert events == []
        assert cursor is None

    def test_get_events_raises_distinct_error_when_sqlite_read_fails(self, event_storage):
        """A broken store must not be indistinguishable from an empty result."""
        class BrokenConnection:
            def execute(self, *_args, **_kwargs):
                raise Exception("broken sqlite")

        connection = event_storage._conn
        event_storage._conn = BrokenConnection()
        try:
            with pytest.raises(EventStorageError, match="Failed to query events"):
                event_storage.get_events()
        finally:
            event_storage._conn = connection

    def test_get_events_all(self, event_storage):
        """Test getting all events (no filter)."""
        event_storage.add_event(make_event(100, 1, "Event 1", ["a1"]))
        event_storage.add_event(make_event(100, 2, "Event 2", ["a2"]))
        event_storage.add_event(make_event(100, 3, "Event 3", ["a1", "a2"]))

        events, cursor = event_storage.get_events()

        assert len(events) == 3
        # Events returned in descending order (newest first)
        assert events[0].content == "Event 3"
        assert events[1].content == "Event 2"
        assert events[2].content == "Event 1"

    def test_get_events_by_avatar(self, event_storage):
        """Test filtering events by single avatar."""
        event_storage.add_event(make_event(100, 1, "Event A1 only", ["a1"]))
        event_storage.add_event(make_event(100, 2, "Event A2 only", ["a2"]))
        event_storage.add_event(make_event(100, 3, "Event both", ["a1", "a2"]))

        events, _ = event_storage.get_events(avatar_id="a1")

        assert len(events) == 2
        contents = [e.content for e in events]
        assert "Event A1 only" in contents
        assert "Event both" in contents
        assert "Event A2 only" not in contents

    def test_get_events_by_sect(self, event_storage):
        """Test filtering events by sect_id."""
        # 事件1：仅关联宗门1
        e1 = make_event(100, 1, "Sect 1 only")
        e1.related_sects = [1]
        event_storage.add_event(e1)

        # 事件2：仅关联宗门2
        e2 = make_event(100, 2, "Sect 2 only")
        e2.related_sects = [2]
        event_storage.add_event(e2)

        # 事件3：无宗门关联
        e3 = make_event(100, 3, "No sect")
        e3.related_sects = None
        event_storage.add_event(e3)

        events, _ = event_storage.get_events(sect_id=1)

        assert len(events) == 1
        assert events[0].content == "Sect 1 only"

    def test_get_events_by_avatar_pair(self, event_storage):
        """Test filtering events by avatar pair."""
        event_storage.add_event(make_event(100, 1, "Event A1 only", ["a1"]))
        event_storage.add_event(make_event(100, 2, "Event A2 only", ["a2"]))
        event_storage.add_event(make_event(100, 3, "Event A1+A2", ["a1", "a2"]))
        event_storage.add_event(make_event(100, 4, "Event A1+A3", ["a1", "a3"]))

        events, _ = event_storage.get_events(avatar_id_pair=("a1", "a2"))

        assert len(events) == 1
        assert events[0].content == "Event A1+A2"

    def test_get_events_by_avatar_returns_related_avatars(self, event_storage):
        """Test that related_avatars are correctly returned."""
        event_storage.add_event(make_event(100, 1, "Multi avatar", ["a1", "a2", "a3"]))

        events, _ = event_storage.get_events(avatar_id="a1")

        assert len(events) == 1
        assert set(events[0].related_avatars) == {"a1", "a2", "a3"}

    def test_get_events_batches_related_avatar_and_sect_lookups_per_page(self, event_storage):
        """Test get_events batches related avatar/sect lookups instead of querying per row."""
        for idx in range(3):
            event = make_event(100, idx + 1, f"Event {idx}", [f"a{idx}", f"b{idx}"])
            event.related_sects = [idx + 1, idx + 10]
            event_storage.add_event(event)

        related_query_counts = {
            "event_avatars": 0,
            "event_sects": 0,
        }

        def tracer(sql: str) -> None:
            normalized = " ".join(sql.split()).lower()
            if " from event_avatars " in normalized:
                related_query_counts["event_avatars"] += 1
            if " from event_sects " in normalized:
                related_query_counts["event_sects"] += 1

        event_storage._conn.set_trace_callback(tracer)
        try:
            events, _ = event_storage.get_events(limit=3)
        finally:
            event_storage._conn.set_trace_callback(None)

        assert len(events) == 3
        assert related_query_counts["event_avatars"] == 1
        assert related_query_counts["event_sects"] == 1
        assert set(events[0].related_sects) == {3, 12}


class TestEventStoragePagination:
    """EventStorage pagination tests."""

    def test_pagination_limit(self, event_storage):
        """Test that limit parameter works."""
        for i in range(10):
            event_storage.add_event(make_event(100, i + 1, f"Event {i}"))

        events, cursor = event_storage.get_events(limit=5)

        assert len(events) == 5
        assert cursor is not None  # Has more

    def test_pagination_cursor_format(self, event_storage):
        """Test cursor format is {month_stamp}_{rowid}."""
        for i in range(10):
            event_storage.add_event(make_event(100, i + 1, f"Event {i}"))

        _, cursor = event_storage.get_events(limit=5)

        assert cursor is not None
        parts = cursor.split("_")
        assert len(parts) == 2
        # Both parts should be integers
        assert parts[0].isdigit()
        assert parts[1].isdigit()

    def test_pagination_cursor_continues(self, event_storage):
        """Test that using cursor returns next page."""
        for i in range(10):
            event_storage.add_event(make_event(100, i + 1, f"Event {i}"))

        # First page
        page1, cursor1 = event_storage.get_events(limit=5)
        assert len(page1) == 5
        assert cursor1 is not None  # More events exist

        # Second page
        page2, cursor2 = event_storage.get_events(limit=5, cursor=cursor1)
        assert len(page2) == 5

        # No overlap between pages
        page1_ids = {e.id for e in page1}
        page2_ids = {e.id for e in page2}
        assert page1_ids.isdisjoint(page2_ids)

        # cursor2 is None because all 10 events have been returned
        assert cursor2 is None

        # All 10 unique events were returned across both pages
        all_ids = page1_ids | page2_ids
        assert len(all_ids) == 10

    def test_pagination_no_more_events(self, event_storage):
        """Test that cursor is None when no more events."""
        for i in range(3):
            event_storage.add_event(make_event(100, i + 1, f"Event {i}"))

        events, cursor = event_storage.get_events(limit=10)

        assert len(events) == 3
        assert cursor is None  # No more

    def test_pagination_with_filter(self, event_storage):
        """Test pagination combined with avatar filter."""
        for i in range(10):
            avatar_id = "a1" if i % 2 == 0 else "a2"
            event_storage.add_event(make_event(100, i + 1, f"Event {i}", [avatar_id]))

        # Get a1's events (5 total)
        page1, cursor = event_storage.get_events(avatar_id="a1", limit=3)
        assert len(page1) == 3

        page2, _ = event_storage.get_events(avatar_id="a1", limit=3, cursor=cursor)
        assert len(page2) == 2  # Only 2 remaining


class TestEventStorageHelperMethods:
    """Tests for helper query methods."""

    def test_get_events_by_avatar_method(self, event_storage):
        """Test get_events_by_avatar returns in chronological order."""
        event_storage.add_event(make_event(100, 1, "First", ["a1"]))
        event_storage.add_event(make_event(100, 6, "Second", ["a1"]))
        event_storage.add_event(make_event(101, 1, "Third", ["a1"]))

        events = event_storage.get_events_by_avatar("a1")

        # Should be in chronological order (oldest first)
        assert events[0].content == "First"
        assert events[1].content == "Second"
        assert events[2].content == "Third"

    def test_get_events_between_method(self, event_storage):
        """Test get_events_between returns in chronological order."""
        event_storage.add_event(make_event(100, 1, "First pair", ["a1", "a2"]))
        event_storage.add_event(make_event(100, 6, "Second pair", ["a1", "a2"]))
        event_storage.add_event(make_event(100, 3, "A1 only", ["a1"]))

        events = event_storage.get_events_between("a1", "a2")

        assert len(events) == 2
        # Chronological order
        assert events[0].content == "First pair"
        assert events[1].content == "Second pair"

    def test_get_major_events_by_avatar(self, event_storage):
        """Test getting only major events for an avatar."""
        event_storage.add_event(make_event(100, 1, "Minor 1", ["a1"], is_major=False))
        event_storage.add_event(make_event(100, 2, "Major 1", ["a1"], is_major=True))
        event_storage.add_event(make_event(100, 3, "Story", ["a1"], is_major=True, is_story=True))
        event_storage.add_event(make_event(100, 4, "Major 2", ["a1"], is_major=True))

        events = event_storage.get_major_events_by_avatar("a1")

        # Should only include major non-story events
        assert len(events) == 2
        contents = [e.content for e in events]
        assert "Major 1" in contents
        assert "Major 2" in contents
        assert "Story" not in contents
        assert "Minor 1" not in contents

    def test_get_major_events_by_avatar_batches_related_avatar_and_sect_lookups(self, event_storage):
        """Test get_major_events_by_avatar batches related avatar/sect lookups for the page."""
        for idx in range(3):
            event = make_event(100, idx + 1, f"Major {idx}", [f"a{idx}", "a1"], is_major=True)
            event.related_sects = [idx + 1, idx + 10]
            event_storage.add_event(event)

        related_query_counts = {
            "event_avatars": 0,
            "event_sects": 0,
        }

        def tracer(sql: str) -> None:
            normalized = " ".join(sql.split()).lower()
            if " from event_avatars " in normalized:
                related_query_counts["event_avatars"] += 1
            if " from event_sects " in normalized:
                related_query_counts["event_sects"] += 1

        event_storage._conn.set_trace_callback(tracer)
        try:
            events = event_storage.get_major_events_by_avatar("a1", limit=3)
        finally:
            event_storage._conn.set_trace_callback(None)

        assert len(events) == 3
        assert related_query_counts["event_avatars"] == 1
        assert related_query_counts["event_sects"] == 1
        assert set(events[-1].related_sects) == {3, 12}

    def test_get_minor_events_by_avatar(self, event_storage):
        """Test getting minor events (including stories) for an avatar."""
        event_storage.add_event(make_event(100, 1, "Minor 1", ["a1"], is_major=False))
        event_storage.add_event(make_event(100, 2, "Major 1", ["a1"], is_major=True))
        event_storage.add_event(make_event(100, 3, "Story", ["a1"], is_major=True, is_story=True))

        events = event_storage.get_minor_events_by_avatar("a1")

        # Should include minor and story events
        assert len(events) == 2
        contents = [e.content for e in events]
        assert "Minor 1" in contents
        assert "Story" in contents
        assert "Major 1" not in contents

    def test_get_recent_events(self, event_storage):
        """Test get_recent_events returns in chronological order."""
        event_storage.add_event(make_event(100, 1, "First"))
        event_storage.add_event(make_event(100, 6, "Second"))
        event_storage.add_event(make_event(101, 1, "Third"))

        events = event_storage.get_recent_events()

        # Should be chronological (oldest first)
        assert events[0].content == "First"
        assert events[1].content == "Second"
        assert events[2].content == "Third"


class TestEventStorageQueryEfficiency:
    """Tests for query counts in SQLite-backed read paths."""

    def test_get_events_uses_batched_association_queries(self, event_storage):
        """get_events should not issue per-row association lookups."""
        for i in range(4):
            event = make_event(100, i + 1, f"Event {i}", [f"a{i}", f"b{i}"])
            event.related_sects = [1, 2]
            event_storage.add_event(event)

        sql_statements: list[str] = []

        def tracer(sql: str) -> None:
            sql_statements.append(sql)

        event_storage._conn.set_trace_callback(tracer)
        try:
            events, cursor = event_storage.get_events(limit=3)
        finally:
            event_storage._conn.set_trace_callback(None)

        assert len(events) == 3
        assert cursor is not None
        assert len(sql_statements) <= 3

    def test_get_major_events_by_avatar_uses_batched_association_queries(self, event_storage):
        """Major-event queries should not reload associations row by row."""
        for i in range(3):
            event = make_event(100, i + 1, f"Major {i}", ["a1", f"other{i}"], is_major=True)
            event.related_sects = [1]
            event_storage.add_event(event)

        sql_statements: list[str] = []

        def tracer(sql: str) -> None:
            sql_statements.append(sql)

        event_storage._conn.set_trace_callback(tracer)
        try:
            events = event_storage.get_major_events_by_avatar("a1")
        finally:
            event_storage._conn.set_trace_callback(None)

        assert len(events) == 3
        assert len(sql_statements) <= 3


class TestEventStorageCleanup:
    """Tests for event cleanup functionality."""

    def test_cleanup_keeps_major_by_default(self, event_storage):
        """Test that cleanup keeps major events by default."""
        event_storage.add_event(make_event(100, 1, "Minor", is_major=False))
        event_storage.add_event(make_event(100, 2, "Major", is_major=True))

        deleted = event_storage.cleanup()

        assert deleted == 1
        assert event_storage.count() == 1
        events = event_storage.get_recent_events()
        assert events[0].content == "Major"

    def test_cleanup_deletes_all_when_keep_major_false(self, event_storage):
        """Test cleanup with keep_major=False."""
        event_storage.add_event(make_event(100, 1, "Minor", is_major=False))
        event_storage.add_event(make_event(100, 2, "Major", is_major=True))

        deleted = event_storage.cleanup(keep_major=False)

        assert deleted == 2
        assert event_storage.count() == 0

    def test_cleanup_before_month_stamp(self, event_storage):
        """Test cleanup with before_month_stamp filter."""
        event_storage.add_event(make_event(100, 1, "Old", is_major=False))
        event_storage.add_event(make_event(200, 1, "New", is_major=False))

        # Delete events before year 150
        before_stamp = int(create_month_stamp(Year(150), Month.JANUARY))
        deleted = event_storage.cleanup(keep_major=False, before_month_stamp=before_stamp)

        assert deleted == 1
        assert event_storage.count() == 1
        events = event_storage.get_recent_events()
        assert events[0].content == "New"


class TestEventStorageCursorParsing:
    """Tests for cursor parsing edge cases."""

    def test_parse_cursor_valid(self, event_storage):
        """Test parsing a valid cursor."""
        month_stamp, rowid = event_storage._parse_cursor("1200_42")

        assert month_stamp == 1200
        assert rowid == 42

    def test_parse_cursor_invalid_format(self, event_storage):
        """Test parsing an invalid cursor raises ValueError."""
        with pytest.raises(ValueError):
            event_storage._parse_cursor("invalid")

    def test_make_cursor(self, event_storage):
        """Test cursor generation."""
        cursor = event_storage._make_cursor(1200, 42)

        assert cursor == "1200_42"


# --- EventManager Tests ---

class TestEventManagerWithStorage:
    """EventManager tests with SQLite storage."""

    def test_add_event(self, event_manager):
        """Test adding events through EventManager."""
        event = make_event(100, 5, "Test event", ["a1"])

        event_manager.add_event(event)

        assert event_manager.count() == 1

    def test_add_event_captures_subject_name_from_world_resolver(self, event_manager):
        event_manager.set_subject_resolver(
            lambda avatar_id: SimpleNamespace(name="Alice") if avatar_id == "a1" else None
        )
        event = make_event(100, 5, "Alice acted", ["a1"])

        event_manager.add_event(event)
        events = event_manager.get_recent_events()

        assert events[0].subject_snapshots == {"a1": "Alice"}

    def test_add_null_event_ignored(self, event_manager):
        """Test that NULL_EVENT is ignored."""
        event_manager.add_event(NULL_EVENT)

        assert event_manager.count() == 0

    def test_get_recent_events(self, event_manager):
        """Test getting recent events."""
        event_manager.add_event(make_event(100, 1, "First", ["a1"]))
        event_manager.add_event(make_event(100, 6, "Second", ["a1"]))

        events = event_manager.get_recent_events()

        assert len(events) == 2
        # Chronological order
        assert events[0].content == "First"
        assert events[1].content == "Second"

    def test_get_events_by_avatar(self, event_manager):
        """Test getting events by avatar."""
        event_manager.add_event(make_event(100, 1, "A1 event", ["a1"]))
        event_manager.add_event(make_event(100, 2, "A2 event", ["a2"]))

        events = event_manager.get_events_by_avatar("a1")

        assert len(events) == 1
        assert events[0].content == "A1 event"

    def test_get_events_between(self, event_manager):
        """Test getting events between two avatars."""
        event_manager.add_event(make_event(100, 1, "A1 only", ["a1"]))
        event_manager.add_event(make_event(100, 2, "A1+A2", ["a1", "a2"]))

        events = event_manager.get_events_between("a1", "a2")

        assert len(events) == 1
        assert events[0].content == "A1+A2"

    def test_get_major_events_by_avatar(self, event_manager):
        """Test getting major events for an avatar."""
        event_manager.add_event(make_event(100, 1, "Minor", ["a1"], is_major=False))
        event_manager.add_event(make_event(100, 2, "Major", ["a1"], is_major=True))

        events = event_manager.get_major_events_by_avatar("a1")

        assert len(events) == 1
        assert events[0].content == "Major"

    def test_get_minor_events_by_avatar(self, event_manager):
        """Test getting minor events for an avatar."""
        event_manager.add_event(make_event(100, 1, "Minor", ["a1"], is_major=False))
        event_manager.add_event(make_event(100, 2, "Major", ["a1"], is_major=True))

        events = event_manager.get_minor_events_by_avatar("a1")

        assert len(events) == 1
        assert events[0].content == "Minor"

    def test_get_major_events_between(self, event_manager):
        """Test getting major events between two avatars."""
        event_manager.add_event(make_event(100, 1, "Minor pair", ["a1", "a2"], is_major=False))
        event_manager.add_event(make_event(100, 2, "Major pair", ["a1", "a2"], is_major=True))

        events = event_manager.get_major_events_between("a1", "a2")

        assert len(events) == 1
        assert events[0].content == "Major pair"

    def test_get_minor_events_between(self, event_manager):
        """Test getting minor events between two avatars."""
        event_manager.add_event(make_event(100, 1, "Minor pair", ["a1", "a2"], is_major=False))
        event_manager.add_event(make_event(100, 2, "Major pair", ["a1", "a2"], is_major=True))

        events = event_manager.get_minor_events_between("a1", "a2")

        assert len(events) == 1
        assert events[0].content == "Minor pair"


class TestEventManagerPagination:
    """EventManager pagination tests."""

    def test_get_events_paginated_basic(self, event_manager):
        """Test basic pagination through EventManager."""
        for i in range(10):
            event_manager.add_event(make_event(100, i + 1, f"Event {i}"))

        events, cursor, has_more = event_manager.get_events_paginated(limit=5)

        assert len(events) == 5
        assert cursor is not None
        assert has_more is True

    def test_get_events_paginated_with_filter(self, event_manager):
        """Test paginated query with avatar filter."""
        for i in range(10):
            avatar = "a1" if i % 2 == 0 else "a2"
            event_manager.add_event(make_event(100, i + 1, f"Event {i}", [avatar]))

        events, cursor, has_more = event_manager.get_events_paginated(avatar_id="a1", limit=3)

        assert len(events) == 3
        assert has_more is True
        for e in events:
            assert "a1" in e.related_avatars

    def test_get_events_paginated_with_pair_filter(self, event_manager):
        """Test paginated query with avatar pair filter."""
        event_manager.add_event(make_event(100, 1, "A1 only", ["a1"]))
        event_manager.add_event(make_event(100, 2, "A1+A2", ["a1", "a2"]))
        event_manager.add_event(make_event(100, 3, "A2 only", ["a2"]))

        events, _, _ = event_manager.get_events_paginated(avatar_id_pair=("a1", "a2"))

        assert len(events) == 1
        assert events[0].content == "A1+A2"

    def test_get_events_paginated_no_more(self, event_manager):
        """Test pagination when there are no more events."""
        event_manager.add_event(make_event(100, 1, "Event 1"))
        event_manager.add_event(make_event(100, 2, "Event 2"))

        events, cursor, has_more = event_manager.get_events_paginated(limit=10)

        assert len(events) == 2
        assert cursor is None
        assert has_more is False


class TestEventManagerMemoryMode:
    """EventManager tests in memory fallback mode."""

    def test_add_and_get_events(self, memory_event_manager):
        """Test basic operations in memory mode."""
        memory_event_manager.add_event(make_event(100, 1, "Event 1", ["a1"]))
        memory_event_manager.add_event(make_event(100, 2, "Event 2", ["a2"]))

        events = memory_event_manager.get_recent_events()

        assert len(events) == 2

    def test_get_events_by_avatar_memory(self, memory_event_manager):
        """Test avatar filtering in memory mode."""
        memory_event_manager.add_event(make_event(100, 1, "A1 event", ["a1"]))
        memory_event_manager.add_event(make_event(100, 2, "A2 event", ["a2"]))

        events = memory_event_manager.get_events_by_avatar("a1")

        assert len(events) == 1
        assert events[0].content == "A1 event"

    def test_get_events_between_memory(self, memory_event_manager):
        """Test pair filtering in memory mode."""
        memory_event_manager.add_event(make_event(100, 1, "A1 only", ["a1"]))
        memory_event_manager.add_event(make_event(100, 2, "A1+A2", ["a1", "a2"]))

        events = memory_event_manager.get_events_between("a1", "a2")

        assert len(events) == 1
        assert events[0].content == "A1+A2"

    def test_get_major_events_memory(self, memory_event_manager):
        """Test major event filtering in memory mode."""
        memory_event_manager.add_event(make_event(100, 1, "Minor", ["a1"], is_major=False))
        memory_event_manager.add_event(make_event(100, 2, "Major", ["a1"], is_major=True))

        events = memory_event_manager.get_major_events_by_avatar("a1")

        assert len(events) == 1
        assert events[0].content == "Major"

    def test_get_minor_events_memory(self, memory_event_manager):
        """Test minor event filtering in memory mode."""
        memory_event_manager.add_event(make_event(100, 1, "Minor", ["a1"], is_major=False))
        memory_event_manager.add_event(make_event(100, 2, "Story", ["a1"], is_major=True, is_story=True))
        memory_event_manager.add_event(make_event(100, 3, "Major", ["a1"], is_major=True))

        events = memory_event_manager.get_minor_events_by_avatar("a1")

        assert len(events) == 2
        contents = [e.content for e in events]
        assert "Minor" in contents
        assert "Story" in contents

    def test_pagination_memory_mode(self, memory_event_manager):
        """Test that pagination in memory mode returns all events without real pagination."""
        for i in range(10):
            memory_event_manager.add_event(make_event(100, i + 1, f"Event {i}"))

        events, cursor, has_more = memory_event_manager.get_events_paginated(limit=5)

        # Memory mode doesn't support real pagination
        assert len(events) == 5  # Still respects limit
        assert cursor is None
        assert has_more is False

    def test_cleanup_memory_mode(self, memory_event_manager):
        """Test cleanup in memory mode clears all events."""
        memory_event_manager.add_event(make_event(100, 1, "Event 1"))
        memory_event_manager.add_event(make_event(100, 2, "Event 2"))

        deleted = memory_event_manager.cleanup()

        assert deleted == 2
        assert memory_event_manager.count() == 0


class TestEventManagerCleanup:
    """EventManager cleanup tests with SQLite storage."""

    def test_cleanup_delegates_to_storage(self, event_manager):
        """Test that cleanup delegates to storage."""
        event_manager.add_event(make_event(100, 1, "Minor", is_major=False))
        event_manager.add_event(make_event(100, 2, "Major", is_major=True))

        deleted = event_manager.cleanup()

        assert deleted == 1
        assert event_manager.count() == 1


# --- Edge Cases ---

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_storage_closed_operations_fail_gracefully(self, temp_db_path):
        """Test that operations on closed storage fail gracefully."""
        storage = EventStorage(temp_db_path)
        storage.close()

        # Mock logger to suppress expected errors
        storage._logger = MagicMock()

        # Should return False/empty rather than throwing
        assert storage.add_event(make_event(100, 1, "Test")) is False
        events, cursor = storage.get_events()
        assert events == []
        assert storage.count() == 0

    def test_event_with_many_avatars(self, event_storage):
        """Test event with many related avatars."""
        avatar_ids = [f"avatar_{i}" for i in range(20)]
        event = make_event(100, 1, "Large group event", avatar_ids)

        event_storage.add_event(event)

        events, _ = event_storage.get_events()
        assert len(events) == 1
        assert set(events[0].related_avatars) == set(avatar_ids)

    def test_empty_content(self, event_storage):
        """Test event with empty content."""
        event = make_event(100, 1, "", ["a1"])

        result = event_storage.add_event(event)

        assert result is True
        events, _ = event_storage.get_events()
        assert events[0].content == ""

    def test_special_characters_in_content(self, event_storage):
        """Test event with special characters in content."""
        content = "测试中文 & 'quotes' \"double\" <tag> END"
        event = make_event(100, 1, content, ["a1"])

        event_storage.add_event(event)

        events, _ = event_storage.get_events()
        assert events[0].content == content

    def test_same_month_stamp_ordering(self, event_storage):
        """Test that events with same month_stamp maintain insertion order."""
        # Add multiple events in the same month
        for i in range(5):
            event_storage.add_event(make_event(100, 6, f"Event {i}"))

        events, _ = event_storage.get_events()

        # Should be in reverse insertion order (newest first)
        assert events[0].content == "Event 4"
        assert events[4].content == "Event 0"


class TestEventStorageThreadSafety:
    """Tests for thread-safe access around the shared SQLite connection."""

    def test_concurrent_add_event_calls_do_not_corrupt_storage(self, event_storage):
        """Concurrent writes should serialize cleanly and preserve all events."""
        total_events = 40

        def write_event(index: int) -> bool:
            return event_storage.add_event(
                make_event(
                    100 + (index % 3),
                    (index % 12) + 1,
                    f"Concurrent event {index}",
                    [f"avatar_{index % 5}"],
                    event_id=f"concurrent-{index}",
                )
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(write_event, range(total_events)))

        assert all(results)
        assert event_storage.count() == total_events

        events, _ = event_storage.get_events(limit=total_events + 5)
        assert len(events) == total_events
        assert {event.id for event in events} == {f"concurrent-{i}" for i in range(total_events)}

    def test_concurrent_reads_and_writes_remain_usable(self, event_storage):
        """Mixed readers and writers should not throw or leave the store unusable."""
        preload_events = 12
        added_during_test = 18

        for i in range(preload_events):
            event_storage.add_event(
                make_event(
                    99,
                    (i % 12) + 1,
                    f"Seed event {i}",
                    [f"seed_avatar_{i % 3}"],
                    event_id=f"seed-{i}",
                )
            )

        def writer(index: int) -> bool:
            return event_storage.add_event(
                make_event(
                    101,
                    (index % 12) + 1,
                    f"Live event {index}",
                    [f"live_avatar_{index % 4}"],
                    is_major=(index % 2 == 0),
                    event_id=f"live-{index}",
                )
            )

        def reader(index: int) -> tuple[int, int, int]:
            all_events, _ = event_storage.get_events(limit=64)
            recent_for_avatar = event_storage.get_events_by_avatar(f"seed_avatar_{index % 3}", limit=10)
            major_for_avatar = event_storage.get_major_events_by_avatar(f"live_avatar_{index % 4}", limit=10)
            return len(all_events), len(recent_for_avatar), len(major_for_avatar)

        futures = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            for i in range(added_during_test):
                futures.append(executor.submit(writer, i))
                futures.append(executor.submit(reader, i))

        results = [future.result() for future in futures]

        writer_results = results[0::2]
        reader_results = results[1::2]

        assert all(writer_results)
        assert all(isinstance(snapshot, tuple) and len(snapshot) == 3 for snapshot in reader_results)

        expected_total = preload_events + added_during_test
        assert event_storage.count() == expected_total

        final_events, _ = event_storage.get_events(limit=expected_total + 5)
        assert len(final_events) == expected_total
