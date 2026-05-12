# 读后无书 · YouMind 适配版

> YouMind 不是用来替代 Hermes/OpenClaw 的——它是产品的**云端工作台 / 日常推送层**。

## 分层架构

```
┌──────────────────────────────────────────────────────────┐
│  YouMind   ← 云端轻量层：定时推送、私有 skill 库、对话产出 │
│   - 每日浸泡（定时推送到微信/Telegram/Lark）              │
│   - 内容拆解（生成文档供本地同步）                       │
│   - 结构审视（判断 + 提案，不动文件）                    │
└────────────────────────┬─────────────────────────────────┘
                         │  同步
                         ▼
┌──────────────────────────────────────────────────────────┐
│  本地：Hermes / OpenClaw / Claude Code                    │
│   - 真正的文件读写（$TWB_ROOT/books, dao, wiki）          │
│   - Python 脚本（compile, parse, validate）              │
│   - Obsidian 集成                                        │
│   - 把 YouMind 的产出落库                                │
└──────────────────────────────────────────────────────────┘
```

## 为什么要这样分

YouMind 的 `createSkill` API 只接受 **1-10 个纯文本 instruction step**，没有：
- 本地文件系统读写
- Python 子进程
- 多 Agent 并行调度
- 长程文件操作

但 YouMind 有 Hermes/OpenClaw 不擅长的东西：
- **定时任务**（每天早上 8 点推送今日之道）
- **跨平台 dispatch**（微信 / Telegram / Lark / YouMind board）
- **云端文档管理**（Material → Document workflow）
- **零安装**（用户没装 Claude Code 也能在 YouMind 网页用）

所以最合理的分工：

| 维度 | YouMind 负责 | 本地（Hermes/Claude）负责 |
|---|---|---|
| 每日浸泡推送 | ✓ 定时任务 + dispatch | — |
| 一次性浸泡对话 | ✓ Chat skill | ✓（也行）|
| 拆书生成内容 | ✓ 产出 markdown 文档 | — |
| 拆书结果落库 | — | ✓ 写 `$TWB_ROOT/books/` |
| 结构判断（找候选道、健康度） | ✓ | — |
| 结构改写（改 `道.md`、跑 compile） | — | ✓ |
| Wiki 草稿生成 | ✓ | — |
| Wiki 文件写入 | — | ✓ |

## 部署步骤（给另一台机器的 Hermes Agent）

详见 [DEPLOY.md](./DEPLOY.md)。

简短版：把这份内容**整段**贴给那台 Hermes：

> 请用 YouMind MCP 工具部署 `~/.talk-without-book/youmind/` 下的资源：
> 1. 上传 `materials/framework.md` 和 `materials/道.md`（如本地有 `$TWB_ROOT/dao/道.md` 则用之，否则用 template）
> 2. 创建三个私有 skill：daily、extract、structure（用 `skills/*.md` 里的 instructions）
> 3. 创建一个 scheduled task：每天早上 8 点跑 daily skill
> 4. 全部完成后告诉我每个 skill 的 ID 和 board URL

## 文件清单

```
youmind/
├── README.md                  ← 本文件
├── DEPLOY.md                  ← 详细部署指令（给 Hermes 用）
├── board-structure.md         ← 推荐的 YouMind board 结构
├── scheduled-task.md          ← 每日推送任务配置
├── skills/
│   ├── daily.md               ← 每日浸泡 skill（YouMind 适配）
│   ├── extract.md             ← 内容拆解 skill
│   └── structure.md           ← 结构审视 skill
└── materials/
    ├── framework.md           ← 道法术器势 框架（上传为 material）
    └── 道.md.template         ← 空道库模板
```
