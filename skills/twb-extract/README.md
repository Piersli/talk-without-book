# twb:extract — 读后无书 · 内容拆解

> **读后无书（talk without book）**：让你读过的书脱离原文也能存在，最终你无需翻书也能深度思考。

把一本书拆解为**道法术器势**五维节点。读后无书三件套的第一环。

## 安装

```bash
git clone <this-repo> ~/.claude/skills/twb-extract
```

或手动把整个目录（含 `SKILL.md` 和 `framework.md`）放进 `~/.claude/skills/twb-extract/`。

## 知识库位置

skill 会按以下顺序查找你的 读后无书 知识库：

1. `$TWB_HOME` 环境变量
2. `./读后无书/`（当前目录）
3. `~/读后无书/`（推荐）
4. `~/Documents/读后无书/`

如果都没有，skill 会问你是不是要新建一个。

## 使用

在 Claude Code 里说：

```
拆解 /path/to/book.txt
```

或：

```
提取 ~/Downloads/同读.md 这本书
```

skill 会引导你完成五阶段拆解（Phase 1 阅读 → Phase 2 法 → Phase 3 术/器/势 → Phase 4 写入），输出到 `$TWB_HOME/books/{Book_Name}/`。

## 组合关系

- 拆完一本书后，建议跑 **`twb:structure`** 把它并入跨书结构、刷新 Wiki。
- 然后用 **`twb:daily`** 做每日浸泡。

三个 skill 互相独立，靠文件系统通信。
