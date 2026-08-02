import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Union

from src.classes.core.world import World
from src.classes.core.avatar import Avatar, Gender
from src.classes.appearance import get_appearance_by_level
from src.systems.time import MonthStamp
from src.classes.environment.region import Region
from src.utils.resolution import resolve_query
from src.systems.cultivation import (
    CultivationProgress,
    Realm,
    REALM_ORDER,
    realm_max_lifespan_effect_by_realm,
)
from src.classes.root import Root
from src.classes.age import Age
from src.utils.name_generator import get_random_name_for_sect, pick_surname_for_sect, get_random_name_with_surname, get_random_name_for_race
from src.utils.id_generator import get_avatar_id
from src.classes.core.sect import Sect, sects_by_id, sects_by_name
from src.classes.relation.relation import Relation
from src.classes.technique import get_technique_by_sect, attribute_to_root, Technique, techniques_by_id, techniques_by_name
from src.classes.items.weapon import Weapon, weapons_by_id, weapons_by_name
from src.classes.items.auxiliary import Auxiliary, auxiliaries_by_id, auxiliaries_by_name
from src.classes.goldfinger import Goldfinger, get_random_compatible_goldfinger
from src.classes.persona import Persona, personas_by_id, personas_by_name
from src.classes.items.magic_stone import MagicStone
from src.classes.death_reason import DeathReason, DeathType
from src.classes.official_rank import OFFICIAL_NONE, resolve_rank_changes
from src.classes.relation.relations import set_friendliness
from src.utils.born_region import get_born_region_id
from src.classes.race import Race, get_race, roll_avatar_race


# —— 参数常量（便于调参）——
SECT_MEMBER_RATIO: float = 2 / 3

AGE_MIN: int = 16
AGE_MAX: int = 150
LEVEL_MIN: int = 0
LEVEL_MAX: int = 120

FAMILY_PAIR_CAP_DIV: int = 5            # 家庭上限：n // 5
FAMILY_TRIGGER_PROB: float = 0.45       # 生成家庭对概率
FATHER_CHILD_PROB: float = 0.60         # 家庭为父子（同姓、父为男）的概率；否则母子（异姓、母为女）
FAMILY_CHILDREN_MAX: int = 3            # 单个小家庭最多额外生成的子女人数
FAMILY_SAME_SECT_CAP: int = 2           # 同一小家庭落在同一宗门的人数上限
FAMILY_PARENT_SECT_FOLLOW_PROB: float = 0.50
FAMILY_OTHER_SECT_PROB: float = 0.30

LOVERS_PAIR_CAP_DIV: int = 5            # 道侣两两预算：n // 5
LOVERS_TRIGGER_PROB: float = 0.32       # 生成一对道侣的概率（强制异性）

MASTER_PAIR_PROB: float = 0.40          # 同宗门内生成一对师徒的概率

INITIAL_FRIENDLINESS_PAIR_CAP_DIV: int = 4

PARENT_MIN_DIFF: int = 16               # 父母与子女最小年龄差
PARENT_MAX_DIFF: int = 80               # 父母与子女最大年龄差（用于生成目标差值）
PARENT_AGE_CAP: int = 120               # 父母年龄上限（修仙世界放宽）

MASTER_LEVEL_MIN_DIFF: int = 20         # 师傅与徒弟最小等级差
MASTER_LEVEL_EXTRA_MAX: int = 10        # 在最小等级差基础上的额外浮动

# 父母-子女等级差（修仙世界中通常父母更强）
PARENT_LEVEL_MIN_DIFF: int = 10         # 父母与子女最小等级差
PARENT_LEVEL_EXTRA_MAX: int = 10        # 在最小等级差基础上的额外浮动

# —— 新凡人（单个）生成相关概率与范围 ——
NEW_MORTAL_PARENT_PROB: float = 0.30    # 有概率是某个既有角色的子女
NEW_MORTAL_SECT_PROB: float = 0.50      # 有概率成为某个“已有宗门”的弟子
NEW_MORTAL_MASTER_PROB: float = 0.40    # 若成为宗门弟子，有概率拜该宗门现有人物为师
NEW_MORTAL_LEVEL_MAX: int = 40          # 新凡人默认偏低等级上限

INITIAL_AGE_MAX_BY_REALM: dict[Realm, int] = {
    Realm.Qi_Refinement: 70,
    Realm.Foundation_Establishment: 100,
    Realm.Core_Formation: 130,
    Realm.Nascent_Soul: 150,
}

# Manual creation intentionally keeps Qi Refinement characters young enough to
# avoid the old-age/grave workflow in the character-creation UI.
MANUAL_QI_REFINEMENT_AGE_MAX = 65

INITIAL_COURT_REPUTATION_CHANCE_BY_ORTHODOXY: dict[str, float] = {
    "confucianism": 0.70,
}

INITIAL_COURT_REPUTATION_CHANCE_DEFAULT: float = 0.25

INITIAL_COURT_REPUTATION_RANGE_BY_REALM: dict[Realm, tuple[int, int]] = {
    Realm.Qi_Refinement: (50, 140),
    Realm.Foundation_Establishment: (120, 300),
    Realm.Core_Formation: (260, 620),
    Realm.Nascent_Soul: (600, 1150),
}

INITIAL_SECT_CONTRIBUTION_RANGE_BY_RANK: dict[str, tuple[int, int]] = {
    "outer": (0, 60),
    "inner": (20, 120),
    "elder": (80, 240),
    "patriarch": (150, 400),
}

INITIAL_GOLDFINGER_PROBABILITY: float = 0.01


def _weighted_random_choice(weights: dict[str, int]) -> str:
    total = sum(max(0, weight) for weight in weights.values())
    if total <= 0:
        return "mutual_friend"

    pick = random.randint(1, total)
    cumulative = 0
    for key, weight in weights.items():
        cumulative += max(0, weight)
        if pick <= cumulative:
            return key
    return "mutual_friend"


def _roll_social_initial_friendliness_pair(avatar_a: Avatar, avatar_b: Avatar) -> tuple[int, int]:
    same_sect = avatar_a.sect is not None and avatar_a.sect is avatar_b.sect
    age_gap = abs(int(avatar_a.age.age) - int(avatar_b.age.age))
    level_gap = abs(int(avatar_a.cultivation_progress.level) - int(avatar_b.cultivation_progress.level))

    positive_bias = 0
    negative_bias = 0
    if same_sect:
        positive_bias += 3
        negative_bias -= 2
    if age_gap <= 12:
        positive_bias += 2
    elif age_gap <= 28:
        positive_bias += 1
    elif age_gap >= 55:
        negative_bias += 1
    if level_gap <= 12:
        positive_bias += 1
    elif level_gap >= 40:
        negative_bias += 2
    if getattr(getattr(avatar_a, "race", None), "id", "human") != getattr(getattr(avatar_b, "race", None), "id", "human"):
        bias_a = int(avatar_a.effects.get("extra_cross_race_friendliness", 0) or 0)
        bias_b = int(avatar_b.effects.get("extra_cross_race_friendliness", 0) or 0)
        from src.sim import avatar_init

        a_to_b, b_to_a = avatar_init._roll_social_initial_friendliness_pair_without_cross_race(
            avatar_a,
            avatar_b,
            positive_bias,
            negative_bias,
        )
        return max(-100, min(100, a_to_b + bias_a)), max(-100, min(100, b_to_a + bias_b))

    from src.sim import avatar_init

    return avatar_init._roll_social_initial_friendliness_pair_without_cross_race(
        avatar_a, avatar_b, positive_bias, negative_bias
    )


def _roll_social_initial_friendliness_pair_without_cross_race(
    avatar_a: Avatar,
    avatar_b: Avatar,
    positive_bias: int,
    negative_bias: int,
) -> tuple[int, int]:
    same_sect = avatar_a.sect is not None and avatar_a.sect is avatar_b.sect
    level_gap = abs(int(avatar_a.cultivation_progress.level) - int(avatar_b.cultivation_progress.level))

    weights = {
        "mutual_friend": 34 + positive_bias * 7,
        "mutual_best_friend": 4 + positive_bias * 3,
        "mutual_disliked": 10 + negative_bias * 5 - positive_bias * 2,
        "mutual_archenemy": 2 + negative_bias * 2 - positive_bias * 2,
        "one_sided_admiration": 10 + (6 if level_gap >= 18 else 0) + positive_bias * 2,
        "one_sided_dislike": 8 + negative_bias * 4,
    }
    archetype = _weighted_random_choice(weights)

    if archetype == "mutual_friend":
        low = 25 + positive_bias * 2
        high = 42 + positive_bias * 4
        return random.randint(low, high), random.randint(low, high)
    if archetype == "mutual_best_friend":
        low = 60 + max(0, positive_bias - 1) * 2
        high = 74 + positive_bias * 3
        return random.randint(low, high), random.randint(low, high)
    if archetype == "mutual_disliked":
        low = -46 - negative_bias * 5
        high = -26 - max(0, positive_bias - 1)
        return random.randint(low, high), random.randint(low, high)
    if archetype == "mutual_archenemy":
        low = -80 - negative_bias * 4
        high = -62
        return random.randint(low, high), random.randint(low, high)
    if archetype == "one_sided_admiration":
        warm_low = 28 + positive_bias * 2
        warm_high = 48 + positive_bias * 4
        neutral_low = 4 + positive_bias
        neutral_high = 18 + positive_bias * 2
        if avatar_a.cultivation_progress.level > avatar_b.cultivation_progress.level:
            return random.randint(neutral_low, neutral_high), random.randint(warm_low, warm_high)
        if avatar_b.cultivation_progress.level > avatar_a.cultivation_progress.level:
            return random.randint(warm_low, warm_high), random.randint(neutral_low, neutral_high)
        if random.random() < 0.5:
            return random.randint(warm_low, warm_high), random.randint(neutral_low, neutral_high)
        return random.randint(neutral_low, neutral_high), random.randint(warm_low, warm_high)

    cold_low = -42 - negative_bias * 4
    cold_high = -26
    other_low = -4
    other_high = 14 + positive_bias
    if same_sect:
        other_low = 2
        other_high = 20 + positive_bias
    if random.random() < 0.5:
        return random.randint(cold_low, cold_high), random.randint(other_low, other_high)
    return random.randint(other_low, other_high), random.randint(cold_low, cold_high)


def _roll_identity_relation_friendliness(relation: Relation) -> tuple[int | None, int | None]:
    if relation is Relation.IS_LOVER_OF:
        return random.randint(45, 82), random.randint(45, 82)
    if relation is Relation.IS_SWORN_SIBLING_OF:
        return random.randint(35, 72), random.randint(35, 72)
    if relation is Relation.IS_DISCIPLE_OF:
        return random.randint(18, 45), random.randint(28, 62)
    if relation is Relation.IS_MASTER_OF:
        return random.randint(28, 62), random.randint(18, 45)
    return None, None


def _apply_structural_initial_friendliness(from_avatar: Avatar, to_avatar: Avatar, relation: Relation) -> None:
    a_to_b, b_to_a = _roll_identity_relation_friendliness(relation)
    if a_to_b is not None:
        set_friendliness(from_avatar, to_avatar, a_to_b)
    if b_to_a is not None:
        set_friendliness(to_avatar, from_avatar, b_to_a)


def _plan_group_initial_friendliness(
    avatars_by_index: list[Avatar],
    relations: dict[tuple[int, int], Relation],
) -> dict[tuple[int, int], int]:
    pair_budget = max(0, len(avatars_by_index) // INITIAL_FRIENDLINESS_PAIR_CAP_DIV)
    if pair_budget <= 0:
        return {}

    blocked_pairs = {frozenset((a, b)) for (a, b) in relations}
    candidate_pairs = [
        (a, b)
        for a in range(len(avatars_by_index))
        for b in range(a + 1, len(avatars_by_index))
        if frozenset((a, b)) not in blocked_pairs
    ]
    random.shuffle(candidate_pairs)

    friendliness: dict[tuple[int, int], int] = {}
    for a, b in candidate_pairs[:pair_budget]:
        avatar_a = avatars_by_index[a]
        avatar_b = avatars_by_index[b]
        a_to_b, b_to_a = _roll_social_initial_friendliness_pair(avatar_a, avatar_b)
        friendliness[(a, b)] = a_to_b
        friendliness[(b, a)] = b_to_a
    return friendliness


def _create_random_age() -> int:
    return random.randint(AGE_MIN, AGE_MAX)


def _create_random_innate_lifespan() -> int:
    return Age.roll_innate_max_lifespan()


class ManualAvatarAgeLimitError(ValueError):
    """Raised when an API-created avatar exceeds its realm age limit."""

    def __init__(self, *, age: int, max_age: int, realm: Realm):
        self.age = age
        self.max_age = max_age
        self.realm = realm
        super().__init__(f"Age {age} exceeds the maximum {max_age} for {realm.value}")


def _mark_dead_if_lifespan_exhausted(avatar: Avatar, current_month_stamp: MonthStamp) -> None:
    if avatar.age.age < avatar.age.max_lifespan:
        return
    avatar.set_dead(str(DeathReason(DeathType.OLD_AGE)), current_month_stamp)


def _get_initial_age_max_for_realm(realm: Realm) -> int:
    return INITIAL_AGE_MAX_BY_REALM.get(realm, AGE_MAX)


def get_manual_avatar_age_max(realm: Realm) -> int:
    if realm is Realm.Qi_Refinement:
        return MANUAL_QI_REFINEMENT_AGE_MAX
    return Age.INITIAL_MAX_LIFESPAN_MIN + realm_max_lifespan_effect_by_realm[realm] - 1


def get_manual_avatar_age_limits() -> dict[str, object]:
    """Return the single source of truth for manual-character age limits."""
    return {
        "min": AGE_MIN,
        "max_by_realm": {
            realm.value: get_manual_avatar_age_max(realm)
            for realm in REALM_ORDER
        },
    }


def _create_manual_innate_lifespan(age_years: int, realm: Realm) -> int:
    """Roll an innate lifespan that keeps a supported manual avatar alive."""
    realm_bonus = realm_max_lifespan_effect_by_realm[realm]
    minimum = max(Age.INITIAL_MAX_LIFESPAN_MIN, age_years + 1 - realm_bonus)
    return random.randint(minimum, Age.INITIAL_MAX_LIFESPAN_MAX)


def _get_initial_official_chance(avatar: Avatar) -> float:
    orthodoxy_id = str(getattr(getattr(avatar, "orthodoxy", None), "id", "") or "")
    return INITIAL_COURT_REPUTATION_CHANCE_BY_ORTHODOXY.get(
        orthodoxy_id,
        INITIAL_COURT_REPUTATION_CHANCE_DEFAULT,
    )


def _roll_initial_court_reputation(avatar: Avatar) -> int:
    if random.random() >= _get_initial_official_chance(avatar):
        return 0

    realm = getattr(getattr(avatar, "cultivation_progress", None), "realm", Realm.Qi_Refinement)
    min_rep, max_rep = INITIAL_COURT_REPUTATION_RANGE_BY_REALM.get(realm, (50, 140))
    return random.randint(min_rep, max_rep)


def _assign_initial_official_status(avatar: Avatar) -> None:
    avatar.court_reputation = int(_roll_initial_court_reputation(avatar))
    avatar.official_rank = OFFICIAL_NONE
    _old_rank, new_rank = resolve_rank_changes(avatar)
    if new_rank != OFFICIAL_NONE:
        avatar.recalc_effects()


def _assign_initial_sect_contribution(avatar: Avatar) -> None:
    if getattr(avatar, "sect", None) is None or getattr(avatar, "sect_rank", None) is None:
        avatar.sect_contribution = 0
        return

    rank_key = str(getattr(avatar.sect_rank, "value", "") or "outer")
    low, high = INITIAL_SECT_CONTRIBUTION_RANGE_BY_RANK.get(rank_key, (0, 60))
    avatar.sect_contribution = random.randint(low, high)


def _assign_initial_goldfinger(avatar: Avatar) -> None:
    if getattr(avatar, "goldfinger", None) is not None:
        avatar.goldfinger_state = dict(getattr(avatar, "goldfinger_state", {}) or {})
        avatar.recalc_effects()
        return

    # The package export remains the supported test/configuration seam.
    from . import INITIAL_GOLDFINGER_PROBABILITY as probability
    from . import get_random_compatible_goldfinger as choose_goldfinger

    if random.random() >= probability:
        return

    goldfinger = choose_goldfinger(avatar)
    if goldfinger is None:
        return

    avatar.goldfinger = goldfinger
    avatar.goldfinger_state = {}
    avatar.recalc_effects()


def _roll_cultivation_start_month(
    birth_month_stamp: MonthStamp,
    current_month_stamp: MonthStamp,
) -> MonthStamp:
    earliest_start_month = int(birth_month_stamp) + 16 * 12
    latest_start_month = int(current_month_stamp)
    if latest_start_month <= earliest_start_month:
        return MonthStamp(latest_start_month)
    return MonthStamp(random.randint(earliest_start_month, latest_start_month))


def random_gender() -> Gender:
    return Gender.MALE if random.random() < 0.5 else Gender.FEMALE


class EquipmentAllocator:
    """
    负责所有初始装备分配逻辑，提供兵器与辅助装备的统一接口。
    （仅用于世界生成或完整角色生成，觉醒逻辑使用简化配置）
    """

    @staticmethod
    def assign_weapon(avatar: Avatar) -> None:
        """
        初始兵器逻辑：
        - 80% 继承宗门偏好兵器类型，否则完全随机
        - 根据境界随机生成一把兵器
        """
        from src.classes.items.weapon import get_random_weapon_by_realm
        from src.classes.weapon_type import WeaponType

        weapon_type = None
        if avatar.sect is not None and avatar.sect.preferred_weapon:
            if random.random() < 0.8:
                for wt in WeaponType:
                    if wt.value == avatar.sect.preferred_weapon:
                        weapon_type = wt
                        break
        
        avatar.weapon = get_random_weapon_by_realm(avatar.cultivation_progress.realm, weapon_type)

    @staticmethod
    def assign_auxiliary(avatar: Avatar) -> None:
        """
        初始辅助装备逻辑：
        - 根据境界随机生成一件辅助装备
        """
        from src.classes.items.auxiliary import get_random_auxiliary_by_realm
        
        avatar.auxiliary = get_random_auxiliary_by_realm(avatar.cultivation_progress.realm)


