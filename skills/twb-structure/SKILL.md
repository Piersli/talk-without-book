---
name: twb-structure
description: "Use when the user wants to integrate newly extracted books into the 读后无书 (talk without book) knowledge base, refresh cross-book structure, audit the knowledge base health, review candidate new 道, regenerate Wiki pages, or run the compile pipeline. Triggers on: '结构整理', '整理结构', '汇编', '编译知识库', '更新道', '看候选道', '审视知识库', '同步道库', '重新编译', '生成 wiki', '把新书并进来', '跨书分析'."
argument-hint: "[可选：'audit' | 'compile' | '候选道' | '审视书 <Book_Name>'，或自然语言]"
version: 0.1.0
author: Piersli
platforms: [macos, linux, windows]
required_environment_variables:
  - name: ANTHROPIC_API_KEY
    prompt: Anthropic API key (used for cross-book LLM analysis during full compile)
    help: https://console.anthropic.com/
    required_for: full compile (审视和增量集成可不调 LLM)
metadata:
  hermes:
    tags: [wiki, compilation, books, cross-book-analysis]
    category: knowledge
    requires_toolsets: [terminal, python]
  openclaw:
    tags: [wiki, compilation, knowledge]
    category: knowledge
---

# 读后无书 · 结构整理 skill

**读后无书（talk without book）** 三件套之一。

把已经被 `twb:extract` 拆解出来的书节点，**收敛成跨书结构**——找出多本书共同指向的「道」（永恒真相），生成 Wiki，建立跨书关联。

> 一本书的提取只是材料。当你读了三本、五本、二十本之后，**它们共同指向的那几条永恒真相**才是你真正可以带走的。
> 本 skill 帮你完成那次收敛——让你拥有自己的「道」体系，从此可以离开书来思考。

读后无书三件套：
- `twb:extract` — 单本书 → 本书的节点（法/术/器/势）
- **`twb:structure`** — 全部书的节点 → 全局道索引 + Wiki + 跨书页 ← **本 skill**
- `twb:daily` — 道库 → 浸泡式对话陪伴

三件套独立可用，组合更强。用户自己选择走多远。

## 数据路径

### 知识库根目录查找（**每次会话开始时必须做**）

按以下顺序查找，**第一个匹配的就是 `$TWB_ROOT`**：

1. 环境变量 `$TWB_HOME`
2. `./talkwithbook/`（当前工作目录）
3. `~/talkwithbook/`
4. `~/Documents/talkwithbook/`
5. `~/Desktop/claude-code/talkwithbook/`（老用户兼容）

如果都没找到，告诉用户："找不到 **读后无书** 知识库。要不要在 `~/talkwithbook` 创建一个？还是你的库在别处？"

### 用户数据（在 `$TWB_ROOT` 下）

读：
- `$TWB_ROOT/books/*/{法,术,器,势,meta}.md` — 各本书的节点（twb:extract 的产物）
- `$TWB_ROOT/dao/道.md` — 全局道索引
- `$TWB_ROOT/wiki/` — 已有的 Wiki 页（如果存在）

写：
- `$TWB_ROOT/dao/道.md` — **必须用户确认**才能增/改
- `$TWB_ROOT/wiki/...` — Wiki 页面

### Skill 自带的工具

工具脚本位于 **skill 自己的目录** `${SKILL_DIR}/scripts/`：
- `scripts/compile.py` — 完整编译管线（Phase 1-4）
- `scripts/parse.py` — 仅解析（不调 LLM）
- `scripts/validate.py` — 仅检查完整性
- `scripts/render.py`、`scripts/analyze.py`、`scripts/models.py` — 内部模块

调用方式（在 skill 内取自身路径）：
```bash
SKILL_DIR="$(dirname "$(realpath "${BASH_SOURCE[0]:-$0}")")"
python "$SKILL_DIR/scripts/compile.py" "$TWB_ROOT"
```

**如果 `${SKILL_DIR}/scripts/` 不存在**（说明部署不完整），告诉用户：
> skill 的脚本目录缺失。请到 GitHub 上重新下载本 skill，确保 `scripts/` 子目录被一起拉下来。

需要环境变量 `ANTHROPIC_API_KEY`（让 Claude API 做 LLM 分析和渲染）。如果没设置，告诉用户去设。

## 输入

<input>$ARGUMENTS</input>

## 意图判别

| 用户说 | 意图 |
|---|---|
| "审视知识库"、"audit"、空输入 | **A. 审视当前状态** |
| "把新书并进来"、"同步"、"刚拆了 X 书"、"compile" | **B. 增量集成（一本或几本新书）** |
| "重新编译"、"全量重生成 wiki"、"刷新整个知识库" | **C. 全量编译** |
| "候选道"、"看看有没有新道"、"道索引该不该加" | **D. 评审候选道** |
| "审视书 X"、"看看 X 这本书提的怎么样" | **E. 单书质量审视** |

**绝不**在用户没有明确请求时主动执行 C（全量编译）——它要花十几分钟和真金白银的 API 调用。

---

## A. 审视当前状态（默认动作）

### 步骤

1. 用 Bash 跑 `python "$SKILL_DIR/scripts/parse.py" "$TWB_ROOT"` —— 只解析，不调 LLM（快、便宜、无副作用）
2. 解析它的输出：道数、书数、各书的节点数、孤立节点、覆盖率
3. 检查 `$TWB_ROOT/wiki/` 是否存在、何时生成的
4. 输出**简洁的快照**，不要堆砌

### 输出格式

```
读后无书 知识库快照：

📚 书籍：{N} 本
  · {Book_A}    法{n} 术{n} 器{n} 势{n}
  · {Book_B}    ...

🎯 道索引：{N} 条
  最近触碰的：{道编号列表}
  最少触碰的：{道编号}（仅 {N} 本书引用）

📖 Wiki：{generated|stale|missing}
  上次生成：{date or "从未"}
  对比 $TWB_ROOT/books/ 最新变更：{up-to-date|out of sync}

⚠️ 异常（如有）：
  · 有 {N} 本书的节点没有上位道关系
  · 有 {N} 条道没有任何法
  · ...
```

末尾推荐**下一步动作**——根据快照判断：
- 如果 Wiki out of sync 且新书少：推荐增量集成（B）
- 如果 Wiki 严重过期或第一次：推荐全量编译（C）
- 如果发现孤立节点：建议看候选道（D）

---

## B. 增量集成（最常用）

用户刚跑完 `twb:extract` 拆完一本书，想把它并入知识库。

### 步骤

1. 确认是哪本书（看 `$TWB_ROOT/books/` 下最新的目录，或用户提到的名字）
2. **跑 parse 看看这本书的节点**（确认 twb:extract 输出合规）
3. **比对**：这本书的法节点，**哪些已经被现有道覆盖**？哪些**可能是候选新道**？
4. 把候选新道（即与现有 7 条道关联度都低的反复出现的主题）**列给用户**——**等用户决定**是否升格为道
5. 如果用户同意升格：手动编辑 `$TWB_ROOT/dao/道.md` 追加新道（含表述、检索问题、与其他道的关系），并更新原书的相关节点添加上位道引用
6. 跑 `python "$SKILL_DIR/scripts/compile.py" "$TWB_ROOT"` 重新生成 Wiki（让 LLM 把新书的视角并到各道页里）
7. 跑 validate 检查完整性
8. 汇报变更

### 关键原则

**绝不自动添加新道**——道是产品的脊，必须由用户判断。即使候选道在 5 本书里反复出现，也只是**候选**，要用户拍板。

候选道汇报格式：

```
我从 《{Book}》里识别到 {N} 个候选新道：

候选道 A：{临时标题}
  在本书的支撑：法{N}（标题）+ 法{M} 都在指向 {一句话主题}
  与现有道的关系：与道{X} 部分重合但角度不同（说明）
  我的判断：建议{升格|不升格}，理由：{...}

要不要把候选道 A 升为道{N+1}？
（或者你也可以让我把它合并到道{X} 里作为该道的新角度）
```

---

## C. 全量编译

完整跑 `$SKILL_DIR/scripts/compile.py`，所有 Wiki 页重新生成。

### 警告

跑之前**告诉用户**：
- 估计耗时：每本书约 1-2 分钟 LLM 调用
- 估计成本：每本书约 $0.05-0.15（Sonnet 价位）
- 现有 `$TWB_ROOT/wiki/` 内容会被覆盖（不可逆）

**只有用户明确同意才执行**。

### 执行

```bash
python "$SKILL_DIR/scripts/compile.py" "$TWB_ROOT"
```

执行时**展示进度**——compile.py 自己有 print 输出，转发给用户。

完成后跑 validate 检查完整性。Wiki markdown 已写入 `$TWB_ROOT/wiki/`。

**注意**：本 skill 不渲染 HTML。HTML 浏览界面是独立的姊妹仓库
（[读后无书 · 浸泡应用](https://github.com/Piersli/talk-without-book-app)）的职责。
如果用户已经装了那个 app，可以一句话提示"用浏览器看看新生成的 wiki"；
没装就不要主动建议——本 skill 的工作到生成 markdown 为止。

---

## D. 评审候选道

主动扫描所有书的节点，找出可能没被现有道覆盖的反复主题。

### 步骤

1. 跑 parse 加载所有节点
2. 把所有法（含上位道字段）列出来，找上位道空缺或勉强的
3. 用聚类思维把它们按主题分组
4. 对每个**没有清晰道归属**的主题群，写一个候选道提案
5. 与现有道做对比——是真新道，还是某个现有道的延伸？

### 输出

```
扫描了 {N} 条法，发现 {M} 个未充分归属的主题群：

主题群 1：{临时标题}
  涉及法：{Book}/法{X}, {Book}/法{Y}, {Book}/法{Z}
  共同的因果机制：{一句话}
  我的判断：
  - 与道{X} 距离：{...}
  - 与道{Y} 距离：{...}
  建议：{升格新道 | 并入道X | 暂留观察}
```

让用户对每个主题群单独决定。**不要批量处理**。

---

## E. 单书质量审视

用户提到某本书，想看它在知识库里的健康度。

### 检查项

- 这本书的法是否都有上位道？
- 法的因果机制写得是否具体（不只是道的同义复述）？
- 这本书触碰了几条道？强度如何？
- 在 Wiki 页里，这本书的视角是否被合理引用？
- 是否有孤立的术/器/势节点（缺上位关系）？

### 输出

```
《{Book}》健康度：

📐 结构完整性：
  · 法 {N} 条，全部有上位道：{Y/N}
  · 术 {N} 条，{有/部分有/无}上位法
  · 器 {N} 条，{有/部分有/无}上位术
  · 势 {N} 条

🎯 触碰强度：
  · 主触碰：道{X}（{N} 条法）、道{Y}（{N} 条法）
  · 弱触碰：道{Z}（仅 1 条法）

💡 改进建议（如有）：
  · 法{N} 的因果机制偏抽象，建议补具体案例
  · 术{N} 没有上位法，可能该重新归类
  · ...
```

---

## 关键约束（所有意图共用）

1. **道是脊**：$TWB_ROOT/dao/道.md 是产品最神圣的文件。**任何对它的修改必须先得到用户确认**——不能因为"我觉得这是新道"就自动写入。
2. **保留人类判断**：候选道筛选、合并决策、命名都是**用户的工作**。skill 给材料、给观察、给提议，但**最终决策权在用户**。
3. **快速优先慢动作**：parse 是免费的，能 parse 就不要 compile。validate 是免费的，多跑。compile 是贵的，谨慎跑。
4. **变更可追溯**：每次写 $TWB_ROOT/dao/道.md 之前，用户应该知道**改了什么**——展示 diff 思路：旧版本是什么、新版本是什么、为什么。
5. **不堆 emoji**：读后无书 是慢的、有质感的产品。汇报要冷静、清晰。
6. **失败明确**：如果 ANTHROPIC_API_KEY 没设、compile.py 跑挂了、parse 异常，**告诉用户具体原因**，不要假装成功。

---

## 与其他两个 skill 的协作

- 用户跑完 `twb:extract` 后，**主动建议**："拆完了。要不要现在 `twb:structure` 把它并进来？"
- 用户在 `twb:daily` 对话里发现一个反复出现的、现有道覆盖不到的主题时，**主动建议**："这可能是候选道。我们用 `twb:structure` 评审一下？"
- 三个 skill 之间的状态是文件系统——它们读同一组 markdown，写不同的目录，不共享内存，不共享 session。
