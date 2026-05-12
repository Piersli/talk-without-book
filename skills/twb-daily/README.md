# twb:daily — 读后无书 · 每日浸泡

> **读后无书（talk without book）**：让你读过的书脱离原文也能存在，最终你无需翻书也能深度思考。

每日浸泡的对话伙伴——展示今日之道、追问你的回应、用道做第一性原理分析、回顾过往 journal。读后无书三件套的第三环。

## 安装

```bash
git clone <this-repo> ~/.claude/skills/twb-daily
```

或手动把 `SKILL.md` 放进 `~/.claude/skills/twb-daily/`。本 skill **无外部依赖、无脚本**——纯 markdown 行为指令。

## 知识库位置

skill 会按以下顺序查找：

1. `$TWB_HOME` 环境变量
2. `./读后无书/`、`~/读后无书/`、`~/Documents/读后无书/`

如果你还没有道索引（`$TWB_HOME/dao/道.md`），告诉你先用 `twb:extract` + `twb:structure` 建立。

## 使用

在 Claude Code 里说：

| 你说 | 行为 |
|---|---|
| `今天的道` 或 `今日` | 展示今日道 + 检索问题 + 过往 journal 摘要 |
| `我想到了 X...` 或 `记一笔` | 评估你的回应——浮泛会追问，具体直接沉淀到 journal |
| `用道想想 X 这个问题` | 用道做第一性原理分析（扫相关道、给压力测试问题） |
| `道N 让我想到 Y` | 围绕指定道对话，引用过往 journal 和书源 |
| `翻翻过去 道N` | 回顾你对某条道的全部历史，找模式、引代表段 |

## 设计哲学

- **浸泡 > 查阅**：不是知识助手，是有韵律的、慢的、个人的浸泡伙伴
- **追问 > 总结**：好的伙伴问得多，结论给得少
- **写入是承诺**：journal 是你的长期资产，宁可多追问一次也不写浮泛内容

## 可选的 cc 启动器集成

如果你用 macOS / Linux 并把 cc 启动器装上了，可以在终端启动时自动看到今日之道 banner，并用 `cc note <道N> "..."` 快速捕捉。

但 **cc 不是必需**——skill 在任何 Claude Code 会话里都可用。

## 组合关系

- 依赖：**`twb:extract`** 和 **`twb:structure`** 已经建好了 `dao/道.md` 和 journal 目录
- 本 skill 写入：`dao/journal/道N.md`（用户的回响记录）
