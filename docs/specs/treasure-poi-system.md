# 宝物出世 POI 系统 Spec

本文档定义“宝物出世”系统的实现方案。宝物是地图上的限时 Point of Interest（POI），不是全世界立刻可见具体地点的普通事件文本，也不是新的装备栏、法宝成长体系或独立争夺战系统。

当前状态：已确认设计，待实现运行时逻辑与前端接入。

相关既有系统：

- 墓碑与通用 POI：[grave-poi-system.md](grave-poi-system.md)
- 单选装备交换与角色扮演 continuation：[single-choice-unified-framework.md](single-choice-unified-framework.md)
- 事件语义：[story-event-system.md](story-event-system.md)
- 地图官方真源与运行时状态：[region-first-map-system.md](region-first-map-system.md)

## 1. 目标与边界

### 1.1 目标

1. 世界中会随机出现限时宝物 POI。
2. 宝物存在二十年，即 `240` 个游戏月；到期无人取走时，宝光消散并移除。
3. 出世可产生全局模糊异象，公开宝物大境界但不公开坐标、具体物品或来源。
4. 角色进入 POI 的既有观察范围时，必定发现宝物。
5. 地图上帝视角始终显示有效宝物 POI；但角色的行动参数只包含自己已发现的宝物。
6. 已发现角色可通过既有 `MoveToPOI` 前往；到达同格后可执行即时动作“取宝”。
7. 取宝是否发生、是否继续停留、离开或攻击同格角色，仍由既有行动决策系统决定；宝物系统不替角色强制选择行为。
8. 成功取宝后仅复用既有武器和辅助装备替换流程。
9. 所有宝物状态、发现关系、尝试次数和待取物品都可随存档恢复。

### 1.2 非目标

第一阶段明确不做：

1. 新的装备槽、本命法宝、器灵、认主、成长、封印或独特性。
2. 谈判、结伴、组队、专属争夺战或“占领宝物”状态。
3. 按伤势、HP、感知、气运、宗门或其他临时状态修正取宝成功率。
4. 取宝失败后给出材料、边角、部分奖励等中间产物。
5. 地图预设中的静态宝物点；宝物是运行时世界状态，不写入 `map.json`。
6. 为旧存档维护复杂迁移或双轨反序列化。旧存档缺少宝物数据时按“无活跃宝物”恢复即可。

## 2. 已确认产品规则

### 2.1 生成规则

| 项目 | 确认值 |
|---|---|
| 检查频率 | 每月一次 |
| 出世概率 | `0.5%` / 月 |
| 活跃上限 | 全世界最多 `3` 个有效宝物 POI |
| 持续时间 | `240` 月（二十年） |
| 坐标 | 在随机有效地图格生成 |
| 地图显示 | 上帝视角地图显示全部有效宝物 |
| 角色认知 | 仅进入观察范围的角色被写入 `discovered_by` |
| 可生成物品 | 既有 `weapon` 或 `auxiliary` |
| 可生成大境界 | 筑基、金丹、元婴；没有练气 |

“随机有效地图格”至少要求：在边界内、能被地图模型正常读取、不是已存在宝物所在格。实现时应优先使用地图已有的合法 tile 语义，不恢复或引入 `tile_map.csv/region_map.csv` 平行路径。

### 2.2 叙事来源

每个宝物在生成时确定一种叙事来源并随存档保存：

```text
ancient_cultivator_relic  # 古修遗兵
spirit_vein_treasure      # 灵脉孕宝
demon_king_relic          # 妖王遗宝
demonic_artifact          # 魔道凶器
meteorite_relic           # 天外陨宝
lost_sect_artifact        # 宗门失传器
```

来源仅服务事件与详情叙事，不改变装备数值、取宝概率、地图位置或争夺规则。

### 2.3 发现与行动可见性

发现规则严格复用墓碑 POI 的实现：`POIManager.discover_nearby()` 以 `get_avatar_observation_radius()` 和曼哈顿距离检查；POI 在观察范围内时必定发现。

发现关系只保存在 `poi.discovered_by`，不在 Avatar 上维护第二份 `known_poi_ids`，以避免双写不一致。

以下两个可见性层必须区分：

| 层 | 宝物是否可见 |
|---|---|
| `/api/v1/query/world/map`、地图 POI 图层 | 所有尚未到期的宝物都显示 |
| `MoveToPOI` 参数选项 | 仅当前角色已发现的 POI |
| `TakeTreasure` 参数选项 | 仅当前角色已发现的 `treasure` POI |
| 动作 `can_start()` | 额外校验 POI 未过期且角色处于同格 |

## 3. 领域模型与存档

### 3.1 `TreasurePOI`

新增 `src/classes/poi/treasure.py`：

```python
@dataclass(kw_only=True)
class TreasurePOI(PointOfInterest):
    kind: str = "treasure"
    treasure_source: str
    treasure_realm: str
    treasure_payload: dict[str, Any] | None
    treasure_icon_id: str
    attempt_count: int = 0
```

`PointOfInterest` 已经承担以下通用字段，宝物不得重复维护：

```text
id, kind, x, y, name, desc,
created_month, expires_month,
discovered_by, icon_key, is_clickable
```

ID 建议为不可冲突的运行时 ID，例如：

```text
treasure:<created_month>:<short-random-id>
```

宝物物品只有一个 `treasure_payload`。它不应同时持有武器和辅助装备，也不应在 payload 外额外保存一个活的 Python Item 对象。

### 3.2 通用装备 payload

现有墓碑在 `src/classes/poi/grave.py` 内含有物品 snapshot 和恢复逻辑。实现宝物时应提取为 POI 范围的共享 helper，例如：

```text
src/classes/poi/item_payload.py
  build_equipment_payload(item) -> dict | None
  restore_equipment_item(payload) -> Weapon | Auxiliary | None
```

payload 只保存 JSON 基础类型：

```json
{
  "kind": "weapon",
  "item_id": 1001,
  "name": "玄陨剑",
  "realm": "CORE_FORMATION",
  "special_data": {}
}
```

恢复时通过既有 `weapons_by_id` 或 `auxiliaries_by_id` 找到原型并实例化，再恢复 `special_data`。这样墓碑与宝物共用同一份持久化契约，且不会共享物品实例。

### 3.3 存档格式

世界存档继续只通过既有 `world_data["pois"]` 保存：

```json
{
  "schema_version": 1,
  "id": "treasure:1296:8f3d2a",
  "kind": "treasure",
  "x": 42,
  "y": 17,
  "name": "金丹宝物",
  "desc": "灵光氤氲，一件古老宝物正在此地出世。",
  "created_month": 1296,
  "expires_month": 1416,
  "discovered_by": ["avatar-1", "avatar-8"],
  "icon_key": "treasure_04",
  "is_clickable": true,
  "treasure_source": "meteorite_relic",
  "treasure_realm": "CORE_FORMATION",
  "treasure_payload": {
    "kind": "weapon",
    "item_id": 1001,
    "name": "玄陨剑",
    "realm": "CORE_FORMATION",
    "special_data": {}
  },
  "treasure_icon_id": "treasure_04",
  "attempt_count": 4
}
```

序列化约束：

1. 只保存 JSON 基础类型。
2. 跨对象关系只保存 Avatar ID，不持有 Avatar 引用。
3. `discovered_by` 存为字符串数组，加载时恢复 `set[str]`。
4. `icon_key`、来源、物品、境界和尝试次数读档后保持不变，不重新随机。
5. 如果配置中对应 item ID 已不存在，动作应产生受控失败事件并保留 POI，不得异常中断模拟。

### 3.4 多态反序列化

当前 `POIManager.load_from_list()` 主要只识别 `grave`。实现时应使用明确 loader 分发表：

```python
POI_LOADERS = {
    "grave": GravePOI.from_save_dict,
    "treasure": TreasurePOI.from_save_dict,
}
```

不认识的 `kind` 可忽略并记录 warning；不需要为了旧存档新建兼容分支。`src/classes/poi/__init__.py` 必须导出 `TreasurePOI` 和共享 helper，保证导入路径完整。

## 4. 世界生命周期

### 4.1 配置

新增 `static/config.yml -> world.treasure`：

```yaml
world:
  treasure:
    spawn_probability_per_month: 0.005
    max_active_count: 3
    duration_months: 240
    realms:
      - FOUNDATION_ESTABLISHMENT
      - CORE_FORMATION
      - NASCENT_SOUL
    source_weights:
      ancient_cultivator_relic: 20
      spirit_vein_treasure: 20
      demon_king_relic: 15
      demonic_artifact: 15
      meteorite_relic: 15
      lost_sect_artifact: 15
    backlash_probability: 0.10
    backlash_hp_ratio: 0.12
```

运行时应在调用时读取当前配置，避免在模块 import 时冻结配置对象。

### 4.2 服务职责

新增 `src/systems/treasure.py`，职责是：

1. 判断活跃宝物数量和本月出世概率。
2. 随机抽取有效格、可用大境界、装备类别、对应物品、叙事来源和宝箱图标。
3. 创建并交给 `POIManager.add()`。
4. 生成不含地点的全局异象事件。
5. 清理本月到期的宝物并生成宝光消散事件。

`TreasurePOI` 只保存状态、序列化和 detail payload；它不读取概率配置，也不主动扫描地图。

### 4.3 模拟相位

新增月度 `treasure_lifecycle` 相位，位置在死亡结算之后、POI 发现之前：

```text
11  resolve_death
12  treasure_lifecycle
      a. 删除本月到期的 treasure POI，并产生消散事件
      b. 活跃宝物少于上限时按概率尝试出世
      c. 生成成功时通过 POIManager.add() 产生 upsert 增量
13  discover_pois
      a. 在观察范围的角色自动发现新旧宝物
```

新增相位后必须重排后续 `SimulationPhase.index`，`step()` 仍只负责编排。宝物到期清理不能继续只依赖年度维护，因为年度清理无法保证“第 240 个月”精确消散。墓碑是否继续走年度清理由墓碑系统自身决定，本改动不改变其 50 年语义。

### 4.4 事件

所有事件继续由模拟器集中收集和入库：

| 时机 | 内容范围 | 关联 | `is_major` |
|---|---|---|---:|
| 宝物出世 | 模糊异象，公开宝物等级，不含坐标 | 无 | `False` |
| 角色发现 | 坐标、名称、来源可见 | 发现者 | `False` |
| 取宝失败 | 失败或禁制反震 | 尝试者 | `False` |
| 取宝成功并接受 | 获得具体物品 | 取宝者 | `True` |
| 二十年消散 | 宝光消散，不必公开坐标 | 无 | `False` |

事件先产生事实结果；本阶段不为宝物另加 LLM 小故事。未来需要扩写时再以 `StoryEventService` 在基础事件之后追加 `is_story=True` 正文。

## 5. 动作与取宝结算

### 5.1 参数与可开始条件

新增 `src/classes/action/take_treasure.py`：

```python
class TakeTreasure(InstantAction):
    ACTION_NAME_ID = "take_treasure_action_name"
    DESC_ID = "take_treasure_description"
    REQUIREMENTS_ID = "take_treasure_requirements"
    EMOJI = "..."
    PARAMS = {"poi_id": "poi_id"}
    PARAM_OPTION_SOURCES = {
        "poi_id": ParamOptionSource.KNOWN_TREASURE_POI_ID,
    }
    IS_MAJOR = True
```

`EMOJI` 沿用现有动作展示惯例，具体值在实现时选择一个已有兼容符号。动作需要在 `src/classes/action/__init__.py` 导入，确保动作注册生效。

新增 `ParamOptionSource.KNOWN_TREASURE_POI_ID`，实现为：

```python
_known_poi_options(avatar, kind="treasure")
```

选项的 `value` 必须是 POI ID，不能是名称，且要补可执行性测试。

`can_start(poi_id)` 必须依次校验：

1. POI 存在且 `isinstance(poi, TreasurePOI)`。
2. POI 未到期。
3. 当前角色已发现该 POI。
4. `treasure_payload` 尚存在。
5. 当前角色坐标与 POI 坐标完全一致。

`can_possibly_start()` 只有在当前格存在已发现、有效且仍有 payload 的宝物时才返回 `True`。

### 5.2 成功率

取宝只由取宝者与宝物的大境界差决定：

```python
success_rate = clamp(
    0.45 + (taker_realm_rank - treasure_realm_rank) * 0.15,
    minimum=0.05,
    maximum=0.95,
)
```

| 大境界差 | 成功率 |
|---:|---:|
| 低两阶或更多 | 5% |
| 低一阶 | 30% |
| 相同 | 45% |
| 高一阶 | 60% |
| 高两阶 | 75% |
| 高四阶或更多 | 95% |

实现时将 `DigGrave` 内部的境界 rank 映射提取为共享 helper，避免两份硬编码。宝物没有练气等级，但练气角色允许尝试筑基宝物。

禁止将以下因素加入取宝概率：当前 HP、伤势、感知、气运、性格、宗门、装备品质、同格角色数量或之前失败次数。

### 5.3 失败与反震

每次 `TakeTreasure.step()` 都将 `attempt_count += 1`。

若随机判定失败：

1. POI 与 payload 保留。
2. 不发任何物品或材料。
3. 按 `world.treasure.backlash_probability` 小概率触发禁制反震。
4. 反震伤害为当前最大 HP 的配置比例，最少 `1` 点。
5. 伤害致死时必须走正常死亡结算，不直接绕过 `handle_death()`。
6. 产生仅关联尝试者的非重大事件。

本动作不复用掘墓的气运扣除规则。

### 5.4 成功与装备交换

成功后：

1. 从 `treasure_payload` 恢复一个独立装备实例。
2. 根据 payload `kind` 构造 `ItemExchangeKind.WEAPON` 或 `ItemExchangeKind.AUXILIARY`。
3. 调用既有 `resolve_item_exchange()`，使 LLM、规则 fallback 与角色扮演 continuation 仍走同一决策框架。
4. 只有角色实际接受新装备时，才 `poi_manager.remove(treasure.id)`。
5. POI 删除自动产生现有 `poi_updates` remove 增量。
6. 写入取宝成功重大事件。

空装备栏时沿用 `auto_accept_when_empty=True`。已有装备时，角色可以接受替换或拒绝。

### 5.5 “拒绝后保留在原处”交换语义

现有 `RejectMode.ABANDON_NEW` 的叙事是放弃新物品，不能准确表达宝物仍在 POI 的规则。应在 `src/systems/single_choice/item_exchange.py` 增加通用语义：

```python
class RejectMode(Enum):
    ABANDON_NEW = "abandon_new"
    SELL_NEW = "sell_new"
    LEAVE_AT_SOURCE = "leave_at_source"

class ItemDisposition(Enum):
    ...
    LEFT_AT_SOURCE = "left_at_source"
```

`TakeTreasure` 使用 `LEAVE_AT_SOURCE`。拒绝选项文案应表达“暂不取用，宝物仍留在原处”；动作根据 `outcome.accepted` 决定是否删除 POI。该设计保持 `single_choice` 的领域中立性，既不让 POI 逻辑侵入决策引擎，也不把角色扮演分支散落到业务动作中。

## 6. API 与前端

### 6.1 已有 API 复用

无需新增宝物专用 HTTP endpoint：

| 现有接口或机制 | 宝物接入方式 |
|---|---|
| `/api/v1/query/world/map` | 复用 `poi.get_summary_payload()` 返回全部有效宝物 |
| tick WebSocket `poi_updates` | `POIManager.add/remove()` 自动 upsert/remove |
| `/api/v1/query/detail?type=poi&id=...` | `TreasurePOI.get_detail_payload(world)` 返回宝物详情 |
| `MoveToPOI` | 已有通用 POI 移动动作，无需改语义 |

地图公开显示所有有效 POI 是已确认产品决策；不得为宝物在 `get_world_map()` 中按发现者过滤。

### 6.2 DTO

先更新 `web/src/types/api.ts`，再更新 `web/src/types/core.ts` 与 mapper。`POIDetail` 应增加宝物可选详情：

```ts
treasure?: {
  source: string
  realm: string
  item: {
    kind: 'weapon' | 'auxiliary'
    item_id: number
    name: string
    realm: string
  } | null
  attempt_count: number
  expires_month: number
}
```

不使用 `any`，不在前端写死后端提供的用户可见来源或境界 label。若来源需要本地化，应由后端提供稳定 key 和本地化结构化 DTO，或前端按 i18n key 映射。

### 6.3 地图图标与详情

已生成并验收的资产：

```text
web/src/assets/icons/pois/
  treasure_01.png
  treasure_02.png
  treasure_03.png
  treasure_04.png
  treasure_05.png
  treasure_06.png
  treasure_07.png
  treasure_08.png
  treasure_09.png
```

实现时：

1. 在 `web/src/utils/poiIcons.ts` 显式导入并注册上述 9 个 key。
2. `TreasurePOI.icon_key` 在创建时从这 9 个 key 中随机选择并随存档保存。
3. `POILayer.vue` 复用已有纹理加载和点击事件，无需按宝物重写图层。
4. 现有墓碑点击仍跳转死者 Avatar detail；宝物保持普通 `type: 'poi'`，打开 `POIDetail.vue`。
5. `POIDetail.vue` 以 `data.kind` 分支：墓碑展示死者/遗物，宝物展示来源、境界、物品、尝试次数和剩余期限。

图标生成工具为 `tools/item_icons/generate_treasure_icons.py`：它读取不入库的 `tools/img_gen/image_api.env` 中的 `FAL_API_KEY`，调用 `openai/gpt-image-2` 生成洋红底 3x3 图集，经过切图、去背景、去溢色、像素化后写入以上资产目录。密钥不得进入 git、日志、测试断言或前端包。

### 6.4 i18n

日常开发遵守 i18n Phase 1，只补 `zh-CN` 拆分源 PO 文件；修改后运行 `python tools/i18n/build_mo.py`。

至少新增：

```text
take_treasure_action_name
take_treasure_description
take_treasure_requirements
poi.treasure.title_short
poi.treasure.source
poi.treasure.realm
poi.treasure.item
poi.treasure.attempt_count
poi.treasure.expires
poi.treasure.empty
```

`.po` 的 `msgid` 使用稳定英文 key 或英文源文，中文只写入 `msgstr`。事件文本、动作文本、来源文案不能直接在 Python 逻辑中硬编码中文最终文案。

## 7. 实施顺序

1. 完成 POI 共享装备 payload helper，并迁移墓碑调用。
2. 新增 `TreasurePOI`、POI loader 分发、序列化和 detail payload。
3. 新增 `TreasureService`、配置与 `treasure_lifecycle` 月度相位。
4. 扩展发现事件文案和精确 240 月消散事件。
5. 新增 `KNOWN_TREASURE_POI_ID` 和 `TakeTreasure` 动作，并在 action 包导入注册。
6. 为 item exchange 加入 `LEAVE_AT_SOURCE`，让拒绝不消耗宝物。
7. 扩展 map/detail DTO、mapper、图标映射和 POI detail 展示。
8. 补后端与前端测试，运行针对性回归、类型检查和 locale 编译。

该顺序先完成后端事实与存档，再接行动决策和显示，避免前端先依赖临时 DTO 或尚未持久化的状态。

## 8. 测试与验收

### 8.1 后端

1. `TreasurePOI.to_save_dict/from_save_dict` 保留所有字段、payload、来源、发现者、图标和尝试次数。
2. `POIManager.load_from_list()` 同时恢复墓碑和宝物。
3. 旧存档未含 `pois` 或不含宝物时可正常加载。
4. 生成只会选择筑基、金丹、元婴武器或辅助装备，永不产生练气宝物。
5. 活跃宝物达到 3 个时不再生成。
6. 生成位置始终有效且不与已有宝物同格。
7. 出世事件公开等级但不含坐标。
8. POI 在观察范围内必定发现，范围外不发现。
9. `MoveToPOI` 与 `TakeTreasure` 的参数 value 都是可执行 POI ID。
10. 未发现、过期、非宝物、不同格、payload 为空时，`TakeTreasure.can_start()` 必须拒绝。
11. 成功率覆盖低阶、同阶、高阶和 5%/95% 边界，且不读取 HP、伤势、气运等无关字段。
12. 失败保留 POI 与 payload；反震只影响 HP，且伤害致死走正常死亡入口。
13. 成功接受后更新角色装备、移除整个 POI、产生 major event 与 remove 增量。
14. 成功但拒绝后 POI/payload 仍在，且返回 `LEFT_AT_SOURCE`。
15. 第 240 个月恰好移除宝物并产生消散事件，不等到年度维护。

### 8.2 前端

1. `treasure_01` 至 `treasure_09` 全部在 `POI_ICON_URLS` 注册。
2. 图标缺失时仍走 `fallback_poi`。
3. Map DTO、mapper 和 map store 可接收宝物 summary/upsert/remove。
4. `POILayer` 正确加载并点击宝物图标。
5. 宝物点击打开 POI detail，不触发墓碑专用的死者跳转。
6. 宝物详情展示来源、境界、装备、尝试次数与到期信息；墓碑详情不回归。
7. `npm run type-check` 通过，不引入 `any`。

### 8.3 建议命令

```powershell
& 'C:\Users\wangx\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/test_grave_poi.py tests/test_action_poi.py
cd web
npm run test -- poiIcons
npm run type-check
```

实现中新增宝物测试后，应将对应测试路径加入第一条 pytest 命令。若改动 i18n 源文件，还需执行：

```powershell
& 'C:\Users\wangx\AppData\Local\Programs\Python\Python312\python.exe' tools/i18n/build_mo.py
```
