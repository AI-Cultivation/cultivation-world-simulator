from dataclasses import dataclass, field
from pathlib import Path
import json
from enum import Enum

from src.classes.alignment import Alignment
from src.utils.df import game_configs, get_str, get_float, get_int, get_bool
from src.classes.effect import load_effect_from_str
from src.classes.sect_effect import SectEffectsMixin
from src.classes.core.orthodoxy import get_orthodoxy
from src.utils.config import CONFIG

from typing import TYPE_CHECKING, Optional

from src.systems.cultivation import Realm
if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar
    from src.classes.technique import Technique
    from src.classes.sect_ranks import SectRank
    from src.classes.weapon_type import WeaponType

"""
宗门、宗门总部基础数据。
驻地名称与描述已迁移到 sect_region.csv，供地图区域系统使用。
此处仅保留宗门本体信息与头像编辑所需的静态字段。
"""


class SectRuleId(str, Enum):
    RIGHTEOUS_ORTHODOXY = "righteous_orthodoxy"
    EVIL_SECT_LOYALTY = "evil_sect_loyalty"
    NEUTRAL_SECRECY = "neutral_secrecy"

# 宗门驻地（基础展示数据，具体地图位置在 sect_region.csv 中定义）
@dataclass
class SectHeadQuarter:
    """
    宗门总部
    """
    name: str
    desc: str
    image: Path

@dataclass
class Sect(SectEffectsMixin):
    """
    宗门
    """
    id: int
    name: str
    desc: str
    member_act_style: str
    alignment: Alignment
    headquarter: SectHeadQuarter
    # 本宗关联的功法名称（来自 technique.csv 的 sect 列）
    technique_names: list[str]
    name_id: str = ""
    # 随机选择宗门时使用的权重（默认1）
    weight: float = 1.0
    # 宗门倾向的兵器类型
    preferred_weapon: Optional["WeaponType"] = None
    # 影响角色或系统的效果
    effects: dict[str, object] = field(default_factory=dict)
    effect_desc: str = ""
    sect_effects: dict[str, object] = field(default_factory=dict)
    temporary_sect_effects: list[dict] = field(default_factory=list)
    # 宗门自定义职位名称（可选）：SectRank -> 名称
    rank_names: dict[str, str] = field(default_factory=dict)
    # 道统ID
    orthodoxy_id: str = "dao"
    # 门规
    rule_id: str = ""
    rule_desc: str = ""
    # 是否接纳妖族弟子
    accept_yao: bool = True
    
    # 势力相关
    magic_stone: int = 0
    war_weariness: int = 0
    is_active: bool = True
    total_battle_strength: float = 0.0
    influence_radius: int = 0
    color: str = "#FFFFFF"
    # 宗门周期思考（仅展示用途，不写入事件流）
    periodic_thinking: str = ""
    # 最近一次宗门决策摘要（运行时）
    last_decision_summary: str = ""

    # 运行时成员列表：Avatar ID -> Avatar
    members: dict[str, "Avatar"] = field(default_factory=dict, init=False)
    # 功法对象列表：Technique
    techniques: list["Technique"] = field(default_factory=list, init=False)

    def __post_init__(self):
        self.members = {}
        self.techniques = []
        self.sect_effects = dict(self.sect_effects or {})
        self.temporary_sect_effects = list(self.temporary_sect_effects or [])
        self.war_weariness = self._clamp_war_weariness(self.war_weariness)

    @staticmethod
    def _clamp_war_weariness(value: int | float) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            normalized = 0
        return max(0, min(100, normalized))

    def set_war_weariness(self, value: int | float) -> None:
        self.war_weariness = self._clamp_war_weariness(value)

    def change_war_weariness(self, delta: int | float) -> None:
        self.set_war_weariness(int(self.war_weariness) + int(delta))

    def add_member(self, avatar: "Avatar") -> None:
        """添加成员到宗门"""
        if avatar.id not in self.members:
            self.members[avatar.id] = avatar
    
    def remove_member(self, avatar: "Avatar") -> None:
        """从宗门移除成员"""
        if avatar.id in self.members:
            del self.members[avatar.id]

    def accepts_race(self, race: object) -> bool:
        from src.classes.race import is_yao_race

        return self.accept_yao or not is_yao_race(race)

    def accepts_avatar_race(self, avatar: "Avatar") -> bool:
        return self.accepts_race(getattr(avatar, "race", None))

    def get_info(self) -> str:
        from src.i18n import t
        hq = self.headquarter
        orthodoxy = get_orthodoxy(self.orthodoxy_id)
        orthodoxy_name = t(orthodoxy.name) if orthodoxy else self.orthodoxy_id
        return t("{sect_name} (Orthodoxy: {orthodoxy}, Alignment: {alignment}, Headquarters: {hq_name})",
                sect_name=self.name, orthodoxy=orthodoxy_name, alignment=str(self.alignment), hq_name=hq.name)

    def get_detailed_info(self) -> str:
        # 详细描述：风格、阵营、驻地
        from src.i18n import t
        hq = self.headquarter
        effect_part = t(" Effect: {effect_desc}", effect_desc=self.effect_desc) if self.effect_desc else ""
        
        orthodoxy = get_orthodoxy(self.orthodoxy_id)
        orthodoxy_name = t(orthodoxy.name) if orthodoxy else self.orthodoxy_id
        
        return t("{sect_name} (Orthodoxy: {orthodoxy}, Alignment: {alignment}, Style: {style}, Headquarters: {hq_name}){effect}",
                sect_name=self.name, orthodoxy=orthodoxy_name, alignment=str(self.alignment), 
                style=t(self.member_act_style), hq_name=hq.name, effect=effect_part)
    
    def get_rank_name(self, rank: "SectRank") -> str:
        """
        获取宗门的职位名称（支持自定义）
        
        Args:
            rank: 宗门职位枚举
            
        Returns:
            职位名称字符串
        """
        from src.classes.sect_ranks import SectRank, DEFAULT_RANK_NAMES
        from src.i18n import t
        # 优先使用自定义名称，否则使用默认名称
        val = self.rank_names.get(rank.value, DEFAULT_RANK_NAMES.get(rank, t("Disciple")))
        return t(val)

    def get_structured_info(self) -> dict:
        hq = self.headquarter
        from src.i18n import t
        from src.classes.sect_ranks import RANK_ORDER
        from src.classes.technique import techniques_by_name
        status_snapshot_by_avatar = self._build_member_status_snapshot_map()
        
        # 成员列表：直接从 self.members 获取
        members_list = []
        for a in self.members.values():
            rank_enum = getattr(a, "sect_rank", None)
            sort_val = 999
            if rank_enum and rank_enum in RANK_ORDER:
                sort_val = RANK_ORDER[rank_enum]
            member_status = status_snapshot_by_avatar.get(str(getattr(a, "id", "")), {})
                
            members_list.append({
                "id": str(a.id),
                "name": a.name,
                # 这里仅提供一个占位头像 ID，前端会有自己的 fallback 逻辑
                "pic_id": getattr(a, "custom_pic_id", 0) or 0,
                "gender": a.gender.value if hasattr(a.gender, "value") else "male",
                "rank": a.get_sect_rank_name(),
                "realm": a.cultivation_progress.get_info() if hasattr(a, 'cultivation_progress') else t("Unknown"),
                "contribution": int(member_status.get("sect_contribution", 0) or 0),
                "base_battle_strength": int(member_status.get("base_battle_strength", 0) or 0),
                "status_score": float(member_status.get("status_score", 0.0) or 0.0),
                "_sort_val": sort_val,
            })
        # 按职位排序
        members_list.sort(key=lambda x: (x["_sort_val"], -x["contribution"], -x["status_score"], x["name"]))
        # 清理排序字段
        for m in members_list:
            del m["_sort_val"]

        # 填充 techniques
        # 使用 technique_names 从全局字典中查找对应的 Technique 对象并序列化
        techniques_data = []
        for t_name in self.technique_names:
            t_obj = techniques_by_name.get(t_name)
            if t_obj:
                techniques_data.append(t_obj.get_structured_info())
            else:
                # Fallback for missing techniques: create a minimal structure
                techniques_data.append({
                    "name": t_name,
                    "desc": t("(Unknown technique)"),
                    "grade": "",
                    "color": (200, 200, 200), # Gray
                    "attribute": "",
                    "effect_desc": ""
                })

        orthodoxy = get_orthodoxy(self.orthodoxy_id)

        return {
            "id": self.id,
            "name": self.name,
            "desc": self.desc,
            "alignment": str(self.alignment), # 直接返回中文
            "style": t(self.member_act_style),
            "hq_name": hq.name,
            "hq_desc": hq.desc,
            "effect_desc": self.effect_desc,
            "techniques": techniques_data,
            # 领域模型仍以 technique_names 维护配置来源，API 同时提供结构化 techniques。
            "technique_names": self.technique_names,
            "preferred_weapon": str(self.preferred_weapon) if self.preferred_weapon else "",
            "members": members_list,
            "orthodoxy": orthodoxy.get_info(detailed=True) if orthodoxy else {"id": self.orthodoxy_id},
            "magic_stone": self.magic_stone,
            "war_weariness": self.war_weariness,
            "is_active": self.is_active,
            "total_battle_strength": self.total_battle_strength,
            "influence_radius": self.influence_radius,
            "color": self.color,
            "rule_id": self.rule_id,
            "rule_desc": self.rule_desc,
            "accept_yao": self.accept_yao,
            "periodic_thinking": self.periodic_thinking,
            # 前端仍标记为 deprecated 的别名，语义等同 periodic_thinking。
            "yearly_thinking": self.periodic_thinking,
        }

    def is_alignment_recruitable(self, alignment: Alignment | None) -> bool:
        if alignment is None:
            return True
        if self.alignment == Alignment.RIGHTEOUS:
            return alignment != Alignment.EVIL
        if self.alignment == Alignment.EVIL:
            return alignment != Alignment.RIGHTEOUS
        return True

    def is_member_rule_breaker(self, avatar: "Avatar") -> bool:
        """
        当前版本只处理“极端到足以驱逐”的明显门规冲突。
        更细的门规行为判断后续可以在这里继续扩展。
        """
        alignment = getattr(avatar, "alignment", None)
        if alignment is None:
            return False

        if self.rule_id == SectRuleId.RIGHTEOUS_ORTHODOXY.value:
            return alignment == Alignment.EVIL
        if self.rule_id == SectRuleId.EVIL_SECT_LOYALTY.value:
            return alignment == Alignment.RIGHTEOUS
        return False

    def get_identity_summary(self) -> dict:
        from src.i18n import t

        orthodoxy = get_orthodoxy(self.orthodoxy_id)
        return {
            "sect_name": self.name,
            "purpose": self.desc,
            "style": t(self.member_act_style),
            "alignment": str(self.alignment),
            "orthodoxy_id": self.orthodoxy_id,
            "orthodoxy_name": t(orthodoxy.name) if orthodoxy else self.orthodoxy_id,
            "rule_id": self.rule_id,
            "rule_desc": self.rule_desc,
        }

    def get_member_upkeep_by_realm(self) -> dict[Realm, int]:
        return get_sect_member_upkeep_by_realm()

    def get_member_upkeep_by_rank(self) -> dict["SectRank", int]:
        from src.classes.sect_ranks import SectRank

        realm_upkeep = self.get_member_upkeep_by_realm()
        return {
            SectRank.OuterDisciple: realm_upkeep.get(Realm.Qi_Refinement, 0),
            SectRank.InnerDisciple: realm_upkeep.get(Realm.Foundation_Establishment, 0),
            SectRank.Elder: realm_upkeep.get(Realm.Core_Formation, 0),
            SectRank.Patriarch: realm_upkeep.get(Realm.Nascent_Soul, 0),
        }

    def _resolve_member_rank(self, avatar: "Avatar") -> "SectRank":
        from src.classes.sect_ranks import SectRank, get_rank_from_realm

        rank = getattr(avatar, "sect_rank", None)
        if isinstance(rank, SectRank):
            return rank
        if isinstance(rank, str):
            normalized = rank.strip().lower()
            string_mapping = {
                "patriarch": SectRank.Patriarch,
                "elder": SectRank.Elder,
                "inner": SectRank.InnerDisciple,
                "innerdisciple": SectRank.InnerDisciple,
                "outer": SectRank.OuterDisciple,
                "outerdisciple": SectRank.OuterDisciple,
            }
            if normalized in string_mapping:
                return string_mapping[normalized]
        realm = getattr(getattr(avatar, "cultivation_progress", None), "realm", Realm.Qi_Refinement)
        return get_rank_from_realm(realm)

    def get_member_upkeep_for_avatar(self, avatar: "Avatar") -> int:
        rank = self._resolve_member_rank(avatar)
        return self.get_member_upkeep_by_rank().get(rank, 0)

    def estimate_yearly_member_upkeep(self) -> tuple[int, dict[str, dict[str, int]]]:
        total = 0
        breakdown: dict[str, dict[str, int]] = {}
        upkeep_by_rank = self.get_member_upkeep_by_rank()

        for avatar in getattr(self, "members", {}).values():
            if getattr(avatar, "is_dead", False):
                continue
            rank = self._resolve_member_rank(avatar)
            cost = upkeep_by_rank.get(rank, 0)
            key = str(rank.value)
            entry = breakdown.setdefault(
                key,
                {
                    "rank": str(rank),
                    "member_count": 0,
                    "upkeep_per_member": cost,
                    "subtotal": 0,
                },
            )
            entry["member_count"] += 1
            entry["subtotal"] += cost
            total += cost

        return total, breakdown

    def _get_status_normalization_context(self) -> dict[str, float]:
        from src.classes.sect_member_status import SectMemberStatusService
        return SectMemberStatusService.normalization(self)

    def get_member_status_score(
        self,
        avatar: "Avatar",
        *,
        max_contribution: float | None = None,
        max_battle_strength: float | None = None,
    ) -> float:
        from src.classes.sect_member_status import SectMemberStatusService
        normalization = self._get_status_normalization_context()
        return SectMemberStatusService.score(
            avatar,
            max_contribution=float(max_contribution if max_contribution is not None else normalization["max_contribution"]),
            max_battle_strength=float(max_battle_strength if max_battle_strength is not None else normalization["max_battle_strength"]),
        )

    def get_member_status_snapshot(self, avatar: "Avatar") -> dict[str, float | int]:
        from src.classes.sect_member_status import SectMemberStatusService
        return SectMemberStatusService.snapshot(self, avatar)

    def _build_member_status_snapshot_map(self) -> dict[str, dict[str, float | int]]:
        from src.classes.sect_member_status import SectMemberStatusService
        return SectMemberStatusService.snapshot_map(self)

    def get_member_status_snapshot_with_normalization(
        self,
        avatar: "Avatar",
        *,
        max_contribution: float,
        max_battle_strength: float,
    ) -> dict[str, float | int]:
        from src.classes.sect_member_status import SectMemberStatusService
        return SectMemberStatusService.snapshot(self, avatar, normalization={
            "max_contribution": max_contribution, "max_battle_strength": max_battle_strength,
        })

    def get_living_members_sorted_by_status(self) -> list["Avatar"]:
        from src.classes.sect_member_status import SectMemberStatusService
        return SectMemberStatusService.living_members_sorted(self)

    def refresh_member_ranks(self) -> None:
        from src.classes.sect_ranks import SectRank

        members = self.get_living_members_sorted_by_status()
        count = len(members)
        if count <= 0:
            return

        elder_quota = 0
        if count >= 4:
            elder_quota = max(1, count // 6)
        inner_quota = 0
        if count >= 2:
            inner_quota = max(1, count // 3)
        inner_quota = min(inner_quota, max(0, count - 1 - elder_quota))

        for index, avatar in enumerate(members):
            if index == 0:
                avatar.sect_rank = SectRank.Patriarch
            elif index <= elder_quota:
                avatar.sect_rank = SectRank.Elder
            elif index <= elder_quota + inner_quota:
                avatar.sect_rank = SectRank.InnerDisciple
            else:
                avatar.sect_rank = SectRank.OuterDisciple


def get_sect_member_upkeep_by_realm() -> dict[Realm, int]:
    defaults = {
        Realm.Qi_Refinement: 15,
        Realm.Foundation_Establishment: 30,
        Realm.Core_Formation: 60,
        Realm.Nascent_Soul: 120,
    }

    sect_conf = getattr(CONFIG, "sect", None)
    configured = getattr(sect_conf, "member_upkeep_by_realm", None) if sect_conf is not None else None
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

def _split_names(value: object) -> list[str]:
    raw = "" if value is None or str(value) == "nan" else str(value)
    sep = CONFIG.df.ids_separator
    parts = [x.strip() for x in raw.split(sep) if x.strip()] if raw else []
    return parts

def _merge_effects_dict(base: dict[str, object], addition: dict[str, object]) -> dict[str, object]:
    """合并两个 effects 字典（简单合并逻辑）"""
    if not base and not addition:
        return {}
    merged: dict[str, object] = dict(base) if base else {}
    for key, val in (addition or {}).items():
        if key in merged:
            old = merged[key]
            if isinstance(old, list) and isinstance(val, list):
                # 去重并集
                seen = set(old)
                result = list(old)
                for x in val:
                    if x not in seen:
                        seen.add(x)
                        result.append(x)
                merged[key] = result
            elif isinstance(old, (int, float)) and isinstance(val, (int, float)):
                merged[key] = old + val
            else:
                # 默认覆盖
                merged[key] = val
        else:
            merged[key] = val
    return merged

def _load_sects_data() -> tuple[dict[int, Sect], dict[str, Sect]]:
    """从配表加载 sect 数据
    返回：新的 (sects_by_id, sects_by_name)
    """
    new_by_id: dict[int, Sect] = {}
    new_by_name: dict[str, Sect] = {}

    df = game_configs["sect"]
    # 读取宗门驻地映射（优先从 sect_region.csv 获取驻地地名/描述）
    sect_region_df = game_configs.get("sect_region")
    hq_by_sect_id: dict[int, tuple[str, str]] = {}
    if sect_region_df is not None:
        for sr in sect_region_df:
            sid = get_int(sr, "sect_id", -1)
            if sid == -1:
                continue
            hq_name = get_str(sr, "name")
            hq_desc = get_str(sr, "desc")
            hq_by_sect_id[sid] = (hq_name, hq_desc)
    
    # 可能不存在 technique 配表或未添加 sect 列，做容错
    tech_df = game_configs.get("technique")
    assets_base = Path("assets/sects")
    
    for row in df:
        name = get_str(row, "name")
        image_path = assets_base / f"{name}.png"
        
        # 先读取当前宗门 ID，供后续使用
        sid = get_int(row, "id")

        # 收集该宗门下配置的功法名称
        technique_names: list[str] = []
        # 检查 tech_df 是否存在以及是否有数据
        if tech_df:
            technique_names = [
                get_str(t, "name")
                for t in tech_df
                if get_int(t, "sect_id") == sid and get_str(t, "name")
            ]

        weight = get_float(row, "weight", 1.0)

        # 读取 effects
        base_effects = load_effect_from_str(get_str(row, "effects"))
        
        # 道统处理
        orthodoxy_id = get_str(row, "orthodoxy_id") or "dao"
        orthodoxy = get_orthodoxy(orthodoxy_id)
        
        # 合并道统 Effects 到宗门 Effects
        final_effects = base_effects
        if orthodoxy and orthodoxy.effects:
             # 以道统为基础，宗门效果叠加/覆盖之
             final_effects = _merge_effects_dict(orthodoxy.effects, base_effects)
        
        from src.classes.effect import format_effects_to_text
        effect_desc = format_effects_to_text(final_effects)

        # 读取倾向兵器类型
        from src.classes.weapon_type import WeaponType
        preferred_weapon_str = get_str(row, "preferred_weapon")
        preferred_weapon = WeaponType.from_str(preferred_weapon_str) if preferred_weapon_str else None

        # 解析自定义职位
        raw_ranks = get_str(row, "rank_names")
        rank_names_map = {}
        if raw_ranks:
            # 格式：掌门;长老;内门;外门
            parts = [x.strip() for x in raw_ranks.split(";") if x.strip()]
            if len(parts) == 4:
                from src.classes.sect_ranks import SectRank
                rank_names_map = {
                    SectRank.Patriarch.value: parts[0],
                    SectRank.Elder.value: parts[1],
                    SectRank.InnerDisciple.value: parts[2],
                    SectRank.OuterDisciple.value: parts[3],
                }

        # 从 sect_region.csv 中优先取驻地名称/描述；否则使用行内驻地列或退回宗门名
        csv_hq = hq_by_sect_id.get(sid)
        hq_name_from_csv = (csv_hq[0] if csv_hq else "").strip() if csv_hq else ""
        hq_desc_from_csv = (csv_hq[1] if csv_hq else "").strip() if csv_hq else ""

        hq_name = hq_name_from_csv or get_str(row, "headquarter_name") or name
        hq_desc = hq_desc_from_csv or get_str(row, "headquarter_desc")
        
        color = get_str(row, "color") or "#FFFFFF"
        rule_id = get_str(row, "rule_id")
        rule_desc_id = get_str(row, "rule_desc_id")
        from src.i18n import t
        rule_desc = t(rule_desc_id) if rule_desc_id else ""
        if rule_desc == rule_desc_id:
            rule_desc = ""

        sect = Sect(
            id=sid,
            name_id=get_str(row, "name_id"),
            name=name,
            desc=get_str(row, "desc"),
            member_act_style=get_str(row, "member_act_style"),
            alignment=Alignment.from_str(get_str(row, "alignment")),
            headquarter=SectHeadQuarter(
                name=hq_name,
                desc=hq_desc,
                image=image_path,
            ),
            technique_names=technique_names,
            weight=weight,
            preferred_weapon=preferred_weapon,
            effects=final_effects,
            effect_desc=effect_desc,
            rank_names=rank_names_map,
            orthodoxy_id=orthodoxy_id,
            color=color,
            rule_id=rule_id,
            rule_desc=rule_desc,
            accept_yao=get_bool(row, "accept_yao", True),
        )
        new_by_id[sect.id] = sect
        new_by_name[sect.name] = sect

    return new_by_id, new_by_name

# 全局容器（保持引用不变）
sects_by_id: dict[int, Sect] = {}
sects_by_name: dict[str, Sect] = {}

def reload():
    """重新加载数据，保留全局字典引用"""
    new_id, new_name = _load_sects_data()
    
    sects_by_id.clear()
    sects_by_id.update(new_id)
    
    sects_by_name.clear()
    sects_by_name.update(new_name)

# 模块初始化时执行一次
reload()


def get_sect_info_with_rank(avatar: "Avatar", detailed: bool = False) -> str:
    """
    获取包含职位的宗门信息字符串
    
    Args:
        avatar: 角色对象
        detailed: 是否包含宗门详细信息（阵营、风格、驻地等）
        
    Returns:
        - 散修：返回"散修"
        - detailed=False：返回"明心剑宗长老"
        - detailed=True：返回"明心剑宗长老（阵营：正，风格：...，驻地：...）"
    """
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from src.classes.core.avatar import Avatar
    
    # 散修直接返回
    from src.i18n import t
    if avatar.sect is None:
        return t("Rogue Cultivator")
    
    # 获取职位+宗门名（如"明心剑宗长老"）
    sect_rank_str = avatar.get_sect_str()
    
    # 如果不需要详细信息，直接返回职位字符串
    if not detailed:
        return sect_rank_str
    
    # 需要详细信息：拼接宗门的详细描述
    # 不解析字符串，而是重新构造
    hq = avatar.sect.headquarter
    effect_part = t(" Effect: {effect_desc}", effect_desc=avatar.sect.effect_desc) if avatar.sect.effect_desc else ""
    
    # 构造详细信息，使用标准空格和括号
    orthodoxy = get_orthodoxy(avatar.sect.orthodoxy_id)
    orthodoxy_name = t(orthodoxy.name) if orthodoxy else avatar.sect.orthodoxy_id
    
    detail_content = t("(Orthodoxy: {orthodoxy}, Alignment: {alignment}, Style: {style}, Headquarters: {hq_name}){effect}",
                       orthodoxy=orthodoxy_name,
                       alignment=avatar.sect.alignment, 
                       style=t(avatar.sect.member_act_style), 
                       hq_name=hq.name, 
                       effect=effect_part)
    
    return f"{sect_rank_str} {detail_content}"


def get_sect_decision_context(
    sect: "Sect",
    world: "World",
    event_storage: "EventStorage",
    *,
    history_limit: int = 50,
):
    """
    便捷入口：获取宗门决策上下文。

    为避免领域层直接依赖具体系统实现，仅在此做一次转调。
    """
    from src.systems.sect_decision_context import build_sect_decision_context

    return build_sect_decision_context(
        sect=sect,
        world=world,
        event_storage=event_storage,
        history_limit=history_limit,
    )
