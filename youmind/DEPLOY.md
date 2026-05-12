# YouMind 部署指令

> 把这份内容贴给你**另一台机器上配好了 YOUMIND_API_KEY 的 Hermes Agent**，它就会自动部署。

---

## 任务

请用 YouMind MCP 工具部署「读后无书」的云端版本到我的 YouMind 账户。所有材料在本地：

```
$INSTALL_DIR/youmind/
├── skills/{daily,extract,structure}.md
├── materials/framework.md
├── materials/道.md.template
├── board-structure.md
└── scheduled-task.md
```

其中 `$INSTALL_DIR` 就是 `~/.talk-without-book/`（你之前装在这里）。

## 步骤

### Step 1：创建 board

```typescript
const board = await youmind.createBoard({
  name: "读后无书 Skill 工作台",
  description: "读后无书（talk without book）的云端工作台。三个私有 skill + 道库 + 浸泡日历。",
  visibility: "private"
})
```

记下 `board.id`。

### Step 2：上传基础材料

```typescript
// framework.md
await youmind.createMaterialByUrl({
  board_id: board.id,
  // 如果 youmind 不支持本地文件直接上传，可以读文件内容然后用 createDocumentByMarkdown 作为材料
  source: "$INSTALL_DIR/youmind/materials/framework.md",
  name: "framework.md"
})

// 道.md：优先用本地真实道库
const realDao = "$TWB_ROOT/dao/道.md"
const templateDao = "$INSTALL_DIR/youmind/materials/道.md.template"
const daoSource = fs.exists(realDao) ? realDao : templateDao
await youmind.createMaterialByUrl({
  board_id: board.id,
  source: daoSource,
  name: "道.md"
})
```

### Step 3：创建三个 skill

读 `$INSTALL_DIR/youmind/skills/daily.md`，从中**提取 "instructions" 一节下的 1-7 步**，作为 createSkill 的 instructions 参数：

```typescript
// daily skill
const dailySkillContent = fs.read("$INSTALL_DIR/youmind/skills/daily.md")
const dailyInstructions = parseInstructionsSteps(dailySkillContent)  // 1-7 步

const dailySkill = await youmind.createSkill({
  name: "读后无书每日浸泡",
  display_name: "读后无书 · 每日浸泡",
  description: "每天抽一条道 + 检索问题，引导用户做今日浸泡。读 board 里的 道.md 材料；用户响应后帮助具象化并保存为文档。",
  instructions: dailyInstructions,
  tags: ["reading", "immersion", "daily", "dao"],
  category: "知识 / 个人成长",
  visibility: "private",
  board_id: board.id
})

// extract skill
const extractSkill = await youmind.createSkill({
  name: "读后无书内容拆解",
  ...
})

// structure skill  
const structureSkill = await youmind.createSkill({
  name: "读后无书结构审视",
  ...
})
```

### Step 4：创建定时任务

```typescript
const task = await youmind.createScheduledTask({
  name: "读后无书 · 每日之道推送",
  cron: "0 8 * * *",                    // 每天早上 8 点
  skill_id: dailySkill.id,
  prompt: "请按 `读后无书每日浸泡` skill 的步骤 1-4 跑一遍，生成今日浸泡卡片。不等待我的回应，直接 dispatch 出去。",
  dispatch: ["youmind", "telegram"]      // 按用户偏好调整
})
```

如果用户没有配 Telegram bot，先只 dispatch 到 `["youmind"]`，让 board 里有记录即可。

### Step 5：写入工作台说明文档

```typescript
await youmind.createDocumentByMarkdown({
  board_id: board.id,
  name: "00 · 工作台导览",
  content: fs.read("$INSTALL_DIR/youmind/board-structure.md")
})

await youmind.createDocumentByMarkdown({
  board_id: board.id,
  name: "00 · 同步规则",
  content: <board-structure.md 里"同步规则约定"那一节的内容>
})
```

### Step 6：报告结果给用户

完成后给用户一份清单：

```
✅ 读后无书 YouMind 部署完成

📁 Board：读后无书 Skill 工作台
   URL: {board.url}

🛠 三个私有 skill：
   - 读后无书每日浸泡   ID: {dailySkill.id}
   - 读后无书内容拆解   ID: {extractSkill.id}
   - 读后无书结构审视   ID: {structureSkill.id}

⏰ 定时任务：
   - 每天 08:00 推送今日之道
   - dispatch: YouMind + Telegram
   - URL: {task.url}

📤 同步策略：
   - YouMind 上沉淀的浸泡记录 → 本地 $TWB_ROOT/dao/journal/道N.md（由 Hermes 定期拉）
   - 本地 $TWB_ROOT/dao/道.md 变更 → YouMind 上的 道.md material（由 Hermes 推）

下一步：
   - 试触发一次：在 YouMind 里说"今天的道"
   - 检查 Telegram 是否收到（如果配置了）
   - 拆一本书：在 YouMind chat 里调用「读后无书内容拆解」skill
```

## 如果遇到 API 不一致

YouMind API 可能演化。如果上面的字段名跟你看到的不一致，按你的工具实际签名为准，**保留语义**：
- "创建一个有 N 步 instructions 的私有 skill" → 关键
- "skill 的 instructions 来自 daily.md 里 `## instructions` 节下的 1-7 步" → 关键
- "scheduled task 每天 8 点跑这个 skill" → 关键

不要把 `daily.md`（这个文件本身）作为 instructions 整段塞进去——它有 metadata、约束、说明部分。只取 `## instructions（...）` 那一节下面的编号列表。

## 给用户的最终交互

部署完成后，告诉用户：

> 你现在可以在 YouMind 网页打开 board "读后无书 Skill 工作台"。明天早上 8 点，今日之道会自动推送到你的 Telegram/YouMind。
>
> 如果想立刻试一次，在 YouMind chat 里说"今天的道"——会触发 daily skill 跑一遍。
