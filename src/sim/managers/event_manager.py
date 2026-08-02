"""
事件管理器。

提供事件写入和查询 facade，底层优先使用 SQLite storage。
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, TYPE_CHECKING
from src.classes.event_query import EventAudience, EventMemoryScope, EventQuery, matches_memory_scope

if TYPE_CHECKING:
    from src.classes.event import Event
    from src.classes.event_storage import EventStorage


class EventManager:
    """
    事件管理器：使用 SQLite 持久化存储。

    对外提供统一事件接口：
    - add_event: 添加事件
    - get_recent_events: 获取最近事件
    - get_events_by_avatar: 按角色查询
    - get_events_between: 按角色对查询
    - get_major_events_by_avatar: 获取角色大事
    - get_minor_events_by_avatar: 获取角色小事
    - get_major_events_between: 获取角色对大事
    - get_minor_events_between: 获取角色对小事
    """

    def __init__(self, storage: Optional["EventStorage"] = None):
        """
        初始化事件管理器。

        Args:
            storage: SQLite 存储层。如果为 None，则使用内存模式（仅用于测试）。
        """
        self._storage = storage
        self._subject_resolver: Callable[[str], object | None] | None = None
        # 内存后备，仅当 storage 为 None 时使用，主要用于测试。
        self._memory_events: List["Event"] = []

    @classmethod
    def create_with_db(cls, db_path: Path) -> "EventManager":
        """
        工厂方法：创建使用 SQLite 的事件管理器。

        Args:
            db_path: 数据库文件路径。

        Returns:
            配置好的 EventManager 实例。
        """
        from src.classes.event_storage import EventStorage
        storage = EventStorage(db_path)
        return cls(storage)

    @classmethod
    def create_in_memory(cls) -> "EventManager":
        """
        工厂方法：创建内存模式的事件管理器（仅用于测试）。

        Returns:
            内存模式的 EventManager 实例。
        """
        return cls(storage=None)

    def set_subject_resolver(self, resolver: Callable[[str], object | None]) -> None:
        self._subject_resolver = resolver

    def _capture_subject_snapshots(self, event: "Event") -> None:
        if self._subject_resolver is None:
            return
        snapshots = dict(getattr(event, "subject_snapshots", {}) or {})
        for avatar_id in getattr(event, "related_avatars", None) or []:
            avatar_id_str = str(avatar_id)
            if avatar_id_str in snapshots:
                continue
            avatar = self._subject_resolver(avatar_id_str)
            name = getattr(avatar, "name", None) if avatar is not None else None
            if name:
                snapshots[avatar_id_str] = str(name)
        event.subject_snapshots = snapshots

    def add_event(self, event: "Event") -> None:
        """
        添加事件。

        如果有 SQLite 存储，实时写入数据库。
        否则存入内存后备列表。
        """
        # 过滤空事件。
        from src.classes.event import is_null_event
        if is_null_event(event):
            return

        self._capture_subject_snapshots(event)

        if self._storage:
            self._storage.add_event(event)
        else:
            # 内存后备模式。
            self._memory_events.append(event)

    @staticmethod
    def _is_observed_by(event: "Event", avatar_id: str) -> bool:
        avatar_id = str(avatar_id)
        if event.related_avatars and avatar_id in {str(item) for item in event.related_avatars}:
            return True
        for observation in getattr(event, "observations", []) or []:
            if str(getattr(observation, "observer_avatar_id", "")) == avatar_id:
                return True
        return False

    @staticmethod
    def _render_for_observer(event: "Event", avatar_id: str) -> "Event":
        from src.classes.event import Event
        from src.classes.event_renderer import render_observed_event

        avatar_id = str(avatar_id)
        matched_observation = None
        for observation in getattr(event, "observations", []) or []:
            if str(getattr(observation, "observer_avatar_id", "")) == avatar_id:
                matched_observation = {
                    "propagation_kind": getattr(observation, "propagation_kind", "self_direct"),
                    "subject_avatar_id": getattr(observation, "subject_avatar_id", None),
                }
                break

        if matched_observation is None and event.related_avatars and avatar_id in {str(item) for item in event.related_avatars}:
            matched_observation = {
                "propagation_kind": "self_direct",
                "subject_avatar_id": avatar_id,
            }

        if matched_observation is None:
            return event

        rendered = Event.from_dict(event.to_dict())
        rendered.content = render_observed_event(rendered, matched_observation)
        return rendered

    def get_recent_events(self, limit: int = 100) -> List["Event"]:
        """获取最近的事件（时间正序）。"""
        if self._storage:
            return self._storage.get_recent_events(limit=limit)
        else:
            return self._memory_events[-limit:]

    def get_events_by_avatar(self, avatar_id: str, *, limit: int = 50) -> List["Event"]:
        """获取角色相关的事件（时间正序）。"""
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id),), limit=limit, chronological=True))

    def get_events_between(self, avatar_id1: str, avatar_id2: str, *, limit: int = 50) -> List["Event"]:
        """获取两个角色之间的事件（时间正序）。"""
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id1), str(avatar_id2)), limit=limit, chronological=True))

    def get_major_events_by_avatar(self, avatar_id: str, *, limit: int = 10) -> List["Event"]:
        """获取角色的大事（长期记忆，时间正序）。"""
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id),), audience=EventAudience.OBSERVED,
                                            memory_scope=EventMemoryScope.MAJOR, limit=limit, chronological=True))

    def get_minor_events_by_avatar(self, avatar_id: str, *, limit: int = 10) -> List["Event"]:
        """获取角色的小事（短期记忆，时间正序）。"""
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id),), audience=EventAudience.OBSERVED,
                                            memory_scope=EventMemoryScope.MINOR, limit=limit, chronological=True))

    def get_major_events_between(self, avatar_id1: str, avatar_id2: str, *, limit: int = 10) -> List["Event"]:
        """获取两个角色之间的大事（长期记忆，时间正序）。"""
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id1), str(avatar_id2)),
                                            memory_scope=EventMemoryScope.MAJOR, limit=limit, chronological=True))

    def get_minor_events_between(self, avatar_id1: str, avatar_id2: str, *, limit: int = 10) -> List["Event"]:
        """获取两个角色之间的小事（短期记忆，时间正序）。"""
        return self.query_events(EventQuery(avatar_ids=(str(avatar_id1), str(avatar_id2)),
                                            memory_scope=EventMemoryScope.MINOR, limit=limit, chronological=True))

    def query_events(self, query: EventQuery) -> List["Event"]:
        """Execute the same semantic query contract in either storage backend."""
        if self._storage:
            return self._storage.query_events(query)

        if query.audience is EventAudience.OBSERVED and len(query.avatar_ids) != 1:
            raise ValueError("Observed event queries require exactly one avatar")
        result: list["Event"] = []
        for event in reversed(self._memory_events):
            related = {str(item) for item in (event.related_avatars or [])}
            if query.audience is EventAudience.OBSERVED:
                matched = self._is_observed_by(event, query.avatar_ids[0])
            else:
                matched = all(avatar_id in related for avatar_id in query.avatar_ids)
            if not matched or not matches_memory_scope(event, query.memory_scope):
                continue
            if query.sect_id is not None and query.sect_id not in (getattr(event, "related_sects", None) or []):
                continue
            result.append(self._render_for_observer(event, query.avatar_ids[0]) if query.audience is EventAudience.OBSERVED else event)
            if len(result) >= query.limit:
                break
        return list(reversed(result)) if query.chronological else result

    # --- 分页查询接口（新增）---

    def get_events_paginated(
        self,
        avatar_id: Optional[str] = None,
        avatar_id_pair: Optional[tuple[str, str]] = None,
        sect_id: Optional[int] = None,
        major_scope: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 100,
    ) -> tuple[List["Event"], Optional[str], bool]:
        """
        分页查询事件。

        Args:
            avatar_id: 按单个角色筛选。
            avatar_id_pair: Pair 查询（两个角色之间的事件）。
            sect_id: 按单个宗门筛选。
            cursor: 分页 cursor，获取该位置之前的事件。
            limit: 每页数量。

        Returns:
            (events, next_cursor, has_more)
            - events: 事件列表（时间倒序，最新在前）。
            - next_cursor: 下一页的 cursor，None 表示没有更多。
            - has_more: 是否有更多数据。
        """
        if self._storage:
            events, next_cursor = self._storage.get_events(
                avatar_id=avatar_id,
                avatar_id_pair=avatar_id_pair,
                sect_id=sect_id,
                major_scope=major_scope,
                cursor=cursor,
                limit=limit,
            )
            return events, next_cursor, next_cursor is not None
        else:
            # 内存模式不支持完整分页，做轻量过滤后返回最近的。
            filtered_events = self._memory_events
            if avatar_id_pair:
                id1, id2 = avatar_id_pair
                filtered_events = [
                    e for e in filtered_events
                    if e.related_avatars and id1 in e.related_avatars and id2 in e.related_avatars
                ]
            elif avatar_id:
                filtered_events = [
                    e for e in filtered_events
                    if e.related_avatars and avatar_id in e.related_avatars
                ]

            if sect_id is not None:
                filtered_events = [
                    e for e in filtered_events
                    if getattr(e, "related_sects", None) and sect_id in (e.related_sects or [])
                ]

            if major_scope == "major":
                filtered_events = [e for e in filtered_events if e.is_major and not e.is_story]
            elif major_scope == "minor":
                filtered_events = [e for e in filtered_events if (not e.is_major) or e.is_story]

            events = filtered_events[-limit:]
            return list(reversed(events)), None, False

    # --- 清理接口 ---

    def cleanup(self, keep_major: bool = True, before_month_stamp: Optional[int] = None) -> int:
        """
        清理事件。

        Args:
            keep_major: 是否保留大事。
            before_month_stamp: 删除此时间之前的事件。

        Returns:
            删除的事件数量。
        """
        if self._storage:
            return self._storage.cleanup(keep_major=keep_major, before_month_stamp=before_month_stamp)
        else:
            # 内存模式：简单清空。
            count = len(self._memory_events)
            self._memory_events.clear()
            return count

    def count(self) -> int:
        """获取事件总数。"""
        if self._storage:
            return self._storage.count()
        else:
            return len(self._memory_events)

    def close(self) -> None:
        """关闭资源。"""
        if self._storage:
            self._storage.close()
