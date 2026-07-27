<!-- 语言 / Language -->
<h3 align="center">
  <a href="README.md">简体中文</a> · <a href="docs/readme/ZH-TW_README.md">繁體中文</a> · <a href="docs/readme/EN_README.md">English</a> · <a href="docs/readme/VI-VN_README.md">Tiếng Việt</a> · <a href="docs/readme/JA-JP_README.md">日本語</a> · <a href="docs/readme/FR-FR_README.md">Français</a>
</h3>
<p align="center">— ✦ —</p>

# 修仙世界模拟器 (Cultivation World Simulator)

![GitHub stars](https://img.shields.io/github/stars/4thfever/cultivation-world-simulator?style=social)
[![LINUX DO](https://img.shields.io/badge/LINUX.DO-%E7%A4%BE%E5%8C%BA-2EA44F)](https://linux.do/t/topic/2439437)
[![Bilibili](https://img.shields.io/badge/Bilibili-%E6%9F%A5%E7%9C%8B%E8%A7%86%E9%A2%91-FB7299?logo=bilibili)](https://space.bilibili.com/527346837)
![QQ Group](https://img.shields.io/badge/QQ%E7%BE%A4-1071821688-deepskyblue?logo=tencent-qq&logoColor=white)
[![Discord](https://img.shields.io/badge/Discord-Join%20Us-7289da?logo=discord&logoColor=white)](https://discord.gg/3Wnjvc7K)
[![Epic Games Store](https://img.shields.io/badge/Epic%20Games%20Store-Get%20It%20Free-313131?logo=epicgames&logoColor=white)](https://store.epicgames.com/p/ai-cultivation-world-simulator-adebb8)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi&logoColor=white)
![Vue](https://img.shields.io/badge/Vue.js-3.x-4FC08D?style=flat&logo=vuedotjs&logoColor=white)
![TypeScript](https://img.shields.io/badge/typescript-%23007ACC.svg?style=flat&logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/vite-%23646CFF.svg?style=flat&logo=vite&logoColor=white)
![PixiJS](https://img.shields.io/badge/PixiJS-E72264?style=flat&logo=pixijs&logoColor=white)


<p align="center">
  <img src="assets/screenshot.gif" alt="游戏演示" width="100%">
</p>

> **你将作为“天道”，观察一个由规则系统与 AI 共同驱动的修仙世界模拟器自行演化。**
> **全员 LLM 驱动、群像涌现叙事，桌面版已在 Epic Games Store 免费发布，也支持 Docker 部署、源码开发与二次创作。**

<table align="center">
  <tr>
    <td align="center"><a href="https://hellogithub.com/repository/4thfever/cultivation-world-simulator" target="_blank"><img src="https://api.hellogithub.com/v1/widgets/recommend.svg?rid=d0d75240fb95445bba1d7af7574d8420&claim_uid=DogxfCROM1PBL89" alt="Featured｜HelloGitHub" width="300" /></a></td>
    <td align="center"><a href="https://trendshift.io/repositories/20502" target="_blank"><img src="https://trendshift.io/api/badge/repositories/20502" alt="4thfever%2Fcultivation-world-simulator | Trendshift" width="300" /></a></td>
  </tr>
</table>

## 📖 简介

这是一个 **AI 驱动的修仙世界模拟器**。
模拟器中，每一个修士都是独立的Agent，可以自由观测环境并做出决策。同时，为了避免AI的幻觉与过度发散，编入了复杂灵活的修仙世界观与运行规则。在规则与 AI 共同编织的世界中，修士Agent们与宗门意志相互博弈又合作，新的精彩剧情不断涌现。你可以静观沧海桑田，见证门派兴衰与天骄崛起，也可以降下天劫或魔改心灵，微妙地干预世界进程。

### ✨ 核心亮点

- 👁️ **扮演“天道”**：你不是修士，而是掌控世界规则的**天道**。观察众生百态，体味苦辣酸甜。
- 🤖 **全员 AI 驱动**：每个 NPC 都独立基于LLM驱动，都有独立的性格、记忆、人际关系和行为逻辑。他们会根据即时局势做出决策，会有爱恨情仇，会结党营私，甚至会逆天改命。
- 🌏 **规则作为基石**：世界基于灵根、境界、功法、性格、宗门、丹药、兵器、武道会、拍卖会、寿元等元素共同组成的严谨体系运行。AI 的想象力被限制在合理又足够丰富的修仙逻辑框架内，确保世界真实可信。
- 🦋 **涌现式剧情**：开发者也不知道下一秒会发生什么。没有预设剧本，只有无数因果交织出的世界演变。宗门大战、正魔之争、天骄陨落，皆由世界逻辑自主推演。

<table border="0">
  <tr>
    <td width="33%" valign="top">
      <h4 align="center">宗门体系</h4>
      <img src="assets/zh-CN/screenshots/宗门.png" width="100%" />
      <br/><br/>
      <h4 align="center">城市区域</h4>
      <img src="assets/zh-CN/screenshots/城市.png" width="100%" />
      <br/><br/>
      <h4 align="center">事件经历</h4>
      <img src="assets/zh-CN/screenshots/经历.png" width="100%" />
    </td>
    <td width="33%" valign="top">
      <h4 align="center">角色面板</h4>
      <img src="assets/zh-CN/screenshots/角色.png" width="100%" />
      <br/><br/>
      <h4 align="center">性格与装备</h4>
      <img src="assets/zh-CN/screenshots/特质.png" width="100%" />
      <br/><br/>
      <h4 align="center">自主思考</h4>
      <img src="assets/zh-CN/screenshots/思考.png" width="100%" />
      <br/><br/>
      <h4 align="center">江湖绰号</h4>
      <img src="assets/zh-CN/screenshots/绰号.png" width="100%" />
    </td>
    <td width="33%" valign="top">
      <h4 align="center">洞府探秘</h4>
      <img src="assets/zh-CN/screenshots/洞府.png" width="100%" />
      <br/><br/>
      <h4 align="center">角色信息</h4>
      <img src="assets/zh-CN/screenshots/角色信息.png" width="100%" />
      <br/><br/>
      <h4 align="center">丹药/法宝/武器</h4>
      <img src="assets/zh-CN/screenshots/丹药.png" width="100%" />
      <img src="assets/zh-CN/screenshots/法宝.png" width="100%" />
      <img src="assets/zh-CN/screenshots/武器.png" width="100%" />
    </td>
  </tr>
</table>

## 🚀 快速开始

### 推荐方式

- **想改代码或调试**：使用源码部署，并准备 Python `3.10+`、Node.js `18+` 和可用的模型服务。
- **想直接体验**：可前往 [Epic Games Store](https://store.epicgames.com/p/ai-cultivation-world-simulator-adebb8) 免费获取桌面版；也可以使用 Docker 一键部署。
- 如需快速查阅世界信息、动作、宗门等资料，可在 `tools/wiki` 生成本地辅助 wiki。

### 首次启动说明

- 使用 Epic 桌面版时，启动后按设置页提示确认模型配置，即可开始新游戏。
- 使用源码或 Docker 时，首次进入后需要先在设置页配置可用的模型预设（如 DeepSeek / MiniMax / Ollama），再开始新游戏。
- 开发模式下，前端页面通常会自动打开；如果没有自动打开，请访问启动日志中显示的前端地址。

### 方式零：Epic Games Store 桌面版

适合只想游玩、不想配置开发环境的玩家。

1. 前往 [Epic Games Store](https://store.epicgames.com/p/ai-cultivation-world-simulator-adebb8) 免费获取并安装。
2. 启动游戏后，按设置页提示确认模型配置，即可开始新游戏。
3. 如果你希望使用自己的模型服务，可以在设置页切换 DeepSeek / MiniMax / Ollama 等预设。

### 方式一：源码部署（开发模式，推荐）

适合需要修改代码或调试的开发者。

1. **安装依赖并启动**
   ```bash
   # 1. 安装后端依赖
   pip install -r requirements.txt

   # 2. 安装前端依赖 (需 Node.js)
   cd web && npm install && cd ..

   # 3. 启动服务 (自动拉起前后端)
   python src/server/main.py --dev
   ```

2. **配置模型**
   在前端设置页选择模型预设（如 DeepSeek / MiniMax / Ollama）后，即可开始新游戏。配置会自动保存到用户数据目录。

3. **访问前端**
   开发模式会自动拉起前端开发服务器，请访问启动日志中显示的前端地址，通常为 `http://localhost:5173`。

### 方式二：Docker 一键部署（未测试）

无需配置环境，直接运行即可：

```bash
git clone https://github.com/4thfever/cultivation-world-simulator.git
cd cultivation-world-simulator
docker-compose up -d --build
```

访问前端：`http://localhost:8123`

后端容器通过 `CWS_DATA_DIR=/data` 统一持久化用户数据，包含设置、密钥、存档和日志。默认已映射到宿主机 `./docker-data`，即使执行 `docker compose down` 后重新 `up`，这些数据也会保留。

<details>
<summary><b>局域网/手机访问配置 (点击展开)</b></summary>

> ⚠️ 移动端 UI 暂未完全适配，仅供尝鲜。

1. **后端配置**：推荐通过环境变量启动后端，例如 PowerShell 中执行 `$env:SERVER_HOST='0.0.0.0'; python src/server/main.py --dev`。如需改默认值，可编辑只读配置 `static/config.yml` 中的 `system.host`。
2. **前端配置**：修改 `web/vite.config.ts`，在 server 块中添加 `host: '0.0.0.0'`。
3. **访问方式**：确保手机与电脑在同一 WiFi 下，访问 `http://<电脑局域网IP>:5173`。

</details>

<details>
<summary><b>外接 API / Agent/Claw 接入 (点击展开)</b></summary>

这部分适合做外部 agent / Claw 接入、自动化脚本，或者实现“观察 -> 决策 -> 干预 -> 再观察”的闭环游玩。

推荐直接围绕稳定命名空间开发：

- 只读查询：`/api/v1/query/*`
- 受控写入：`/api/v1/command/*`

常见起点接口：

- `GET /api/v1/query/runtime/status`
- `GET /api/v1/query/world/state`
- `GET /api/v1/query/events`
- `GET /api/v1/query/detail?type=avatar|region|sect&id=<target_id>`
- `POST /api/v1/command/game/start`
- `POST /api/v1/command/avatar/*`
- `POST /api/v1/command/world/*`

最小接入流程通常是：

1. 先调用 `GET /api/v1/query/runtime/status` 判断当前运行状态。
2. 如未开局，调用 `POST /api/v1/command/game/start` 初始化。
3. 用 `world/state`、`events`、`detail` 拉取世界快照与目标信息。
4. 根据策略调用一个 `command` 执行干预。
5. 干预后重新 `query`，不要依赖本地缓存推断结果。

接口成功时通常返回：

```json
{
  "ok": true,
  "data": {}
}
```

失败时会返回结构化错误，可读取 `detail.code` 与 `detail.message` 做程序判断。

补充说明：

- 应用设置仍通过 `/api/settings*` 与 `/api/settings/llm*` 管理，它们属于设置真源，不属于外接控制兼容层。
- 更完整的接口清单、分层设计与扩展约定请参考 `docs/specs/external-control-api.md`。

</details>

### 💭 为什么要做这个？
修仙网文中的世界很精彩，但读者永远只能观察到一隅。

修仙品类游戏要么是完全的预设剧本，要么依靠人工设计的简单规则状态机，有许许多多牵强和降智的表现。

在大语言模型出现后，让“每一个角色都是鲜活的”的目标变得似乎可以触达了。

希望能够创造出纯粹的、快乐的、直接的、活着的修仙世界的沉浸感。不是像一些游戏公司的纯粹宣传工具，也不是像斯坦福小镇那样的纯粹研究，而是能给玩家提供真实代入感和沉浸感的实际世界。

## 📞 联系方式
如果您对项目有任何问题或建议，欢迎提交 Issue。

- **Bilibili**: [点击关注](https://space.bilibili.com/527346837)
- **QQ群**: `1071821688` (入群答案：肥桥今天吃什么)
- **Discord**: [加入社区](https://discord.gg/3Wnjvc7K)

---


## ⭐ Star History

如果你觉得这个项目有趣，请给我们一个 Star ⭐！这将激励我们持续改进和添加新功能。

<div align="center">
  <a href="https://star-history.com/#4thfever/cultivation-world-simulator&Date">
    <img src="https://api.star-history.com/svg?repos=4thfever/cultivation-world-simulator&type=Date" alt="Star History Chart" width="600">
  </a>
</div>

# 分享

感谢贡献者为本 repo 贡献分享。

- [cultivation-world-simulator-api-skill](https://github.com/RealityError/cultivation-world-simulator-api-skill)
- [cultivation-world-simulator-android](https://github.com/RealityError/cultivation-world-simulator-android)
- [LINUX DO 社区分享帖](https://linux.do/t/topic/2439437)

## 👥 贡献者

<table>
  <tr>
    <td align="center"><a href="https://github.com/4thfever"><img src="https://avatars.githubusercontent.com/u/19970391?v=4" width="56" height="56" alt="4thfever" /><br /><sub><b>4thfever</b></sub></a></td>
    <td align="center"><a href="https://github.com/xzhseh"><img src="https://avatars.githubusercontent.com/u/91381303?v=4" width="56" height="56" alt="xzhseh" /><br /><sub><b>xzhseh</b></sub></a></td>
    <td align="center"><a href="https://github.com/teps3105"><img src="https://avatars.githubusercontent.com/u/16871632?v=4" width="56" height="56" alt="teps3105" /><br /><sub><b>teps3105</b></sub></a></td>
    <td align="center"><a href="https://github.com/Meanliss"><img src="https://avatars.githubusercontent.com/u/117923713?v=4" width="56" height="56" alt="Meanliss" /><br /><sub><b>Meanliss</b></sub></a></td>
    <td align="center"><a href="https://github.com/octo-patch"><img src="https://avatars.githubusercontent.com/u/266937838?v=4" width="56" height="56" alt="octo-patch" /><br /><sub><b>octo-patch</b></sub></a></td>
    <td align="center"><a href="https://github.com/cooleryu"><img src="https://avatars.githubusercontent.com/u/53998515?v=4" width="56" height="56" alt="cooleryu" /><br /><sub><b>cooleryu</b></sub></a></td>
    <td align="center"><a href="https://github.com/LuckVd"><img src="https://avatars.githubusercontent.com/u/37114923?v=4" width="56" height="56" alt="LuckVd" /><br /><sub><b>LuckVd</b></sub></a></td>
  </tr>
  <tr>
    <td align="center"><a href="https://github.com/MarkYangKp"><img src="https://avatars.githubusercontent.com/u/42310488?v=4" width="56" height="56" alt="MarkYangKp" /><br /><sub><b>MarkYangKp</b></sub></a></td>
    <td align="center"><a href="https://github.com/Robinwhliu"><img src="https://avatars.githubusercontent.com/u/86167266?v=4" width="56" height="56" alt="Robinwhliu" /><br /><sub><b>Robinwhliu</b></sub></a></td>
    <td align="center"><a href="https://github.com/Seafoodsz"><img src="https://avatars.githubusercontent.com/u/13925953?v=4" width="56" height="56" alt="Seafoodsz" /><br /><sub><b>Seafoodsz</b></sub></a></td>
    <td align="center"><a href="https://github.com/Tianrant"><img src="https://avatars.githubusercontent.com/u/260025727?v=4" width="56" height="56" alt="Tianrant" /><br /><sub><b>Tianrant</b></sub></a></td>
    <td align="center"><a href="https://github.com/cw1990"><img src="https://avatars.githubusercontent.com/u/10458746?v=4" width="56" height="56" alt="cw1990" /><br /><sub><b>cw1990</b></sub></a></td>
    <td align="center"><a href="https://github.com/RealityError"><img src="https://avatars.githubusercontent.com/u/67266280?v=4" width="56" height="56" alt="RealityError" /><br /><sub><b>RealityError</b></sub></a></td>
    <td align="center"><a href="https://github.com/mitsuko33000-ops"><img src="https://avatars.githubusercontent.com/u/270795383?v=4" width="56" height="56" alt="mitsuko33000-ops" /><br /><sub><b>mitsuko33000-ops</b></sub></a></td>
  </tr>
</table>

更多贡献细节请查看 [CONTRIBUTORS.md](CONTRIBUTORS.md)。

## 📋 功能开发进度

### 🏗️ 基础系统
- ✅ 基础世界地图、时间、事件系统
- ✅ 多样化地形类型（平原、山脉、森林、沙漠、水域等）
- ✅ 基于Web前端显示界面
- ✅ 基础模拟器框架
- ✅ 配置文件
- ✅ 桌面版一键启动包
- ✅ 菜单栏 & 存档 & 读档
- ✅ 灵活自定义LLM接口
- ✅ 支持mac os
- ✅ 多语言本地化
- ✅ 开始游戏页
- ✅ BGM & 音效
- ✅ 玩家可编辑
- ✅ 扮演模式

### 🗺️ 世界系统
- ✅ 基础tile地块系统
- ✅ 基础区域、修行区域、城市区域、宗门区域
- ✅ 同地块NPC交互
- ✅ 灵气分布与产出设计
- ✅ 世界事件
- ✅ 天地人榜
- ✅ 更大更美观地图 & 随机地图

### 👤 角色系统
- ✅ 角色基础属性系统
- ✅ 修炼境界体系
- ✅ 灵根系统
- ✅ 基础移动动作
- ✅ 角色特质与性格
- ✅ 境界突破机制
- ✅ 角色间的相互关系
- ✅ 角色交互范围
- ✅ 角色Effects系统：增益/减益效果
- ✅ 功法
- ✅ 兵器 & 辅助装备
- ✅ 外挂系统
- ✅ 丹药
- ✅ 角色长短期记忆
- ✅ 角色的长短期目标，支持玩家主动设定
- ✅ 角色绰号
- ✅ 生活技能
  - ✅ 采集、狩猎、采矿、种植
  - ✅ 铸造
  - ✅ 炼丹
- ✅ 凡人

### 🏛️ 组织
- ✅ 宗门
  - ✅ 设定、功法、疗伤、驻地、行事风格、任务
  - ✅ 宗门特殊动作：合欢宗（双修），百兽宗（御兽）等
  - ✅ 宗门等阶
  - ✅ 道统
- ✅ 朝廷
- ✅ 组织意志AI
- ✅ 组织任务、资源、机能
- ✅ 组织间关系网络

### ⚡ 动作系统
- ✅ 基础移动动作
- ✅ 动作执行框架
- ✅ 有明确规则的定义动作
- ✅ 长动作执行和结算系统
  - ✅ 支持多月份持续的动作（如修炼、突破、游戏等）
  - ✅ 动作完成时的自动结算机制
- ✅ 多人动作：动作发起与动作响应
- ✅ 影响人际关系的LLM动作
- ✅ 系统性的动作注册与运行逻辑

### 🎭 事件系统
- ✅ 天地灵气变动
- ✅ 多人大事件：
  - ✅ 拍卖会
  - ✅ 秘境探索
  - ✅ 天下武道会
  - ✅ 宗门传道大会
- [ ] 突发事件
  - [ ] 宝物/洞府出世
  - [ ] 天灾

### ⚔️ 战斗系统
- ✅ 优劣互克关系
- ✅ 胜率计算系统

### 🎒 物品系统
- ✅ 基础物品、灵石框架
- ✅ 物品交易机制

### 🌿 生态系统
- ✅ 动植物
- ✅ 狩猎、采集、材料系统
- ✅ 妖族

### 🤖 AI增强系统
- ✅ LLM接口集成
- ✅ 角色AI系统（规则AI + LLM AI）
- ✅ 协程化决策机制，异步运行，多线程加速ai决策
- ✅ 长期规划和目标导向行为
- ✅ 突发动作响应系统（对外界刺激的即时反应）
- ✅ LLM驱动的NPC对话、思考、互动
- ✅ LLM生成小片段剧情
- ✅ 根据任务需求分别接入max/flash模型
- ✅ 小剧场
  - ✅ 战斗小剧场
  - ✅ 对话小剧场
  - ✅ 小剧场不同文字风格
- ✅ 一次性选择（如是否要切换功法）

### 🏛️ 世界背景系统
- ✅ 注入基础世界知识
- ✅ 用户输入历史，动态生成功法、装备、宗门、区域信息

### ✨ 特殊
- ✅ 奇遇
- ✅ 天劫 & 心魔
- ✅ 命格
- ✅ 阵法
- ✅ 蛊
- ✅ 机缘
- ✅ 世界秘密
- ✅ POI
- ✅ 背景板NPC
- [ ] 飞升上界

### 🔭 远期展望
- [ ] 开宗立派/成为皇帝
- [ ] 历史/事件的小说化&图片化&视频化
- [ ] Skill agent化，修士自行规划、分析、调用工具、决策
- [ ] 将自己的Claw配入修仙世界
