from __future__ import annotations

# 基类与工具
from .action import (
    Action,
    DefineAction,
    LLMAction,
    ChunkActionMixin,
    ActualActionMixin,
    InstantAction,
    TimedAction,
    long_action,
)
from .registry import register_action

# 具体动作（按文件拆分）
from .move import Move
from .move_to_region import MoveToRegion
from .move_to_poi import MoveToPOI
from .move_to_avatar import MoveToAvatar
from .move_away_from_avatar import MoveAwayFromAvatar
from .move_away_from_region import MoveAwayFromRegion
from .escape import Escape
from .respire import Respire
from .breakthrough import Breakthrough
from .play import Reading, TeaTasting, Traveling, ZitherPlaying
from .hunt import Hunt
from .harvest import Harvest
from .sell import Sell
from .attack import Attack
from .plunder_people import PlunderPeople
from .help_people import HelpPeople
from .devour_people import DevourPeople
from .eat_mortals import EatMortals
from .self_heal import SelfHeal
from .catch import Catch
from .nurture_weapon import NurtureWeapon
from .assassinate import Assassinate
from .move_to_direction import MoveToDirection
from .cast import Cast
from .refine import Refine
from .buy import Buy
from .mine import Mine
from .retreat import Retreat
from .rest import Rest
from .meditate import Meditate
from .educate import Educate
from .govern import Govern
from .temper import Temper
from .plant import Plant
from .sect_mission import SectMission
from .inflict_gu import InflictGu
from .set_formation import SetFormation
from .dig_grave import DigGrave
from .take_treasure import TakeTreasure

# 注册到 ActionRegistry（标注是否为实际可执行动作）
register_action(actual=False)(Action)
register_action(actual=False)(DefineAction)
register_action(actual=False)(LLMAction)
register_action(actual=False)(ChunkActionMixin)
register_action(actual=False)(ActualActionMixin)
register_action(actual=False)(InstantAction)
register_action(actual=False)(TimedAction)

register_action(actual=False)(Move)
register_action(actual=True)(MoveToRegion)
register_action(actual=True)(MoveToPOI)
register_action(actual=True)(MoveToAvatar)
register_action(actual=True)(MoveAwayFromAvatar)
register_action(actual=True)(MoveAwayFromRegion)
register_action(actual=False)(Escape)
register_action(actual=True)(Respire)
register_action(actual=True)(Breakthrough)
register_action(actual=True)(Reading)
register_action(actual=True)(TeaTasting)
register_action(actual=True)(Traveling)
register_action(actual=True)(ZitherPlaying)
register_action(actual=True)(Hunt)
register_action(actual=True)(Harvest)
register_action(actual=True)(Sell)
register_action(actual=False)(Attack)
register_action(actual=True)(PlunderPeople)
register_action(actual=True)(HelpPeople)
register_action(actual=True)(DevourPeople)
register_action(actual=True)(EatMortals)
register_action(actual=True)(SelfHeal)
register_action(actual=True)(Catch)
register_action(actual=True)(NurtureWeapon)
register_action(actual=True)(Assassinate)
register_action(actual=True)(MoveToDirection)
register_action(actual=True)(Cast)
register_action(actual=True)(Refine)
register_action(actual=True)(Buy)
register_action(actual=True)(Mine)
register_action(actual=True)(Retreat)
register_action(actual=True)(Rest)
register_action(actual=True)(Meditate)
register_action(actual=True)(Educate)
register_action(actual=True)(Govern)
register_action(actual=True)(Temper)
register_action(actual=True)(Plant)
register_action(actual=True)(SectMission)
register_action(actual=True)(InflictGu)
register_action(actual=True)(SetFormation)
register_action(actual=True)(DigGrave)
register_action(actual=True)(TakeTreasure)
# Talk 已移动到 mutual_action 模块，在那里注册

__all__ = [
    # 基类
    "Action",
    "DefineAction",
    "LLMAction",
    "ChunkActionMixin",
    "ActualActionMixin",
    "InstantAction",
    "TimedAction",
    "long_action",
    # 派生类
    "Move",
    "MoveToRegion",
    "MoveToPOI",
    "MoveToAvatar",
    "MoveAwayFromAvatar",
    "MoveAwayFromRegion",
    "Escape",
    "Respire",
    "Breakthrough",
    "Reading",
    "TeaTasting",
    "Traveling",
    "ZitherPlaying",
    "Hunt",
    "Harvest",
    "Sell",
    "Attack",
    "PlunderPeople",
    "HelpPeople",
    "DevourPeople",
    "EatMortals",
    "SelfHeal",
    "Catch",
    "NurtureWeapon",
    "Assassinate",
    "MoveToDirection",
    "Cast",
    "Refine",
    "Buy",
    "Mine",
    "Retreat",
    "Rest",
    "Meditate",
    "Educate",
    "Govern",
    "Temper",
    "Plant",
    "SectMission",
    "InflictGu",
    "SetFormation",
    "DigGrave",
    "TakeTreasure",
]
