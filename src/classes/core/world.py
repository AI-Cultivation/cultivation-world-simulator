from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Any, Iterable
import uuid

from src.classes.environment.map import Map
from src.systems.time import Year, Month, MonthStamp
from src.sim.managers.avatar_manager import AvatarManager
from src.sim.managers.mortal_manager import MortalManager
from src.sim.managers.deceased_manager import DeceasedManager
from src.sim.managers.event_manager import EventManager
from src.classes.circulation import CirculationManager
from src.classes.gathering.gathering import GatheringManager
from src.classes.poi import POIManager
from src.classes.world_lore import WorldLore
from src.classes.world_secret import WorldSecretRuntime
from src.utils.df import game_configs
from src.classes.language import language_manager
from src.i18n import t
from src.classes.ranking import RankingManager
from src.classes.sect_diplomacy_state import SectDiplomacyState
from src.classes.war import STATUS_PEACE, STATUS_WAR
from src.systems.opportunity import OpportunityManager

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar
    from src.classes.celestial_phenomenon import CelestialPhenomenon
    from src.classes.core.dynasty import Dynasty
    from src.classes.core.sect import Sect


@dataclass
class World():
    map: Map
    month_stamp: MonthStamp
    avatar_manager: AvatarManager = field(default_factory=AvatarManager)
    # 凡人管理器
    mortal_manager: MortalManager = field(default_factory=MortalManager)
    # 全局事件管理器
    event_manager: EventManager = field(default_factory=EventManager)
    # 已故角色档案管理器（独立于 AvatarManager，不受 cleanup 影响）
    deceased_manager: DeceasedManager = field(default_factory=DeceasedManager)
    # 运行时点位兴趣点，如墓碑、未来古碑/阵眼等
    poi_manager: POIManager = field(default_factory=POIManager)
    # 当前天地灵机（世界级buff/debuff）
    current_phenomenon: Optional["CelestialPhenomenon"] = None
    # 当前王朝（凡人王朝）
    dynasty: Optional["Dynasty"] = None
    # 天地灵机开始年份（用于计算持续时间）
    phenomenon_start_year: int = 0
    # 出世物品流通管理器
    circulation: CirculationManager = field(default_factory=CirculationManager)
    # Gathering 管理器
    gathering_manager: GatheringManager = field(default_factory=GatheringManager)
    # 本局世界观与历史输入
    world_lore: "WorldLore" = field(default_factory=WorldLore)
    # 世界观塑形后的静态对象快照，用于存档/读档恢复
    world_lore_snapshot: dict[str, Any] = field(default_factory=dict)
    # 本局世界秘密运行时状态，独立于 world_lore
    world_secret: WorldSecretRuntime = field(default_factory=WorldSecretRuntime)
    # 世界开始年份
    start_year: int = 0
    # 榜单管理器
    ranking_manager: RankingManager = field(default_factory=RankingManager)
    # 游玩单局 ID，用于区分存档
    playthrough_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sect_diplomacy: SectDiplomacyState = field(default_factory=SectDiplomacyState)
    # 机缘管理器：维护单人限时机缘状态与冷却。
    opportunity_manager: OpportunityManager = field(default_factory=OpportunityManager)
    # 宗门上下文（惰性初始化），用于统一本局启用宗门作用域
    _sect_context: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if hasattr(self.event_manager, "set_subject_resolver"):
            self.event_manager.set_subject_resolver(
                lambda avatar_id: self.avatar_manager.get_avatar(str(avatar_id))
            )

    def get_info(self, detailed: bool = False, avatar: Optional["Avatar"] = None) -> dict:
        """
        返回世界信息（dict），其中包含地图信息（dict）。
        如果指定了 avatar，将传给 map.get_info 用于过滤区域和计算距离。
        """
        static_info = self.static_info
        map_info = self.map.get_info(detailed=detailed, avatar=avatar)
        world_info = {**map_info, **static_info}

        if self.current_phenomenon:
            # 使用翻译 Key
            key = t("Current World Phenomenon")
            # 格式化内容，注意这里我们假设 name 和 desc 已经是当前语言的（它们是对象属性，加载时确定）
            # 但如果需要在 Prompt 中有特定的格式（如中文用【】，英文不用），也可以引入 key
            # 为了简单起见，我们把格式也放入翻译
            # "phenomenon_format": "【{name}】{desc}" (ZH) vs "{name}: {desc}" (EN)
            value = t("phenomenon_format", name=self.current_phenomenon.name, desc=self.current_phenomenon.desc)
            world_info[key] = value

        return world_info

    def get_avatars_in_same_region(self, avatar: "Avatar"):
        return self.avatar_manager.get_avatars_in_same_region(avatar)

    def get_observable_avatars(self, avatar: "Avatar"):
        return self.avatar_manager.get_observable_avatars(avatar)

    @property
    def sect_context(self) -> "SectContext":
        """
        提供统一的宗门作用域访问入口。
        - active_sects 默认来自 existed_sects；
        - 若不存在，则回退到全局 sects_by_id。
        """
        if self._sect_context is None:
            self._sect_context = SectContext(self)
            # 使用当前世界上的 existed_sects 初始化上下文（若存在）
            existed = getattr(self, "existed_sects", None)
            if existed:
                self._sect_context.from_existed_sects(existed)
        return self._sect_context

    @property
    def sect_relation_modifiers(self) -> list[dict[str, Any]]:
        return self.sect_diplomacy.relation_modifiers

    @sect_relation_modifiers.setter
    def sect_relation_modifiers(self, value: Iterable[dict[str, Any]]) -> None:
        self.sect_diplomacy.set_relation_modifiers(value)

    @property
    def sect_wars(self) -> list[dict[str, Any]]:
        return self.sect_diplomacy.wars

    @sect_wars.setter
    def sect_wars(self, value: Iterable[dict[str, Any]]) -> None:
        self.sect_diplomacy.set_wars(value)

    def add_sect_relation_modifier(
        self,
        *,
        sect_a_id: int,
        sect_b_id: int,
        delta: int,
        duration: int,
        reason: str,
        meta: Optional[dict] = None,
    ) -> None:
        self.sect_diplomacy.add_relation_modifier(sect_a_id=sect_a_id, sect_b_id=sect_b_id, delta=delta, duration=duration, reason=reason, current_month=int(self.month_stamp), meta=meta)

    def get_sect_war(self, sect_a_id: int, sect_b_id: int) -> Optional[dict[str, Any]]:
        return self.sect_diplomacy.get_war(sect_a_id, sect_b_id)

    def are_sects_at_war(self, sect_a_id: int, sect_b_id: int) -> bool:
        war = self.get_sect_war(sect_a_id, sect_b_id)
        return bool(war and str(war.get("status", "")) == STATUS_WAR)

    def declare_sect_war(
        self,
        *,
        sect_a_id: int,
        sect_b_id: int,
        reason: str = "",
        start_month: Optional[int] = None,
    ) -> dict[str, Any]:
        return self.sect_diplomacy.declare_war(sect_a_id=sect_a_id, sect_b_id=sect_b_id, current_month=int(self.month_stamp if start_month is None else start_month), reason=reason)

    def make_sect_peace(
        self,
        *,
        sect_a_id: int,
        sect_b_id: int,
        reason: str = "",
        peace_start_month: Optional[int] = None,
    ) -> dict[str, Any]:
        return self.sect_diplomacy.make_peace(sect_a_id=sect_a_id, sect_b_id=sect_b_id, current_month=int(self.month_stamp if peace_start_month is None else peace_start_month), reason=reason)

    def record_sect_battle(self, sect_a_id: int, sect_b_id: int, *, battle_month: Optional[int] = None) -> None:
        self.sect_diplomacy.record_battle(sect_a_id, sect_b_id, current_month=int(self.month_stamp if battle_month is None else battle_month))

    def get_sect_diplomacy_state(
        self,
        sect_a_id: int,
        sect_b_id: int,
        *,
        current_month: Optional[int] = None,
    ) -> dict[str, Any]:
        return self.sect_diplomacy.get_state(
            sect_a_id,
            sect_b_id,
            current_month=int(self.month_stamp if current_month is None else current_month),
            start_year=self.start_year,
        )

    def prune_expired_sect_relation_modifiers(self, current_month: Optional[int] = None) -> None:
        self.sect_diplomacy.prune_relation_modifiers(
            current_month=int(self.month_stamp if current_month is None else current_month)
        )

    def get_active_sect_relation_breakdown(
        self, current_month: Optional[int] = None
    ) -> dict[tuple[int, int], list[dict[str, Any]]]:
        return self.sect_diplomacy.relation_breakdown(
            current_month=int(self.month_stamp if current_month is None else current_month)
        )

    def get_active_sect_diplomacy_breakdown(
        self,
        current_month: Optional[int] = None,
        sect_ids: Optional[Iterable[int]] = None,
    ) -> dict[tuple[int, int], list[dict[str, Any]]]:
        return self.sect_diplomacy.diplomacy_breakdown(
            current_month=int(self.month_stamp if current_month is None else current_month),
            start_year=self.start_year,
            sect_ids=sect_ids,
        )

    def set_world_lore(self, lore_text: str) -> None:
        """设置本局的世界观与历史输入文本。"""
        self.world_lore.text = lore_text

    @property
    def static_info(self) -> dict:
        info_list = game_configs.get("world_info", [])
        desc = {}
        for row in info_list:
            t_val = row.get("title")
            d_val = row.get("desc")
            if t_val and d_val:
                desc[t_val] = d_val
        return desc

    @classmethod
    def create_with_db(
        cls,
        map: "Map",
        month_stamp: MonthStamp,
        events_db_path: Path,
        start_year: int = 0,
    ) -> "World":
        """
        工厂方法：创建使用 SQLite 持久化事件的 World 实例。

        Args:
            map: 地图对象。
            month_stamp: 时间戳。
            events_db_path: 事件数据库文件路径。
            start_year: 世界开始年份。

        Returns:
            配置好的 World 实例。
        """
        event_manager = EventManager.create_with_db(events_db_path)
        world = cls(
            map=map,
            month_stamp=month_stamp,
            event_manager=event_manager,
            start_year=start_year,
        )
        
        # 初始化天下武道会的时间
        world.ranking_manager.init_tournament_info(
            start_year,
            month_stamp.get_year(),
            month_stamp.get_month().value
        )
        
        return world


class SectContext:
    """
    本局宗门上下文。
    负责维护“本局启用且仍存续的宗门 ID 集合”，并提供统一的 active 宗门读取入口。
    """

    def __init__(self, world: World):
        self._world = world
        self.active_sect_ids: set[int] = set()

    def from_existed_sects(self, existed_sects: Iterable["Sect"]) -> None:
        """根据本局启用宗门列表初始化 active_sect_ids。"""
        self.active_sect_ids = {
            int(getattr(sect, "id", 0))
            for sect in existed_sects
            if getattr(sect, "is_active", True)
        }

    def mark_sect_inactive(self, sect_id: int) -> None:
        """在上下文中标记某宗门为失效。"""
        try:
            sid = int(sect_id)
        except (TypeError, ValueError):
            return
        self.active_sect_ids.discard(sid)

    def get_active_sects(self) -> list["Sect"]:
        """
        返回当前本局仍然激活的宗门列表。
        优先使用 world.existed_sects（保持与当前局实际挂载的 Sect 实例一致），
        再结合 active_sect_ids 做过滤；若不存在，则回退到全局 sects_by_id。
        """
        from src.classes.core.sect import sects_by_id
        existed = getattr(self._world, "existed_sects", None) or []

        # 1. 若世界上存在显式的 existed_sects，则以其为主（保持与当前局实例一致）
        if existed:
            if self.active_sect_ids:
                return [
                    sect
                    for sect in existed
                    if int(getattr(sect, "id", 0)) in self.active_sect_ids
                    and getattr(sect, "is_active", True)
                ]
            return [sect for sect in existed if getattr(sect, "is_active", True)]

        # 2. 不存在 existed_sects 时，再根据 active_sect_ids 过滤全局 sects_by_id
        if self.active_sect_ids:
            return [
                sect
                for sid, sect in sects_by_id.items()
                if sid in self.active_sect_ids and getattr(sect, "is_active", True)
            ]

        # 3. 最后回退到全局 sects_by_id 的激活宗门
        return [sect for sect in sects_by_id.values() if getattr(sect, "is_active", True)]
