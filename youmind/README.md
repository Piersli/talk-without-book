# 读后无书 · YouMind 版

> 三个 skill **完全在 YouMind 内执行**——不依赖本地，不需要装 Python，不需要 Claude Code。
>
> 你的 YouMind board = 你的整个知识库。

## 两种使用路径

读后无书现在有两条独立可用的路径：

### 路径 A：纯 YouMind（这里说的）

**适合**：不想装东西、只用 YouMind 网页/手机的人。

完整闭环在云端：
- **twb-extract**：上传一本书 → 生成 5 份节点文档（法/术/器/势/meta）到 board
- **twb-structure**：扫所有书 → 更新 `道.md` material → 生成 Wiki 文档
- **twb-daily**：每天 8 点定时推送今日之道到你绑定的通道（Telegram/微信/Lark）→ 你回应 → 沉淀成浸泡记录文档

你的所有知识资产都在 YouMind board 里。导出/备份用 YouMind 自己的导出功能。

### 路径 B：本地 + YouMind（混合）

**适合**：想要 Obsidian 集成、想要 Python 脚本的可控性、想要 1000 本书级别的处理速度的人。

- 本地 Hermes/Claude/OpenClaw 装了三个原版 skill（用 Python 脚本）
- YouMind 装了这三个云端版 skill 主要做定时推送
- 两层通过 Hermes 同步：本地是 source of truth，YouMind 是浸泡入口

详见仓库根目录的 [README.md](../README.md)。

## 路径 A 的部署

把 [DEPLOY.md](./DEPLOY.md) 整段贴给一个**配好了 YOUMIND_API_KEY** 的 agent（任意 Hermes / Claude Code 都行），它会：

1. 创建 board「读后无书 Skill 工作台」
2. 上传 `framework.md` 作为 material
3. 上传 `道.md.template`（如本地有真实道库则用本地版本）作为 material
4. 创建三个私有 skill：daily、extract、structure
5. 创建每日 8 点的 scheduled task
6. 给你部署报告

## 路径 A 的工作流

### 0→1：第一次用

```
[在 YouMind chat 里]
用户：拆解 [上传一本 PDF]
→ 触发 读后无书内容拆解 skill
→ skill 读取你上传的书 + framework.md + 当前 道.md（空）
→ 输出 5 份 documents 到 board

用户：审视道库
→ 触发 读后无书结构整理 skill（A 健康度模式）
→ 报告：这本书没触碰任何现有道（因为初始空）
→ 建议：用 "看候选道" 让我从这本书里识别道

用户：看候选道
→ 触发 读后无书结构整理 skill（B 候选道评审模式）
→ 给出 7-10 个候选道建议
→ 用户挑出 3-5 个

用户：把这 5 个并进来
→ 触发 读后无书结构整理 skill（F 道.md 更新模式）
→ 显示具体 diff
→ 用户确认
→ updateMaterial(道.md) 真实写入
→ 从明天起，定时任务会推这些道
```

### 日常：每天浸泡

```
[早上 8 点 · 自动]
你的 Telegram/微信收到：
  "今日之道 · 5月12日 · 周二
   道3：人性的核心参数在进化时间尺度上是常数
   ...
   今日提问：你最近一次想'这次不一样'——事后看是哪个老剧本？"

[10 分钟后 · 你在 Telegram 回复]
"昨天看到 AI 创业潮，又想是不是要 all in。其实跟 2017 的区块链、2021 的元宇宙是同一个剧本——
 我每次都信'这次不一样'，每次都因此走过弯路。"

[YouMind 自动接住]
→ 进入 daily skill 的 step 5-7
→ 评估：回应足够具体
→ 创建 document「2026-05-12 · 道3 浸泡」
→ 在 board 里沉淀

[未来某天 · 你想回顾]
你：翻翻过去 道3
→ 列出你对道3 的所有浸泡记录
→ 找模式、找演变
```

### 周期性：道库结构治理

```
[每月一次或想到时]
你：审视道库健康度
→ 报告：道2 已有 3 个月未被触碰；候选道 N=2 个有充分支撑；某条法的因果机制看似偏抽象

你：那把这 2 个候选道升格
→ 显示 diff
→ 你确认
→ updateMaterial 真实修改
→ 完成
```

## 关键设计选择

1. **YouMind board = 文件系统**。没有 `$TWB_ROOT/dao/道.md`，只有 board 里的 `道.md` material。所有"读写"通过 YouMind 的 listFiles / updateMaterial / createDocument。

2. **LLM 替代 Python**。compile.py / parse.py / validate.py 这些本地脚本所做的事，YouMind 里由 skill 内的 LLM 直接做：解析、综合、校验。

3. **每个 skill 自包含**。daily 不调用 extract，extract 不调用 structure。它们靠 board 里的文件系统传递状态。一个用户可以只用 daily（导入别人的道库），不需要拆书。

4. **道是脊**。`道.md` material 的任何更新必须用户明确同意。即使 LLM 高置信度认为应该新增/合并某条道，也只是提议。

## 文件清单

```
youmind/
├── README.md          ← 本文件（YouMind 版本的产品哲学）
├── DEPLOY.md          ← 自动部署指令（给配了 YOUMIND_API_KEY 的 agent 用）
├── board-structure.md ← 推荐的 board 组织方式
├── scheduled-task.md  ← 每日推送任务配置
├── skills/
│   ├── daily.md       ← 每日浸泡（7 步）
│   ├── extract.md     ← 内容拆解（10 步）
│   └── structure.md   ← 结构整理 · 完整执行版（10 步）
└── materials/
    ├── framework.md → symlink → 主仓库的 framework.md
    └── 道.md.template ← 空骨架
```
