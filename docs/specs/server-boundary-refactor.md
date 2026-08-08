# 服务端会话与领域边界重构方案

## 1. 背景

当前服务端已经完成第一轮 runtime / query / command 分层：写操作经由
`GameSessionRuntime.run_mutation()` 串行化，公共 API 也已区分 query 与 command。
方向正确，但实现仍保留了几处迁移期边界：

1. `src/server/main.py` 持有全局 `game_instance`，测试普遍直接读写该 dict；
2. `GameCommandDependencies` 和 `GameQueryDependencies` 分别注入 53 与 43 个依赖；
3. `roleplay_service.py` 同时编排决策、有限选择、对话和失败恢复；
4. `EventStorage` 并存分页 `get_events()` 与 `EventQuery` 查询路径；
5. `Sect` core 模块混合领域模型、静态 registry、展示文本和决策上下文入口。

这些不是立即的功能缺陷，但会持续提高新 API、角色扮演流程和测试的改动成本。
本 spec 只处理上述边界，不以“拆文件”或统一重写为目的。

## 2. 目标与非目标

### 目标

1. 让每个 server app / 测试拥有独立 session runtime，不再把 `main.game_instance` 当作常规业务和测试入口。
2. 将 query / command service 收敛为按领域组织、依赖数量可理解的应用服务。
3. 让角色扮演的三类交互拥有独立流程编排，并复用同一状态机与 mutation 边界。
4. 令 SQLite 与内存事件后端只执行一套明确的 `EventQuery` 语义。
5. 将宗门领域状态与 registry / API 展示职责分离。

### 非目标

1. 不修改 `/api/v1/*` 的业务含义、响应 envelope 或前端 DTO，除非发现已经存在的契约错误。
2. 不引入通用 DI 框架、service locator 或新的万能 `dict[str, Any]` 容器。
3. 不为旧 `main.py` patch 点维护长期双轨；迁移期适配必须有删除阶段。
4. 不修改模拟世界规则、动作结算、角色扮演的产品语义，且 runtime roleplay 状态仍不得进入存档。
5. 不将纯 DTO 汇总文件（如 `web/src/types/api.ts`）仅因文件长度而强行拆分。

## 3. 设计原则

```text
API / Host -> application service -> runtime + domain service -> domain model
                                      -> assembler / serializer
```

- 所有世界状态 mutation 必须继续经由 `GameSessionRuntime` 的统一串行化入口。
- 领域模型不得依赖 FastAPI、前端 DTO 或展示型 i18n 文案。
- 会随 settings reload / data root 切换而变化的配置，调用时通过 getter 获取；稳定领域协作者以具名对象或 Protocol 注入。
- 迁移完成以“旧入口不再承载真实职责”为准，而不是增加一层转发为准。

## 4. 目标设计

### 4.1 独立 session 与 composition root

新增可复用的 app composition / test harness。它创建独立的：

- `GameSessionRuntime` 与其底层 state；
- `ConnectionManager`；
- static data、settings、query / command services；
- FastAPI app。

生产启动的 `main.py` 只负责创建默认 composition、创建 app 与启动 server。测试应通过
fixture 或 harness 构造 composition，并只 patch 该实例的局部 collaborator。

迁移顺序：

1. 为 public API 和 lifecycle 测试提供 `server_app_factory` fixture；
2. 将直接 `main.game_instance.clear()/update()` 的测试迁移至 fixture runtime；
3. 删除只为测试保留的 `main.py` 业务 wrapper；
4. 最后移除生产代码对模块级 `game_instance` 的依赖。

验收：同一进程内两个 app 实例的暂停、world、初始化状态和 roleplay session 完全隔离；测试不再通过导入 `src.server.main` 获取可变 session。

### 4.2 面向领域的 application services

现有大依赖 dataclass 不再继续扩展。按调用语义拆分为小型服务，例如：

```text
WorldQueryService        AvatarQueryService       OverviewQueryService
AvatarCommandService     SaveLoadCommandService   WorldCommandService
RoleplayCommandService   GameLifecycleService
```

每个服务只持有本领域需要的 runtime、领域 service / repository、assembler 和动态配置 getter。路由调用具体 service；不再由单一 `GameQueryService` 或 `GameCommandService` 转发所有命令。

可保留一个仅用于组装路由的 facade，但 facade 不得重新成为数十项裸函数依赖的容器。

验收：新增一个 avatar、save/load 或 roleplay 用例时，不需要改动无关领域的 dependency dataclass；任意具体应用服务的直接依赖应可在一个短 dataclass / Protocol 中完整表达。

### 4.3 Roleplay flow 拆分

保留已有 roleplay state machine、prompt builder、history 和 conversation LLM 服务。将剩余编排拆为：

```text
RoleplayFacade
  ├─ DecisionFlow       # prepare -> LLM -> commit / restore
  ├─ ChoiceFlow         # 开始 choice、提交 choice、恢复 observing
  └─ ConversationFlow   # 开始会话、回合、摘要结束、失败恢复
```

三条 flow 都通过 runtime mutation 执行 commit / restore。LLM 调用在 mutation 临界区外；请求 ID、controlled avatar 和状态转换由 state machine 校验。Facade 仅处理路由适配与公开 session 视图。

验收：三条流程均有 prepare / commit / failure-restore 测试；重复请求、过期 request ID、目标角色不匹配和 LLM 失败不会遗留 `submitting` 状态；roleplay runtime 数据不写入存档。

### 4.4 统一 EventQuery

`EventQuery` 扩展为唯一的内部查询输入，包含：

- audience（`DIRECT` / `OBSERVED`）；
- avatar IDs、sect ID、memory scope；
- cursor、limit、排序方向。

查询执行返回显式 `EventPage(events, next_cursor)`。SQLite 只有一个 query compiler / executor，集中处理筛选、排序、分页、关联 hydration 与观察文案渲染；内存 `EventManager` 以相同参数语义实现。现有 `get_major_events_by_avatar()` 等保留为无逻辑的语义化 adapter。

验收：SQLite 与内存后端使用同一组参数化契约测试；分页顺序、major/minor 规则、direct/observed 归属和空结果语义一致；数据库异常不会伪装为空列表。

### 4.5 Sect 职责收口

目标模块职责：

```text
src/classes/core/sect.py        Sect、SectHeadQuarter 与纯领域规则
src/classes/sect_registry.py    静态加载、reload、按 id/name 查询
src/classes/sect_member_status.py  成员地位与贡献等可测试计算
src/server/assemblers/sect_detail.py  面向 API 的本地化 DTO / 展示
```

`Sect` 可以保留成员、资源、规则与领域行为，但不直接负责静态缓存、API DTO 或用户可见文本拼装。调用方经由 registry / static data registry 取得宗门。

验收：core `Sect` 不导入 server、FastAPI、前端 DTO 或 i18n 展示逻辑；宗门详情仍通过强类型后端 DTO + mapper 暴露。

## 5. 实施阶段

### Phase A：先立边界与测试入口

建立 composition fixture，迁移 public API / lifecycle 测试；收紧 `main.py` 为启动入口。此阶段不改变 API 行为。

### Phase B：缩小 application service 依赖面

先拆 Avatar、SaveLoad、Roleplay 三组 command，再拆 World / Overview query。移除旧 dependency bag 中已经迁出的字段。

### Phase C：角色扮演与事件查询

抽取三条 roleplay flow；引入 `EventPage`，统一 SQLite / 内存查询契约。每次迁移后删除被替代的分支，而非双写。

### Phase D：Sect 收口与清理

迁出 registry、成员计算与展示职责；删除过渡 re-export、`main.py` compatibility wrapper 和不再被使用的测试 helper。

## 6. 验证与完成定义

每个 phase 至少运行受影响的单测；整轮合并前运行：

```powershell
pytest -n 8
cd web; npm run test
cd web; npm run type-check
```

完成条件：

1. app session 可独立构造且测试不再直接写全局 `main.game_instance`；
2. query / command 不再由 40+ / 50+ 依赖的单一服务承载；
3. roleplay 三类交互在明确 flow 中完成且 mutation / 异常恢复语义不变；
4. 两种事件后端共享可验证的查询语义；
5. `Sect` 的领域、registry 和展示边界清晰，公共 API 保持稳定。

## 7. 与既有文档的关系

本 spec 是 `docs/specs/high-cohesion-refactor.md` 中 server composition、事件查询与 Sect 边界内容的窄化执行版，并补充 session 隔离与 roleplay flow。实现以本 spec 的范围和阶段为准；不自动纳入 avatar initialization、opportunity 或 LLM provider 错误模型等其他重构主题。
