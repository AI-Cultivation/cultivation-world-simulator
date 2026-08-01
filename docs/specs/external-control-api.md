# 外接控制 API 基础重构方案

本文档记录“外接控制 API”方向的整体设计与落地计划，目标不是零散补几个接口，而是把服务端重构成一个适合长期演进、方便外部 agent 接入、方便后续继续 vibe coding 的稳定底盘。

## 1. 背景与目标

当前项目已经具备一批可用的只读查询 API 和少量控制 API：

- 只读侧：世界快照、地图、详情、事件分页、榜单、宗门关系、王朝/凡人概览。
- 写入侧：开局、暂停/恢复、重置、设置长期目标、设置天地灵机、创建/删除角色、角色调整、存档读档。

这些能力已经足够支撑外部工具做“观察世界”，也已经有第三方 skill 基于现有 API 成功接入。

但当前架构仍有以下问题：

1. 路由层过厚，`src/server/main.py` 直接承担了大量领域读写。
2. 运行时状态集中在全局 `game_instance` 字典，边界不清晰。
3. 写接口没有统一的串行化入口，未来外部 agent 高频调用时会有状态竞争风险。
4. 现有接口更多是“前端内部契约”，并非“外部稳定契约”。
5. 成功/失败响应风格不统一，不利于 README、doc、skill 和第三方接入。

本次重构的核心目标：

1. 明确对外 API 的稳定边界。
2. 让“查询世界”和“干预世界”成为两个清晰模型。
3. 让后续新增接口只是在既有框架中增加 query/command，而不是继续堆逻辑。
4. 支持通过 Claw 等外部 agent 进行游玩、观察和有限控制。

## 2. 重构原则

### 2.1 不追求向前兼容

本次允许不兼容旧的内部接口命名与响应格式。

原则：

- 优先把结构拉直。
- 不为了兼容继续扩散旧命名、旧返回格式、旧职责混杂。
- 若前端需要适配，优先让前端跟随新契约调整。

### 2.2 以“外部集成”而不是“前端私有接口”作为第一视角

新 API 的第一使用者假设为：

- 外部 AI skill
- Claw / agent
- 自动化脚本
- 调试工具

因此接口应具备：

- 明确命名
- 明确 DTO
- 稳定错误返回
- 明确只读/写入边界
- 明确副作用

### 2.3 不做“万能 patch API”

本次不建议设计成“任意对象任意字段可 patch”的通用写接口。

应优先采用“有语义的 command”模型，例如：

- `set_long_term_objective`
- `set_world_phenomenon`
- `create_avatar`
- `delete_avatar`
- `adjust_avatar_loadout`
- `relocate_avatar`
- `change_avatar_sect`
- `modify_avatar_relation`

这样可以保持：

- 约束清晰
- 验证逻辑集中
- 文档可读
- 测试容易落地

## 3. 目标架构

### 3.1 分层

建议拆为四层：

#### A. Runtime / Session 层

建议新建模块，例如：

- `src/server/runtime/session.py`
- `src/server/runtime/locks.py`

职责：

- 统一持有当前运行时状态
- 替代散落在 `main.py` 中的 `game_instance` 直接读写
- 暴露当前 `world / sim / run_config / init_status / llm_status`
- 提供统一的 pause/resume/reset/start/load/save 生命周期入口
- 提供 mutation 串行化锁

建议的核心对象：

- `GameSessionState`
- `GameSessionRuntime`

#### B. Application Services 层

建议新建模块，例如：

- `src/server/services/game_queries.py`
- `src/server/services/game_lifecycle.py`
- `src/server/services/world_control.py`
- `src/server/services/avatar_control.py`

职责：

- 接收路由参数对应的业务意图
- 调用 runtime 和领域对象
- 返回明确的 DTO 或结果对象

要求：

- service 可以依赖 runtime、assembler、领域层
- service 不直接依赖 FastAPI request/response 对象

#### C. API / DTO / Assembler 层

建议新建模块，例如：

- `src/server/api/public_v1/*.py`
- `src/server/schemas/public_api.py`
- `src/server/assemblers/*.py`

职责：

- 参数校验
- DTO 定义
- 统一成功/失败响应格式
- 路由挂载

要求：

- 路由层只做“校验 -> 调 service -> 返回 DTO”
- 不在路由层散落手写业务逻辑

#### D. Domain 层

现有 `src/classes/**`, `src/sim/**`, `src/systems/**`

职责不变：

- 保持规则、状态、模拟器步进、领域行为

约束：

- 领域层不反向依赖 `server/main.py`
- 领域层不感知“HTTP 接口长什么样”

### 3.4 当前落地后的服务端模块地图

截至当前重构落地，`src/server` 侧已经形成如下职责划分：

- `src/server/main.py`
  - 仓库默认入口与 composition root
  - 负责组装 runtime、service、app 与启动入口
- `src/server/services/game_query_service.py`
  - 聚合 public v1 query 与 DTO 组装
  - 统一承接 runtime、assembler、serializer 与静态数据依赖
- `src/server/services/game_command_service.py`
  - 聚合 public v1 command 编排
  - 统一承接 lifecycle / avatar / save-load / custom content 等写操作
- `src/server/init_flow.py`
  - 聚合开局初始化流程
  - 包含资源扫描、地图加载、世界创建、世界观应用、宗门/NPC 初始化、LLM 检测与首步事件生成
- `src/server/loop_runtime.py`
  - 聚合后台 game loop、tick 载荷拼装与自动存档触发逻辑
- `src/server/host_app.py`
  - 聚合 FastAPI app / lifespan / router / mounts / 启动入口宿主逻辑
- `src/server/bootstrap.py`
  - 聚合 runtime 路径解析、host/port 解析与浏览器目标地址准备
- `src/server/serialization.py`
  - 聚合公共序列化函数，如事件、天地灵机、秘境状态
- `src/server/public_helpers.py`
  - 聚合运行时通用 helper，如头像资源扫描、存档名校验、运行时 locale 应用

这意味着后续新增外接能力时，应优先遵循：

- 新只读接口先考虑落到 `GameQueryService` 及对应 assembler。
- 新写接口先考虑落到 `GameCommandService`。
- 新初始化步骤优先扩展 `init_flow.py`，不要把 phase 逻辑重新塞回 `main.py`。
- 新宿主/启动行为优先扩展 `host_app.py` / `bootstrap.py`。

### 3.2 命名空间

建议新接口统一放在稳定前缀下：

- `/api/v1/system/*`
- `/api/v1/query/*`
- `/api/v1/command/*`

或者更偏资源风格的替代方案：

- `/api/v1/runtime/*`
- `/api/v1/world/*`
- `/api/v1/avatars/*`
- `/api/v1/events/*`

本项目更推荐第一种，因为它天然区分 query / command，便于外部 agent 理解副作用。

建议划分：

- `query`
  - 只读、无副作用
  - 可安全被 skill 和 agent 高频调用
- `command`
  - 有副作用
  - 必须经过统一锁和统一校验

### 3.3 响应格式

建议统一为：

成功：

```json
{
  "ok": true,
  "data": {}
}
```

失败：

```json
{
  "ok": false,
  "error": {
    "code": "WORLD_NOT_READY",
    "message": "World not initialized",
    "details": {}
  }
}
```

约束：

- 不再混用 `200 + {"error": ...}` 与 `HTTPException(detail=...)` 两套语义。
- 内部仍可用 HTTP 状态码区分错误类别，但响应体结构应稳定。
- `error.code` 必须是稳定字符串，方便 skill 做程序判断。

## 4. 并发与健壮性基础

### 4.1 Mutation 串行化

本次必须建立统一 mutation 入口。

建议：

- Runtime 持有一把统一的 `asyncio.Lock`
- 所有写操作经由 `runtime.run_mutation(...)`
- `Simulator.step()` 也通过同一执行通道运行

目标：

- 避免 HTTP mutation 与 `sim.step()` 并发改 world
- 避免多个外部 command 同时写世界

### 4.2 修为阶层别名与稳定 ID

修为阶层在查询结果中可能同时出现两类字段：

- 稳定 ID：`realm`、`stage`、`realm_id`、`stage_id`，值来自领域枚举，例如 `FOUNDATION_ESTABLISHMENT`、`EARLY_STAGE`。
- 展示别名：`cultivation.display_full_name`、`cultivation_display`，会随角色道统或种族变化，例如同一标准境界可显示为“筑基前期”“易筋初成”“明理初境”“化形前期”。

对外 API 约束：

- 所有 command、action params、脚本自动化输入必须使用稳定 ID。
- query 返回的展示别名只用于 UI、日志、叙事或给 agent 读懂世界，不得反向作为命令参数。
- 如果同一响应同时给出 `realm` 与 `cultivation`，`realm` 保持稳定 ID 语义，`cultivation` 承担显示语义。

### 4.3 Query 的快照语义

query 不应直接暴露“半更新中”的临时状态。

建议：

- 简单查询可直接读取当前状态
- 对体量较大或涉及多对象拼装的查询，优先通过 service 封装，保证同一次返回内部字段语义一致

### 4.4 生命周期守卫

所有 command 必须统一校验：

- 世界是否已初始化
- 当前是否允许 mutation
- 当前是否处于加载/初始化中
- 目标对象是否存在

避免每个 endpoint 自己重复判断。

## 5. 第一批 v1 API 范围

### 5.1 Query API

第一批稳定开放：

1. `GET /api/v1/query/runtime/status`
2. `GET /api/v1/query/world/state`
3. `GET /api/v1/query/world/map`
4. `GET /api/v1/query/detail`
5. `GET /api/v1/query/events`
6. `GET /api/v1/query/rankings`
7. `GET /api/v1/query/sect-relations`
8. `GET /api/v1/query/sects/territories`
9. `GET /api/v1/query/system/current-run`
10. `GET /api/v1/query/meta/game-data`
11. `GET /api/v1/query/meta/avatars`
12. `GET /api/v1/query/meta/avatar-adjust-options`
13. `GET /api/v1/query/meta/avatar-list`
14. `GET /api/v1/query/meta/phenomena`
15. `GET /api/v1/query/mortals/overview`
16. `GET /api/v1/query/dynasty/overview`
17. `GET /api/v1/query/dynasty/detail`
18. `GET /api/v1/query/saves`

### 5.2 Command API

第一批稳定开放：

1. `POST /api/v1/command/game/start`
2. `POST /api/v1/command/game/pause`
3. `POST /api/v1/command/game/resume`
4. `POST /api/v1/command/game/reset`
5. `POST /api/v1/command/game/reinit`
6. `POST /api/v1/command/game/save`
7. `POST /api/v1/command/game/load`
8. `POST /api/v1/command/game/delete-save`
9. `POST /api/v1/command/system/shutdown`
10. `DELETE /api/v1/command/events/cleanup`
11. `POST /api/v1/command/world/set-phenomenon`
12. `POST /api/v1/command/avatar/set-long-term-objective`
13. `POST /api/v1/command/avatar/clear-long-term-objective`
14. `POST /api/v1/command/avatar/create`
15. `POST /api/v1/command/avatar/delete`
16. `POST /api/v1/command/avatar/update-adjustment`
17. `POST /api/v1/command/avatar/update-portrait`
18. `POST /api/v1/command/avatar/generate-custom-content`
19. `POST /api/v1/command/avatar/create-custom-content`

### 5.3 暂缓到第二批

这些能力适合放到底盘稳定之后：

1. 修改角色位置
2. 修改角色宗门归属
3. 修改角色关系
4. 触发特定世界事件
5. 直接写世界数值
6. 多会话 / 多实例
7. 鉴权与权限分级

## 6. 推荐目录结构

```text
src/server/
  api/
    public_v1/
      __init__.py
      query.py
      command.py
      system.py
  runtime/
    __init__.py
    session.py
    locks.py
  schemas/
    public_api.py
    query.py
    command.py
  services/
    game_queries.py
    game_lifecycle.py
    world_control.py
    avatar_control.py
```

说明：

- 不要求一次把所有文件都拆完。
- 第一阶段可以先抽 runtime 和核心 service，再把路由渐进迁移到 `public_v1`。

## 7. 分阶段实施计划

### Phase 0: 设计冻结

目标：

- 定义命名空间
- 定义统一响应格式
- 定义 runtime/service 分层
- 确认第一批 v1 API 范围

交付物：

- 本文档
- `.cursor` 规则与 skill
- `AGENTS.md` 摘要

### Phase 1: Runtime 底盘重构

目标：

- 引入 `GameSessionRuntime`
- 收口 `game_instance`
- 提供统一读写入口
- 建立 mutation 锁

建议任务：

1. 新建 runtime 模块
2. 将 `world/sim/run_config/init_status/is_paused` 封装到 runtime
3. 将 `start/reinit/reset/pause/resume` 迁移到 lifecycle service
4. 让 `game_loop` 和 HTTP mutation 共用统一串行化机制

完成标准：

- 路由不再直接散落操作 `game_instance`
- `sim.step()` 与 mutation 不并发写世界

### Phase 2: Query Service 与 Public Query API

目标：

- 把主要只读接口整理为稳定查询契约

建议任务：

1. 抽出 `GameQueryService`
2. 将 `/state`、`/map`、`/detail`、`/events` 等迁移到 query service
3. 新建 `/api/v1/query/*`
4. 统一返回 `ok/data`

完成标准：

- 只读接口有稳定前缀、稳定 DTO、稳定错误格式

### Phase 3: Command Service 与 Public Command API

目标：

- 把现有控制接口迁移到 command 模型

建议任务：

1. 抽出 `AvatarControlService`
2. 抽出 `WorldControlService`
3. 抽出 `GameLifecycleService`
4. 新建 `/api/v1/command/*`

完成标准：

- command 全部走统一 runtime mutation 入口
- command 不再在路由层直接改 world

### Phase 4: 前端与文档跟随

目标：

- 前端改用 v1 契约
- README / docs / skill 补齐

建议任务：

1. 前端 `web/src/api/**` 切到新接口
2. README 增加“支持外部 agent / Claw 接入”说明
3. 增加外接 API 使用文档
4. 补充示例请求与错误码说明

### Phase 5: 第二批控制能力

在基础稳定后再继续加：

- 位置控制
- 宗门归属修改
- 关系控制
- 世界干预类命令

## 8. 测试策略

本次重构必须补足以下测试：

### 8.1 Runtime 测试

- 生命周期状态流转测试
- mutation 锁行为测试
- 初始化中 / 未初始化 / ready 状态守卫测试

### 8.2 Query API 测试

- `/api/v1/query/*` 成功返回格式
- 空世界 / 未初始化时的统一错误格式
- 事件分页契约不回退

### 8.3 Command API 测试

- 所有 command 在 world ready 时的 happy path
- 非法参数、目标不存在、状态不允许时的错误码
- command 与 runtime 的串行化行为

### 8.4 回归测试

- 初始化流程
- 存档/读档
- WebSocket tick
- 角色调整
- 事件查询

## 9. Vibe Coding 检查清单

后续任何人继续扩展外接控制 API 时，都应先检查：

1. 这是 query 还是 command？
2. 是否应该放进已有 service，而不是继续写进 `main.py`？
3. 是否复用了统一 runtime，而不是直接碰全局状态？
4. 如果是 command，是否走统一 mutation 锁？
5. 返回是否符合统一 `ok/data` 或 `ok/error` 契约？
6. 是否补了 API 测试，而不是只测领域逻辑？
7. README / docs / skill 是否需要同步更新？

## 10. 当前结论

本方向值得做，而且适合一次性做“底盘重构”。

本次最重要的不是补多少接口，而是把以下四件事定住：

1. 稳定的 v1 命名空间
2. runtime/service/API 三层边界
3. query / command 分离
4. mutation 串行化

只要这四件事立住，后续新增接口将会非常顺畅；届时无论是 README、Claw skill，还是后续继续 vibe coding，都会有统一抓手。

## 11. 兼容层现状与移除顺序

截至当前阶段，`/api/v1/*` 已经是前端运行时与外接 agent 的主路径；旧 `/api/*` 路由更多承担兼容层职责。

### 11.1 已移除的旧命名空间

第一批与最后一批旧查询兼容层现已全部移除，包括：

- `/api/meta/*`
- `/api/events`
- `/api/events/cleanup`
- `/api/rankings`
- `/api/sect-relations`
- `/api/sects/territories`
- `/api/mortals/overview`
- `/api/dynasty/overview`
- `/api/dynasty/detail`
- `/api/control/*`
- `/api/action/*`
- `/api/game/*`
- `/api/saves`

### 11.2 当前依赖分布

- `web/src` 前端运行时代码：
  - 业务接口已基本切到 `/api/v1/*`
  - 例外是设置真源 `/api/settings*` 与 `/api/settings/llm*`，这些属于应用设置面，不属于外接控制兼容层
- `tests/*`：
  - 外接控制相关测试已全部迁到 `/api/v1/*`
- Docker / 部署契约：
  - Docker 健康检查已迁到 `/api/v1/query/runtime/status`
  - Docker smoke 已迁到 `/api/v1/query/world/state`、`/api/v1/command/game/*` 与 `/api/v1/query/saves`
- 仓库文档与规则：
  - 若仍出现旧路径引用，应视为待清理历史文档，而非兼容承诺

### 11.3 推荐移除顺序

第一批已完成移除：

1. 旧 `/api/meta/*`
2. 旧 `/api/action/*`
3. 旧 `/api/control/*`
4. 旧 `/api/game/*`
5. 旧 `/api/saves`
6. 旧 `/api/events*`
7. 旧 `/api/rankings`、`/api/sect-relations`、`/api/sects/territories`
8. 旧 `/api/mortals/overview`、`/api/dynasty/*`

当前阶段建议继续处理：

1. 新增 API 一律只挂 `/api/v1/query/*` 或 `/api/v1/command/*`
2. 若文档、规则、测试中仍引用旧 `/api/*` 路径，继续做清理
3. 将后续示例、skill 和 agent 指南统一基于 v1 契约编写

### 11.4 当前代码策略

旧 `/api/*` 兼容路由已经移除；当前约束如下：

- 新功能禁止继续挂到旧命名空间
- 外部控制、前端运行时、测试与文档统一以 `/api/v1/*` 为唯一稳定契约
- `/api/settings*` 与 `/api/settings/llm*` 仍然保留，作为应用设置真源，不属于本兼容层讨论范围

## 12. Claw / Agent 最小接入套路

如果目标只是做一个“能观察、能决策、能干预”的控制 skill，推荐采用下面这套最小回路：

### 12.1 每轮推荐顺序

1. 先查 `GET /api/v1/query/runtime/status`
2. 若 `status` 不是 `ready`：
   - 若是未开局，调用 `POST /api/v1/command/game/start`
   - 若是初始化中，继续轮询 `runtime/status`
   - 若是错误态，优先读取错误信息并决定是否 `reinit`
3. 世界 ready 后，再查：
   - `GET /api/v1/query/world/state`
   - `GET /api/v1/query/events`
   - 必要时 `GET /api/v1/query/detail`
4. 根据策略调用一个有语义的 command
5. command 完成后重新回到 query，而不是假设本地状态一定正确

### 12.2 推荐的最小接口集合

只做基础控制时，通常只需要这些：

- 状态：
  - `GET /api/v1/query/runtime/status`
- 观察：
  - `GET /api/v1/query/world/state`
  - `GET /api/v1/query/events`
  - `GET /api/v1/query/detail`
- 控制：
  - `POST /api/v1/command/game/start`
  - `POST /api/v1/command/game/pause`
  - `POST /api/v1/command/game/resume`
  - `POST /api/v1/command/avatar/set-long-term-objective`
  - `POST /api/v1/command/world/set-phenomenon`

### 12.3 新增接口时的最小模板

如果后续要新增一个接口，推荐按下面判断：

- 新只读能力：
  - service / assembler 准备好后，接到 `src/server/services/game_query_service.py`
  - 再挂到 `src/server/api/public_v1/query.py`
- 新写能力：
  - 业务逻辑优先落 service
  - command 编排接到 `src/server/services/game_command_service.py`
  - 再挂到 `src/server/api/public_v1/command.py`
- 若会改 world / sim：
  - 必须走 runtime mutation 串行化
- 若前端也要消费：
  - 同步更新 `web/src/types/api.ts` 与对应 mapper

### 12.4 不建议的做法

- 不要从 skill 里依赖旧 `/api/*` 路径
- 不要假设一次 command 后本地缓存就是真相，优先重新 query
- 不要新增“万能 patch”式写接口
- 不要把新公共接口逻辑重新堆回 `src/server/main.py`
