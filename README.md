# 读后无书 · talk without book

> 让你读过的书脱离原文也能存在——最终你无需翻书也能深度思考。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Skills Standard](https://img.shields.io/badge/agentskills.io-compatible-blue.svg)](https://agentskills.io)
[![Claude Code](https://img.shields.io/badge/Claude_Code-✓-orange.svg)](https://claude.ai/code)
[![Hermes Agent](https://img.shields.io/badge/Hermes_Agent-✓-purple.svg)](https://hermes-agent.org)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-✓-red.svg)](https://openclaw.ai)

---

## 这是什么

读后无书是一套**方法论 + 三个独立可组合的 Claude Code skill**——让喜欢读书且想沉淀知识结构系统的人，把读过的书收敛成自己的「道」体系，最终达到"无需翻书也能深度思考"的境界。

## 为什么叫这个名字

读完一本好书后，最有价值的不是你能引用它的哪一页，而是**这本书改变了你怎么思考**。

那种改变如果真的发生了——你就不再需要翻书。书里的道理已经长进你自己，遇到新问题它会浮现，遇到旧选择它会校正。**你和它的对话不需要回到原文。**

「读后无书」就是这件事的工程化版本：用一套方法论 + 三个工具，帮你把读完的书变成你自己的思考装置。

工具叫 `twb`（**t**alk **w**ithout **b**ook），方向是"读后无书"。

## 给谁用

- 喜欢读书
- 想沉淀知识结构系统
- 不甘心"读完就忘"
- 愿意慢一点、深一点

不是给：想快速摘要的人、只想要 ChatGPT 帮我读完一本书的人、要做学术引用管理的人。

## 道法术器势 — 固定的 schema

读后无书围绕一个固定的五维框架展开。**这是产品的不变量，所有使用者共享同一套 schema**：

| 维度 | 一句话 | 来源 |
|---|---|---|
| **道** | 永恒不变的底层真相（人性 / 世界 / 关系类） | 跨多本书才能收敛 |
| **法** | 从道衍生的、有失效条件的因果规律 | 单本书可识别 |
| **术** | 具体可行动的方法、策略 | 单本书可识别 |
| **器** | 工具、模板、案例、分类框架 | 单本书可识别 |
| **势** | 条件、边界、趋势判断 | 单本书可识别 |

**道是脊**——它是所有书共同指向的少数几条永恒真相，是你"无需翻书"时脑子里自动浮现的那个东西。

具体每一维度的判别和质量标准见 [METHODOLOGY.md](./METHODOLOGY.md)。

## 三件套——独立可用，组合更强

```
  twb:extract       twb:structure        twb:daily
  ─────────         ─────────            ─────────
  一本书             多本书的节点          道索引
     ↓                  ↓                   ↓
  本书的节点          全局道 + Wiki        浸泡式对话陪伴
   (法/术/器/势)       (跨书收敛)            (内化)
```

| skill | 单独的价值主张 | 谁会用 |
|---|---|---|
| [**twb:extract**](./skills/twb-extract/) | 帮我把一本书读透 | 任何不甘心"读完就忘"的人 |
| [**twb:structure**](./skills/twb-structure/) | 帮我找出我读过的书共同指向的道 | 读了足够多书、想要综合的人 |
| [**twb:daily**](./skills/twb-daily/) | 帮我把已沉淀的智慧每天活在思考里 | 手头有道库、想要日常浸泡的人 |

**用户可以只用一个，也可以三件套全用——自己选择走多远**。最少用法甚至可以跳过 extract 和 structure，直接用别人分享的道库做 daily 浸泡。

## 安装 — 一行搞定

### 方式 A：直接告诉 agent

复制下面这句话给你的 Claude Code / Hermes Agent / OpenClaw：

> 请把 `https://github.com/Piersli/talk-without-book` 这套 skill 装上：
> `curl -fsSL https://raw.githubusercontent.com/Piersli/talk-without-book/main/bootstrap.sh | bash`

agent 会自动跑安装脚本，**安装期间不需要离开对话**。

### 方式 B：终端一行

```bash
curl -fsSL https://raw.githubusercontent.com/Piersli/talk-without-book/main/bootstrap.sh | bash
```

### 方式 C：手动 clone

```bash
git clone https://github.com/Piersli/talk-without-book.git ~/读后无书
bash ~/读后无书/install.sh
```

### 方式 D：OpenClaw 用户

```bash
clawhub install talk-without-book
```
（前提：本仓库已提交到 ClawHub Registry——待办）

---

**前三种方式都会做同一件事**：自动检测你装了哪些 agent 平台，把三个 skill 部署到所有发现的位置：

- ✓ **Claude Code** → `~/.claude/skills/`（本地执行）
- ✓ **Hermes Agent** → `~/.hermes/skills/`（本地执行）
- ✓ **OpenClaw** → `~/.openclaw/skills/`（本地执行）

三个 skill 遵守 [agentskills.io 开放标准](https://agentskills.io)，跨平台兼容。详见 [INSTALL.md](./INSTALL.md)。

**前四种方式都做同一件事**：自动检测装了哪些 agent 平台，把三个 skill 部署到所有发现的位置：

- ✓ **Claude Code** → `~/.claude/skills/`
- ✓ **Hermes Agent** → `~/.hermes/skills/`
- ✓ **OpenClaw** → `~/.openclaw/skills/`

详见 [INSTALL.md](./INSTALL.md)。

## 怎么用 — 装完之后

跟你的 agent 说这些话：

```
今天的道                  → twb-daily 启动
拆解 /path/to/book.md     → twb-extract 启动
审视知识库                → twb-structure 启动
```

完整触发词速查见 [TRIGGERS.md](./TRIGGERS.md)。

## HTML 浏览界面

所有 markdown 产出物都会渲染为一份**衬线字体、奶白底、《每日斯多葛》风格**的 HTML 站点。

### 推荐：交互模式（一行直接写入）

```bash
python ~/.claude/skills/twb-structure/scripts/render_html.py $TWB_HOME --serve
```

会在 `http://127.0.0.1:8080` 起一个本地 server，自动打开浏览器。

- 在任意道的家页或今日页输入「记一笔」→ 按钮点一下
- **直接写入** `$TWB_HOME/dao/journal/道N.md`
- 立即重新渲染，新条目出现在"过往回响"里

### 静态模式（不需要保持 server 在跑）

```bash
python ~/.claude/skills/twb-structure/scripts/render_html.py $TWB_HOME
open $TWB_HOME/site/index.html
```

只读浏览。"记一笔"按钮会 fallback 为复制触发词到剪贴板（粘贴给 Agent 由 `twb:daily` skill 接住）。

### 站点结构

- `index.html` — 今日之道（入口）
- `dao/` — 所有的道（总览 + 每条道的家页，每条道的家页是 journal 的归宿）
- `books/` — 拆解过的书（书架 + 每本书的全部节点）
- `journal/index.html` — 浸泡记录跨道总览
- `_assets/style.css` + `_assets/script.js` — 共享资源

Markdown 永远是源，HTML 只是派生视图。Agent 和你共用同一份 markdown。

## 哲学

读后无书的设计有几条不变的原则。如果某天产品某个功能违反了这些，那个功能要被改掉，不是原则：

- **浸泡 > 查阅**：这不是"查"的工具，是"养"的工具
- **道是永恒资产**：所有功能为道服务，道为人的思考服务
- **每天只有一条**：广度让位于深度
- **追问 > 总结**：好的对话伙伴问得多，结论给得少
- **写入是承诺**：journal 是长期资产，宁可多追问一次也不写浮泛内容
- **得鱼忘筌**：工具最终目的是让你不需要它

## 状态

WIP。当前是作者本人 dogfood 阶段。**寻找愿意成为第一批使用者并反馈的读书人**。

## 协议

[待定]

## 致谢

灵感来源：
- Andrej Karpathy 的 [LLM Wiki 设计](https://karpathy.github.io/2025/...)（编译式知识架构）
- Steven Johnson 的 ["Magic Cards and Knowledge Bottles"](https://adjacentpossible.substack.com/...)（知识瓶 / Intelligence as Service）
- Andy Matuschak 的 ["Why Books Don't Work"](https://andymatuschak.org/books/) + Quantum Country（mnemonic medium）
- 《每日斯多葛》—— 一天一条的浸泡形态参考
- 中国传统"得鱼忘筌、得意忘言"
