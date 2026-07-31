/**
 * 核心领域模型 (Core Domain Models)
 * 这些类型代表了前端应用内部使用的“标准”数据结构。
 * 它们应该是完整的、经过清洗的数据，尽量减少 undefined 的使用。
 */

// --- 基础实体 ---

export interface EntityBase {
  id: string;
  name: string;
}

export interface Coordinates {
  x: number;
  y: number;
}

// --- 物品与效果 ---

export interface EffectEntity extends EntityBase {
  desc?: string;
  effect_desc?: string;
  story_prompt?: string;
  mechanism_type?: string;
  grade?: string;
  realm?: string;
  rarity?: string; // e.g., 'SSR', 'R', '上品'
  type?: string;
  type_name?: string; // 新增：中文类型名，如"丹药"、"破境"等
  color?: string | number[]; // 某些实体自带颜色
  attribute?: string;
  key?: string;
  icon_key?: string;
  icon_category?: string;
  is_custom?: boolean;
  drops?: EffectEntity[];
  hq_name?: string;
  hq_desc?: string;
}

export interface Material extends EffectEntity {
  count: number;
}

export interface CultivationDisplay {
  profile_id: string;
  profile_name: string;
  realm_id: string;
  stage_id: string;
  level: number;
  canonical_realm_name: string;
  canonical_stage_name: string;
  canonical_full_name: string;
  display_realm_name: string;
  display_stage_name: string;
  display_full_name: string;
}

export interface FateRevelation {
  trigger_text: string;
  oracle_text: string;
  revealed_month?: number;
  location?: string;
}

// --- 角色 (Avatar) ---

export interface AvatarSummary extends EntityBase, Coordinates {
  action?: string;
  action_emoji?: string;
  gender?: string;
  race?: string;
  pic_id?: number;
  realm?: string;
  cultivation?: CultivationDisplay;
  cultivation_display?: string;
  is_dead?: boolean;
}

export interface AvatarDetail extends EntityBase {
  // 基础信息
  pic_id?: number | null;
  gender: string;
  race?: EffectEntity;
  age: number;
  origin: string;
  cultivation_start_age?: number;
  cultivation_start_month_stamp?: number;
  lifespan: number;
  nickname?: string;
  appearance: string; // 外貌描述
  is_dead?: boolean;
  action_state?: string; // 当前正在进行的动作描述
  death_info?: {
    time: number;
    reason: string;
    location: [number, number];
  };
  
  // 修行状态
  realm: string;
  realm_id?: string;
  stage_id?: string;
  cultivation?: CultivationDisplay;
  level: number;
  hp: { cur: number; max: number };
  observation_radius?: number;
  luck: number;
  official_rank?: string;
  court_reputation?: number;
  is_official?: boolean;
  magic_stone: number;
  sect_contribution: number;
  base_battle_strength: number;
  ranking?: { type: string; rank: number };
  
  // 情绪
  emotion: {
    name: string;
    emoji: string;
    desc: string;
  };
  
  // 属性与资质
  alignment: string;
  alignment_detail?: EffectEntity;
  root: string;
  root_detail?: EffectEntity;
  
  // 思维与目标
  thinking: string;
  short_term_objective: string;
  long_term_objective: string;
  backstory?: string | null;
  fate_revelation?: FateRevelation | null;
  
  // 关联实体
  sect?: SectInfo;
  orthodoxy?: EffectEntity; // 新增道统字段
  personas: EffectEntity[];
  goldfinger?: EffectEntity;
  technique?: EffectEntity;
  weapon?: EffectEntity & { proficiency: string };
  auxiliary?: EffectEntity;
  spirit_animal?: EffectEntity;
  
  // 列表数据
  materials: Material[];
  relations: RelationInfo[];
  
  // 附加信息
  current_effects?: string;
  "当前效果"?: string;
  sect_status_summary?: {
    sect_name: string;
    sect_rank: string;
    sect_is_at_war: boolean;
    active_war_count: number;
    active_wars: Array<{
      other_sect_id: number;
      other_sect_name: string;
      war_months: number;
      war_reason?: string;
      last_battle_month?: number | null;
    }>;
    rule_desc?: string;
    sect_alignment?: string;
    sect_orthodoxy?: string;
  } | null;
}

export interface SectInfo extends EffectEntity {
  alignment: string;
  style: string;
  hq_name: string;
  hq_desc: string;
  rank: string;
  contribution?: number;
}

export interface SectMember {
  id: string;
  name: string;
  pic_id: number;
  gender: string;
  rank: string;
  realm: string;
  contribution?: number;
  base_battle_strength?: number;
  status_score?: number;
}

export interface SectDetail extends EntityBase {
  desc: string;
  alignment: string;
  style: string;
  hq_name: string;
  hq_desc: string;
  effect_desc: string;
  rule_id?: string;
  rule_desc?: string;
  accept_yao?: boolean;
  technique_names?: string[]; // Deprecated
  techniques: EffectEntity[];
  preferred_weapon: string;
  members: SectMember[];
  orthodoxy: EffectEntity;
  magic_stone: number;
  is_active: boolean;
  total_battle_strength: number;
  influence_radius: number;
  color: string;
  runtime_effect_desc?: string;
  runtime_extra_income_per_tile?: number;
  runtime_effects_count?: number;
  runtime_effect_items?: SectRuntimeEffectItem[];
  war_weariness?: number;
  periodic_thinking?: string;
  yearly_thinking?: string; // Deprecated
  diplomacy_items?: SectDiplomacyItem[];
  territory_summary?: {
    tile_count: number;
    border_tile_count?: number;
    border_pressure_ratio?: number;
    conflict_tile_count: number;
    headquarter_center?: [number, number] | null;
  };
  economy_summary?: {
    current_magic_stone: number;
    effective_income_per_tile: number;
    controlled_tile_income: number;
    estimated_yearly_income?: number;
    estimated_yearly_upkeep?: number;
  };
  war_summary?: {
    active_war_count: number;
    peace_count: number;
    strongest_enemy_name: string;
    strongest_enemy_relation: number;
  };
}

export interface SectRuntimeEffectItem {
  source: string;
  source_label: string;
  desc: string;
  remaining_months: number;
  is_permanent?: boolean;
}

export interface SectDiplomacyItem {
  other_sect_id: number;
  other_sect_name: string;
  status: 'war' | 'peace' | string;
  duration_months: number;
  war_months: number;
  peace_months: number;
  relation_value?: number;
  war_reason?: string;
  last_battle_month?: number | null;
  reason_summary?: string;
}

export interface RelationInfo {
  target_id: string;
  name: string;
  relation: string;
  relation_type: string;
  blood_relation?: string | null;
  identity_relations?: string[];
  numeric_relation?: string;
  friendliness?: number;
  realm: string;
  sect: string;
  is_mortal?: boolean;
  is_dead?: boolean;
  relation_scope?: 'active' | 'archived' | 'computed' | 'mortal_child' | string;
  label_key?: string;
  target_gender?: string;
  cultivation?: CultivationDisplay;
}

// --- 地图与区域 (Map & Region) ---

export type MapMatrix = string[][];

export interface RegionSummary extends EntityBase, Coordinates {
  type: string;
  sect_id?: number;
  sect_name?: string;
  sect_color?: string;
  // 是否为激活宗门（由后端地图查询接口提供，当前主路径为 /api/v1/query/world/map）。未提供时视为 true。
  sect_is_active?: boolean;
  sub_type?: string; // for cultivate regions: "cave" or "ruin"
  formation?: RegionFormationInfo | null;
}

export interface POISummary extends EntityBase, Coordinates {
  kind: string;
  icon_key?: string;
  clickable?: boolean;
  deceased_avatar_id?: string;
}

export interface POIDetail extends POISummary {
  desc?: string;
  deceased?: {
    id: string;
    name: string;
    age_at_death?: number | null;
    realm_at_death: string;
    stage_at_death: string;
    death_reason: string;
    death_time: number;
    sect_name_at_death: string;
    alignment_at_death: string;
    backstory?: string | null;
    custom_pic_id?: number | null;
  };
  grave_goods?: {
    weapon?: {
      kind?: string;
      item_id?: number;
      name: string;
      realm?: string;
    } | null;
    auxiliary?: {
      kind?: string;
      item_id?: number;
      name: string;
      realm?: string;
    } | null;
  };
  dig_attempt_count?: number;
  treasure?: {
    source: string;
    source_label?: string;
    realm: string;
    realm_name?: string;
    item: {
      kind?: 'weapon' | 'auxiliary' | string;
      item_id?: number;
      name: string;
      realm?: string;
    } | null;
    attempt_count: number;
    expires_month?: number | null;
  };
}

export interface RegionFormationInfo {
  formation_type: string;
  name: string;
  remaining_months: number;
  effect_desc: string;
  caster_id?: string;
  disk_item_id?: number;
  cost?: number;
  effects?: Record<string, number | string | boolean | string[]>;
}

export interface RegionDetail extends EntityBase {
  desc: string;
  type: string;
  type_name: string; // 中文类型名
  sub_type?: string;
  sect_id?: number;
  population?: number;
  population_capacity?: number;
  
  essence?: { 
    type: string; 
    density: number; 
  };
  
  // 洞府主人（修炼区域特有）
  host?: {
    id: string;
    name: string;
  } | null;
  
  animals: EffectEntity[];
  plants: EffectEntity[];
  lodes: EffectEntity[];
  store_items?: (EffectEntity & { price: number })[];
  formation?: RegionFormationInfo | null;
}

// --- 天地灵机 ---

export interface CelestialPhenomenon {
  id: number;
  name: string;
  desc: string;
  rarity: string;
  duration_years?: number;
  effect_desc?: string;
}

// web/src/types/core.ts

// 新增秘境信息接口
export interface HiddenDomainInfo {
  id: string;
  name: string;
  desc: string;
  required_realm: string; // 限制境界
  danger_prob: number; // 凶险度 (0.0 - 1.0)
  drop_prob: number;   // 机缘度 (0.0 - 1.0)
  cd_years: number;    // CD 年份
  open_prob: number;   // 开启概率
}

export interface TrackedMortalInfo {
  id: string;
  name: string;
  gender: string;
  age: number;
  born_region_id: number;
  born_region_name: string;
  parents: string[];
  is_awakening_candidate: boolean;
}

export interface MortalCityOverview {
  id: number;
  name: string;
  population: number;
  population_capacity: number;
  natural_growth: number;
}

export interface MortalOverview {
  summary: {
    total_population: number;
    total_population_capacity: number;
    total_natural_growth: number;
    tracked_mortal_count: number;
    awakening_candidate_count: number;
  };
  cities: MortalCityOverview[];
  tracked_mortals: TrackedMortalInfo[];
}

export interface DynastyOverview {
  name: string;
  title: string;
  royal_surname: string;
  royal_house_name: string;
  desc: string;
  effect_desc: string;
  style_tag: string;
  official_preference_label: string;
  is_low_magic: boolean;
  current_emperor: {
    name: string;
    surname: string;
    given_name: string;
    age: number;
    max_age: number;
    is_mortal: boolean;
  } | null;
}

export interface DynastyOfficial {
  id: string;
  name: string;
  realm: string;
  officialRankKey: string;
  officialRankName: string;
  courtReputation: number;
  sectName: string;
}

export interface DynastyDetail {
  overview: DynastyOverview;
  summary: {
    officialCount: number;
    topOfficialRankName: string;
  };
  officials: DynastyOfficial[];
}

export interface AvatarOverviewSummary {
  totalCount: number;
  aliveCount: number;
  deadCount: number;
  sectMemberCount: number;
  rogueCount: number;
}

export interface AvatarRealmDistributionItem {
  realm: string;
  realmId?: string;
  count: number;
}

export interface AvatarOverview {
  summary: AvatarOverviewSummary;
  realmDistribution: AvatarRealmDistributionItem[];
}

// --- 事件 (Events) ---

export type EventSubject =
  | {
      type: 'avatar';
      id: string;
      name: string;
      color?: string | null;
      isDead?: boolean;
    }
  | {
      type: 'sect';
      id: number;
      name: string;
      color?: string | null;
      isActive?: boolean;
    }

export interface GameEvent {
  id: string;
  text: string;
  content?: string; // 详细描述
  year: number;
  month: number;
  // 排序权重
  timestamp: number; 
  relatedAvatarIds: string[];
  relatedSects?: number[];
  subjects: EventSubject[];
  isMajor: boolean;
  isStory: boolean;
  renderKey?: string;
  renderParams?: Record<string, string | number | boolean | null>;
  
  // 真实创建时间 (用于精确排序)
  createdAt?: number;

  // 运行时辅助字段
  _seq?: number; 
}
