from typing import Any


def get_effect_desc(effect_key: str) -> str:
    """获取 effect 的描述名称（支持国际化）。"""
    from src.i18n import t

    # 映射 effect_key -> msgid
    msgid_map = {
        "extra_hp_recovery_rate": "effect_extra_hp_recovery_rate",
        "extra_max_hp": "effect_extra_max_hp",
        "extra_max_lifespan": "effect_extra_max_lifespan",
        "extra_appearance": "effect_extra_appearance",
        "extra_weapon_proficiency_gain": "effect_extra_weapon_proficiency_gain",
        "extra_dual_cultivation_exp": "effect_extra_dual_cultivation_exp",
        "extra_breakthrough_success_rate": "effect_extra_breakthrough_success_rate",
        "extra_retreat_success_rate": "effect_extra_retreat_success_rate",
        "extra_rest_exp": "effect_extra_rest_exp",
        "extra_rest_hp_recovery_rate": "effect_extra_rest_hp_recovery_rate",
        "extra_luck": "effect_extra_luck",
        "extra_fortune_probability": "effect_extra_fortune_probability",
        "extra_misfortune_probability": "effect_extra_misfortune_probability",
        "extra_opportunity_probability": "effect_extra_opportunity_probability",
        "extra_harvest_materials": "effect_extra_harvest_materials",
        "extra_hunt_materials": "effect_extra_hunt_materials",
        "extra_mine_materials": "effect_extra_mine_materials",
        "extra_plant_income": "effect_extra_plant_income",
        "extra_item_sell_price_multiplier": "effect_extra_item_sell_price_multiplier",
        "shop_buy_price_reduction": "effect_shop_buy_price_reduction",
        "extra_weapon_upgrade_chance": "effect_extra_weapon_upgrade_chance",
        "extra_plunder_multiplier": "effect_extra_plunder_multiplier",
        "extra_eat_mortals_exp_multiplier": "effect_extra_eat_mortals_exp_multiplier",
        "extra_cross_race_friendliness": "effect_extra_cross_race_friendliness",
        "extra_gu_success_rate": "effect_extra_gu_success_rate",
        "extra_gu_duration_months": "effect_extra_gu_duration_months",
        "extra_gu_resistance_rate": "effect_extra_gu_resistance_rate",
        "extra_formation_power": "effect_extra_formation_power",
        "extra_formation_duration_months": "effect_extra_formation_duration_months",
        "formation_cost_reduction": "effect_formation_cost_reduction",
        "extra_catch_success_rate": "effect_extra_catch_success_rate",
        "extra_respire_exp": "effect_extra_respire_exp",
        "extra_respire_exp_multiplier": "effect_extra_respire_exp_multiplier",
        "extra_battle_strength_points": "effect_extra_battle_strength_points",
        "extra_escape_success_rate": "effect_extra_escape_success_rate",
        "extra_assassinate_success_rate": "effect_extra_assassinate_success_rate",
        "extra_observation_radius": "effect_extra_observation_radius",
        "extra_move_step": "effect_extra_move_step",
        "legal_actions": "effect_legal_actions",
        "damage_reduction": "effect_damage_reduction",
        "realm_suppression_bonus": "effect_realm_suppression_bonus",
        "respire_duration_reduction": "effect_respire_duration_reduction",
        "temper_duration_reduction": "effect_temper_duration_reduction",
        "extra_cast_success_rate": "effect_extra_cast_success_rate",
        "extra_refine_success_rate": "effect_extra_refine_success_rate",
        "extra_sect_mission_success_rate": "effect_extra_sect_mission_success_rate",
        "extra_hidden_domain_drop_prob": "effect_extra_hidden_domain_drop_prob",
        "extra_hidden_domain_danger_prob": "effect_extra_hidden_domain_danger_prob",
        "extra_epiphany_probability": "effect_extra_epiphany_probability",
        "extra_educate_efficiency": "effect_extra_educate_efficiency",
        "extra_educate_population_prob": "effect_extra_educate_population_prob",
        "extra_govern_reputation_gain_multiplier": "effect_extra_govern_reputation_gain_multiplier",
        "extra_temper_exp_multiplier": "effect_extra_temper_exp_multiplier",
        "extra_income_per_tile": "effect_extra_income_per_tile",
    }

    msgid = msgid_map.get(effect_key, effect_key)
    return t(msgid)


def get_action_short_name(action_name: str) -> str:
    """获取 action 的简称（复用 Action 系统翻译）。"""
    from src.i18n import t

    # 使用统一命名规则：action_xxx_short_name
    msgid = f"action_{action_name.lower()}_short_name"
    return t(msgid)


def format_value(key: str, value: Any) -> str:
    """格式化效果数值。"""
    if key == "legal_actions" and isinstance(value, list):
        from src.i18n import t

        actions = [get_action_short_name(str(a)) for a in value]
        sep = t("action_list_separator")
        return sep.join(actions)

    if isinstance(value, (int, float)):
        if key == "extra_formation_power" and isinstance(value, float):
            percent = value * 100
            sign = "+" if percent > 0 else ""
            return f"{sign}{percent:.1f}%"

        if key == "formation_cost_reduction" and isinstance(value, float):
            percent = value * 100
            return f"-{percent:.1f}%"

        # 百分比类字段统一展示为百分号。
        if (
            "rate" in key
            or "probability" in key
            or "chance" in key
            or "multiplier" in key
            or "gain" in key
            or "reduction" in key
            or "bonus" in key
        ):
            # 约定 0.1 表示 +10%。
            if isinstance(value, float):
                percent = value * 100
                sign = "+" if percent > 0 else ""
                return f"{sign}{percent:.1f}%"

        if key == "extra_max_lifespan" and value == 0:
            return "+0"

        sign = "+" if value > 0 else ""
        return f"{sign}{value}"

    return str(value)


def translate_condition(condition: str) -> str:
    """将代码形式的条件表达式转换为可读描述。"""
    import re

    from src.i18n import t

    if not condition:
        return t("Conditional effect")

    # 1) Persona 条件（特质）
    # 例: any(p.key == "CHILD_OF_FORTUNE" for p in avatar.personas)
    if "avatar.personas" in condition:
        m_key = re.search(r'p\.key\s*==\s*["\'](.*?)["\']', condition)
        if m_key:
            key = m_key.group(1)
            from src.classes.persona import personas_by_id

            trait_name = key
            for p in personas_by_id.values():
                if p.key == key:
                    trait_name = p.name
                    break
            return t("Has [{trait}] trait", trait=trait_name)

        m_name = re.search(r'p\.name\s*==\s*["\'](.*?)["\']', condition)
        if m_name:
            return t("Has [{trait}] trait", trait=m_name.group(1))

    # 1.5) Goldfinger 条件（外挂）
    # 例: avatar.goldfinger and avatar.goldfinger.key == "CHILD_OF_FORTUNE"
    if "avatar.goldfinger" in condition:
        m_key = re.search(r'goldfinger\.key\s*==\s*["\'](.*?)["\']', condition)
        if m_key:
            key = m_key.group(1)
            from src.classes.goldfinger import goldfingers_by_id

            goldfinger_name = key
            for goldfinger in goldfingers_by_id.values():
                if goldfinger.key == key:
                    goldfinger_name = goldfinger.name
                    break
            return t("Has [{trait}] trait", trait=goldfinger_name)

    # 2) Alignment 条件（阵营）
    # 例: avatar.alignment == Alignment.RIGHTEOUS
    if "avatar.alignment" in condition:
        m_align = re.search(r"Alignment\.([A-Z_]+)", condition)
        if m_align:
            align_key = m_align.group(1)
            from src.classes.alignment import Alignment

            try:
                align_enum = Alignment[align_key]
                return t("When alignment is {align}", align=str(align_enum))
            except KeyError:
                pass

    # 3) WeaponType 条件（武器类型）
    # 例: avatar.weapon.weapon_type == WeaponType.SWORD
    weapon_matches = re.finditer(
        r"avatar\.weapon\.(?:weapon_type|type)\s*==\s*"
        r"(?:WeaponType\.)?(?:[\"'](?P<quoted>[A-Z_]+)[\"']|(?P<bare>[A-Z_]+))",
        condition,
    )
    weapon_keys = [match.group("quoted") or match.group("bare") for match in weapon_matches]
    if weapon_keys:
        from src.classes.weapon_type import WeaponType

        weapon_names = []
        for weapon_key in weapon_keys:
            try:
                weapon_names.append(str(WeaponType[weapon_key]))
            except KeyError:
                weapon_names = []
                break
        if weapon_names:
            return t("When using {weapon_type}", weapon_type=t("action_list_separator").join(weapon_names))

    # 4) 兜底简化：去掉常见前缀与符号，尽量可读。
    simple_cond = condition
    simple_cond = simple_cond.replace("avatar.", "")
    simple_cond = simple_cond.replace("Alignment.", "")
    simple_cond = simple_cond.replace("WeaponType.", "")
    simple_cond = simple_cond.replace("==", ":")
    return t("When {condition}", condition=simple_cond)


def format_effects_to_text(effects: dict[str, Any] | list[dict[str, Any]]) -> str:
    """把 effects 转为易读文本，例如 {"extra_max_hp": 100} -> "最大生命 +100"。"""
    from src.i18n import t

    if not effects:
        return ""

    if isinstance(effects, list):
        parts = []
        for eff in effects:
            text = format_effects_to_text(eff)
            if text:
                parts.append(text)
        return "\n".join(parts)

    # 1) 优先使用整段描述覆盖。
    if "_desc" in effects:
        return t(effects["_desc"])

    desc_list = []
    for k, v in effects.items():
        if k in ["when", "duration_month", "when_desc"]:
            continue

        name = get_effect_desc(k)

        # 字符串代码片段（eval 或 avatar 引用）不直接回显，避免噪声。
        if isinstance(v, str):
            if v.startswith("eval(") or "avatar." in v or "//" in v:
                val_str = t("Special effect (dynamic)")
            else:
                val_str = format_value(k, v)
        else:
            val_str = format_value(k, v)

        desc_list.append(f"{name} {val_str}")

    sep = t("effect_separator")
    text = sep.join(desc_list)

    # 2) 附加条件描述。
    if effects.get("when"):
        if "when_desc" in effects:
            cond = t(effects["when_desc"])
        else:
            cond = translate_condition(str(effects["when"]))
        return f"[{cond}] {text}"

    return text
