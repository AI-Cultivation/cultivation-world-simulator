"""
Effects 效果系统
================

本文件定义了游戏中所有合法的 effect 字段。
Effects 通过角色的 avatar.effects 属性合并并生效。

Effect 来源：
- 宗门 (sect)
- 功法 (technique)
- 灵根 (root)
- 特质 (persona)
- 兵器和辅助装备 (weapon, auxiliary)
"""

# =============================================================================
# Effect 常量定义
# =============================================================================

# --- 战斗相关 ---
EXTRA_BATTLE_STRENGTH_POINTS = "extra_battle_strength_points"
"""
额外战斗力点数
类型: int
结算: src/classes/battle.py
说明: 直接增加角色的战斗力数值。
数值参考: 
  - 微量: 1~2 (相当于提升1-2个小境界)
  - 中量: 3~5 (相当于提升半个大境界)
  - 大量: 8+ (相当于提升一个大境界)
"""

EXTRA_MAX_HP = "extra_max_hp"
"""
额外最大生命值
类型: int
结算: src/classes/avatar.py (__post_init__)
说明: 增加角色的最大生命值上限。
数值参考: 
  - 微量: 10~30
  - 中量: 50~100 (练气期基础HP约100)
  - 大量: 150+
"""

EXTRA_OBSERVATION_RADIUS = "extra_observation_radius"
"""
额外观察半径
类型: int
结算: src/classes/observe.py
说明: 增加角色的观察范围（格子数）。
数值参考: 
  - 微量: 1
  - 中量: 2
  - 大量: 3
"""

EXTRA_APPEARANCE = "extra_appearance"
"""
额外颜值
类型: int
结算: src/classes/core/avatar/core.py (Avatar.appearance)
说明: 在角色初始颜值基础上叠加，最终结果会被限制在 1~10。
数值参考:
  - 微量: 1
  - 大量: 2
"""

# --- 修炼相关 (仙道-吐纳) ---
EXTRA_RESPIRE_EXP = "extra_respire_exp"
"""
额外吐纳经验
类型: int
结算: src/classes/action/respire.py
说明: 每次吐纳结算时，额外增加的固定经验值。
数值参考: 
  - 微量: 5~10
  - 中量: 20~50 (基础吐纳约每次100点经验)
  - 大量: 100+
"""
    
EXTRA_RESPIRE_EXP_MULTIPLIER = "extra_respire_exp_multiplier"
"""
额外吐纳经验倍率
类型: float
结算: src/classes/action/respire.py
说明: 每次吐纳结算时，额外增加的经验倍率。
数值参考: 
  - 微量: 0.1 (+10%)
  - 中量: 0.5 (+50%)
  - 大量: 1.0 (+100%)
"""

RESPIRE_DURATION_REDUCTION = "respire_duration_reduction"
"""
吐纳时长缩减
类型: float
结算: src/classes/action/respire.py
说明: 吐纳动作的时长缩减比例。
数值参考: 
  - 微量: 0.05~0.1 (缩减5%-10%)
  - 中量: 0.15 (15%)
  - 极限: 0.3 (30%)
"""

# --- 修炼相关 (武道-锻体) ---
TEMPER_DURATION_REDUCTION = "temper_duration_reduction"
"""
锻体时长缩减
类型: float
结算: src/classes/action/temper.py
说明: 锻体动作的时长缩减比例。
数值参考:
  - 微量: 0.05~0.1
  - 中量: 0.15
  - 极限: 0.3
"""

EXTRA_BREAKTHROUGH_SUCCESS_RATE = "extra_breakthrough_success_rate"
"""
额外突破成功率
类型: float
结算: src/classes/action/breakthrough.py
说明: 修改突破瓶颈时的成功率。
数值参考: 
  - 微量: 0.05 (5%)
  - 中量: 0.1 (10%)
  - 大量: 0.3 (30%)
"""

EXTRA_RETREAT_SUCCESS_RATE = "extra_retreat_success_rate"
"""
额外闭关成功率
类型: float
结算: src/classes/action/retreat.py
说明: 闭关判定成功率的加成。
数值参考: 
  - 微量: 0.05 (5%)
  - 中量: 0.1 (10%)
  - 大量: 0.2 (20%)
"""

EXTRA_REST_EXP = "extra_rest_exp"
"""
额外休息修为经验
类型: int
结算: src/classes/action/rest.py
说明: 休息动作结算时额外获得的固定修为经验。
"""

# --- 双修相关 ---
EXTRA_DUAL_CULTIVATION_EXP = "extra_dual_cultivation_exp"
"""
额外双修经验
类型: int
结算: src/classes/mutual_action/dual_cultivation.py
说明: 双修时发起者额外获得的固定经验值。
数值参考: 
  - 微量: 10~30
  - 中量: 50~100 (双修基础收益约300~500)
  - 大量: 150+
"""

# --- 采集相关 ---
EXTRA_HARVEST_MATERIALS = "extra_harvest_materials"
"""
额外采集材料数量
类型: int
结算: src/classes/action/harvest.py
说明: 采集植物时额外获得的材料数量。
数值参考: 
  - 微量: 1
  - 中量: 2
  - 大量: 3
"""

EXTRA_HUNT_MATERIALS = "extra_hunt_materials"
"""
额外狩猎材料数量
类型: int
结算: src/classes/action/hunt.py
说明: 狩猎动物时额外获得的材料数量。
数值参考: 
  - 微量: 1
  - 中量: 2
  - 大量: 3
"""

EXTRA_MINE_MATERIALS = "extra_mine_materials"
"""
额外挖矿材料数量
类型: int
结算: src/classes/action/mine.py
说明: 挖矿时额外获得的材料数量。
"""

EXTRA_PLANT_INCOME = "extra_plant_income"
"""
额外种植灵石收益
类型: int
结算: src/classes/action/plant.py
说明: 种植时额外获得的灵石数量。
"""

# --- 移动相关 ---
EXTRA_MOVE_STEP = "extra_move_step"
"""
额外移动步数
类型: int
结算: src/classes/action/move.py
说明: 每次移动时可以多移动的格子数。
数值参考: 
  - 中量: 1
  - 大量: 2
"""

# --- 捕捉相关 ---
EXTRA_CATCH_SUCCESS_RATE = "extra_catch_success_rate"
"""
额外捕捉成功率
类型: float
结算: src/classes/action/catch.py
说明: 捕捉灵兽时增加的成功率。
数值参考: 
  - 微量: 0.05~0.1 (5%-10%)
  - 中量: 0.2 (20%)
  - 大量: 0.3 (30%)
"""

# --- 逃跑相关 ---
EXTRA_ESCAPE_SUCCESS_RATE = "extra_escape_success_rate"
"""
额外逃跑成功率
类型: float
结算: src/classes/battle.py
说明: 从战斗中逃离的成功率加成。
数值参考: 
  - 微量: 0.1
  - 中量: 0.2
  - 大量: 0.3~0.5 (配合基础概率几乎必逃)
"""

# --- 暗杀相关 ---
EXTRA_ASSASSINATE_SUCCESS_RATE = "extra_assassinate_success_rate"
"""
额外暗杀成功率
类型: float
结算: src/classes/battle.py (get_assassination_success_rate)
说明: 暗杀判定成功率的加成。
数值参考: 
  - 微量: 0.05 (5%)
  - 中量: 0.1 (10%)
  - 大量: 0.15 (15%)
"""

# --- 奇遇相关 ---
EXTRA_LUCK = "extra_luck"
"""
额外气运
类型: int
结算: src/classes/effect/luck.py
说明: 影响奇遇、厄运、秘境、顿悟、突破等“命数”相关收益。
数值参考:
  - 普通人: 0
  - 有福缘: 5~10
  - 主角模板: 15~25
  - 倒霉体质: -5~-10
"""

EXTRA_FORTUNE_PROBABILITY = "extra_fortune_probability"
"""
额外奇遇概率
类型: float
结算: src/classes/fortune.py
说明: 每月触发奇遇的额外概率（绝对值）。
数值参考: 
  - 基础概率通常极低 (<0.01)
  - 微量: 0.001 (0.1%，有)
  - 中量: 0.002~0.005 (高)
  - 极高: 0.01 (1%，不少了)
"""

EXTRA_MISFORTUNE_PROBABILITY = "extra_misfortune_probability"
"""
额外霉运概率
类型: float
结算: src/classes/misfortune.py
数值参考: 
  - 基础概率通常极低 (<0.01)
  - 微量: 0.001 (0.1%，有)
  - 中量: 0.002~0.005 (高)
  - 极高: 0.01 (1%，不少了)
"""

EXTRA_OPPORTUNITY_PROBABILITY = "extra_opportunity_probability"
"""
额外机缘概率
类型: float
结算: src/systems/opportunity/
说明: 每月触发限时机缘感应的额外概率（绝对值）。
数值参考:
  - 基础概率通常极低 (<0.01)
  - 微量: 0.001 (0.1%，有)
  - 中量: 0.002~0.005 (高)
  - 极高: 0.01 (1%，不少了)
"""

# --- 铸造相关 ---
EXTRA_CAST_SUCCESS_RATE = "extra_cast_success_rate"
"""
额外铸造成功率
类型: float
结算: src/classes/action/cast.py
说明: 铸造（Cast）动作的成功率加成。
数值参考: 
  - 微量: 0.05 (+5%)
  - 中量: 0.1 (+10%)
  - 大量: 0.2+ (+20%)
"""

EXTRA_REFINE_SUCCESS_RATE = "extra_refine_success_rate"
"""
额外炼丹成功率
类型: float
结算: src/classes/action/refine.py
说明: 炼丹（Refine）动作的成功率加成。
数值参考: 
  - 微量: 0.05 (+5%)
  - 中量: 0.1 (+10%)
  - 大量: 0.2+ (+20%)
"""

EXTRA_SECT_MISSION_SUCCESS_RATE = "extra_sect_mission_success_rate"
"""
额外宗门任务成功率
类型: float
结算: src/classes/action/sect_mission.py
说明: 宗门任务动作的成功率加成。
数值参考:
  - 微量: 0.05 (+5%)
  - 中量: 0.1 (+10%)
  - 大量: 0.2+ (+20%)
"""

# --- 兵器相关 ---
EXTRA_WEAPON_PROFICIENCY_GAIN = "extra_weapon_proficiency_gain"
"""
额外兵器熟练度增长速度
类型: float
结算: src/classes/action/nurture_weapon.py
说明: 熟练度增长倍率（乘法加成）。
数值参考: 
  - 微量: 0.1~0.2 (+10%-20%)
  - 中量: 0.5 (+50%)
  - 大量: 1.0 (+100%，翻倍)
"""

EXTRA_WEAPON_UPGRADE_CHANCE = "extra_weapon_upgrade_chance"
"""
额外兵器升华概率
类型: float
结算: src/classes/action/nurture_weapon.py
说明: 温养兵器时升华为宝物的概率加成。
数值参考: 
  - 基础概率: 0.05 (5%)
  - 微量: 0.05 (+5%)
  - 中量: 0.1 (10%)
  - 大量: 0.15 (15%)
"""

# --- 生存与恢复相关 ---
EXTRA_MAX_LIFESPAN = "extra_max_lifespan"
"""
额外最大寿元
类型: int (年)
结算: src/classes/age.py
说明: 增加角色的最大寿命上限。
数值参考: 
  - 微量: 5~10
  - 中量: 20~50
  - 大量: 100+
"""

EXTRA_HP_RECOVERY_RATE = "extra_hp_recovery_rate"
"""
额外HP恢复速率。同时影响动作SelfHeal和Simulator中的自然回复。
类型: float
结算: src/classes/action/self_heal.py
说明: 疗伤时的HP恢复效率倍率。
数值参考: 
  - 微量: 0.1~0.2
  - 中量: 0.5 (+50%)
  - 大量: 1.0 (翻倍)
"""

EXTRA_REST_HP_RECOVERY_RATE = "extra_rest_hp_recovery_rate"
"""
额外休息恢复倍率
类型: float
结算: src/classes/action/rest.py
说明: 休息动作恢复生命值时的额外倍率。
"""

DAMAGE_REDUCTION = "damage_reduction"
"""
伤害减免
类型: float
结算: src/classes/battle.py
说明: 受到伤害的减免比例（乘法减少）。
数值参考: 
  - 微量: 0.05
  - 中量: 0.1
  - 坦克: 0.2~0.3 (不建议超过0.3)
"""

REALM_SUPPRESSION_BONUS = "realm_suppression_bonus"
"""
境界压制加成
类型: float
结算: src/classes/battle.py
说明: 当境界高于对手时，每级境界差提供的战斗力百分比加成。可以理解为“额外威压”
数值参考: 
  - 基础值: 0.0 (无额外加成，仅靠基础属性)
  - 微量: 0.05 (每级差多10%战斗力)
  - 中量: 0.1
  - 大量: 0.15
"""

# --- 经济相关 ---
EXTRA_ITEM_SELL_PRICE_MULTIPLIER = "extra_item_sell_price_multiplier"
"""
额外物品出售价格倍率
类型: float
结算: src/classes/action/sold.py
说明: 出售物品时的价格加成倍率。
数值参考: 
  - 微量: 0.1 (+10%)
  - 中量: 0.2~0.3
  - 奸商: 0.5
"""

SHOP_BUY_PRICE_REDUCTION = "shop_buy_price_reduction"
"""
商铺购买价格倍率减免
类型: float
结算: src/classes/prices.py
说明: 降低从系统购买物品时的溢价倍率。
数值参考: 
  - 微量: 0.1 (倍率-0.1)
  - 中量: 0.5 (倍率-0.5)
限制: 最终倍率最低为 1.0
"""

EXTRA_PLUNDER_MULTIPLIER = "extra_plunder_multiplier"
"""
额外搜刮收益倍率
类型: float
结算: src/classes/action/plunder_people.py
说明: 搜刮凡人时的收益倍率。
数值参考: 
  - 微量: 0.5 
  - 中量: 1.0
  - 大量: 2
"""

EXTRA_EAT_MORTALS_EXP_MULTIPLIER = "extra_eat_mortals_exp_multiplier"
"""
额外吃凡人修为经验倍率
类型: float
结算: src/classes/action/eat_mortals.py
说明: 妖族吃凡人时获得修为经验的倍率加成。
"""

EXTRA_CROSS_RACE_FRIENDLINESS = "extra_cross_race_friendliness"
"""
跨种族初始好感修正
类型: int
结算: src/sim/avatar_init/
说明: 不同种族角色生成初始关系时的好感修正。
"""

# 秘境相关
EXTRA_HIDDEN_DOMAIN_DROP_PROB = "extra_hidden_domain_drop_prob"
"""
额外秘境掉落概率
类型: float
结算: src/classes/gathering/hidden_domain.py
说明: 增加在秘境中获得宝物的概率。
数值参考:
  - 微量: 0.05
  - 中量: 0.1
  - 大量: 0.2
"""

EXTRA_HIDDEN_DOMAIN_DANGER_PROB = "extra_hidden_domain_danger_prob"
"""
额外秘境危险概率
类型: float
结算: src/classes/gathering/hidden_domain.py
说明: 增加（或减少，负值）在秘境中遇到危险的概率。
数值参考:
  - 降低危险: -0.1 (降低10%危险率)
  - 增加危险: 0.1
"""

# --- 宗门传道相关 ---
EXTRA_EPIPHANY_PROBABILITY = "extra_epiphany_probability"
"""
额外顿悟概率
类型: float
结算: src/classes/gathering/sect_teaching.py
说明: 在宗门传道大会等事件中，直接习得他人功法/经验的额外概率。
数值参考: 
  - 微量: 0.05
  - 中量: 0.1
  - 天才: 0.2
"""

# --- 特殊权限 ---
LEGAL_ACTIONS = "legal_actions"
"""
合法动作列表
类型: list[str]
结算: 各个 action 的权限检查
说明: 允许角色执行的特殊动作列表。
可用值:
  - "DevourPeople": 吞噬生灵（邪道法宝万魂幡）
  - "InflictGu": 下蛊（蛊具）
"""

# --- 蛊术相关 ---
EXTRA_GU_SUCCESS_RATE = "extra_gu_success_rate"
"""
额外下蛊成功率
类型: float
结算: src/systems/gu.py
说明: 增加施展下蛊动作时的成功率。
数值参考:
  - 蛊具小幅: 0.03
  - 蛊师: 0.10
  - 蛊仙: 0.18
"""

EXTRA_GU_DURATION_MONTHS = "extra_gu_duration_months"
"""
额外蛊持续月份
类型: int
结算: src/systems/gu.py
说明: 增加成功下蛊后的持续月份。
数值参考:
  - 小幅: 3
  - 蛊师: 6
  - 蛊仙: 12
"""

EXTRA_GU_RESISTANCE_RATE = "extra_gu_resistance_rate"
"""
额外防蛊成功率修正
类型: float
结算: src/systems/gu.py
说明: 降低被下蛊时的成功率。
数值参考:
  - 普通防护: 0.08
  - 明显防护: 0.12
  - 强防护: 0.18
  - 顶级防护: 0.20
"""

# --- 阵法相关 ---
EXTRA_FORMATION_POWER = "extra_formation_power"
"""
额外阵法强度
类型: float
结算: src/systems/formation.py
说明: 布置阵法时提高最终区域阵法效果。
数值参考:
  - 阵师: 0.15
  - 阵仙: 0.35
"""

EXTRA_FORMATION_DURATION_MONTHS = "extra_formation_duration_months"
"""
额外阵法持续月份
类型: int
结算: src/systems/formation.py
说明: 布置阵法时增加持续时间。
数值参考:
  - 阵师: 6
  - 阵仙: 12
"""

FORMATION_COST_REDUCTION = "formation_cost_reduction"
"""
布阵灵石消耗降低
类型: float
结算: src/systems/formation.py
说明: 布置阵法时降低灵石消耗。
数值参考:
  - 阵师: 0.10
  - 阵仙: 0.25
"""

# =============================================================================
# CSV 配置格式规范
# =============================================================================

"""
CSV 中 effects 列的写法（支持宽松JSON格式）:

基础格式（推荐无引号key）:
  {extra_battle_strength_points: 3}
  {extra_battle_strength_points: 2, extra_max_hp: 50}
  {legal_actions: ['DevourPeople']}

条件effect（when字段）:
  [{when: 'avatar.weapon.weapon_type == WeaponType.SWORD', extra_battle_strength_points: 3}]
  可访问: avatar, WeaponType, EquipmentGrade, Alignment

动态值（字符串表达式会被eval）:
  {extra_battle_strength_points: 'avatar.weapon.special_data.get("souls", 0) * 0.1'}

注意: CSV中包含逗号的effects值需要用双引号包裹，避免被误认为列分隔符
"""

# =============================================================================
# Effect 合并规则
# =============================================================================

"""
Effects 通过 src/classes/effect/process.py 中的 _merge_effects() 函数合并。

合并规则:
1. 列表类型 (如 legal_actions): 取并集（去重）
2. 数值类型 (如 extra_*): 累加
3. 其他类型: 后者覆盖前者
4. 动态表达式 (字符串形式): 在 Avatar.effects property 中 eval 计算

合并顺序（从低到高优先级）:
1. 宗门 (sect)
2. 功法 (technique)
3. 灵根 (root)
4. 特质 (persona) - 遍历所有 personas
5. 兵器和辅助装备 (weapon, auxiliary)

最终结果通过 Avatar.effects 属性获取（实时计算）。
"""

# =============================================================================
# 所有合法 Effect 字段清单
# =============================================================================

ALL_EFFECTS = [
    # 战斗相关
    "extra_battle_strength_points",      # int - 额外战斗力
    "extra_max_hp",                      # int - 额外最大生命值
    "extra_observation_radius",          # int - 额外观察半径
    "extra_appearance",                  # int - 额外颜值
    "damage_reduction",                  # float - 伤害减免
    "realm_suppression_bonus",           # float - 境界压制加成
    
    # 修炼相关
    "extra_respire_exp",                 # int - 额外吐纳经验
    "extra_respire_exp_multiplier",      # float - 额外吐纳经验倍率
    "respire_duration_reduction",        # float - 吐纳时长缩减
    "temper_duration_reduction",         # float - 锻体时长缩减
    "extra_breakthrough_success_rate",   # float - 额外突破成功率
    "extra_retreat_success_rate",        # float - 额外闭关成功率
    "extra_rest_exp",                    # int - 额外休息修为经验
    
    # 双修相关
    "extra_dual_cultivation_exp",        # int - 额外双修经验
    
    # 采集相关
    "extra_harvest_materials",           # int - 额外采集材料数量
    "extra_hunt_materials",              # int - 额外狩猎材料数量
    "extra_mine_materials",               # int - 额外挖矿材料数量
    "extra_plant_income",                # int - 额外种植灵石收益
    
    # 移动相关
    "extra_move_step",                   # int - 额外移动步数
    
    # 捕捉相关
    "extra_catch_success_rate",          # float - 额外捕捉成功率
    
    # 逃跑相关
    "extra_escape_success_rate",         # float - 额外逃跑成功率
    
    # 暗杀相关
    "extra_assassinate_success_rate",    # float - 额外暗杀成功率

    # 奇遇相关
    "extra_luck",                        # int - 额外气运
    "extra_fortune_probability",         # float - 额外奇遇概率
    "extra_misfortune_probability",      # float - 额外霉运概率
    "extra_opportunity_probability",     # float - 额外机缘概率
    
    # 铸造相关
    "extra_cast_success_rate",           # float - 额外铸造成功率
    "extra_refine_success_rate",         # float - 额外炼丹成功率
    "extra_sect_mission_success_rate",   # float - 额外宗门任务成功率

    # 兵器相关
    "extra_weapon_proficiency_gain",     # float - 额外兵器熟练度增长倍率
    "extra_weapon_upgrade_chance",       # float - 额外兵器升华概率
    
    # 生存与恢复相关
    "extra_max_lifespan",                # int - 额外最大寿元（年）
    "extra_hp_recovery_rate",            # float - 额外HP恢复速率倍率
    "extra_rest_hp_recovery_rate",       # float - 额外休息恢复倍率
    
    # 经济相关
    "extra_item_sell_price_multiplier",  # float - 额外物品出售价格倍率
    "shop_buy_price_reduction",          # float - 商铺购买价格倍率减免
    "extra_plunder_multiplier",          # float - 额外搜刮收益倍率
    "extra_eat_mortals_exp_multiplier",  # float - 额外吃凡人修为经验倍率
    "extra_cross_race_friendliness",     # int - 跨种族初始好感修正
    "extra_gu_success_rate",             # float - 额外下蛊成功率
    "extra_gu_duration_months",          # int - 额外蛊持续月份
    "extra_gu_resistance_rate",          # float - 额外防蛊成功率修正
    "extra_formation_power",             # float - 额外阵法强度
    "extra_formation_duration_months",   # int - 额外阵法持续月份
    "formation_cost_reduction",          # float - 布阵灵石消耗降低
    
    # 秘境相关
    "extra_hidden_domain_drop_prob",     # float - 额外秘境掉落概率
    "extra_hidden_domain_danger_prob",   # float - 额外秘境危险概率

    # 宗门传道相关
    "extra_epiphany_probability",        # float - 额外顿悟概率

    # 特殊权限
    "legal_actions",                     # list[str] - 合法动作列表
]

