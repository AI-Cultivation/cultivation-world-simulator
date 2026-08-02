# 高聚合模块与边界收口重构方案

本文档定义下一轮以可维护性为目标的重构范围。它不引入新的玩家功能，也不改变世界规则；目标是消除当前代码中已经出现、会持续放大维护成本的职责混杂、依赖总线和重复查询实现。

本文以当前代码为基线。仓库已有 server runtime、query/command service、`avatar_init` 与 `opportunity` 的过渡 re-export，但这些外观上的模块边界不等于职责已经迁移。本轮以真实实现位置和依赖方向作为完成标准。

## 1. 目标

1. 将 `src/server/main.py` 收敛为进程入口与 composition root，不再作为全局业务依赖总线。
2. 让 `Sect` 保持领域状态与规则，不再直接承担 i18n 文案、前端 DTO 和静态 registry 加载。
3. 让事件查询只有一套可测试的筛选、排序、hydration 与错误语义，SQLite 和内存后备保持一致。
4. 将角色初始化和机缘系统拆成真实模块，而不是由 `__init__.py` 转发仍然位于同一文件中的实现。
5. 用结构化 provider 异常取代 LLM transport 中的字符串错误协议。
6. 关键读取和写入失败不得伪装成业务上的空结果。

## 2. 非目标

1. 不改变 `/api/v1/*` 的业务语义、前端 DTO 或存档 JSON 形状，除非为修复明确错误边界所必需。
2. 不引入通用 DI 框架、service locator，或用新的万能 `dict[str, Any]` 替换现有依赖字典。
3. 不为历史 `main.py` patch 点、旧模块路径或旧存档维护长期双轨；零代价 re-export 和 `.get()` 可临时保留，但必须有删除阶段。
4. 不在本轮重写世界规则、动作结算、宗门外交或角色扮演有限决策框架。
5. 不把 roleplay session、pending request、conversation session 或 continuation 写入存档。

## 3. 总体原则

### 3.1 依赖方向

```text
API / Host -> application service -> runtime + domain service -> domain model
                                      -> assembler / serializer
```

- `src/classes/**` 和 `src/systems/**` 不依赖 `src/server/**`。
- 领域模型不导入 FastAPI、前端 DTO 或具体 i18n 展示格式。
- `main.py` 只创建对象和连接对象；不承担业务转发，不作为测试 patch 的常用入口。

### 3.2 动态依赖与稳定依赖

- 会因设置 reload、数据根切换或配置更新而变化的内容，调用时通过窄 getter 读取。
- 稳定领域服务、serializer 和 assembler 在构造期通过具名字段注入。
- dataclass 的字段必须是职责级对象或明确 Protocol，不能把数十个裸函数平铺成“有类型的 giant dict”。

### 3.3 迁移原则

- 先建立新路径和契约测试，再迁移一个完整调用面，最后删除旧实现。
- 过渡模块只允许 re-export 已迁移的真实实现；禁止“新模块 import 旧巨型 `__init__`”后宣称拆分完成。
- 每个阶段结束时必须减少旧入口的真实职责，不接受只增加包装层的迁移。

## 4. 目标设计

### 4.1 服务端 composition

当前 `main.py` 仍集中构造 query、command 和 runtime hook 的大依赖集合。`GameQueryDependencies`、`GameCommandDependencies` 虽已经是 dataclass，但仍主要承载大量裸函数，服务本身大多只是转发器。

目标结构：

```text
ServerComposition
  - runtime: GameSessionRuntime
  - connection_manager: ConnectionManager
  - settings: SettingsServicePort
  - static_data: StaticGameDataRegistry
  - queries: GameQueryService
  - commands: GameCommandService
  - lifecycle: GameLifecycleService
  - host: HostDependencies
```

要求：

1. `create_server_composition()` 位于 `src/server/composition.py` 或同职责 package，负责组装上述对象。
2. `create_configured_app()` 接收 `ServerComposition` 与一个小型 `HostDependencies`，不再接收数十个函数参数。
3. `GameQueryService` 和 `GameCommandService` 仅依赖职责明确的 collaborator，例如 `WorldQueryFacade`、`AvatarCommandFacade`、`SaveLoadService`、`RoleplayService`；不得继续扩展扁平函数列表。
4. `main.py` 最终只负责解析启动环境、创建 composition、创建 app、调用 `start_server()`。
5. 被配置 reload 影响的 collaborator 必须在自身方法中通过 getter 读取当前配置，不能把 `CONFIG` 当作永久快照。

### 4.2 Sect 领域、展示与 registry 分离

`Sect` 当前同时保存状态、计算成员地位、输出本地化描述、组装前端结构化数据，并与静态 registry 加载共处一个模块。

目标模块：

```text
src/classes/core/sect.py              # Sect、SectHeadQuarter、纯领域规则
src/classes/sect_member_status.py     # 成员地位、贡献与战力归一化计算
src/classes/sect_registry.py          # 静态数据加载、reload、按 id/name 查询
src/server/assemblers/sect_detail.py  # API DTO 与本地化展示
```

要求：

1. `Sect` 可以保留成员增删、种族接纳、门规判断、资源状态等领域行为。
2. `Sect` 不得直接导入 `src.i18n`、`techniques_by_name` 或 API 组装器；`get_structured_info()` 和面向用户的字符串描述迁入 assembler/presenter。
3. 成员地位算法提取为可独立测试的服务，避免 `Sect` 因展示排序规则和战斗系统耦合而膨胀。
4. `sects_by_id`、`sects_by_name` 和 `reload()` 迁出 core model 文件；调用方通过 registry 或现有静态数据 registry 获取。
5. 新 DTO 必须保持后端本地化、强类型 mapper 的前端契约，不在前端补中文 fallback。

### 4.3 事件查询规格

定义 storage 内部查询对象：

```python
class EventAudience(str, Enum):
    DIRECT = "direct"          # related_avatars 直接参与
    OBSERVED = "observed"      # event_observations 可见

class EventMemoryScope(str, Enum):
    ALL = "all"
    MAJOR = "major"            # is_major and not is_story
    MINOR = "minor"            # not is_major or is_story

@dataclass(frozen=True)
class EventQuery:
    avatar_ids: tuple[str, ...] = ()
    audience: EventAudience = EventAudience.DIRECT
    sect_id: int | None = None
    memory_scope: EventMemoryScope = EventMemoryScope.ALL
    cursor: EventCursor | None = None
    limit: int = 100
    chronological: bool = False
```

语义要求：

1. 单角色的长期/短期记忆使用 `OBSERVED`，角色对事件使用 `DIRECT`；这是显式业务语义，不再隐含于不同 SQL 片段。
2. `EventStorage` 只有一个 query compiler/executor，统一处理筛选、排序、分页、批量关联 hydration、观测文案渲染和数据库错误翻译。
3. `EventManager` 的内存模式必须执行同一 `EventQuery` 语义；不能再以独立循环悄然定义另一套筛选规则。
4. 对外继续提供 `get_major_events_by_avatar()`、`get_events_between()` 等语义 API，它们只负责构造 `EventQuery`。
5. 数据库错误必须抛出或转换为明确的领域读取失败；空列表只表示确实没有匹配事件。

### 4.4 角色初始化真实拆分

目标模块：

```text
src/sim/avatar_init/
  social_initialization.py  # 初始关系、友好度
  initial_attributes.py     # 年龄、寿元、装备、��职、贡献、金手指
  population_planning.py    # MortalPlan、PopulationPlan、约束图、宗门分配
  avatar_factory.py         # AvatarFactory、单体/批量构建
  manual_avatar.py          # 外部请求解析、校验、override、手工创建
  __init__.py               # 稳定导出，仅此而已
```

要求：

1. `factory.py`、`planning.py`、`request_parser.py` 等过渡模块必须改为承载真实实现，不能继续从 package `__init__` import。
2. `__init__.py` 仅重导出稳定公开入口和已声明公共类型，不包含实际算法；目标小于 100 行。
3. `create_random_mortal()` 和 `make_avatars()` 维持现有调用语义；`create_avatar_from_request()` 继续是手动创建的唯一入口。
4. 随机群体算法不依赖 HTTP/request 类型；输入解析和 API 校验不与随机算法混在同一文件。
5. 迁移后补模块级测试，至少覆盖约束求解、关系落地、手动创建参数、年龄上限和种族/宗门兼容性。

### 4.5 Opportunity 包真实拆分

目标模块：

```text
src/systems/opportunity/
  models.py       # OpportunityRecord、枚举、OpportunityManager
  config.py       # 概率、时长、权重的动态读取
  targeting.py    # 目标选择、方向与提示
  outcomes.py     # 奖励选择与结果结算
  phases.py       # 月度检查和状态推进
  persistence.py  # save/load
  __init__.py     # 稳定导出
```

要求：

1. 上述模块中的真实定义必须迁出 `__init__.py`；现有同名薄模块不再反向 import `__init__.py`。
2. `OpportunityManager` 只管理 runtime record 和冷却状态，不直接承担目标生成、事件文案或奖励结算。
3. 概率和配置在调用时从当前配置读取，符合本局/设置 reload 语义。
4. 机缘的事件生成仍遵循“先基础事实事件，再经 `StoryEventService` 尝试追加故事”的规则。
5. 保存数据只包含 JSON 基础类型和 ID；不持久化临时对象引用。

### 4.6 LLM provider 异常模型

目标：用内部异常替代 `Exception("HTTP_...::...")`、`Exception("NETWORK_ERROR::...")` 等字符串协议。

```python
@dataclass
class ProviderCallError(Exception):
    kind: ProviderFailureKind
    message: str
    status_code: int | None = None
    response_body: str = ""
    provider_message: str = ""
    cause: Exception | None = None
```

要求：

1. OpenAI-compatible 与 Anthropic adapter 分别将 HTTP、网络、无效响应转换为 `ProviderCallError`，并保留原始 cause。
2. 错误分类函数消费结构化异常；字符串解析仅作为短期兼容适配，不得成为主路径。
3. `call_llm()` 保持并发控制、日志记录和全局配置失败通知的现有语义。
4. `call_llm_json()` 只重试可解析失败；provider/network 错误按既有失败分类向上传播，不误报为 JSON 解析问题。
5. `test_connectivity()` 返回用户可读错误，但不得 `print` 替代结构化日志。

## 5. 实施阶段

### Phase A：架构契约与 composition

1. 为 composition、`main.py` 瘦身和动态 getter 建立测试。
2. 创建 `ServerComposition`，迁移 app factory 和 service 构造。
3. 删除无生产调用方的 `main.py` 转发入口；测试改为构造 composition 或 patch 局部依赖。

验收：`main.py` 没有巨型依赖字典、业务 helper 或新的 legacy export；app factory 不接收函数参数清单。

### Phase B：事件与 Sect 边界

1. 实现 `EventQuery` 并迁移 SQLite/in-memory 查询。
2. 为两种 backend 建立同一组参数化契约测试。
3. 提取 `SectMemberStatusService`、`sect_registry.py` 和 server assembler 展示逻辑。

验收：事件筛选和 hydration 各只有一个执行路径；core `Sect` 不再依赖 i18n、静态 technique registry 或 API DTO。

### Phase C：真实模块迁移

1. 迁出 `avatar_init/__init__.py` 的全部实现并删除反向 re-export。
2. 迁出 `opportunity/__init__.py` 的全部实现并删除反向 re-export。
3. 保持稳定 package import，清理不再需要的兼容文件。

验收：两个 `__init__.py` 都只承担公开 API；从任一子模块导入不会通过 `__init__.py` 间接加载完整子系统。

### Phase D：LLM 错误模型与失败可观测性

1. 引入 `ProviderCallError` 并替换 transport 字符串异常。
2. 审计本轮模块中的宽泛 `except Exception`；关键 I/O、查询和 mutation 不得返回伪空值。
3. 补 provider HTTP/network/invalid-response、SQLite 读取失败和 mutation 失败测试。

验收：关键失败具有原始异常链、结构化日志和稳定错误分类；调用方可区分“没有结果”和“读取失败”。

## 6. 测试与完成定义

每个 phase 至少运行受影响测试；阶段完成后运行 `pytest -n 8`，整轮合并前运行 `pytest`。

本 spec 完成的条件：

1. `main.py` 是薄 composition root，应用服务不再由长函数列表装配。
2. `Sect`、事件查询、avatar init、opportunity 均具备与职责一致的真实模块边界。
3. SQLite 与内存事件 backend 对同一 query spec 给出相同事件集合、顺序与 major/minor/story 语义。
4. LLM transport 使用结构化异常，不再通过编码字符串恢复错误类型。
5. 本轮所有新模块遵守 runtime mutation、i18n、存档 JSON 与 story event 的既有架构约束。
6. 受影响的单元测试、公共 API 测试、存档测试和全量后端测试通过。
