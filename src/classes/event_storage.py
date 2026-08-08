"""
SQLite 事件存储层。

提供事件的持久化存储、分页查询和清理功能。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from contextlib import contextmanager
from datetime import datetime, timezone

from src.run.log import get_logger
from src.classes.event_query import EventAudience, EventMemoryScope, EventPage, EventQuery


class EventStorageError(RuntimeError):
    """A persistent event-store operation failed.

    An empty result means that no event matched a query; it must never hide a
    SQLite failure.  Callers can now distinguish these two cases reliably.
    """

if TYPE_CHECKING:
    from src.classes.event import Event
    from src.classes.event_observation import EventObservation

def _format_time(ts: float) -> str:
    """将 timestamp float 转换为 SQLite 兼容的 UTC 字符串"""
    return datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f')

def _parse_time(ts_str: str) -> float:
    """将 SQLite 时间字符串解析为 timestamp float"""
    if not ts_str:
        return 0.0
    try:
        # 尝试带微秒的格式
        dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        try:
            # 尝试不带微秒的格式
            dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return 0.0
    # 假设数据库存的是 UTC (naive time string from sqlite usually treated as such)
    return dt.replace(tzinfo=timezone.utc).timestamp()

class EventStorage:
    """
    SQLite 事件存储层。

    提供：
    - 实时写入事件
    - 分页查询（cursor-based）
    - 按角色/角色对查询
    - 历史清理
    """

    def __init__(self, db_path: Path):
        """
        初始化数据库连接，创建表（如不存在）。

        Args:
            db_path: 数据库文件路径。
        """
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        # 单连接模型下，用可重入锁串行化所有 SQL 操作，避免读写交错污染连接状态。
        self._db_lock = threading.RLock()
        self._logger = get_logger().logger
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库连接和表结构。"""
        try:
            with self._db_lock:
                # 确保目录存在。
                self._db_path.parent.mkdir(parents=True, exist_ok=True)

                self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
                self._conn.row_factory = sqlite3.Row

                # 启用外键约束。
                self._conn.execute("PRAGMA foreign_keys = ON")

                # 创建表。
                self._conn.executescript("""
                    CREATE TABLE IF NOT EXISTS events (
                        id TEXT PRIMARY KEY,
                        month_stamp INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        is_major BOOLEAN DEFAULT FALSE,
                        is_story BOOLEAN DEFAULT FALSE,
                        event_type TEXT DEFAULT '',
                        render_key TEXT,
                        render_params TEXT,
                        subject_snapshots TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS event_avatars (
                        event_id TEXT NOT NULL,
                        avatar_id TEXT NOT NULL,
                        PRIMARY KEY (event_id, avatar_id),
                        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_events_month_stamp
                        ON events(month_stamp DESC);
                    CREATE INDEX IF NOT EXISTS idx_events_is_major
                        ON events(is_major);
                    CREATE INDEX IF NOT EXISTS idx_event_avatars_avatar_id
                        ON event_avatars(avatar_id);
                    CREATE INDEX IF NOT EXISTS idx_event_avatars_event_id
                        ON event_avatars(event_id);

                    CREATE TABLE IF NOT EXISTS event_sects (
                        event_id TEXT NOT NULL,
                        sect_id INTEGER NOT NULL,
                        PRIMARY KEY (event_id, sect_id),
                        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_event_sects_sect_id
                        ON event_sects(sect_id);
                    CREATE INDEX IF NOT EXISTS idx_event_sects_event_id
                        ON event_sects(event_id);

                    CREATE TABLE IF NOT EXISTS event_observations (
                        id TEXT PRIMARY KEY,
                        event_id TEXT NOT NULL,
                        observer_avatar_id TEXT NOT NULL,
                        subject_avatar_id TEXT,
                        propagation_kind TEXT NOT NULL,
                        relation_type TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(event_id, observer_avatar_id, propagation_kind),
                        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_event_observations_observer_avatar_id
                        ON event_observations(observer_avatar_id);
                    CREATE INDEX IF NOT EXISTS idx_event_observations_event_id
                        ON event_observations(event_id);
                    CREATE INDEX IF NOT EXISTS idx_event_observations_subject_avatar_id
                        ON event_observations(subject_avatar_id);
                """)
                columns = {
                    row["name"]
                    for row in self._conn.execute("PRAGMA table_info(events)").fetchall()
                }
                if "subject_snapshots" not in columns:
                    self._conn.execute("ALTER TABLE events ADD COLUMN subject_snapshots TEXT")
                self._conn.commit()
            self._logger.info(f"EventStorage initialized: {self._db_path}")
        except Exception as e:
            self._logger.error(f"Failed to initialize EventStorage: {e}")
            raise

    @contextmanager
    def _transaction(self):
        """事务上下文管理器。"""
        with self._db_lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def add_event(self, event: "Event") -> bool:
        """
        写入单个事件。

        失败时记录日志并返回 False，不抛异常。

        Args:
            event: 要写入的事件对象。

        Returns:
            写入是否成功。
        """
        if self._conn is None:
            self._logger.error("EventStorage not initialized")
            return False

        try:
            with self._transaction():
                # 插入事件主表。
                self._conn.execute(
                    """
                    INSERT OR IGNORE INTO events (
                        id, month_stamp, content, is_major, is_story, event_type, render_key, render_params, subject_snapshots, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.id,
                        int(event.month_stamp),
                        event.content,
                        event.is_major,
                        event.is_story,
                        event.event_type,
                        event.render_key,
                        json.dumps(event.render_params, ensure_ascii=False) if event.render_params is not None else None,
                        json.dumps(getattr(event, "subject_snapshots", {}), ensure_ascii=False),
                        _format_time(event.created_at),
                    )
                )

                # 插入关联表。
                if event.related_avatars:
                    for avatar_id in event.related_avatars:
                        self._conn.execute(
                            """
                            INSERT OR IGNORE INTO event_avatars (event_id, avatar_id)
                            VALUES (?, ?)
                            """,
                            (event.id, str(avatar_id))
                        )
                
                # 插入宗门关联表。
                if getattr(event, "related_sects", None):
                    for sect_id in event.related_sects:
                        self._conn.execute(
                            """
                            INSERT OR IGNORE INTO event_sects (event_id, sect_id)
                            VALUES (?, ?)
                            """,
                            (event.id, int(sect_id))
                        )

                for observation in self._build_observations_for_event(event):
                    self._conn.execute(
                        """
                        INSERT OR IGNORE INTO event_observations (
                            id, event_id, observer_avatar_id, subject_avatar_id,
                            propagation_kind, relation_type, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            observation.id,
                            event.id,
                            str(observation.observer_avatar_id),
                            str(observation.subject_avatar_id) if observation.subject_avatar_id is not None else None,
                            str(observation.propagation_kind),
                            observation.relation_type,
                            _format_time(observation.created_at),
                        )
                    )
            return True
        except Exception as e:
            self._logger.error(f"Failed to write event {event.id}: {e}")
            return False

    def _build_observations_for_event(self, event: "Event") -> list["EventObservation"]:
        from src.classes.event_observation import EventObservation

        observations: list[EventObservation] = []
        seen: set[tuple[str, str, str]] = set()

        for avatar_id in event.related_avatars or []:
            key = (event.id, str(avatar_id), "self_direct")
            if key in seen:
                continue
            seen.add(key)
            observations.append(
                EventObservation(
                    event_id=event.id,
                    observer_avatar_id=str(avatar_id),
                    subject_avatar_id=str(avatar_id),
                    propagation_kind="self_direct",
                )
            )

        for observation in getattr(event, "observations", []) or []:
            observation.event_id = event.id
            key = (event.id, str(observation.observer_avatar_id), str(observation.propagation_kind))
            if key in seen:
                continue
            seen.add(key)
            observations.append(observation)

        return observations

    def _load_avatar_map_for_events(self, event_ids: list[str]) -> dict[str, list[str]]:
        if not event_ids:
            return {}

        placeholders = ",".join("?" for _ in event_ids)
        with self._db_lock:
            rows = self._conn.execute(
                f"""
                SELECT event_id, avatar_id
                FROM event_avatars
                WHERE event_id IN ({placeholders})
                ORDER BY rowid ASC
                """,
                event_ids,
            ).fetchall()

        grouped: dict[str, list[str]] = {}
        for row in rows:
            grouped.setdefault(row["event_id"], []).append(row["avatar_id"])
        return grouped

    def _load_sect_map_for_events(self, event_ids: list[str]) -> dict[str, list[int]]:
        if not event_ids:
            return {}

        placeholders = ",".join("?" for _ in event_ids)
        with self._db_lock:
            rows = self._conn.execute(
                f"""
                SELECT event_id, sect_id
                FROM event_sects
                WHERE event_id IN ({placeholders})
                ORDER BY rowid ASC
                """,
                event_ids,
            ).fetchall()

        grouped: dict[str, list[int]] = {}
        for row in rows:
            grouped.setdefault(row["event_id"], []).append(row["sect_id"])
        return grouped

    def _row_to_event(
        self,
        row,
        *,
        avatar_map: Optional[dict[str, list[str]]] = None,
        sect_map: Optional[dict[str, list[int]]] = None,
    ) -> "Event":
        from src.classes.event import Event
        from src.systems.time import MonthStamp

        if avatar_map is None:
            with self._db_lock:
                avatar_rows = self._conn.execute(
                    "SELECT avatar_id FROM event_avatars WHERE event_id = ?",
                    (row["id"],)
                ).fetchall()
            related_avatars = [r["avatar_id"] for r in avatar_rows]
        else:
            related_avatars = avatar_map.get(row["id"], [])

        if sect_map is None:
            with self._db_lock:
                sect_rows = self._conn.execute(
                    "SELECT sect_id FROM event_sects WHERE event_id = ?",
                    (row["id"],)
                ).fetchall()
            related_sects = [r["sect_id"] for r in sect_rows]
        else:
            related_sects = sect_map.get(row["id"], [])

        snapshot_json = row["subject_snapshots"] if "subject_snapshots" in row.keys() else None
        return Event(
            month_stamp=MonthStamp(row["month_stamp"]),
            content=row["content"],
            related_avatars=related_avatars if related_avatars else None,
            related_sects=related_sects if related_sects else None,
            is_major=bool(row["is_major"]),
            is_story=bool(row["is_story"]),
            event_type=row["event_type"] or "",
            render_key=row["render_key"],
            render_params=json.loads(row["render_params"]) if row["render_params"] else None,
            subject_snapshots=json.loads(snapshot_json) if snapshot_json else {},
            id=row["id"],
            created_at=_parse_time(row["created_at"]),
        )

    def _build_events_from_rows(self, rows) -> list["Event"]:
        event_ids = [row["id"] for row in rows]
        avatar_map = self._load_avatar_map_for_events(event_ids)
        sect_map = self._load_sect_map_for_events(event_ids)
        return [
            self._row_to_event(row, avatar_map=avatar_map, sect_map=sect_map)
            for row in rows
        ]

    def _load_observation_map_for_events(self, event_ids: list[str]) -> dict[str, list[sqlite3.Row]]:
        if not event_ids:
            return {}
        placeholders = ",".join("?" for _ in event_ids)
        with self._db_lock:
            rows = self._conn.execute(
                f"""
                SELECT id, event_id, observer_avatar_id, subject_avatar_id, propagation_kind, relation_type, created_at
                FROM event_observations
                WHERE event_id IN ({placeholders})
                ORDER BY created_at ASC
                """,
                event_ids,
            ).fetchall()
        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(row["event_id"], []).append(row)
        return grouped

    def _parse_cursor(self, cursor: str) -> tuple[int, int]:
        """
        解析复合 cursor。

        格式: {month_stamp}_{rowid}

        Returns:
            (month_stamp, rowid)
        """
        parts = cursor.split("_", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid cursor format: {cursor}")
        return int(parts[0]), int(parts[1])

    def _make_cursor(self, month_stamp: int, rowid: int) -> str:
        """生成复合 cursor。"""
        return f"{month_stamp}_{rowid}"

    def _query_direct_page(
        self,
        avatar_id: Optional[str] = None,
        avatar_id_pair: Optional[tuple[str, str]] = None,
        sect_id: Optional[int] = None,
        major_scope: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 100,
    ) -> EventPage["Event"]:
        """
        分页查询事件。

        Args:
            avatar_id: 按单个角色筛选。
            avatar_id_pair: Pair 查询（两个角色之间的事件）。
            sect_id: 按单个宗门筛选。
            cursor: 分页 cursor，获取该位置之前的事件。
            limit: 每页数量。

        Returns:
            (events, next_cursor)，next_cursor 为 None 表示没有更多。
        """
        if self._conn is None:
            return EventPage([])

        base_query = ""
        params: list = []
        try:
            with self._db_lock:
                # 构建查询。
                if avatar_id_pair:
                    # Pair 查询：两个角色都相关的事件。
                    id1, id2 = avatar_id_pair
                    base_query = """
                        SELECT DISTINCT
                            e.rowid, e.id, e.month_stamp, e.content, e.is_major, e.is_story,
                            e.event_type, e.render_key, e.render_params, e.subject_snapshots, e.created_at
                        FROM events e
                        JOIN event_avatars ea1 ON e.id = ea1.event_id AND ea1.avatar_id = ?
                        JOIN event_avatars ea2 ON e.id = ea2.event_id AND ea2.avatar_id = ?
                    """
                    params.extend([id1, id2])
                elif avatar_id:
                    # 单角色查询。
                    base_query = """
                        SELECT DISTINCT
                            e.rowid, e.id, e.month_stamp, e.content, e.is_major, e.is_story,
                            e.event_type, e.render_key, e.render_params, e.subject_snapshots, e.created_at
                        FROM events e
                        JOIN event_avatars ea ON e.id = ea.event_id AND ea.avatar_id = ?
                    """
                    params.append(avatar_id)
                elif sect_id is not None:
                    # 宗门查询。
                    base_query = """
                        SELECT DISTINCT
                            e.rowid, e.id, e.month_stamp, e.content, e.is_major, e.is_story,
                            e.event_type, e.render_key, e.render_params, e.subject_snapshots, e.created_at
                        FROM events e
                        JOIN event_sects es ON e.id = es.event_id AND es.sect_id = ?
                    """
                    params.append(sect_id)
                else:
                    # 全部事件。
                    base_query = """
                        SELECT
                            rowid, id, month_stamp, content, is_major, is_story,
                            event_type, render_key, render_params, e.subject_snapshots, e.created_at
                        FROM events e
                    """

                # Cursor 条件（获取更旧的事件）。
                # 使用 rowid 保证同一 month_stamp 内的确定性顺序。
                where_clauses = []
                if major_scope == "major":
                    where_clauses.append("e.is_major = TRUE AND e.is_story = FALSE")
                elif major_scope == "minor":
                    where_clauses.append("(e.is_major = FALSE OR e.is_story = TRUE)")

                if cursor:
                    cursor_month, cursor_rowid = self._parse_cursor(cursor)
                    where_clauses.append(
                        "(e.month_stamp < ? OR (e.month_stamp = ? AND e.rowid < ?))"
                    )
                    params.extend([cursor_month, cursor_month, cursor_rowid])

                # 组装 WHERE。
                if where_clauses:
                    base_query += " WHERE " + " AND ".join(where_clauses)

                # 排序和分页（最新的在前，向上加载更旧的）。
                # 使用 rowid 保证同一 month_stamp 内的插入顺序。
                base_query += " ORDER BY e.month_stamp DESC, e.rowid DESC LIMIT ?"
                params.append(limit + 1)  # 多取一条判断是否有更多。

                rows = self._conn.execute(base_query, params).fetchall()

                # 判断是否有更多。
                has_more = len(rows) > limit
                if has_more:
                    rows = rows[:limit]

                # 构建事件对象。
                events = self._build_events_from_rows(rows)
                last_rowid = rows[-1]["rowid"] if rows else None
                last_month_stamp = rows[-1]["month_stamp"] if rows else None

                # 生成 next_cursor。
                next_cursor = None
                if has_more and last_rowid is not None:
                    next_cursor = self._make_cursor(last_month_stamp, last_rowid)

                return EventPage(events, next_cursor)

        except Exception as e:
            self._logger.exception(
                "Failed to query events: %s | avatar_id=%r avatar_id_pair=%r sect_id=%r "
                "major_scope=%r cursor=%r limit=%r sql=%r params=%r",
                e,
                avatar_id,
                avatar_id_pair,
                sect_id,
                major_scope,
                cursor,
                limit,
                base_query,
                params,
            )
            raise EventStorageError("Failed to query events") from e

    def query_page(self, query: EventQuery) -> EventPage["Event"]:
        """Execute an EventQuery and preserve its pagination information."""
        if self._conn is None:
            return EventPage([])
        if query.audience is EventAudience.DIRECT:
            avatar_ids = query.avatar_ids
            if len(avatar_ids) > 2:
                raise ValueError("Direct event queries support at most two avatars")
            return self._query_direct_page(
                avatar_id=avatar_ids[0] if len(avatar_ids) == 1 else None,
                avatar_id_pair=(avatar_ids[0], avatar_ids[1]) if len(avatar_ids) == 2 else None,
                sect_id=query.sect_id,
                major_scope=None if query.memory_scope is EventMemoryScope.ALL else query.memory_scope.value,
                cursor=query.cursor,
                limit=query.limit,
            )

        if len(query.avatar_ids) != 1:
            raise ValueError("Observed event queries require exactly one avatar")
        scope_sql = {
            EventMemoryScope.ALL: "1=1",
            EventMemoryScope.MAJOR: "e.is_major = TRUE AND e.is_story = FALSE",
            EventMemoryScope.MINOR: "e.is_major = FALSE OR e.is_story = TRUE",
        }[query.memory_scope]
        params: list[object] = [query.avatar_ids[0]]
        where_clauses = [scope_sql]
        if query.sect_id is not None:
            where_clauses.append("EXISTS (SELECT 1 FROM event_sects es WHERE es.event_id = e.id AND es.sect_id = ?)")
            params.append(query.sect_id)
        if query.cursor:
            cursor_month, cursor_rowid = self._parse_cursor(query.cursor)
            where_clauses.append("(e.month_stamp < ? OR (e.month_stamp = ? AND e.rowid < ?))")
            params.extend([cursor_month, cursor_month, cursor_rowid])
        sql = f"""
            SELECT DISTINCT e.rowid, e.id, e.month_stamp, e.content, e.is_major, e.is_story,
                e.event_type, e.render_key, e.render_params, e.subject_snapshots, e.created_at,
                eo.propagation_kind, eo.observer_avatar_id, eo.subject_avatar_id, eo.relation_type
            FROM events e JOIN event_observations eo
                ON e.id = eo.event_id AND eo.observer_avatar_id = ?
            WHERE {' AND '.join(where_clauses)}
            ORDER BY e.month_stamp DESC, e.rowid DESC LIMIT ?
        """
        params.append(query.limit + 1)
        try:
            with self._db_lock:
                rows = self._conn.execute(sql, params).fetchall()
            has_more = len(rows) > query.limit
            rows = rows[:query.limit]
            events = self._build_events_from_rows(rows)
            from src.classes.event_renderer import render_observed_event
            for event, row in zip(events, rows):
                event.content = render_observed_event(event, row)
            next_cursor = None
            if has_more and rows:
                next_cursor = self._make_cursor(rows[-1]["month_stamp"], rows[-1]["rowid"])
            return EventPage(events, next_cursor)
        except Exception as exc:
            self._logger.exception("Failed to execute observed event query: %s", exc)
            raise EventStorageError("Failed to query events") from exc

    def get_events(
        self,
        avatar_id: Optional[str] = None,
        avatar_id_pair: Optional[tuple[str, str]] = None,
        sect_id: Optional[int] = None,
        major_scope: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 100,
    ) -> tuple[list["Event"], Optional[str]]:
        """Legacy paginated adapter; use :meth:`query_page` in new code."""
        avatar_ids = avatar_id_pair or ((avatar_id,) if avatar_id else ())
        page = self.query_page(EventQuery(
            avatar_ids=tuple(str(item) for item in avatar_ids),
            sect_id=sect_id,
            memory_scope=EventMemoryScope(major_scope) if major_scope in {"major", "minor"} else EventMemoryScope.ALL,
            cursor=cursor,
            limit=limit,
        ))
        return page.events, page.next_cursor

    def get_events_by_avatar(self, avatar_id: str, limit: int = 50) -> list["Event"]:
        """
        后端用：获取角色相关事件（供 LLM prompt 使用）。

        返回最新的 N 条，按时间正序排列。
        """
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id),), limit=limit, chronological=True))

    def get_events_between(self, id1: str, id2: str, limit: int = 50) -> list["Event"]:
        """
        后端用：获取两角色之间的事件。

        返回最新的 N 条，按时间正序排列。
        """
        return self.query_events(EventQuery(avatar_ids=(str(id1), str(id2)), limit=limit, chronological=True))

    def get_major_events_by_avatar(self, avatar_id: str, limit: int = 10) -> list["Event"]:
        """获取角色的大事（长期记忆）。"""
        return self.query_events(EventQuery(
            avatar_ids=(str(avatar_id),), audience=EventAudience.OBSERVED,
            memory_scope=EventMemoryScope.MAJOR, limit=limit, chronological=True,
        ))

    def get_minor_events_by_avatar(self, avatar_id: str, limit: int = 10) -> list["Event"]:
        """获取角色的小事（短期记忆，包括故事）。"""
        return self.query_events(EventQuery(
            avatar_ids=(str(avatar_id),), audience=EventAudience.OBSERVED,
            memory_scope=EventMemoryScope.MINOR, limit=limit, chronological=True,
        ))

    def get_major_events_between(self, id1: str, id2: str, limit: int = 10) -> list["Event"]:
        """获取两个角色之间的大事（长期记忆）。"""
        return self.query_events(EventQuery(
            avatar_ids=(str(id1), str(id2)), memory_scope=EventMemoryScope.MAJOR,
            limit=limit, chronological=True,
        ))

    def get_minor_events_between(self, id1: str, id2: str, limit: int = 10) -> list["Event"]:
        """获取两个角色之间的小事（短期记忆）。"""
        return self.query_events(EventQuery(
            avatar_ids=(str(id1), str(id2)), memory_scope=EventMemoryScope.MINOR,
            limit=limit, chronological=True,
        ))

    def query_events(self, query: EventQuery) -> list["Event"]:
        """Execute the shared event query contract for the SQLite backend."""
        events = self.query_page(query).events
        return list(reversed(events)) if query.chronological else events

    def get_recent_events(self, limit: int = 100) -> list["Event"]:
        """获取最近的事件（供初始状态 API 使用）。"""
        events = self.query_page(EventQuery(limit=limit)).events
        return list(reversed(events))  # 时间正序。

    def cleanup(self, keep_major: bool = True, before_month_stamp: Optional[int] = None) -> int:
        """
        清理事件。

        Args:
            keep_major: 是否保留大事。
            before_month_stamp: 删除此时间之前的事件。

        Returns:
            删除的事件数量。
        """
        if self._conn is None:
            return 0

        try:
            conditions = []
            params: list = []

            if keep_major:
                conditions.append("is_major = FALSE")

            if before_month_stamp is not None:
                conditions.append("month_stamp < ?")
                params.append(before_month_stamp)

            # 如果没有条件且要保留大事，则无需删除任何内容
            if not conditions and keep_major:
                return 0

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            with self._transaction():
                cursor = self._conn.execute(
                    f"DELETE FROM events WHERE {where_clause}",
                    params
                )
                deleted = cursor.rowcount

            self._logger.info(f"Cleaned up {deleted} events")
            return deleted

        except Exception as e:
            self._logger.error(f"Failed to cleanup events: {e}")
            return 0

    def count(self) -> int:
        """获取事件总数。"""
        if self._conn is None:
            return 0
        try:
            with self._db_lock:
                row = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn:
            try:
                with self._db_lock:
                    self._conn.close()
                    self._logger.info("EventStorage closed")
            except Exception as e:
                self._logger.error(f"Failed to close EventStorage: {e}")
            finally:
                self._conn = None
