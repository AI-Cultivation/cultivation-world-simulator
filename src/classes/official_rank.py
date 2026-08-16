from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar
    from src.classes.core.dynasty import Dynasty


OFFICIAL_NONE = "NONE"
OFFICIAL_COUNTY = "COUNTY"
OFFICIAL_COMMANDERY = "COMMANDERY"
OFFICIAL_PROVINCE = "PROVINCE"
OFFICIAL_GRAND_COUNCILOR = "GRAND_COUNCILOR"

OFFICIAL_ORDER = [
    OFFICIAL_NONE,
    OFFICIAL_COUNTY,
    OFFICIAL_COMMANDERY,
    OFFICIAL_PROVINCE,
    OFFICIAL_GRAND_COUNCILOR,
]


@dataclass(frozen=True)
class OfficialRankDef:
    key: str
    name_msgid: str
    threshold: int
    salary: int
    upkeep_decay: int
    effects: dict[str, Any] | list[dict[str, Any]]


DYNASTY_STYLE_MSGIDS: dict[str, str] = {
    "尚法重军": "dynasty_style_law_and_arms",
    "清谈名教": "dynasty_style_pure_discourse_and_orthodoxy",
    "重文理政": "dynasty_style_civil_governance",
    "风流雅政": "dynasty_style_elegant_courtly_rule",
    "山泽杂行": "dynasty_style_wild_marches",
    "尚实通商": "dynasty_style_pragmatic_commerce",
    "沉毅守边": "dynasty_style_stoic_frontier_guard",
    "骑射尚武": "dynasty_style_horsemanship_and_arms",
    "法密权重": "dynasty_style_strict_law_and_central_power",
    "务本守成": "dynasty_style_pragmatic_conservatism",
    "柔治机变": "dynasty_style_flexible_statecraft",
    "坚忍后发": "dynasty_style_endure_and_strike_late",
}


OFFICIAL_RANKS: dict[str, OfficialRankDef] = {
    OFFICIAL_NONE: OfficialRankDef(
        key=OFFICIAL_NONE,
        name_msgid="official_rank_none",
        threshold=0,
        salary=40,
        upkeep_decay=0,
        effects={},
    ),
    OFFICIAL_COUNTY: OfficialRankDef(
        key=OFFICIAL_COUNTY,
        name_msgid="official_rank_county_magistrate",
        threshold=80,
        salary=90,
        upkeep_decay=1,
        effects=[
            {"extra_luck": 2},
            {
                "when": 'avatar.orthodoxy is not None and avatar.orthodoxy.id == "confucianism"',
                "when_desc": "condition_confucian_orthodoxy",
                "extra_educate_efficiency": 0.15,
                "extra_breakthrough_success_rate": 0.01,
            },
        ],
    ),
    OFFICIAL_COMMANDERY: OfficialRankDef(
        key=OFFICIAL_COMMANDERY,
        name_msgid="official_rank_commandery_governor",
        threshold=220,
        salary=180,
        upkeep_decay=3,
        effects=[
            {"extra_luck": 5},
            {
                "when": 'avatar.orthodoxy is not None and avatar.orthodoxy.id == "confucianism"',
                "when_desc": "condition_confucian_orthodoxy",
                "extra_educate_efficiency": 0.30,
                "extra_breakthrough_success_rate": 0.02,
            },
        ],
    ),
    OFFICIAL_PROVINCE: OfficialRankDef(
        key=OFFICIAL_PROVINCE,
        name_msgid="official_rank_provincial_governor",
        threshold=520,
        salary=360,
        upkeep_decay=8,
        effects=[
            {"extra_luck": 9},
            {
                "when": 'avatar.orthodoxy is not None and avatar.orthodoxy.id == "confucianism"',
                "when_desc": "condition_confucian_orthodoxy",
                "extra_educate_efficiency": 0.50,
                "extra_breakthrough_success_rate": 0.04,
            },
        ],
    ),
    OFFICIAL_GRAND_COUNCILOR: OfficialRankDef(
        key=OFFICIAL_GRAND_COUNCILOR,
        name_msgid="official_rank_grand_chancellor",
        threshold=1000,
        salary=700,
        upkeep_decay=15,
        effects=[
            {"extra_luck": 14},
            {
                "when": 'avatar.orthodoxy is not None and avatar.orthodoxy.id == "confucianism"',
                "when_desc": "condition_confucian_orthodoxy",
                "extra_educate_efficiency": 0.80,
                "extra_breakthrough_success_rate": 0.06,
            },
        ],
    ),
}


def get_official_rank(rank_key: str | None) -> OfficialRankDef:
    return OFFICIAL_RANKS.get(str(rank_key or OFFICIAL_NONE), OFFICIAL_RANKS[OFFICIAL_NONE])


def get_official_rank_name(rank_key: str | None) -> str:
    from src.i18n import t

    return t(get_official_rank(rank_key).name_msgid)


def get_next_official_rank(rank_key: str | None) -> OfficialRankDef | None:
    current_key = str(rank_key or OFFICIAL_NONE)
    try:
        index = OFFICIAL_ORDER.index(current_key)
    except ValueError:
        index = 0
    if index >= len(OFFICIAL_ORDER) - 1:
        return None
    return OFFICIAL_RANKS[OFFICIAL_ORDER[index + 1]]


def get_previous_official_rank(rank_key: str | None) -> OfficialRankDef | None:
    current_key = str(rank_key or OFFICIAL_NONE)
    try:
        index = OFFICIAL_ORDER.index(current_key)
    except ValueError:
        index = 0
    if index <= 0:
        return None
    return OFFICIAL_RANKS[OFFICIAL_ORDER[index - 1]]


def get_official_effects(rank_key: str | None) -> dict[str, Any] | list[dict[str, Any]]:
    return get_official_rank(rank_key).effects


def get_governance_salary(rank_key: str | None) -> int:
    return int(get_official_rank(rank_key).salary)


def get_monthly_reputation_decay(rank_key: str | None) -> int:
    return int(get_official_rank(rank_key).upkeep_decay)


def get_realm_governance_multiplier(avatar: "Avatar") -> float:
    from src.systems.cultivation import REALM_RANK

    rank = int(REALM_RANK.get(avatar.cultivation_progress.realm, 0))
    if rank <= 1:
        return 0.0
    if rank == 2:
        return 0.2
    if rank == 3:
        return 0.5
    return 1.0


def get_persona_governance_multiplier(avatar: "Avatar") -> float:
    total = 0.0
    for persona in getattr(avatar, "personas", []) or []:
        key = str(getattr(persona, "key", "") or "").upper()
        if key == "INTO_WORLD":
            total += 0.30
        elif key == "ORTHODOX_GENTLEMAN":
            total += 0.50
        elif key == "SECLUDED":
            total -= 0.30
        elif key == "RECLUSIVE_CULTIVATOR":
            total -= 0.50
    return total


def match_dynasty_preference(avatar: "Avatar", dynasty: "Dynasty | None") -> bool:
    if dynasty is None:
        return False

    pref_type = str(getattr(dynasty, "official_preference_type", "") or "").strip().lower()
    pref_value = str(getattr(dynasty, "official_preference_value", "") or "").strip()
    if not pref_type or not pref_value:
        return False

    if pref_type == "gender":
        avatar_gender = str(getattr(getattr(avatar, "gender", None), "value", "") or "").lower()
        return avatar_gender == pref_value.lower()

    if pref_type == "alignment":
        avatar_alignment = str(getattr(getattr(avatar, "alignment", None), "name", "") or "")
        return avatar_alignment == pref_value

    if pref_type == "orthodoxy":
        avatar_orthodoxy = str(getattr(getattr(avatar, "orthodoxy", None), "id", "") or "")
        return avatar_orthodoxy == pref_value

    if pref_type == "persona_key":
        persona_keys = {
            str(getattr(persona, "key", "") or "").upper()
            for persona in getattr(avatar, "personas", []) or []
        }
        return pref_value.upper() in persona_keys

    return False


def get_dynasty_preference_label(dynasty: "Dynasty | None") -> str:
    from src.i18n import t

    if dynasty is None:
        return ""

    pref_type = str(getattr(dynasty, "official_preference_type", "") or "").strip().lower()
    pref_value = str(getattr(dynasty, "official_preference_value", "") or "").strip()
    if not pref_type or not pref_value:
        return ""

    if pref_type == "gender":
        return t("Prefers male cultivators") if pref_value.lower() == "male" else t("Prefers female cultivators")
    if pref_type == "alignment":
        mapping = {
            "RIGHTEOUS": t("Prefers righteous cultivators"),
            "EVIL": t("Prefers evil cultivators"),
            "NEUTRAL": t("Prefers neutral cultivators"),
        }
        return mapping.get(pref_value, t("Prefers {value}", value=pref_value))
    if pref_type == "orthodoxy":
        mapping = {
            "confucianism": t("Prefers Confucian cultivators"),
            "dao": t("Prefers Daoist cultivators"),
            "buddhism": t("Prefers Buddhist cultivators"),
            "wu": t("Prefers martial cultivators"),
        }
        return mapping.get(pref_value, t("Prefers {value}", value=pref_value))
    if pref_type == "persona_key":
        mapping = {
            "INTO_WORLD": t("Prefers worldly cultivators"),
            "ORTHODOX_GENTLEMAN": t("Prefers orthodox gentlemen"),
            "SECLUDED": t("Prefers secluded cultivators"),
            "RECLUSIVE_CULTIVATOR": t("Prefers solitary mountain cultivators"),
        }
        return mapping.get(pref_value.upper(), t("Prefers {value}", value=pref_value))
    return ""


def calculate_governance_reputation_gain(avatar: "Avatar", dynasty: "Dynasty | None") -> int:
    multiplier = 0.0
    if getattr(getattr(avatar, "orthodoxy", None), "id", "") == "confucianism":
        multiplier += 0.5
    multiplier += get_persona_governance_multiplier(avatar)
    multiplier += get_realm_governance_multiplier(avatar)
    if match_dynasty_preference(avatar, dynasty):
        try:
            multiplier += float(getattr(dynasty, "effects", {}).get("extra_govern_reputation_gain_multiplier", 0.35) or 0.35)
        except (TypeError, ValueError, AttributeError):
            multiplier += 0.35
    return max(1, round(10 * (1 + multiplier)))


def apply_official_reputation_delta(avatar: "Avatar", delta: int) -> None:
    avatar.court_reputation = max(0, int(getattr(avatar, "court_reputation", 0) or 0) + int(delta))


def resolve_rank_changes(avatar: "Avatar") -> tuple[str, str]:
    old_rank = str(getattr(avatar, "official_rank", OFFICIAL_NONE) or OFFICIAL_NONE)
    current_rank = old_rank
    current_rep = int(getattr(avatar, "court_reputation", 0) or 0)

    while True:
        next_rank = get_next_official_rank(current_rank)
        if next_rank is None or current_rep < int(next_rank.threshold):
            break
        current_rank = next_rank.key

    while current_rank != OFFICIAL_NONE:
        current_def = get_official_rank(current_rank)
        if current_rep >= int(current_def.threshold):
            break
        previous_rank = get_previous_official_rank(current_rank)
        current_rank = previous_rank.key if previous_rank is not None else OFFICIAL_NONE

    avatar.official_rank = current_rank
    return old_rank, current_rank
