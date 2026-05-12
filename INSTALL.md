# 安装

读后无书是**三个 [agentskills.io](https://agentskills.io) 兼容的 skill** 的组合，可以在以下 agent 平台运行：

| 平台 | 安装目录 | 状态 |
|---|---|---|
| [Claude Code](https://claude.ai/code) | `~/.claude/skills/` | ✓ 已测 |
| [Hermes Agent](https://hermes-agent.org) | `~/.hermes/skills/` | ✓ 兼容 |
| [OpenClaw](https://openclaw.ai) | `~/.openclaw/skills/` | ✓ 兼容 |

`install.sh` 会**自动检测**你已经安装的平台并把 skill 部署到所有发现的位置。如果还没有任何 agent 平台，会问你是否要装到默认的 Claude Code 位置。

---

## 前置

- **Claude Code** 已安装并能跑（你正在用它读这份文档说明已经满足）
- **Python 3.10+**（仅 twb:structure 需要——跨书 LLM 综合时调用）
- **Anthropic API key**（仅 twb:structure 全量编译时需要；自用层面可以不设）

```bash
# 验证
which python3       # 至少 3.10
echo $ANTHROPIC_API_KEY  # 想用 structure 时再设
```

---

## 安装（推荐 · 一键）

```bash
# 1. 克隆
git clone <repo-url> ~/读后无书

# 2. 跑 install.sh（在 ~/.claude/skills/ 里建符号链接到本仓库）
bash ~/读后无书/install.sh
```

`install.sh` 做的事：
- 检查 `~/.claude/skills/` 存在（不存在则创建）
- 为三个 skill 各创建符号链接到本仓库的 `skills/twb-*/`
- 如果已存在同名 skill 会询问是否覆盖

完成后**重启 Claude Code 会话**——下条消息说 "今天的道"，应能触发 twb:daily。

---

## 安装（手动）

如果不想用 install.sh：

```bash
# 三个 skill 各自符号链接到 ~/.claude/skills/
ln -s ~/读后无书/skills/twb-extract  ~/.claude/skills/twb-extract
ln -s ~/读后无书/skills/twb-structure ~/.claude/skills/twb-structure
ln -s ~/读后无书/skills/twb-daily    ~/.claude/skills/twb-daily
```

或者直接复制（不用符号链接）：

```bash
cp -r ~/读后无书/skills/twb-* ~/.claude/skills/
```

---

## 第一次使用（最小路径）

### 路径 A：你已经有了别人分享的道库

最快路径——跳过 extract 和 structure，直接 daily 浸泡。

```bash
# 1. 把别人分享的道库放到你的知识库目录
mkdir -p ~/talkwithbook/dao
cp <shared-dao-file>.md ~/talkwithbook/dao/道.md

# 2. 在 Claude Code 里
说："今天的道"
```

### 路径 B：从零开始

```bash
# 1. 准备一本你想精读的书（PDF/EPUB/txt/md 都可）

# 2. 在 Claude Code 里
说："拆解 /path/to/your-book.md"
# → twb:extract skill 启动，引导你完成五阶段拆解

# 3. 拆完一本之后
说："审视知识库"
# → twb:structure skill 给你当前状态快照

# 4. 拆完三本以上之后
说："看看候选道"
# → twb:structure 帮你识别多本书共同指向的新道

# 5. 道库有内容后
说："今天的道"
# → twb:daily 开始每日浸泡
```

---

## 知识库目录约定

读后无书在以下位置查找你的知识库，**第一个匹配的就用**：

1. 环境变量 `$TWB_HOME`
2. `./talkwithbook/`（当前目录）
3. `~/talkwithbook/`（默认推荐位置）
4. `~/Documents/talkwithbook/`
5. `~/Desktop/claude-code/talkwithbook/`（老用户兼容）

知识库的目录结构：

```
$TWB_HOME/
├── dao/
│   ├── 道.md              # 全局道索引（核心文件）
│   └── journal/           # twb:daily 写入的回响记录
│       ├── 道1.md
│       └── ...
├── books/
│   ├── Book_Name_A/
│   │   ├── 法.md
│   │   ├── 术.md
│   │   ├── 器.md
│   │   ├── 势.md
│   │   └── meta.md
│   └── Book_Name_B/
├── wiki/                  # twb:structure 编译产出（可选）
│   ├── dao/
│   ├── topics/
│   ├── books/
│   └── cross/
├── site/                  # 浏览器浸泡页（可选）
│   └── index.html
└── .state/
    └── today.tsv          # 今日选了哪条道、哪个问题（多通道同步用）
```

`dao/道.md` 是必须的，其他都是按需生成。

---

## 验证安装

在 Claude Code 里说：

- `今天的道` → twb:daily 应当响应（即使道库为空也会给出空状态提示）
- `审视知识库` → twb:structure 应当响应
- `拆解 /tmp/不存在的书.md` → twb:extract 应当响应（会告诉你文件不存在）

三个 skill 都响应，说明安装成功。

---

## 卸载

```bash
rm ~/.claude/skills/twb-extract
rm ~/.claude/skills/twb-structure
rm ~/.claude/skills/twb-daily
# 如果用了符号链接以上就够了；如果是复制安装，也是同样命令
```

你的知识库数据（`~/talkwithbook/`）不会被删——它属于你。

---

## 常见问题

**Q: skill 安装后 Claude Code 不识别**
A: 重启 Claude Code 会话。skill 是会话启动时加载的。

**Q: 我想把知识库放在别处**
A: 设环境变量 `export TWB_HOME=/your/path`。

**Q: 我已经有 talkwithbook 老知识库**
A: 直接用，路径查找惯例会找到 `~/talkwithbook/` 或 `~/Desktop/claude-code/talkwithbook/`。

**Q: 我可以只装其中一个 skill 吗**
A: 可以。每个 skill 独立可用。常见组合：
- 只想精读单本书 → 只装 twb:extract
- 想要别人的道库做浸泡 → 只装 twb:daily
- 全套体验 → 三个都装
