# twb:structure — 读后无书 · 结构整理

> **读后无书（talk without book）**：让你读过的书脱离原文也能存在，最终你无需翻书也能深度思考。

把已拆解的书节点收敛成跨书结构——**道**的收敛、Wiki 编译、候选道评审。读后无书三件套的中间一环。

## 安装

```bash
git clone <this-repo> ~/.claude/skills/twb-structure
```

或手动把整个目录（含 `SKILL.md` 和 `scripts/` 子目录）放进 `~/.claude/skills/twb-structure/`。

确保拉下来的目录里**有 `scripts/` 子目录**——否则编译管线无法运行。

## 依赖

- **Python 3.10+**
- **`anthropic` 包**：`pip install anthropic`
- **`ANTHROPIC_API_KEY` 环境变量**：跨书 LLM 分析需要

## 知识库位置

skill 会按以下顺序查找：

1. `$TWB_HOME` 环境变量
2. `./读后无书/`、`~/读后无书/`、`~/Documents/读后无书/`

如果都没有，告诉用户先用 `twb:extract` 创建一个。

## 使用

在 Claude Code 里说：

| 你说 | 行为 |
|---|---|
| `审视知识库` | 给当前状态快照（不调 LLM、免费） |
| `把 X 这本书并进来` | 增量集成新拆解的书 |
| `重新编译` | 全量跑编译管线（要 ANTHROPIC_API_KEY、几分钟、付费） |
| `看看候选道` | 扫描所有节点找未充分归属的主题群 |
| `审视 X 这本书` | 单书健康度报告 |

## 关键约束

- **道索引（`$TWB_HOME/dao/道.md`）的修改永远需要用户确认**——skill 提议，用户拍板
- **快速优先**：能 parse 就不要 compile（parse 免费，compile 调 LLM API）

## 组合关系

- 上游：**`twb:extract`** 产生 `books/{Book}/{法,术,器,势}.md`
- 下游：本 skill 产生 `dao/道.md` + `wiki/`，喂给 **`twb:daily`** 做日常浸泡
