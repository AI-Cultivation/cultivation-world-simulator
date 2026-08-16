from __future__ import annotations

import json
from typing import Any, Callable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.classes.core.avatar import Avatar


def load_effect_from_str(value: object) -> dict[str, Any] | list[dict[str, Any]]:
    """
    将 effects 字段解析为 dict 或 list（支持宽松JSON格式）。
    
    支持的格式：
    1. 标准JSON: {"extra_battle_strength_points": 3}
    2. 单引号: {'extra_battle_strength_points': 3}
    3. 无引号key: {extra_battle_strength_points: 3}
    4. 混合格式: {extra_battle_strength_points: 3, 'legal_actions': ['DevourPeople']}
    5. 条件数组: [{when: 'condition', effect1: value1}, ...]
    
    - value 为 None/空字符串/'nan' 时返回 {}
    - 解析失败时返回 {}
    - 支持返回 dict（单个effect）或 list[dict]（多个条件effect）
    """
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    s = str(value).strip()
    if not s or s == "nan":
        return {}
    
    # 先尝试标准 JSON 解析
    try:
        obj = json.loads(s)
        if isinstance(obj, (dict, list)):
            return obj
        return {}
    except Exception:
        pass
    
    # 尝试宽松解析：单引号转双引号 + 无引号key处理
    try:
        import re
        
        # 1. 先保护所有引号内的内容（包括单引号和双引号字符串）
        strings = []
        def save_string(match):
            strings.append(match.group(0))
            return f"__STRING_{len(strings)-1}__"
        
        relaxed = s
        # 保护双引号字符串
        relaxed = re.sub(r'"(?:[^"\\]|\\.)*"', save_string, relaxed)
        # 保护单引号字符串
        relaxed = re.sub(r"'(?:[^'\\]|\\.)*'", save_string, relaxed)
        
        # 2. 给无引号的key添加引号（此时所有字符串都已被保护）
        # 匹配: 开始位置后的标识符 + 冒号
        relaxed = re.sub(r'([{\[,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*):', r'\1"__KEY_\2__"\3:', relaxed)
        
        # 3. 恢复字符串，并将单引号转为双引号
        for i, s_val in enumerate(strings):
            # 如果是单引号字符串，转为双引号
            if s_val.startswith("'"):
                # 需要转义内部的双引号，但要先恢复其中的__STRING_占位符
                content = s_val[1:-1]  # 去掉单引号
                # 恢复内部的字符串占位符
                for j, inner_str in enumerate(strings):
                    if f"__STRING_{j}__" in content and j != i:
                        content = content.replace(f"__STRING_{j}__", inner_str)
                # 转义处理
                content = content.replace('\\', '\\\\').replace('"', '\\"')
                s_val = f'"{content}"'
            relaxed = relaxed.replace(f"__STRING_{i}__", s_val)
        
        # 4. 恢复key（去掉__KEY_标记）
        relaxed = relaxed.replace('"__KEY_', '"').replace('__"', '"')
        
        # 5. 尝试解析
        obj = json.loads(relaxed)
        if isinstance(obj, (dict, list)):
            return obj
        return {}
    except Exception:
        return {}


def _evaluate_conditional_effect(effect: dict[str, Any] | list[dict[str, Any]], avatar: "Avatar") -> dict[str, Any]:
    """
    评估带条件的effect，返回实际生效的effect dict。
    
    支持三种格式：
    1. 普通dict（无条件）: {"extra_battle_strength_points": 1}
    2. 带条件的dict: {"extra_battle_strength_points": 2, "when": "avatar.weapon.weapon_type == WeaponType.SWORD"}
    3. 条件数组: [{"extra_battle_strength_points": 2, "when": "..."}, {...}]
    
    Args:
        effect: 原始effect配置（dict或list）
        avatar: 当前角色对象
    
    Returns:
        评估后实际生效的effect dict（合并所有满足条件的effects）
    """
    from src.classes.weapon_type import WeaponType
    from src.systems.cultivation import Realm
    from src.classes.alignment import Alignment
    
    # 构建安全的eval上下文
    safe_context = {
        "__builtins__": {},
        "avatar": avatar,
        "WeaponType": WeaponType,
        "Realm": Realm,
        "Alignment": Alignment,
        # 常用内置函数
        "any": any,
        "all": all,
        "len": len,
        "set": set,
        "list": list,
        "max": max,
        "min": min,
    }
    
    def _check_condition(when_expr: str) -> bool:
        """检查条件表达式是否为真"""
        if not when_expr:
            return True
        try:
            return bool(eval(when_expr, safe_context, {}))
        except Exception:
            # 条件评估失败时视为False
            return False
    
    def _process_single_effect(eff: dict[str, Any]) -> dict[str, Any]:
        """处理单个effect dict，检查条件并返回生效的部分"""
        if not isinstance(eff, dict):
            return {}
        
        when_expr = eff.get("when")
        if when_expr is None:
            # 无条件effect，直接返回
            return eff
        
        # 有条件effect，检查条件
        if not _check_condition(when_expr):
            return {}
        
        # 条件满足，返回除了when之外的所有字段
        return {k: v for k, v in eff.items() if k != "when"}
    
    # 处理list格式（多个条件effect）
    if isinstance(effect, list):
        result = {}
        for item in effect:
            evaluated = _process_single_effect(item)
            result = _merge_effects(result, evaluated)
        return result
    
    # 处理dict格式（单个effect）
    return _process_single_effect(effect)


def _merge_effects(base: dict[str, object], addition: dict[str, object]) -> dict[str, object]:
    """
    合并两个 effects 字典：
    - list 型（如 legal_actions）：做去重并集
    - 数值型：相加
    - 其他：后者覆盖前者
    返回新字典，不修改原对象。
    """
    if not base and not addition:
        return {}
    merged: dict[str, object] = dict(base) if base else {}
    for key, val in (addition or {}).items():
        if key in merged:
            old = merged[key]
            if isinstance(old, list) and isinstance(val, list):
                # 去重并集，保持相对顺序
                seen: set[object] = set()
                result: list[object] = []
                for x in old + val:
                    if x in seen:
                        continue
                    seen.add(x)
                    result.append(x)
                merged[key] = result
            elif isinstance(old, (int, float)) and isinstance(val, (int, float)):
                merged[key] = old + val
            else:
                merged[key] = val
        else:
            merged[key] = val
    return merged


def build_effects_map_from_df(
    data: list[dict[str, Any]],
    key_column: str,
    parse_key: Callable[[str], Any],
    effects_column: str = "effects",
) -> dict[Any, dict[str, object]]:
    """
    将配表数据列表构造成 {key -> effects} 的映射：
    - key_column：用于定位键（字符串），通过 parse_key 解析为目标键（如 Enum）
    - effects_column：字符串列，使用 load_effect_from_str 解析
    解析失败或空值的行将被忽略。
    """
    effects_map: dict[Any, dict[str, object]] = {}
    if not data:
        return effects_map
    for row in data:
        raw_key = str(row.get(key_column, "")).strip()
        if not raw_key or raw_key == "nan":
            continue
        try:
            key = parse_key(raw_key)
        except Exception:
            continue
        eff = load_effect_from_str(row.get(effects_column, ""))
        if eff:
            effects_map[key] = eff
    return effects_map

