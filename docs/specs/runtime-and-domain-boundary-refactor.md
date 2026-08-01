# 运行时与领域边界重构方案

本文档定义一次面向长期演进的架构重构。目标是收紧服务端运行时状态与 mutation 边界，移除模拟器对 server 层的反向依赖，并拆解已明显聚集多种职责的领域模块。

本文不描述新玩家功能。它的产出是让外接控制 API、角色扮演、模拟器、存档和前端宿主可以在明确边界上继续演进。

## 1. 背景

项目已经完成第一轮服务端拆分：存在 runtime、service、public v1 API、assembler、初始化和 game loop 模块。但部分过渡兼容层仍然是实际依赖中心：

1. `src/server/main.py` 创建全局 `game_instance`，组装大体积依赖字典，并通过 `globals().update()` 暴露历史 helper。
2. `GameSessionRuntime` 虽提供 mutation lock，但仍暴露可写的原始状态字典，生产代码可绕过串行入口。
3. `src/sim/simulator_engine/phases/actions.py` 反向依赖 `src.server` 的角色扮演实现，并以裸 `except Exception` 静默忽略失败。
4. `src/sim/avatar_init/__init__.py` 同时包含群体规划、约束求解、社交初始化、属性分配、对象工厂和请求解析。
5. `EventStorage` 为角色/角色对及大事/小事维护多套重复 SQL 查询和 hydration 流程。
6. `World` 直接承载完整宗门外交状态机，超出其作为世界聚合根的职责。

这些问题会导致新增功能继续依赖 `main.py` 的全局符号、绕开 mutation lock，或在不同查询和领域路径中复制规则。

## 2. 目标

1. 将 `src/server/main.py` 收敛为启动入口与最薄 composition root，不再成为可 patch 的业务服务总线。
2. 让所有会改变 world、sim 或运行时会话状态的生产路径都经由 `GameSessionRuntime` 的统一串行入口。
3. 让 `src/sim/**` 和 `src/classes/**` 不反向导入 `src/server/**`。
4. 将角色扮演的“是否在决策边界请求玩家输入”定义为领域可消费的窄接口，而非 server service 调用。
5. 拆分人口初始化、事件查询和宗门外交的高内聚模块，同时保持调用方可读的语义 API。
6. 将异常处理改为可区分的失败结果或可观测降级，禁止关键状态路径静默失败。

## 3. 非目标

1. 不改动世界规则、动作结算、存档 JSON 形状或公开 `/api/v1/*` 业务语义，除非为修复明确的错误边界所必需。
2. 不同时重写所有历史测试；测试迁移应随模块迁移进行。
3. 不为旧的 `main.py` helper 承担长期双轨兼容。迁移期间只保留短期、显式标记的测试适配层。
4. 不引入通用 DI 框架、全局 service locator 或万能 `dict` 配置包。
5. 不将角色扮演运行时状态写入存档。

## 4. 设计原则

### 4.1 依赖方向

依赖必须单向流动：

```text
API / Host -> Application services -> Runtime + Domain
                                      -> Domain
Simulator phases -> Domain interfaces / SimulationStepContext
```

禁止：

```text
Domain / Simulator -> src.server.services
Domain / Simulator -> src.server.main
```

### 4.2 Runtime 是 mutation 权威入口

`GameSessionRuntime` 负责：

- session 生命周期：start、reinit、load、reset、pause、resume；
- 当前 `world`、`sim`、`run_config` 与初始化状态；
- 所有 mutation 和 simulator step 的串行化；
- runtime-only 状态的清理，包括 roleplay session、pending request、conversation session 和 continuation。

它不负责：

- HTTP DTO；
- FastAPI request/response；
- 领域规则；
- 直接拼装前端展示数据。

### 4.3 明确依赖而非 giant dict 或隐式全局

跨模块依赖使用职责明确的 dataclass 或 Protocol。构造期依赖与调用时必须读取的动态依赖分开：

- 稳定服务或 serializer：构造期注入；
- settings、data paths、可 reload 配置：通过 `get_*` getter 在调用时读取；
- 测试替换：构造 test runtime 或替换局部依赖，不 patch `main.py` 全局符号。

### 4.4 错误不能伪装成业务空值

以下场景必须区分“没有结果”和“查询/状态更新失败”：

- SQLite 读取、写入和事务；
- 决策边界创建；
- roleplay continuation 取消或恢复；
- world mutation 与 simulator step。

允许 best-effort 的资源释放和可选展示降级，但必须捕获预期异常、写入上下文日志，并在代码中说明可忽略原因。

## 5. 目标架构

### 5.1 Server composition

新增或收敛下列对象：

```text
ServerComposition
  - runtime: GameSessionRuntime
  - manager: ConnectionManager
  - query_service: GameQueryService
  - command_service: GameCommandService
  - lifecycle_service: GameLifecycleService
  - host_dependencies: HostDependencies
```

`create_server_composition()` 负责实例化上述对象。`create_configured_app()` 接收 composition，而不是接收数十个函数、lambda 和原始全局字典。

`main.py` 的最终职责仅为：解析进程启动环境、创建 composition、创建 app、调用 `start_server()`。它不得继续导出 `run_*`、`build_public_*`、`init_game_async` 等业务 helper。

### 5.2 Runtime state

短期内可以保留底层 dict 以避免一次性改变存量代码，但生产 API 只允许通过命名方法访问状态。目标接口包括：

```python
class GameSessionRuntime:
    def get_world(self) -> World | None: ...
    def require_world(self) -> World: ...
    def get_simulator(self) -> Simulator | None: ...
    def get_status_snapshot(self) -> RuntimeStatus: ...
    async def run_mutation(self, operation, *args, **kwargs): ...
    async def run_step(self): ...
    async def reset_to_idle(self, *, clear_run_config: bool = True): ...
```

禁止在新的生产代码中：

```python
runtime.state["..."] = value
game_instance["..."] = value
runtime.update({...})
```

`state` 如在迁移期保留，必须标注为测试兼容出口；每次直接访问都应有迁移 issue 或明确的替代方法。

### 5.3 模拟器决策边界

定义位于 `src/sim` 或中立 runtime capability 模块的 Protocol：

```python
class DecisionBoundaryGateway(Protocol):
    def before_ai_decision(self, world: World) -> DecisionBoundaryResult: ...
    def get_controlled_avatar_id(self) -> str: ...
```

`DecisionBoundaryResult` 至少表达：继续、等待玩家、无受控角色、错误。`phase_decide_actions()` 只消费该接口，不导入 server service，也不吞掉未知异常。

server 的角色扮演服务实现该 gateway，并在组装 runtime 时注册。无 server 宿主的模拟、规则测试和脚本可注入空实现。

角色扮演的既有约束不变：单角色接管、仅在决策边界暂停、runtime 不进存档、对话依附 `Conversation` 动作。

### 5.4 领域模块拆分

#### Avatar initialization

将 `src/sim/avatar_init/__init__.py` 拆为：

- `social_initialization.py`：初始关系和友好度；
- `initial_attributes.py`：年龄、寿元、官职、贡献、金手指、装备；
- `population_planning.py`：`MortalPlan`、`PopulationPlan`、约束图和群体宗门分配；
- `avatar_factory.py`：基于 plan 创建 avatar 与 group；
- `manual_avatar.py`：手动创建请求的解析、校验与 override 应用；
- `__init__.py`：仅导出 `make_avatars`、`create_avatar_from_request` 和已声明的公共类型。

请求解析不应继续与随机群体算法共处一个模块。

#### Event query

为 storage 内部引入 `EventQuery`，统一表达：关联角色、关联模式（直接关联/被观察）、记忆范围（all/major/minor）、limit、cursor 和排序。

`EventStorage` 内部统一处理 SQL 选择、参数绑定、row hydration、观测渲染、时间排序和错误翻译；对外继续保留 `get_major_events_by_avatar()` 等语义方法作为薄包装。`EventManager` 的内存实现与 SQLite 实现需共享同一查询语义测试集。

#### Sect diplomacy

从 `World` 提取 `SectDiplomacyState`：

- 战争/和平状态；
- relation modifiers；
- 战斗记录；
- 过期清理；
- relationship/diplomacy breakdown；
- 序列化和加载。

`World` 仅持有该对象并提供必要的高层转发。新代码不得继续向 `World` 添加宗门外交算法。

## 6. 分阶段实施

### Phase A: 建立边界与防回归

1. 新增 architecture contract tests，禁止 `src/sim/**`、`src/classes/**` 导入 `src.server.main` 或 `src.server.services`。
2. 引入 `DecisionBoundaryGateway` 及空实现，替换 simulator phase 中的动态 server import 与裸异常捕获。
3. 为 roleplay gateway 成功、等待、故障路径增加测试；故障必须可观测且不得悄然进入 AI 决策。
4. 标记 `GameSessionRuntime.state`、`update()` 和 `main.game_instance` 为迁移出口，禁止新生产调用点。

验收：模拟器可在不导入 `src.server` 的环境下执行 action phases；角色扮演等待行为和正常 AI 行为均通过测试。

### Phase B: 收敛 composition 与 runtime mutation

1. 创建 `ServerComposition` 和 app factory fixture。
2. 将 `main.py` 中 query/command dependency dict 迁移为具名依赖对象。
3. 将 API、loop、lifecycle、settings 的直接字典写操作改为 runtime 命名方法或 `run_mutation()`。
4. 将依赖 `src.server.main` patch 的测试按模块迁移到 app/runtime fixture。
5. 删除没有生产调用方的 legacy global export；不得新增新的 compatibility export。

验收：`main.py` 不含 `globals().update()`；不再有生产模块直接写 `game_instance[...]`；所有 command 与 simulator step 均使用同一个 runtime mutation lock。

### Phase C: 拆分高聚合领域模块

1. 按 5.4 拆分 avatar initialization，并保持公共入口和测试行为一致。
2. 实现 `EventQuery`，将 EventStorage 重复查询收敛到单一执行路径。
3. 提取 `SectDiplomacyState`，迁移存档与加载逻辑。
4. 删除旧模块中只为过渡保留的重复实现。

验收：

- `avatar_init/__init__.py` 仅含公共出口和薄适配；
- EventStorage 的角色与记忆筛选规则只在一处实现；
- `World` 不再直接实现战争、和平和外交 breakdown 算法；
- 新旧存档兼容仅在零代价时保留，按开发阶段规则不维护长期双轨。

### Phase D: 可观测性与清理

1. 审计关键路径的 `except Exception: pass` 与 `except Exception: return []/0`。
2. 将其替换为领域错误、结构化日志或明确的 degraded result。
3. 为 SQLite 故障、roleplay continuation 取消、mutation operation 异常建立回归测试。
4. 更新 `docs/specs/external-control-api.md` 的模块地图和本 spec 的完成状态。

验收：关键查询失败不能被客户端误识别为“没有事件”；关键 mutation/roleplay 失败有可检索日志和稳定错误码。

## 7. 测试策略

每个 phase 至少补充：

1. 静态架构测试：依赖方向、禁止新增 `main.py` 全局业务导出、禁止 simulator 反向依赖 server。
2. Runtime 并发测试：同时发起 command 与 simulator step 时，验证串行执行、world revision 和错误传播。
3. Roleplay 测试：普通 AI、等待玩家、玩家提交、gateway 异常、reset/load 后 runtime 清理。
4. Event 查询契约测试：SQLite 与 memory backend 对相同数据和 query spec 给出相同的事件集合、顺序与 major/minor/story 语义。
5. 存档测试：宗门外交状态保存、加载和当前模型下的完整恢复。
6. 现有后端回归：至少运行受影响测试文件；完成每个 phase 后运行 `pytest -n 8`，合并前运行 `pytest`。

## 8. 风险与决策

### 8.1 测试对 `main.py` 的耦合

这是本重构最大的迁移成本。不得为了保留测试 patch 点而继续扩散 `main.py` 兼容出口。迁移采用 fixture 优先、按调用方分批替换的方式；遗留 helper 必须有明确删除批次。

### 8.2 Runtime 锁中的长任务

LLM 调用和慢 I/O 不应在持有 mutation lock 时无边界地执行。命令必须先在锁内完成必要的世界状态转换，再将可并发的外部工作放到受控阶段；回写世界前重新经由 runtime mutation 入口。不能为规避锁而直接写 world。

### 8.3 Event 查询抽象过度

`EventQuery` 只覆盖已有稳定维度，不做通用 SQL builder。对外仍使用语义化方法，避免调用方在业务代码中拼筛选条件。

### 8.4 存档迁移

`SectDiplomacyState` 的持久化应保持 JSON 基础类型和 ID 引用。若现有存档字段可零代价读取，可保留 `.get()`；否则以当前模型清晰为先，不维护两套长期转换分支。

## 9. 完成定义

满足以下条件时，本 spec 可标记完成：

1. `main.py` 是薄入口，不包含 legacy global export 或巨型依赖字典。
2. 生产路径中所有 world mutation 与 simulator step 均通过 `GameSessionRuntime` 的串行入口。
3. `src/sim/**`、`src/classes/**` 不依赖 `src.server/**` 的具体 service 或 main。
4. 角色扮演决策边界故障可观测，且不会因裸异常吞没而回退到未声明的 AI 行为。
5. avatar init、事件查询、宗门外交均拥有与职责相符的模块边界。
6. 受影响的后端测试、存档测试、角色扮演测试、公共 API 测试全部通过。
