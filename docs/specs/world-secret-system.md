# 世界秘密系统设计说明

本文档描述“世界秘密”系统的一期设计。世界秘密是一局游戏中独立于地图预设的隐藏主线：开局选择一个秘密，系统把该秘密拆成若干碎片并在本局随机绑定触发来源；不同角色各自发现碎片，若某角色集齐全部碎片，则知晓完整秘密，并在一次性选择中决定是否公开。

当前设计目标是先把核心体验做稳：一局只启用一个世界秘密；碎片由被动事件发现；角色知识彼此独立；玩家通过 TopBar 以默认上帝视角查看全貌；角色 AI 只知道自己实际掌握的信息。

## 1. 目标

世界秘密系统希望表达一种长期主线感：

1. 世界背后存在一个预设真相。
2. 真相不是直接通过任务发布，而是由多个碎片从不同角度逐渐还原。
3. 碎片不绑定具体地图预设；静态内容独立于地图。
4. 每局开局时，系统把碎片随机落到当前地图的地点、城市或低概率感悟触发中。
5. 每个角色维护自己的秘密知识，不共享。
6. 角色集齐全部碎片后获得完整秘密。
7. 集齐者立刻通过有限选择决定是否公开；非扮演角色由 LLM 决策，扮演角色交给玩家选择。
8. 公开后完整秘密成为天下共识；所有当前和后续新觉醒/新出生修士默认知道完整秘密。

## 2. 与现有系统的边界

### 2.1 与 world_lore 的区别

`world_lore` 是开局世界观塑形输入，主要用于改写地图、宗门、物品等静态对象。它是“开局塑形”系统。

世界秘密是运行中的主线线索进度系统，保存角色个人知识、碎片发现、完整秘密知晓与公开状态。它是“本局进度”系统。

因此世界秘密不应塞进 `src/classes/world_lore.py` 或 `world_lore_snapshot`。两者可在同一局并行存在，但一期彼此独立。

### 2.2 与 random_minor_event 的区别

随机小事件是一次性日常叙事，事件发生后没有长期主线进度。

世界秘密有长期状态：

- 本局 active secret；
- 碎片触发绑定；
- 每个角色已知碎片；
- 每个角色是否知晓完整秘密；
- 是否已公开天下。

因此事件只记录发现事实，不是真源；真源必须保存在 `World` 与 `Avatar` 状态中。

### 2.3 与 opportunity 的区别

机缘是单角色限时感应，角色可通过移动接近目标后结算。

世界秘密不是任务、机缘或行动目标：

- 不新增主动探听 action。
- 城市探听是被动事件。
- 地点知悉是被动事件。
- 神秘感悟是低概率被动事件。
- 角色是否因已知碎片而改变行动，交给 AI 决策。

## 3. 非目标

一期明确不做以下内容：

1. 不做多世界秘密同时启用。
2. 不新增主动探听、调查、追寻秘密 action。
3. 不做点对点主动告知他人。
4. 不公开碎片绑定的具体地点或城市给前端玩家。
5. 不让世界秘密产生数值或世界规则后果。
6. 不把完整秘密注入所有角色 AI 上下文。
7. 不做正式多语言补全；一期只维护中文内容。
8. 不把世界秘密作为 `world_lore` 的一部分参与地图或宗门改写。

## 4. 开局选择

开局配置新增 `world_secret_id`，属于 `RunConfig` / `NewGameDefaults`。

可选值：

- `none`：无世界秘密。
- `random`：从非 `none` 预设中按权重随机选择一个。
- 具体秘密 ID：启用对应世界秘密。

前端开局下拉框显示具体标题，选项包含：

- 无
- 随机
- 所有预设秘密标题

`none` 应作为真实配置项存在，而不是仅靠特殊逻辑。这样前后端选择列表、存档与查询都能统一处���。

一局只允许一个 active world secret。后续若要扩展多秘密，应另起版本设计。

## 5. 静态配置

建议新增两张 CSV：

```text
static/game_configs/world_secret.csv
static/game_configs/world_secret_fragment.csv
```

### 5.1 `world_secret.csv`

推荐字段：

```csv
id,title,secret,weight
ID,标题,完整秘密,随机权重
none,无,,0
fake_sky,本世界的天空是虚假的,天空并非自然天穹，而是一层巨大伪装屏障；日月星辰只是投影，真正的世界被封闭在某个容器或牢笼之中。,10
```

说明：

- `id` 使用英文 snake_case，作为稳定 ID。
- `title` 面向玩家上帝视角展示。
- `secret` 是完整秘密正文。
- `weight` 用于 `random` 开局选择。
- `none` 的 `secret` 为空，碎片数为 0，权重为 0。

### 5.2 `world_secret_fragment.csv`

推荐字段：

```csv
id,secret_id,order,angle,text,trigger_kind
ID,秘密ID,顺序,碎片角度,碎片文本,触发类型
fake_sky_1,fake_sky,1,天象异常,天空有时会在极短瞬间闪烁，星辰的位置会出现不合天象规律的错位。,region
fake_sky_2,fake_sky,2,飞升边界,高阶修士冲击飞升时，并非无法抵达天外，而是在某个高度撞上一层不可见壁障。,insight
```

说明：

- 碎片数量不固定。
- 当前预设可大多保持 6 个碎片，但系统不写死 6。
- `angle` 用来保证碎片从不同角度组织真相，不退化成随机怪谈。
- `trigger_kind` 一期只允许：
  - `region`
  - `city`
  - `insight`

## 6. 预设内容

一期直接使用需求中给出的这批预设。标题基本保留原文，ID 使用英文 snake_case。

建议 ID：

- `upper_world_feeds_on_ascenders`：上界大能以飞升修士为血食
- `fake_sky`：本世界的天空是虚假的
- `mad_heavenly_dao`：天道意志疯了
- `simulated_world_code`：世界是计算机中的一组模拟代码
- `spiritual_qi_is_dead_memories`：灵气其实是死者的记忆
- `sects_on_colossal_corpses`：所有宗门都建在巨兽尸体上
- `reincarnation_is_copying`：轮回并不存在，转世只是复制
- `yao_are_previous_humans`：妖族其实是上一纪元的人族
- `realms_are_artificial_shackles`：修炼境界是人为设置的枷锁
- `moon_is_an_eye`：月亮是一颗注视此界的眼睛
- `secret_realms_are_tumors`：秘境是世界长出的肿瘤
- `dead_gods_answer_prayers`：诸天神佛早已死亡，回应祈祷的是它们的尸体

文案可为配置落表做轻微结构整理，但不改变核���含义。

## 7. 运行时模型

建议新增：

```text
src/classes/world_secret.py
src/systems/world_secret.py
```

### 7.1 静态定义模型

建议领域模型：

```python
@dataclass
class WorldSecretFragment:
    id: str
    secret_id: str
    order: int
    angle: str
    text: str
    trigger_kind: str


@dataclass
class WorldSecretDefinition:
    id: str
    title: str
    secret: str
    weight: float
    fragments: list[WorldSecretFragment]
```

这些对象由 CSV loader 生成，不直接保存到存档。

### 7.2 世界运行时状态

建议挂在 `World` 上：

```python
world_secret: WorldSecretRuntime = field(default_factory=WorldSecretRuntime)
```

建议模型：

```python
@dataclass
class WorldSecretTriggerBinding:
    fragment_id: str
    trigger_kind: str
    region_id: int | None = None
    city_region_id: int | None = None


@dataclass
class WorldSecretRuntime:
    selected_secret_id: str = "none"
    trigger_bindings: dict[str, WorldSecretTriggerBinding] = field(default_factory=dict)
    resolved_by_avatar_ids: set[str] = field(default_factory=set)
    disclosure_decisions: dict[str, str] = field(default_factory=dict)
    public_revealed: bool = False
    public_revealed_month: int | None = None
    public_revealed_by_avatar_id: str | None = None
```

说明：

- `selected_secret_id = "none"` 表示无秘密。
- `trigger_bindings` 是本局随机绑定结果，必须存档。
- `resolved_by_avatar_ids` 记录历史上集齐过秘密的角色。
- `disclosure_decisions` 记录集齐者的一次性公开/沉默选择。
- `public_revealed` 为真后，所有角色默认知道完整秘密。

### 7.3 角色个人知识

建议挂在 `Avatar` 上：

```python
world_secret_knowledge: dict[str, AvatarWorldSecretKnowledge]
```

建议模型：

```python
@dataclass
class AvatarWorldSecretKnowledge:
    secret_id: str
    known_fragment_ids: set[str] = field(default_factory=set)
    knows_full_secret: bool = False
    full_secret_month: int | None = None
```

如果一期只启用一个秘密，也仍建议按 `secret_id` 映射保存，避免后续扩展返工。

## 8. 本局初始化

开局初始化时机：地图已加载、`World` 已创建后，NPC 初始化前后均可；若要让初始角色立刻受到公开状态影响，建议在角色创建后统一调用一次知识同步。

推荐流程：

1. 读取 `run_config.world_secret_id`。
2. 若为 `none`：
   - `world.world_secret.selected_secret_id = "none"`；
   - `trigger_bindings = {}`；
   - 不触发后续逻辑。
3. 若为 `random`：
   - 从非 `none` 秘密中按 `weight` 随机选择。
4. 若为具体 ID：
   - 启用对应秘密。
5. 为每个 fragment 建立 trigger binding：
   - `region`：随机绑定一个非荒野、非城市 region。
   - `city`：随机绑定一个城市 region。
   - `insight`：不绑定地点。
6. 绑定结果进入 `world.world_secret.trigger_bindings`。

`region` 允许绑定普通区域、洞府/遗迹、宗门驻地等非城市 region。宗门驻地可能让某些线索被宗门成员更容易接触，这是允许的叙事效果。

## 9. 被动触发

世界秘密发现是被动事件，不新增主动 action。

建议新增 phase：

```python
phase_world_secret_discovery(world, living_avatars)
```

接入位置建议在动作执行后、普通世界事件/机缘检测附近，使角色当月移动到目标区域后即可触发。

### 9.1 地点知悉

条件：

1. 本局 active secret 不是 `none`。
2. fragment 的 `trigger_kind == "region"`。
3. 角色当前 `avatar.tile.region.id == binding.region_id`。
4. 角色尚未知道该 fragment。
5. 概率命中。

事件：

- 生成普通事件。
- 事件文本可包含碎片文本。
- `related_avatars=[avatar.id]`。
- `is_major=False`。
- `is_story=False`。

### 9.2 城市探听

城市探听是被动事件，不存在主动探听 action。

条件：

1. fragment 的 `trigger_kind == "city"`。
2. 角色当前位于绑定城市内，即 `avatar.tile.region.id == binding.city_region_id`。
3. 角色尚未知道该 fragment。
4. 概率命中。

事件可写：

```text
某某在某城的坊市流言中听闻一段隐秘线索：……
```

### 9.3 神秘感悟

条件：

1. fragment 的 `trigger_kind == "insight"`。
2. 角色可以触发世界事件。
3. 角色尚未知道该 fragment。
4. 低概率命中。

事件可写：

```text
某某于冥冥感悟中窥见一角真相：……
```

### 9.4 概率节奏

需求目标为“中速”。具体概率由实现时定，建议量级：

- 地点知悉：每角色每月约 `0.04`。
- 城市探听：每角色每月约 `0.05`。
- 神秘感悟：每角色每月约 `0.003`。

这些值可先作为静态平衡配置，后续按体验调参。

同一角色同月允许获得多个碎片。若多个触发同时命中，按命中结果全部记录和产出事件。

## 10. 集齐与完整秘密

当某角色已知 fragment 覆盖 active secret 的所有 fragment 时：

1. 设置该角色 `knows_full_secret=True`。
2. 设置 `full_secret_month=int(world.month_stamp)`。
3. 记录 `world.world_secret.resolved_by_avatar_ids.add(avatar.id)`。
4. 生成重大事件，表示该角色知晓了某个世界秘密。
5. 立刻触发公开/沉默选择。

集齐事件不写完整秘密正文，避免与“是否公开”语义冲突。

推荐事件：

```text
某某将零散线索连成一线，终于知晓了一桩足以动摇此界根基的世界秘密。
```

注意：事件不包含 title，也不包含完整 secret。TopBar 上帝视角可以展示完整信息，但世界事件流仍按角色视角保留悬念。

## 11. 公开/沉默选择

每个集齐者只有一次选择：

- `share_all`
- `keep_secret`

### 11.1 决策来源

默认由 avatar 走 LLM 决策。

若集齐者正是当前扮演模式中的受控角色，则走现有 `single_choice` / roleplay choice，由玩家选择。

若玩家正在扮演 A，但 B 集齐秘密，则 B 仍由 LLM 自动决策。

### 11.2 LLM 失败 fallback

若 LLM 决策失败或返回无效选项，fallback 默认为 `keep_secret`。

理由：

- 避免由于模型失败无意间把秘密公开天下；
- 沉默是副作用更小的默认选择。

### 11.3 公开

若选择 `share_all`：

1. `world.world_secret.public_revealed=True`。
2. 记录公开时间与公开者。
3. 所有当前在世角色默认知道完整秘密。
4. 后续新出生 / 新觉醒修士默认知道完整秘密。
5. 不需要给所有角色补齐碎片。

公开后事件可写完整秘密标题，但是否写完整正文仍应谨慎。推荐事件只写标题和公开事实，不写长正文：

```text
某某将一桩世界秘密公之于众：「本世界的天空是虚假的」。此后天下修士皆知此界真相。
```

完整秘密正文仍主要通过 TopBar 世界秘密面板展示。

### 11.4 沉默

若选择 `keep_secret`：

1. 只记录 `disclosure_decisions[avatar.id] = "keep_secret"`。
2. 不传播给其他角色。
3. 生成普通或重大事件均可；建议普通事件。

推荐事件：

```text
某某知晓真相后选择沉默，只将这桩秘密压在心底。
```

## 12. 信息边界

本系统必须严格区分三类视角。

### 12.1 玩家 TopBar 上帝视角

玩家默认上帝视角全公开。

TopBar 世界秘密面板从开局起可展示：

- 当前秘密 title；
- 完整 secret；
- 所有 fragment；
- 每个 fragment 被哪些角色知道；
- 每个角色已知碎片数；
- 哪些角色已知完整秘密；
- 是否已公开；
- 公开者与公开时间。

但 TopBar 不公开 fragment 绑定的具体地点或城市。

### 12.2 事件流

事件流可出现碎片文本。

事件流不应在角色集齐前直接写完整秘密正文。集齐事件也不写完整 secret。

若公开天下，事件可写 title 和公开事实；完整正文仍不必写入普通事件，以免事件栏过长。

### 12.3 Avatar AI / 决策上下文

这是最关键的边界。

角色 AI 只能看到自己实际知道的信息：

- 已知 fragment 文本；
- 若自己已知完整秘密，看到完整 secret；
- 若世界已公开，看到完整 secret；
- 不知道完整秘密时，不能看到 title；
- 不知道完整秘密时，不能看到 secret；
- 不知道完整秘密时，不能看到未发现 fragment；
- 不能看到 fragment 绑定地点或城市。

原因：title 本身常常就是答案，例如“本世界的天空是虚假的”。如果在角色只知道碎片时把 title 放进 avatar info，就等于直接透题，破坏碎片推理语义。

因此 avatar info 中的字段不应叫 `active_secret_title`。推荐结构：

```json
"world_secret_knowledge": {
  "known_fragments": [
    {
      "angle": "天象异常",
      "text": "天空有时会在极短瞬间闪烁，星辰的位置会��现不合天象规律的错位。"
    }
  ],
  "knows_full_secret": false,
  "full_secret": ""
}
```

若角色已知完整秘密或世界已公开：

```json
"world_secret_knowledge": {
  "known_fragments": [
    {
      "angle": "天象异常",
      "text": "天空有时会在极短瞬间闪烁，星辰的位置会出现不合天象规律的错位。"
    }
  ],
  "knows_full_secret": true,
  "secret_title": "本世界的天空是虚假的",
  "full_secret": "天空并非自然天穹，而是一层巨大伪装屏障；日月星辰只是投影，真正的世界被封闭在某个容器或牢笼之中。"
}
```

公开后不需要给角色补齐所有碎片；AI 上下文只需要完整 secret 和其实际发现过的 fragment。

## 13. AI 决策接入

角色已知碎片应进入 avatar info，并在决策时可见。

推荐只在详细信息中加入，例如：

- `avatar.get_expanded_info(detailed=True)`
- 或 AI 决策上下文组装层

不建议在轻量 `get_info()` 中塞入大量碎片文本，以免列表、详情和 prompt 体积失控。

不知道完整秘密时，AI 只能基于碎片自行联想和决策；系统不硬编码具体行为。

知道完整秘密后，AI 可在思考、目标、行动选择中自行反应。系统一期不提供数值后果。

## 14. 查询 API

建议新增只读接口：

```text
GET /api/v1/query/meta/world-secrets
GET /api/v1/query/world-secrets/overview
```

### 14.1 `meta/world-secrets`

用于开局下拉框。

返回示例：

```json
{
  "secrets": [
    {"id": "none", "title": "无"},
    {"id": "random", "title": "随机"},
    {"id": "fake_sky", "title": "本世界的天空是虚假的"}
  ]
}
```

### 14.2 `world-secrets/overview`

用于 TopBar 面板，上帝视角全公开，但不公开触发地点。

返回示例：

```json
{
  "active_secret": {
    "id": "fake_sky",
    "title": "本世界的天空是虚假的",
    "secret": "天空并非自然天穹，而是一层巨大伪装屏障；日月星辰只是投影，真正的世界被封闭在某个容器或牢笼之中。",
    "fragment_count": 6
  },
  "public_revealed": false,
  "public_revealed_by": null,
  "fragments": [
    {
      "id": "fake_sky_1",
      "order": 1,
      "angle": "天象异常",
      "text": "天空有时会在极短瞬间闪烁，星辰的位置会出现不合天象规律的错位。",
      "known_by": [
        {"id": "avatar_1", "name": "李青", "is_dead": false}
      ]
    }
  ],
  "avatars": [
    {
      "id": "avatar_1",
      "name": "李青",
      "known_fragment_count": 1,
      "fragment_count": 6,
      "knows_full_secret": false,
      "decision": null,
      "is_dead": false
    }
  ]
}
```

`none` 返回可为：

```json
{
  "active_secret": {
    "id": "none",
    "title": "无",
    "secret": "",
    "fragment_count": 0
  },
  "public_revealed": false,
  "fragments": [],
  "avatars": []
}
```

## 15. 前端

TopBar 始终显示世界秘密栏位。

若当前为 `none`，标签可显示“世界秘密：无”或点击后面板显示“本局未启用世界秘密”。

建议新增：

```text
web/src/stores/worldSecret.ts
web/src/components/game/panels/WorldSecretModal.vue
web/src/composables/useWorldSecretModal.ts
```

接入位置：

- `web/src/components/layout/StatusBar.vue`
- `web/src/components/layout/StatusBarPanels.vue`
- `web/src/api/modules/world.ts`
- `web/src/api/mappers/worldSecret.ts` 或并入现有 world mapper
- `web/src/types/api.ts`

弹窗展示建议：

1. 摘要区：当前秘密标题、完整秘密、公开状态。
2. 碎片区：按 `order` 展示 `angle` 与 `text`，列出���知角色。
3. 角色区：每个角色已知进度、是否知晓完整秘密、是否已做公开/沉默选择。

不要在面板中显示碎片绑定的 region/city。

## 16. 存档结构

世界级状态进入 `world_data`：

```json
"world_secret": {
  "selected_secret_id": "fake_sky",
  "trigger_bindings": {
    "fake_sky_1": {
      "fragment_id": "fake_sky_1",
      "trigger_kind": "region",
      "region_id": 101,
      "city_region_id": null
    }
  },
  "resolved_by_avatar_ids": ["avatar_1"],
  "disclosure_decisions": {
    "avatar_1": "keep_secret"
  },
  "public_revealed": false,
  "public_revealed_month": null,
  "public_revealed_by_avatar_id": null
}
```

角色级知识进入 avatar save dict：

```json
"world_secret_knowledge": {
  "fake_sky": {
    "known_fragment_ids": ["fake_sky_1"],
    "knows_full_secret": false,
    "full_secret_month": null
  }
}
```

开发阶段不要求为旧存档付出复杂兼容成本；读档时用 `.get` 零成本兜底即可。

## 17. 新角色同步

当 `world.world_secret.public_revealed=True` 时：

1. 当前所有在世角色默认知道完整秘密。
2. 后续新出生 / 新觉醒修士创建后也默认知道完整秘密。
3. 不需要补齐碎片。

建议提供统一 helper：

```python
sync_avatar_public_world_secret_knowledge(world, avatar)
```

在新角色创建、读档后重建、公开天下后批量调用。

## 18. 事件语义

### 18.1 碎片发现事件

- `is_major=False`
- `is_story=False`
- `related_avatars=[avatar.id]`
- 可包含碎片文本

### 18.2 集齐事件

- `is_major=True`
- `is_story=False`
- `related_avatars=[avatar.id]`
- 不包含 title
- 不包含完整 secret

### 18.3 公开事件

- `is_major=True`
- `is_story=False`
- `related_avatars=[avatar.id]`
- 可包含 title
- 推荐不包含完整 secret 正文

### 18.4 沉默事件

- 可为 `is_major=False`
- `is_story=False`
- `related_avatars=[avatar.id]`
- 不包含完整 secret

## 19. i18n

一期只维护中文。

由于世界秘密正文和碎片是大量中文叙事内容，第一版可直接放入共享 CSV，前端中文文案补 `zh-CN`。不做正式多语言补全。

若未来进入 Phase 2：

1. 语言列表以 `static/locales/registry.json` 为准。
2. 配置文本迁移到 `game_configs_modules` 或本地化 CSV。
3. `.po` 中 `msgid` 不得直接写中文。
4. 不直接改 `LC_MESSAGES/*.po` 合并产物。
5. 改完源文件后运行 `python tools/i18n/build_mo.py`。

## 20. 推荐实现位置

建议后续实现时新增独立模块，避免把逻辑堆入 `main.py`、`world_lore` 或随机事件系统。

可能位置：

- `src/classes/world_secret.py`
- `src/systems/world_secret.py`
- `src/systems/world_secret_loader.py`
- `src/systems/world_secret_service.py`

接入点：

- `src/config/settings_schema.py`：新增 `world_secret_id`
- `src/server/init_flow.py`：初始化本局 secret 与 bindings
- `src/classes/core/world.py`：挂载 runtime
- `src/classes/core/avatar/core.py`：挂载个人知识
- `src/sim/save/save_game.py`：保存 world secret
- `src/sim/load/load_game.py`：恢复 world secret
- `src/sim/save/avatar_save_mixin.py`：保存 avatar secret knowledge
- `src/sim/load/avatar_load_mixin.py`：恢复 avatar secret knowledge
- `src/sim/simulator_engine/phases/world.py`：新增被动发现 phase
- `src/sim/simulator_engine/simulator.py`：接入 phase
- `src/server/services/game_query_service.py`：新增查询组装
- `src/server/api/public_v1/query.py`：新增 v1 query 路由

## 21. 测试建议

至少覆盖：

1. CSV loader 能加载 `none` 与所有预设。
2. 每个非 `none` 秘密有至少一个碎片。
3. 每个 fragment 的 `secret_id` 都存在。
4. 同一秘密下 fragment `order` 不重复。
5. `trigger_kind` 只允许 `region/city/insight`。
6. `random` 不会选中 `none`。
7. `none` 初始化时不生成 trigger bindings。
8. 具体 secret 初始化后，每个非 insight fragment 有合法绑定。
9. `region` 绑定不选择城市，不选择荒野。
10. `city` 绑定只选择城市。
11. 角色在绑定 region 内概率命中时获得 fragment。
12. 角色在绑定 city 内概率命中时获得 fragment。
13. insight 概率命中时获得 fragment。
14. 已知 fragment 不重复获得。
15. 同一角色同月可获得多个命中的 fragment。
16. 集齐全部 fragment 后 `knows_full_secret=True`。
17. 集齐事件不包含 title 和完整 secret。
18. LLM 选择 `share_all` 后 world public revealed，并让当前所有在世角色知道完整 secret。
19. LLM 失败 fallback 为 `keep_secret`。
20. 扮演角色集齐时走 roleplay choice；非扮演角色仍走 LLM。
21. 公开后新觉醒角色默认知道完整 secret。
22. 公开后不强制补齐所有 fragment。
23. avatar AI context 未知完整秘密时只含 known fragments，不含 title/secret/未发现 fragments/绑定地点。
24. avatar AI context 已知完整秘密时可含 title 与 full secret。
25. TopBar overview 全公开 title/secret/fragments，但不公开绑定地点。
26. world secret 与 avatar knowledge 可保存和读档恢复。
27. `/api/v1/query/meta/world-secrets` 返回 `none/random/具体秘密`。
28. `/api/v1/query/world-secrets/overview` 在 `none` 时返回稳定空态。
29. 前端 lazy modal 初始 `show=true` 时会请求数据，watcher 使用 `{ immediate: true }`。

## 22. 当前拍板结论

本轮需求确认后的最终结论：

1. 玩家 TopBar 是默认上帝视角，全公开完整秘密和碎片。
2. 开局下拉框显示具体标题。
3. `none` 是真实配置项。
4. 一局只允许一个世界秘密。
5. 碎片数量不固定。
6. 每个碎片配置 `trigger_kind`。
7. `region` 绑定非城市 region，允许宗门驻地。
8. 城市探听必须位于对应城市内，且是被动事件。
9. 触发节奏为中速，具体概率由实现调参。
10. 同一角色同月可以获得多个碎片。
11. 碎片进入 avatar 决策信息，但未知完整秘密时不提供 title，避免透题。
12. 碎片文本可以出现在事件流。
13. 集齐后立刻选择公开/沉默。
14. 非扮演角色由 LLM 选择；只有集齐者正被玩家扮演时才交给玩家。
15. 公开只给完整秘密，不补齐碎片。
16. 公开后后续新觉醒/新出生修士默认知道完整秘密。
17. 世界秘密无数值后果。
18. 一期只中文。
19. 世界秘密独立于 `world_lore`。
20. 预设内容使用需求中给出的原始批次，标题基本保留原文。
