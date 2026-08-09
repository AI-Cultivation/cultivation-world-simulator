# 静态数据与领域边界重构方案

## 1. 背景

项目当前的 server runtime、query / command 边界已经具备基础结构，但仍存在另一组
会持续放大维护成本的边界问题：静态数据在多个模块 import 时加载并各自 reload；部分
系统把配置、运行时状态、模拟结算、持久化和 API 展示混在同一个文件；LLM transport
仍携带历史字符串错误协议。

本方案以职责边界和可验证行为为目标，不改变世界规则、公开 API 业务语义或存档格式。

## 2. 目标

1. 用统一静态数据目录和 reload 生命周期替代分散的模块级 `reload()` 协调。
2. 拆分世界秘闻的定义、运行时、发现流程、存档和 API 展示职责。
3. 将福缘 / 霉运演进为可扩展的 outcome handler 注册模型。
4. 将 LLM transport、失败分类和调用编排分离，并淘汰字符串错误协议。
5. 为效果系统建立可扩展的结构化定义模型，但不为“文件过长”单独重写它。

## 3. 非目标

1. 不修改 `/api/v1/*` endpoint、响应 envelope 或前端 DTO，除非修复明确的契约错误。
2. 不改变随机概率、事件文案语义、动作结算或存档 JSON 形状。
3. 不引入通用 DI 框架或新的全局万能容器。
4. 不为历史导入路径和旧错误字符串维护长期双轨；零成本 adapter 只能作为有删除条件的迁移手段。

## 4. 总体依赖方向

```text
config files -> static catalog -> domain definitions -> runtime state -> simulation services
                                                               -> persistence / API assemblers

LLM task -> runtime coordinator -> provider adapter
                           -> failure classifier
```

- 静态定义不得持有 world、avatar 等本局对象。
- runtime state 只保存 JSON 基础类型和跨对象 ID。
- API assembler 只读取领域 / runtime 状态，不反向驱动模拟结算。
- 配置 reload 后的动态值必须由调用时 getter 或 catalog snapshot 获取。

## 5. 静态数据目录与 reload 生命周期

### 5.1 现状问题

`src/run/data_loader.py` 需要手工编排多个领域模块的 `reload()`，而各模块又在 import
时直接加载全局字典。reload 后还要用 `fix_runtime_references()` 修复 avatar 对宗门、物品、
种族等旧对象的引用，说明静态定义的身份、版本和运行时绑定没有统一入口。

### 5.2 目标设计

新增 `StaticCatalogService`（可位于 `src/run/static_catalog/`）：

```text
StaticCatalogService
  - load() -> StaticCatalogSnapshot
  - current() -> StaticCatalogSnapshot
  - generation: int
  - reload(reason) -> StaticCatalogSnapshot
  - rebind_world(world, previous, current)
```

`StaticCatalogSnapshot` 是不可变目录视图，包含 sect、technique、weapon、auxiliary、
persona、race、goldfinger、phenomenon 等按 ID 的定义。各 loader 以显式依赖顺序注册；
目录负责一次性构建新 snapshot，成功后原子替换 current snapshot。

### 5.3 要求

1. 新代码不得在 import 时调用 `reload()` 或暴露可变的模块级配置字典作为真源。
2. `data_loader.reload_all_static_data()` 收敛为 catalog 的 facade，不再硬编码每个领域模块的调用顺序。
3. `rebind_world()` 按 ID 统一迁移运行时引用，并返回结构化报告；找不到定义不得静默吞掉。
4. locale / settings reload 通过 catalog generation 触发，调用方不得缓存过时 CONFIG。
5. 旧模块级字典只能作为短期只读 adapter，迁移完成后删除。

### 5.4 验收

- 对同一配置重载后，catalog generation 递增且快照内部引用一致。
- 活人、死者、宗门成员和当前天地异象的重绑定使用统一机制。
- 单个 loader 失败不会替换当前可用 snapshot。
- locale 切换、重新开局、读档后的静态引用测试覆盖成功与失败路径。

## 6. 世界秘闻边界

### 6.1 目标模块

```text
src/systems/world_secret/
  definitions.py       # 配表解析、option DTO、定义查询
  models.py            # fragment、binding、knowledge、runtime state
  initialization.py    # 本局随机选择和触发绑定
  discovery.py         # 每月发现与单选披露流程
  persistence.py       # JSON serialize / load
  overview.py          # API overview assembler
  __init__.py          # 稳定公开入口
```

### 6.2 要求

1. 定义加载从 `StaticCatalogService` 读取，而不是在业务函数中重复读取配置文件。
2. `WorldSecretRuntime` 与角色 knowledge 保持存档友好的纯 JSON / ID 语义。
3. 披露选择继续走统一 `single_choice` resolver；发现流程只产出事实事件，再按既有事件规则入库。
4. `overview.py` 不得修改 runtime 或创建 knowledge；缺失状态只能在初始化 / load 层归一化。
5. API 所需文本与 DTO 由后端 assembler 产生，前端不补中文 fallback。

### 6.3 验收

- 定义解析、初始化绑定、发现、披露、存档往返和 overview 可独立测试。
- 新增 trigger kind 时只需要扩展 definition schema 和 discovery handler，不修改 persistence / overview。
- 公开披露后所有角色知识同步且不会重复生成事件。

## 7. 福缘与霉运 outcome registry

### 7.1 目标设计

将 `fortune.py` 拆为：

```text
src/systems/fortune/
  models.py            # FortuneKind、候选记录、结果对象
  eligibility.py       # 可触发条件与权重
  outcomes.py          # outcome handler registry
  fortune_service.py   # 福缘编排
  misfortune_service.py# 霉运编排
  events.py            # 事实事件与 StoryEventService 对接
```

每个 outcome handler 负责 `can_apply()`、`apply()` 和结构化事实结果；编排服务只选择
候选、执行 handler 并提交事件。福缘和霉运共享筛选、权重和事件协议，不共享不相干的奖励逻辑。

### 7.2 要求与验收

1. 新 outcome 不通过扩展大型 `if / elif` 链接入。
2. handler 的 eligibility、奖励和事件输出各有单测。
3. test mode 不调用真实 LLM；涉及故事扩展时继续通过 `StoryEventService`。
4. 既有概率、奖励范围与事件类型保持不变，并以参数化回归测试锁定。

## 8. LLM transport 与失败模型

### 8.1 目标模块

```text
src/utils/llm/
  providers/openai_compatible.py
  providers/anthropic.py
  providers/base.py
  failure_classifier.py
  coordinator.py
  client.py             # 仅保留稳定 public facade
```

### 8.2 要求

1. provider adapter 只负责请求规范化、HTTP 调用与 `ProviderCallError` 转换。
2. failure classifier 只消费结构化异常；`HTTP_...::...`、`NETWORK_ERROR::...` 仅在迁移 adapter 中短暂支持。
3. coordinator 负责并发控制、test mode、失败通知、JSON parse retry 与日志。
4. JSON 重试只处理 `ParseError`；provider / network failure 原样向上抛出。
5. 连通性检查复用 adapter 和 classifier，不复制请求逻辑。

### 8.3 验收

- OpenAI-compatible 与 Anthropic 的 HTTP、网络、无效响应都映射为结构化异常。
- 配额、鉴权、限流、服务端错误与未知错误分类稳定。
- test mode 对未知 task 失败封闭，不触达真实 provider。
- 失败通知、并发上限与用户可读错误保留现有行为。

## 9. EffectDefinition registry

`effect/consts.py` 当前以常量和说明为主，不以文件行数为理由拆分。只有当 effect 需要类型、
默认值、叠加规则、可见性或 UI 元数据时，才引入：

```python
@dataclass(frozen=True)
class EffectDefinition:
    key: str
    value_type: type
    merge_strategy: MergeStrategy
    default: object
    visibility: EffectVisibility
```

要求：effect parser、merge、配置校验和 API 展示共用 registry；未知 effect 默认失败并给出
来源路径；现有常量可作为迁移期 key alias，最终由 registry 导出。

验收：所有现有效果键可解析；错误类型 / 不可合并值在加载期失败；新增 effect 不需要同步修改多份合法键列表。

## 10. 实施顺序与验证

1. StaticCatalogService 与运行时重绑定契约。
2. 世界秘闻拆分，并切换到 catalog。
3. 福缘 / 霉运 outcome registry。
4. LLM provider adapter 与 failure classifier。
5. 按实际元数据需求决定是否实施 EffectDefinition registry。

每阶段运行受影响测试；合并前运行：

```powershell
pytest -n 8
cd web; npm.cmd run test -- --run
cd web; npm.cmd run type-check
```

完成条件是旧入口不再承载真实职责、迁移 adapter 有明确删除点，并且公开 API、存档和模拟语义保持稳定。
