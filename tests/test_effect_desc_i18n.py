
import pytest
from src.classes.effect.desc import format_effects_to_text
from src.classes.effect.process import _evaluate_conditional_effect
from src.classes.language import language_manager
from src.classes.persona import personas_by_id
from src.classes.weapon_type import WeaponType
from src.i18n import reload_translations
from src.i18n.locale_registry import get_fallback_locale, get_locale_codes, get_source_locale

class TestEffectDescI18n:
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        # 记录原始语言
        original_lang = str(language_manager)
        yield
        # 恢复
        language_manager.set_language(original_lang)
        reload_translations()

    def test_format_effects_with_desc_override(self):
        """测试 _desc 字段覆盖整个效果描述"""
        source_locale = get_source_locale()
        fallback_locale = get_fallback_locale()
        language_manager.set_language(source_locale)
        reload_translations()
        
        # 模拟 弑神枪 的配置
        effects = {
            "extra_battle_strength_points": "3 + avatar.weapon_proficiency * 0.02",
            "_desc": "effect_god_slaying_spear_desc"
        }
        
        text = format_effects_to_text(effects)
        # 应直接显示翻译后的文本，而非 "战力 +3 + ..."
        assert "基于枪法资质提升战力" in text
        assert "avatar.weapon_proficiency" not in text
        
        # 切换语言测试
        language_manager.set_language(fallback_locale)
        reload_translations()
        
        text_en = format_effects_to_text(effects)
        assert "Increases Battle Strength based on Spear Proficiency" in text_en

    def test_format_effects_with_when_desc_override(self):
        """测试 when_desc 字段覆盖条件描述"""
        source_locale = get_source_locale()
        fallback_locale = get_fallback_locale()
        language_manager.set_language(source_locale)
        reload_translations()
        
        # 模拟 万兽笛 的配置
        effects = {
            "when": "avatar.spirit_animal is not None",
            "when_desc": "condition_has_spirit_animal",
            "extra_battle_strength_points": 2
        }
        
        text = format_effects_to_text(effects)
        # 期望格式: [拥有本命灵兽时] 战力点数 +2
        assert "[拥有本命灵兽时]" in text
        # 只要包含 "+2" 和 相关的描述词即可，避免对具体的翻译词（战力/战力点数）过于敏感
        assert "+2" in text
        assert "avatar.spirit_animal" not in text
        
        # 切换语言测试
        language_manager.set_language(fallback_locale)
        reload_translations()
        
        text_en = format_effects_to_text(effects)
        assert "[When possessing a Spirit Animal]" in text_en
        assert "+2" in text_en

    def test_mixed_effects_list(self):
        """测试效果列表（混合有无覆盖的情况）"""
        language_manager.set_language(get_source_locale())
        reload_translations()
        
        # 模拟 天道均衡 的配置 (列表形式)
        effects = [
            {
                "when": "avatar.cultivation_progress.realm.value >= 6",
                "when_desc": "condition_realm_high",
                "extra_respire_exp": -25
            },
            {
                "when": "avatar.cultivation_progress.realm.value < 6",
                "when_desc": "condition_realm_low",
                "extra_respire_exp": 10
            }
        ]
        
        text = format_effects_to_text(effects)
        
        assert "[化神期及以上时]" in text
        assert "-25" in text
        assert "[化神期以下时]" in text
        assert "+10" in text
        
    def test_fallback_behavior(self):
        """测试没有 override 字段时的回退行为（确保不影响原有功能）"""
        language_manager.set_language(get_source_locale())
        reload_translations()
        
        # 普通效果，无 override
        effects = {
            "extra_max_hp": 100,
            "when": "avatar.level > 10"
        }
        
        text = format_effects_to_text(effects)
        # 应使用默认的正则解析
        # 假设 translate_condition 将 "avatar.level > 10" 翻译为 "When level > 10" (或者类似的兜底)
        # 这里只检查关键数值和默认行为存在
        assert "100" in text
        assert "level" in text or "等级" in text 
        assert "[" in text and "]" in text

    def test_formation_effect_values_are_player_readable(self):
        language_manager.set_language(get_source_locale())
        reload_translations()

        text = format_effects_to_text({
            "extra_formation_power": 0.08,
            "extra_formation_duration_months": 2,
            "formation_cost_reduction": 0.05,
        })

        assert "阵法威能 +8.0%" in text
        assert "阵法持续 +2" in text
        assert "布阵消耗 -5.0%" in text

    def test_weapon_persona_conditions_apply_and_are_localized_in_all_locales(self):
        from types import SimpleNamespace

        avatar = SimpleNamespace(
            weapon=SimpleNamespace(weapon_type=WeaponType.SPEAR),
        )
        weapon_personas = [
            persona
            for persona in personas_by_id.values()
            if "avatar.weapon.weapon_type" in str(persona.effects)
        ]
        assert weapon_personas
        assert "avatar.weapon.type" not in str([persona.effects for persona in weapon_personas])

        for persona in weapon_personas:
            condition = persona.effects[0]["when"]
            weapon_key = condition.split("WeaponType.", 1)[1].split()[0]
            matching_avatar = SimpleNamespace(
                weapon=SimpleNamespace(weapon_type=WeaponType[weapon_key]),
            )
            assert _evaluate_conditional_effect(persona.effects, matching_avatar)

        spear_fanatic = personas_by_id[50]
        active = _evaluate_conditional_effect(spear_fanatic.effects, avatar)
        assert active["extra_weapon_proficiency_gain"] == 1.0
        assert active["extra_battle_strength_points"] == 3

        for locale in get_locale_codes():
            language_manager.set_language(locale)
            reload_translations()
            text = format_effects_to_text(spear_fanatic.effects)
            assert "avatar.weapon" not in text
            assert "WeaponType." not in text
            assert "SPEAR" not in text

    def test_official_rank_condition_labels_are_localized_in_all_locales(self):
        from src.classes.official_rank import OFFICIAL_RANKS
        from src.i18n import t

        condition_effects = [
            effect
            for rank in OFFICIAL_RANKS.values()
            for effect in rank.effects
            if isinstance(effect, dict) and effect.get("when_desc")
        ]
        assert condition_effects

        for locale in get_locale_codes():
            language_manager.set_language(locale)
            reload_translations()
            assert t("condition_confucian_orthodoxy") != "condition_confucian_orthodoxy"
            for effect in condition_effects:
                assert "avatar.orthodoxy" not in format_effects_to_text(effect)
