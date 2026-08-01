# I18n 落地实施 Spec

## 1. 背景与目标

当前仓库默认仍处于 Phase 1：

1. 日常功能开发优先只补 `zh-CN`。
2. 非 `zh-CN` 语言允许暂时缺失。
3. locale 测试在日常开发中可忽略。

当项目进入“正式落地 i18n”阶段时，应切换为 Phase 2 工作模式，对 `static/locales/registry.json` 中所有已启用语言进行统一补全、构建、测试与验收。

当前启用语言为：

1. `zh-CN`
2. `zh-TW`
3. `en-US`
4. `vi-VN`
5. `ja-JP`

本 spec 的目标是定义：

1. 仓库内 i18n 的真源位置。
2. 正式落地时需要完成的工作包。
3. 推荐实施顺序。
4. 必跑测试与人工验收项。

## 2. 范围

本次 i18n 落地包括以下内容：

1. 前端 UI 文案。
2. 后端运行时文本。
3. 动态事件与格式化文本。
4. LLM prompt / template 文本。
5. 游戏配置文本。
6. 语言切换入口与运行时 fallback。

本次不包括：

1. 新语言接入机制重构。
2. 全局翻译质量评审流程平台化。
3. 第三方自动翻译服务接入。

## 3. 当前项目中的 i18n 真源

### 3.1 语言注册表

单一真相源：

`static/locales/registry.json`

要求：

1. 所有工具、测试、补全脚本优先读取该文件。
2. 不得在新脚本中重复写死语言列表。

### 3.2 日常维护源文件

后端与前端共享的翻译真源主要为：

1. `static/locales/<lang>/modules/*.po`
2. `static/locales/<lang>/game_configs_modules/*.po`
3. `static/locales/<lang>/templates/*.txt`
4. `static/locales/<lang>/game_configs/*.csv`

说明：

1. `modules/*.po` 用于常规运行时文本、UI 文本、动态格式化文本。
2. `game_configs_modules/*.po` 用于配置型文本，如材料、地区、功法、宗门等。
3. `templates/*.txt` 用于 LLM prompt 模板。
4. `game_configs/*.csv` 用于姓名等配置数据。

### 3.3 构建产物

以下文件属于构建产物，不应作为日常维护入口：

1. `static/locales/<lang>/LC_MESSAGES/messages.po`
2. `static/locales/<lang>/LC_MESSAGES/game_configs.po`
3. `static/locales/<lang>/LC_MESSAGES/*.mo`

修改源文件后，必须运行：

`python tools/i18n/build_mo.py`

## 4. 现状与主要缺口

当前仓库已经具备完整 i18n 基础设施：

1. 已有注册表 `registry.json`
2. 已有多语言目录骨架
3. 已有缺失报告脚本
4. 已有 `.po` 合并与 `.mo` 构建脚本
5. 已有 locale 测试

当前正式落地 i18n 时最主要的缺口不是框架，而是“近阶段新增功能尚未全语言补齐”。

重点风险区：

1. `templates/*.txt` 新增文件在非 `zh-CN` 目录缺失。
2. 新功能只补了 `zh-CN/modules/*.po`，其他语言未同步。
3. 前端存在运行时 fallback 或硬编码中文/英文文案。
4. 游戏配置文本新增后未重新提取或未补齐对应语言。

已知近期新增、需要重点关注的模板包括：

1. `roleplay_conversation_turn.txt`
2. `roleplay_conversation_summary.txt`
3. `relation_delta.txt`
4. `random_minor_event_pair.txt`
5. `random_minor_event_solo.txt`

## 5. 实施工作包

### 5.1 工作包 A：缺口盘点

目标：生成当前仓库的全量缺失清单。

执行：

1. 运行 `python tools/i18n/generate_missing_report.py`
2. 阅读命令生成的缺失报告输出
3. 按语言、文件类型、功能模块拆分缺口

产出：

1. 一份最新缺失报告
2. 一份按优先级排序的补全清单

### 5.2 工作包 B：补全 templates

目标：确保所有启用语言拥有完整的 LLM prompt 模板集合。

范围：

1. `static/locales/<lang>/templates/*.txt`

要求：

1. 以 `zh-CN` 为当前功能最完整基线。
2. 对所有启用语言补齐缺失模板文件。
3. 语义上保持 prompt 结构一致，避免只翻译局部字段。
4. 若中文模板近期已分裂为新文件，其他语言必须同步拆分，而不是继续沿用旧单文件语义。

重点模块：

1. roleplay
2. single choice
3. conversation
4. relation / story / random event
5. sect 相关 thinker / decider

### 5.3 工作包 C：补全 modules/*.po

目标：补齐常规运行时文本和前后端功能文本。

范围：

1. `static/locales/<lang>/modules/*.po`

要求：

1. 以 `zh-CN/modules` 为基准补齐所有启用语言。
2. 不直接改 `LC_MESSAGES/messages.po`。
3. `msgid` 必须保持英文源文或稳定 key，不得直接使用中文。
4. 对于动态格式串，必须校验占位符完整一致。

优先级建议：

1. `ui.po`
2. `labels.po`
3. `single_choice.po`
4. `mutual_action.po`
5. `decision_description.po`
6. `event_content.po`
7. 其他系统模块

### 5.4 工作包 D：补全 game_configs_modules/*.po

目标：补齐世界配置型文本。

范围：

1. `static/locales/<lang>/game_configs_modules/*.po`

内容包括但不限于：

1. 地区
2. 宗门
3. 功法
4. 灵根
5. 材料
6. 武器
7. 丹药
8. 小事件配置文本

要求：

1. 若新增配置项先更新 csv / config 真源，再提取、翻译。
2. 不得只补 UI 文案而忽略游戏内容文本。

### 5.5 工作包 E：补全前端运行时文案

目标：清理前端硬编码与 fallback 漏洞。

范围：

1. `web/src/**/*.vue`
2. `web/src/**/*.ts`

重点检查：

1. store 默认错误文案
2. API 错误回退文案
3. runtime 状态提示
4. 空态文案
5. overlay / dock / panel / system menu 文案

要求：

1. 正式落地 i18n 时，新增用户可见文案必须接入前端 i18n。
2. 不允许依赖中文或英文硬编码作为长期方案。
3. 系统菜单语言入口需保留 `Language` 英文提示。

### 5.6 工作包 F：补全后端运行时文案

目标：清理 Python 侧 `t()` 之外的硬编码用户可见文案。

范围：

1. `src/**/*.py`

重点检查：

1. `HTTPException.detail`
2. runtime fallback 文案
3. query / command 错误消息
4. 新功能中直接返回前端的状态文本
5. roleplay / single choice / conversation 相关提示

要求：

1. 面向用户的字符串应统一进入 i18n 源。
2. 英文异常不应直接透传给最终界面。

### 5.7 工作包 G：配置提取与构建

目标：保证翻译源与构建产物一致。

执行：

1. 如有 CSV 变更，先运行 `python tools/i18n/extract_csv.py`
2. 修改 `modules/*.po` / `game_configs_modules/*.po`
3. 运行 `python tools/i18n/build_mo.py`

要求：

1. `.po` 必须为 UTF-8 无 BOM。
2. 不得使用 PowerShell 重定向直接向 `.po` 追加内容。

## 6. 推荐实施顺序

建议按以下顺序推进，而不是全仓随机补词条：

1. 生成缺失报告。
2. 先补 `templates/*.txt`。
3. 再补与近期新增功能直接相关的 `modules/*.po`。
4. 再补 `game_configs_modules/*.po`。
5. 再扫前后端硬编码文案。
6. 构建 `.mo`。
7. 跑 locale 测试。
8. 做人工语言切换验收。

原因：

1. `templates` 缺失会直接影响 LLM 功能可用性。
2. 新功能链路通常比老模块更容易出现明显缺口。
3. 配置文本补全工作量最大，适合放在框架链路跑通之后集中处理。

## 7. 建议的批次划分

### 批次 1：基础闭环

目标：

1. 所有启用语言模板文件齐全。
2. locale 测试能运行并输出稳定结果。
3. 新增功能不再只在 `zh-CN` 可用。

### 批次 2：功能链路补齐

目标：

1. 补齐近阶段新增系统的运行时文本。
2. 优先覆盖：
   1. roleplay
   2. single choice
   3. conversation
   4. external-control API 相关前端提示

### 批次 3：内容层补齐

目标：

1. 补齐配置型文本和世界内容。
2. 提升整体多语言沉浸感，而不只是“界面能切语言”。

### 批次 4：质量收口

目标：

1. 统一术语。
2. 统一占位符风格。
3. 清理重复、过时或结构不一致的词条。

## 8. 测试与验证

### 8.1 必跑

1. `python tools/i18n/generate_missing_report.py`
2. `python tools/i18n/build_mo.py`
3. `pytest tests/test_frontend_locales.py`
4. `pytest tests/test_backend_locales.py`

### 8.2 建议跑

1. `pytest tests/test_i18n_dynamic.py`
2. `pytest tests/test_i18n_integrity.py`
3. `pytest tests/test_i18n_modules.py`
4. `pytest tests/test_runtime_i18n_guards.py`
5. `pytest tests/test_locale_registry_migration.py`

### 8.3 人工验收

至少对每个启用语言做一轮以下路径检查：

1. 进入系统菜单并切换语言。
2. 新开局。
3. 查看主界面基础 UI。
4. 打开 avatar detail。
5. 查看右侧事件栏。
6. 执行一次 roleplay 决策。
7. 执行一次 roleplay choice。
8. 执行一次 roleplay conversation。
9. 存档与读档后再次确认语言一致性。

## 9. 验收标准

达到以下标准可视为“i18n 正式落地”：

1. `registry.json` 中所有已启用语言均有完整目录骨架。
2. `generate_missing_report.py` 不再报新增功能链路缺失。
3. locale 测试通过。
4. 新增功能链路在所有启用语言下均可用。
5. 用户可见硬编码中文/英文显著减少到可接受范围。
6. 模板文件在所有启用语言下结构一致。

## 10. 实施建议

如果只准备做一轮“第一阶段正式落地”，优先顺序建议为：

1. 先补模板。
2. 再补 roleplay / choice / conversation 这条新链。
3. 再补前后端运行时 fallback。
4. 最后补配置大盘。

原因：

1. 这条路径最能快速把“新功能只在中文完整可用”的问题压下去。
2. 也最容易在测试和人工体验里看到实际收益。

