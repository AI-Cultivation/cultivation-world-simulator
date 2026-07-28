# 规则模拟测试模式设计说明

## 1. 背景

游戏的大量初始化和模拟行为会通过 LLM 生成决策、文本或结构化结果。日常运行应继续使用已配置的 LLM；但在功能开发、集成验证、演示与回归测试中，需要一种可完整启动世界并持续运行、但绝不访问 LLM 服务的模式。

本设计定义“规则模拟测试模式”（下文简称“测试模式”）。它不是单元测试框架中的 mock，也不是 LLM 配置失效后的错误降级，而是玩家在开局时选择的一种**单局运行语义**：本局所有 LLM 依赖点都必须由确定性的内置规则替代，或以明确的“不支持”结果结束，绝不可访问真实 LLM 网络端点。

## 2. 目标

1. 允许用户在“开始游戏”面板开启测试模式，默认关闭。
2. 测试模式下不读取 API Key 以发起请求、不进行 provider 连通性检测、不调用任何实际 LLM HTTP 接口。
3. 世界初始化和常规模拟循环可以完成，角色、动作、事件、宗门、存档和 WebSocket 等整体路径可用于集成验证。
4. 对每一种 LLM task 给出结构合法、确定性且业务可消费的规则结果，或显式声明该能力在测试模式不可用。
5. 测试模式是 `RunConfig` 的一部分，必须随世界快照和存档保存，并在读档后恢复。
6. 正常模式的调用链、LLM 配置和错误行为不因该功能发生语义变化。
7. 新增 LLM task 时，测试模式不得静默漏网并访问真实服务。

## 3. 非目标

1. 不试图用规则系统复刻 LLM 的创作质量、叙事多样性或策略能力。
2. 不把测试模式做成全局、跨局的开关；同一进程中不同世界的语义不得互相污染。
3. 不把 LLM 请求失败自动视为测试模式，也不改变正式模式下既有的异常与降级逻辑。
4. 不为测试模式伪造“像真实生成内容”的自定义内容或自由对话文本。
5. 不要求测试模式下每一个可选玩法能力都可用；主动生成型功能可以明确拒绝。
6. 不引入第二套模拟器、第二套存档格式或第二套角色决策系统。

## 4. 术语与不变量

### 4.1 `test_mode`

`test_mode: bool` 是 `RunConfig` 中的单局字段。`false` 表示正常模式，`true` 表示规则模拟测试模式。默认值必须为 `false`。

### 4.2 LLM task

LLM task 是调用 `call_llm_with_task_name(task_name, ...)` 时的稳定任务名，例如 `action_decision`、`relation_delta`、`story_teller`。

### 4.3 规则 fallback

规则 fallback 是测试模式中对一个明确 task 返回的、符合其业务解析契约的确定性结果。它不是基于异常捕获的临时空对象。

### 4.4 不变量

测试模式必须满足：

1. 任何到 provider 的网络函数都不得被调用。
2. 任何未知或未注册的 LLM task 都不得自动转向正常调用路径。
3. 一个 fallback 的返回形状必须能被调用者解析；不能用全局 `{}` 作为通用结果。
4. 测试模式状态必须来自当前 world 的 `run_config_snapshot` 或当前开局 `RunConfig`，不得使用模块级可变全局开关。
5. 加载测试模式存档后仍为测试模式；加载正常存档后仍为正常模式。
6. 正常模式保留既有 API Key、重试、解析、错误通知与调用日志路径。

## 5. 用户体验

### 5.1 开局面板

文件：`web/src/components/game/panels/system/GameStartPanel.vue`

在常规开局参数靠后、开始按钮之前增加一个复选框。使用 Naive UI 的 `n-checkbox`，绑定 `settingStore.newGameDraft.test_mode`。

中文文案：

- 标签：`测试模式`
- 备注：`仅用于测试游戏功能和整体运行流程。开启后不会调用实际 LLM，AI 结果将由内置规则处理。`

要求：

1. 默认不选中。
2. 表单 `readonly` 时与其他开局参数一起禁用。
3. 备注必须可见，不能只放 tooltip。
4. 不在开始按钮、地图卡片或全局系统设置中隐藏该开关。
5. 当前 i18n 处于 Phase 1，第一期只维护 `zh-CN` 源文案；不直接编辑 `LC_MESSAGES` 合并产物。

### 5.2 开局与读档提示

第一期不要求游戏主界面常驻醒目标识，以免将测试功能误导为正式玩法模式。但 query API 必须可读出当前 `test_mode`，使前端、外部 agent 和测试工具能诊断当前局。

建议后续在运行状态或调试信息中以非错误状态显示：`LLM 模式：规则模拟测试`。该提示不应复用“LLM 连接失败”的错误 UI。

### 5.3 主动生成能力

以下主动请求 LLM 生成内容的功能在测试模式下必须返回明确、可本地化的受控错误，而不能假装生成成功：

1. 自定义内容生成。
2. 自定义金手指草案生成。
3. 角色扮演中的自由对话与对话总结。
4. 任何未来没有定义规则输出、且由用户显式发起的生成命令。

建议错误码：`TEST_MODE_LLM_UNAVAILABLE`。

## 6. 数据模型、API 与存档

### 6.1 配置模型

文件：`src/config/settings_schema.py`

在以下模型新增字段：

```python
test_mode: bool = False
```

- `NewGameDefaults`
- `NewGameDefaultsPatch`，类型为 `Optional[bool]`
- `RunConfig`，通过继承 `NewGameDefaults` 获得该字段

`test_mode` 的层级归属：

1. 它是本局运行语义，因此 `RunConfig` 是唯一运行时真源。
2. 它可作为下一局的开局默认值，因此同时属于 `new_game_defaults`。
3. 它不是 `LLMSettings`、`LLMProfile`、静态 `CONFIG` 或部署环境变量。
4. 开局后不得通过设置页修改当前局，只能新开局或读档改变。

### 6.2 前端 DTO 与 Store

文件：

- `web/src/types/api.ts`
- `web/src/stores/setting.ts`

`RunConfigDTO` 新增 `test_mode: boolean`。`newGameDraft` 初始值必须显式包含 `test_mode: false`，且 `applySettings()` 从 `settings.new_game_defaults` 恢复该字段。

`updateNewGameDraft()` 与 `startGameWithDraft()` 已以 `RunConfigDTO` 为载体；字段加入 DTO 后应自然进入：

```text
GET /api/settings
  -> settingStore.newGameDraft
  -> POST /api/settings (new_game_defaults)
  -> POST /api/v1/command/game/start
```

### 6.3 稳定 API 契约

下列现有接口的 `RunConfig` 结构必须包含 `test_mode`：

| 接口 | 语义 |
|---|---|
| `GET /api/settings` | 返回新开局默认值 |
| `PATCH /api/settings` | 保存下一局默认值 |
| `POST /api/v1/command/game/start` | 指定本局测试模式 |
| `GET /api/v1/query/system/current-run` | 查询当前局测试模式 |

接口不应新增一个独立的“切换测试模式” command。运行中切换会破坏存档语义、异步任务边界和可重复性。

### 6.4 存档与读档

当前 `world.run_config_snapshot` 已由初始化流程生成并经 `run_config` section 保存。实施时不新增平行存档 section：

```text
RunConfig(test_mode=True)
  -> runtime run_config
  -> world.run_config_snapshot
  -> save_data["run_config"]
  -> load context.run_config_snapshot
  -> loaded world.run_config_snapshot
```

读档不得回写用户的 `settings.json`。用户下次新开局的默认值与所读存档的 `test_mode` 可以不同。

## 7. 运行时测试模式传播

### 7.1 设计选择

LLM client 不能直接依赖某个全局 `game_instance`，也不能用模块级 `TEST_MODE` 可变变量。原因是：

1. LLM 调用点分布于初始化、模拟循环、服务命令和角色扮演。
2. 模拟器与 API mutation 都是异步流程。
3. 模块级布尔值会在重开、读档、并发测试或后续多会话支持中泄漏状态。

采用 `contextvars.ContextVar` 传递当前执行链的测试模式。

建议新增：`src/utils/llm/runtime_mode.py`。

```python
def is_test_mode_enabled() -> bool: ...

@contextmanager
def llm_test_mode_scope(enabled: bool): ...
```

内部 `ContextVar` 默认值为 `False`。scope 在退出时必须 reset token，保证异常、取消与嵌套调用后不会污染后续请求。

### 7.2 设置 scope 的边界

任何会执行 LLM 依赖逻辑的 world 入口，必须按当前局快照建立 scope：

1. `perform_game_initialization()`：由即将创建的 `RunConfig.test_mode` 建立整个初始化 scope。
2. `GameLoopRunner.run_once()`：在调用 `sim.step()` 的 mutation 内部，使用 `world.run_config_snapshot["test_mode"]` 建立 scope。
3. 与已加载 world 有关的 mutation command：在 service/runtime mutation 入口或各明确入口建立 scope。
4. 读取 world 的 roleplay、世界观和其他异步 task：根据目标 world 快照建立 scope。

`asyncio.create_task()` 会复制创建时的 context；因此初始化阶段创建的后台 task 也应在正确 scope 内创建。跨线程执行时不得假设 context 自动传播；若某个 LLM 相关业务通过 `asyncio.to_thread()` 间接进入调用链，必须显式验证其模式传播。

### 7.3 world helper

可提供只读 helper，避免散落字典读取：

```python
def is_world_test_mode(world: Any) -> bool:
    return bool((getattr(world, "run_config_snapshot", None) or {}).get("test_mode", False))
```

该 helper 只负责从 world 快照取值；不拥有状态，不修改配置。

## 8. LLM 网关与 fallback registry

### 8.1 统一拦截点

文件：`src/utils/llm/client.py`

`call_llm_with_task_name()` 是结构化任务的统一入口。测试模式下它必须在以下操作之前短路：

1. 读取模板。
2. 构造 prompt。
3. 读取 LLM profile/API Key。
4. 获取 semaphore。
5. 调用 provider。
6. 写入真实 LLM 调用日志。

逻辑：

```text
call_llm_with_task_name(task_name, template_path, infos)
  -> is_test_mode_enabled()?
       yes -> RuleLLMFallbackRegistry.resolve(task_name, infos)
       no  -> 现有 get_task_mode -> template -> call_llm_with_template 链路
```

不得仅在底层 `_call_with_requests()` 前拦截，因为那会让测试模式仍然加载 prompt、产生解析重试，并无法根据 `task_name` 给出合法结构。

`call_llm()` 和 `call_llm_json()` 的原始接口在测试模式下默认抛出 `TestModeUnsupportedLLMTask`；只有具有明确 task 名的调用才允许走规则 registry。若发现业务绕过 task-name 入口，应在本次实施中改为 task-name 入口，或显式为其增加受控规则接口。

### 8.2 模块结构

建议新增：`src/utils/llm/test_mode_fallbacks.py`。

```python
class TestModeLLMError(Exception): ...
class TestModeUnsupportedLLMTask(TestModeLLMError): ...

def resolve_test_mode_task(task_name: str, infos: Mapping[str, Any]) -> dict[str, Any]: ...
def registered_test_mode_tasks() -> frozenset[str]: ...
```

要求：

1. registry 以稳定 `task_name` 为 key。
2. fallback 函数必须是纯函数：不发网络请求、不读用户机密、不修改 world。
3. 返回值只包含调用方契约需要的字段。
4. 结果必须确定性。除非一个 task 的业务契约要求 seed 随机性，否则禁止使用未受控随机数。
5. 未注册 task 直接抛出 `TestModeUnsupportedLLMTask(task_name)`，绝不可调用真实 LLM。
6. 禁止实现“所有未知 task 返回 `{}`”的兜底。

### 8.3 注册任务清单与规则

本次实施必须覆盖当前仓库中的所有 `call_llm_with_task_name` task。每项 fallback 必须结合实际消费字段编写，并有对应单测。

| Task | 常见调用方 | 测试模式规则结果 |
|---|---|---|
| `action_decision` | `classes/ai.py`、角色扮演文本决策 | 返回可解析的空动作计划或由现有合法 fallback 生成的计划；不得返回不存在的 action ID |
| `backstory` | 角色初始背景 | `{"backstory": ""}`，调用方跳过背景写入 |
| `long_term_objective` | 初始角色目标 | `{"long_term_objective": ""}`，调用方跳过目标写入 |
| `nickname` | 称号 | `{"nickname": "", "thinking": "", "reason": ""}`，不授予称号 |
| `story_teller` | 小故事/采集故事 | `{"story": ""}`，事实事件保留，跳过故事扩写 |
| `relation_resolver` | 关系变化判断 | `{"changed": false}` |
| `relation_delta` | 双向关系数值 | `{"delta_a_to_b": 0, "delta_b_to_a": 0}` |
| `interaction_feedback` | 双人交互反馈 | 返回该调用方要求的“无额外影响”合法结构；实施前需按实际 parser 固化字段 |
| `single_choice` | 宗门招募、物品交换、世界秘密等 | 不直接猜选项；应由 `single_choice` 的现有 fallback policy 解析合法 key。必要时让 registry 返回显式 fallback 标记，由 resolver 选择合法项 |
| `sect_decider` | 年度宗门规划 | 返回调用方可解析的维持现状计划，不招募、不扩张、不进行资源转移 |
| `sect_thinker` | 宗门年度思考 | 返回空或固定的短说明，且不改变决策结果 |
| `fate_revelation` | 天机揭示 | 返回调用方可解析的“不触发/无效果”结构 |
| `random_minor_event` | 随机小事件 | 返回调用方可解析的“不触发”结构 |
| `world_lore_style_guide` | 世界观改写 | 由上层直接跳过整条世界观改写 pipeline；不应伪造 style guide |
| `world_lore_region_rewrite` | 世界观区域改写 | 同上，跳过 |
| `world_lore_sect_group_rewrite` | 世界观宗门改写 | 同上，跳过 |
| `world_lore_technique_rewrite` | 世界观功法改写 | 同上，跳过 |
| `world_lore_weapon_rewrite` | 世界观武器改写 | 同上，跳过 |
| `world_lore_auxiliary_rewrite` | 世界观辅助物改写 | 同上，跳过 |
| 其他 `world_lore_*` 动态 job | 世界观改写 planner | 上层按测试模式完全跳过；如果仍抵达 registry，抛出受控错误以暴露遗漏 |
| `custom_content_generation` | 自定义内容、金手指草案 | 抛出/转换为 `TEST_MODE_LLM_UNAVAILABLE`，不伪造草案 |
| 对话 reply/summary task | roleplay conversation service | 抛出/转换为 `TEST_MODE_LLM_UNAVAILABLE`，不伪造角色发言或总结 |

表中的“调用方要求的合法结构”不是实现时的模糊项：编码前必须阅读每个 task 的 parser 与消费方，补齐精确字段并在测试中锁定。若当前调用方已经拥有高质量 fallback，应优先复用它，而不是把 domain fallback 重复搬进 registry。

### 8.4 action 与 single-choice 的分层

`action_decision` 和 `single_choice` 的合法候选项依赖当前 world 状态。纯 registry 不应从 prompt 文本反向猜测 action/option。

因此：

1. `single_choice` 优先在 `systems/single_choice` 的领域 resolver 内短路到已有 `FallbackPolicy`，保证选择一定来自当前 request.options。
2. `action_decision` 优先复用角色 AI 决策链中已有的“无合法计划/保守计划”规则，或新增一个接收 avatar/world 的领域 fallback builder。
3. LLM registry 只承担“禁止 LLM、报告模式、对纯结构任务给固定输出”的职责，不应吸收需要 world 领域知识的所有决策逻辑。

这能避免把业务选择逻辑编码为对 prompt 字符串的脆弱解析。

## 9. 初始化、模拟与特殊能力

### 9.1 初始化

文件：`src/server/init_flow.py`

测试模式下初始化仍按现有阶段推进：加载地图、创建世界、生成角色、初始化宗门、生成首步事件等。LLM 依赖点通过规则路径完成或跳过。

额外规则：

1. `_run_llm_check_background()` 不得启动。
2. 初始化完成时不得设置 `llm_check_failed=True`。
3. runtime 可设置 `llm_check_pending=False`，并可增加非错误的 `llm_mode="test"` 供查询层展示。
4. `world_lore` 用户输入仍保存为世界文本/快照；但测试模式下不执行任何 LLM 驱动的世界观重写 job。
5. 若跳过世界观改写导致某些 UI 文案需要解释，应由 UI 使用测试模式备注，而非将它误报为初始化失败。

### 9.2 模拟循环

文件：`src/server/loop/runner.py`

`GameLoopRunner.run_once()` 在 `runtime.run_mutation(sim.step)` 内执行时必须建立 world 对应的 LLM mode scope。这样一个 tick 内由 action、关系、故事、宗门等异步相位触发的调用都受测试模式保护。

不得在 loop runner 的模块构造时缓存 `test_mode`；重开或读档后每次 tick 都从当前 world snapshot 读取。

### 9.3 世界观重写

文件：`src/systems/world_lore_rewrite/**`

测试模式下，在 world-lore pipeline 的公共入口立即返回“已跳过”的结构化结果。原因是该 pipeline 不是一个孤立文本字段，而是会对地区、宗门、物品等数据做批量改写；用空 JSON 让各子任务继续执行会导致不完整的半改写状态。

跳过时应：

1. 保留原始 `world_lore` 输入。
2. 保留静态/默认世界数据。
3. 不写局部重写产物。
4. 不抛初始化失败。

### 9.4 自定义内容

文件：

- `src/server/services/custom_content_service.py`
- `src/server/services/custom_goldfinger_service.py`

调用入口先检查目标 world/current run 是否测试模式，直接返回稳定错误码。该检查应早于 prompt 生成与 LLM 客户端调用。

用户仍可使用不依赖 LLM 的“提交已写好的 draft 并创建”能力，前提是该 command 本身不生成 LLM 内容且现有领域校验通过。

### 9.5 角色扮演

常规有限选择仍可走 `single_choice` 的确定性 fallback。自由对话和将自然语言意图转为复杂动作链的路径若不能提供严格合法的领域 fallback，则必须拒绝并保持当前 runtime 状态一致。

拒绝测试模式下的自由对话时：

1. 不创建半完成的 conversation session。
2. 不写入长期事件流。
3. 不解除与该会话相关的暂停原因，除非用户显式结束会话。
4. 返回 `TEST_MODE_LLM_UNAVAILABLE`，前端使用可本地化提示展示。

## 10. 错误模型与可观测性

### 10.1 错误分类

新增内部异常类别：

```text
TestModeLLMError
├─ TestModeUnsupportedLLMTask(task_name)
└─ TestModeLLMUnavailable(feature)
```

服务层应把主动功能不可用映射为稳定 API 错误码：

```json
{
  "status": "error",
  "error": {
    "code": "TEST_MODE_LLM_UNAVAILABLE",
    "message": "测试模式下不提供 LLM 内容生成。"
  }
}
```

项目当前统一响应包装若有既定字段形状，应遵从既有 `ok_response/error_response` 契约；上例只表达语义。

未注册 task 是开发完整性问题，不应被吞掉为普通用户错误。其日志必须包含 task name、当前 run 标识和调用位置；测试中应让它失败。

### 10.2 日志

测试模式不写真实 `log_llm_call()` 记录，避免测试结果被误统计为模型用量。可选地写低频结构化调试日志，例如：

```text
[test-mode] resolved LLM task with rule fallback: relation_delta
```

日志不得包含 API Key、完整 prompt 或用户敏感配置。

### 10.3 连通性

测试模式下不调用 `test_connectivity()`，也不读取 provider endpoint。状态不是“LLM 检测失败”，而是“LLM 检测不适用”。

## 11. 测试策略

### 11.1 配置与 API

1. `NewGameDefaults`、`RunConfig` 默认 `test_mode is False`。
2. `NewGameDefaultsPatch(test_mode=True)` 可以保存，且 `GET /api/settings` 回显。
3. `POST /api/v1/command/game/start` 传入 `test_mode=True` 后，`current-run` 返回该字段。
4. 正常开局未传该字段时为 `false`。
5. 运行中不存在切换该字段的 command。

### 11.2 前端

1. `newGameDraft` 默认值为 `test_mode: false`。
2. 从 `AppSettingsDTO.new_game_defaults` hydrate 后正确恢复值。
3. `GameStartPanel` 显示复选框和可见说明文本。
4. 切换复选框后，`startGameWithDraft()` 发送的 payload 包含正确布尔值。
5. readonly 状态禁用该控件。

### 11.3 存档

1. 测试模式 world 的 save data `run_config.test_mode` 为 `true`。
2. 读回该存档后 `world.run_config_snapshot.test_mode` 为 `true`。
3. 正常模式存档读回后为 `false`。
4. 读档不改写 `settings.json` 中下一局默认值。

### 11.4 无网络保证

在测试中 monkeypatch LLM provider 的最低层网络函数（例如 `_call_with_requests`）为“被调用即 AssertionError”。随后：

1. 开启测试模式，运行完整初始化。
2. 连续运行多个 `Simulator.step()`/`GameLoopRunner.run_once()`。
3. 覆盖世界观输入、角色生成、关系/事件等会触发 task 的路径。
4. 断言没有触发 network stub。
5. 断言 `test_connectivity()` 没有执行。

对应地，正常模式的客户端单测必须验证未开启测试模式时仍走现有 provider 调用路径。

### 11.5 fallback 合法性

每个已注册 task 至少要有：

1. registry 直接调用的返回形状测试。
2. 真实消费方解析该结果的业务测试，或覆盖其已有 fallback 分支。
3. 需要世界上下文的 action/single-choice，使用真实 `request.options` 或 avatar fixture 验证结果合法。
4. 不会产生不存在的 action ID、角色 ID、物品 ID、地区 ID 或枚举值。

### 11.6 失败封闭

1. 测试模式调用未知 task 必须抛 `TestModeUnsupportedLLMTask`。
2. 该异常出现时不允许调用 provider。
3. 主动生成功能返回 `TEST_MODE_LLM_UNAVAILABLE`。
4. 初始化/模拟中不应因预期的“跳过生成”产生 error 状态。
5. 测试模式 scope 在异常与取消后恢复；下一次正常模式调用必须不会被错误拦截。

### 11.7 建议测试文件

按现有测试组织就近放置，优先新增：

- `tests/test_llm_test_mode.py`
- `tests/test_settings_service.py` 中的 run config/API 用例
- `tests/test_game_init_integration.py` 中的测试模式初始化用例
- `tests/test_save_load_*.py` 中的 run_config 保存恢复用例
- `web/src/__tests__/stores/setting.test.ts`
- `web/src/__tests__/components/game/GameStartPanel.test.ts`

## 12. 实施阶段

### Phase 1：配置、UI 与数据闭环

1. 增加 schema、DTO、settings 持久化和默认值。
2. 增加开始游戏复选框与 `zh-CN` 文案。
3. 确认 start/current-run/save/load 的 `RunConfig` 闭环。
4. 补后端和前端字段测试。

完成标准：用户可开启测试模式开局，current-run 与存档均能准确显示该值。

### Phase 2：LLM 运行时网关

1. 增加 ContextVar scope 与 world helper。
2. 在初始化、模拟 loop 和相关 service 入口建立 scope。
3. 在 `call_llm_with_task_name()` 添加 fail-closed 测试模式分支。
4. 增加 registry、未知 task 异常和网络禁止测试。

完成标准：测试模式下任何已覆盖调用无法抵达 provider；正常模式不变。

### Phase 3：领域 fallback 与跳过策略

1. 为当前 task 清单实现精确 fallback。
2. 将 `single_choice` 和 action 的候选选择保持在领域层，不解析 prompt。
3. 跳过整个 world-lore pipeline。
4. 对 custom content / roleplay conversation 实现稳定拒绝。
5. 逐项补业务解析与初始化集成测试。

完成标准：测试模式可完成初始化并连续运行；主动生成能力可预测地失败；无真实 LLM 请求。

### Phase 4：文档与回归

1. 将本文档的稳定约束摘要写入适用的 `.cursor/rules` 与 `AGENTS.md`。
2. 视外部 API 的状态字段变更更新 `docs/specs/external-control-api.md`。
3. 运行目标后端、前端测试与类型检查。

完成标准：后续开发者新增 LLM task 时，能从规则与测试发现是否缺失测试模式契约。

## 13. 验收标准

一个实现只有同时满足以下条件才视为完成：

1. 开始游戏面板默认未选测试模式，并展示“仅用于测试、不接入实际 LLM”的可见说明。
2. 测试模式字段通过 settings、开局、当前局查询、世界快照、存档和读档全链路保持一致。
3. 测试模式初始化成功，至少多个世界 tick 可运行。
4. 测试模式下把真实网络函数替换为断言失败后，完整测试仍然通过。
5. 任何未知 task 在测试模式下显式失败，绝不回落到真实 provider。
6. 每个当前 LLM task 都有明确的规则 fallback、领域 fallback 或受控拒绝策略。
7. LLM 连通性检查不会在测试模式运行，且 UI/API 不将其报告为 LLM 配置错误。
8. 正常模式的现有 LLM 调用、失败通知、重试和日志回归测试通过。
9. 前端相关单测及 type-check、后端相关 pytest 均通过。

## 14. 后续维护清单

后续新增或修改 LLM task 时必须依次检查：

1. task 是否通过 `call_llm_with_task_name()` 进入统一网关？
2. 测试模式下它是规则 fallback、领域 fallback、整条 pipeline 跳过，还是显式不可用？
3. fallback 是否只产生调用方可解析的合法值？
4. 是否新增了未知 task fail-closed 的覆盖测试？
5. 该调用是否发生在 world scope 内，能读取正确的 `RunConfig.test_mode`？
6. 是否会错误地进行 LLM 连通性检查、读取 API Key 或写真实调用日志？
7. 是否需要更新本 spec、相关规则和 `AGENTS.md` 摘要？
