# YouMind Board 结构：读后无书 Skill 工作台

> 推荐的 board 组织方式。给 Hermes 部署时作为参考。

## Board 元数据

```yaml
name: 读后无书 Skill 工作台
description: 读后无书（talk without book）的云端工作台。三个私有 skill + 道库 + 浸泡日历。
visibility: private  # 或 unlisted，按你的偏好
```

## 文件组织

```
读后无书 Skill 工作台/
│
├── 📌 00-框架与说明/
│   ├── README.md                  ← 工作台导览
│   ├── METHODOLOGY.md             ← 道法术器势 详解
│   └── 同步规则.md                ← YouMind ↔ 本地 Hermes 同步约定
│
├── 📚 01-道库与材料/
│   ├── framework.md (material)    ← 上传：道法术器势 判定规则
│   ├── 道.md (material)           ← 上传：用户的当前道库（核心）
│   ├── 《Same as Ever》· 法.md    ← 拆完一本书后，5 份文档归在这里
│   ├── 《Same as Ever》· 术.md
│   ├── ...
│
├── 🌱 02-每日浸泡记录/             ← scheduled task 和 daily skill 写入这里
│   ├── 2026-05-12 · 道7 浸泡.md
│   ├── 2026-05-13 · 道1 浸泡.md
│   └── ...
│
├── 📐 03-结构提案/                ← structure skill 产出
│   ├── 提案 2026-05-12 · 候选道评审.md
│   ├── 提案 2026-05-14 · 道4 Wiki 草稿.md
│   └── ...
│
└── 🛠 04-Skill 定义/              ← skill 本身（YouMind 的 skill 也算 board 资源）
    ├── 读后无书每日浸泡
    ├── 读后无书内容拆解
    └── 读后无书结构审视
```

## 关键 material 的初始化

### `framework.md` 

来源：复制本仓库的 `skills/twb-extract/framework.md` 内容，作为 YouMind material 上传。

### `道.md`

两种情况：

- **如果用户在本地已经有道库**（`$TWB_ROOT/dao/道.md`）：
  让 Hermes 把它作为 material 上传到 YouMind board。这样 YouMind 上的浸泡和本地保持一致。

- **如果用户是 YouMind-only（没装本地 Hermes/Claude）**：
  上传本仓库的 `youmind/materials/道.md.template`——一个空骨架，用户后续填充自己的道。

## 同步规则约定

写在 `00-框架与说明/同步规则.md` 里：

```markdown
# YouMind ↔ 本地同步规则

## 写入方向：YouMind → 本地

每次 YouMind 上的活动结束时（人工或定时）：
1. Hermes 从 YouMind 拉取新的 documents
2. 按文档类型分发到本地：
   - 每日浸泡记录 → 追加到 `$TWB_ROOT/dao/journal/道N.md`
   - 内容拆解 5 份 → 写入 `$TWB_ROOT/books/{书名}/`（用户确认后）
   - 结构提案 → 不自动写入，仅留作参考；用户决定后让 Hermes 改 `道.md`

## 写入方向：本地 → YouMind

每次本地 `道.md` 更新时：
1. Hermes 检测到变更
2. 用 YouMind API 更新 board 里的 `道.md` material
3. 这样下次浸泡用的是最新版

## 冲突解决

YouMind 是"窗口"，本地是"源"。任何冲突以本地为准。
特例：YouMind 上沉淀的浸泡记录优先于本地——因为那是用户在云端写的，时间戳晚。
```

## 跨平台 dispatch 设置

scheduled task 创建后，按以下任一种方式接收每日推送：

- **Telegram**：在 YouMind 设置里绑定你的 Telegram bot（@YouMindBot 或自建）
- **微信**：绑定企业微信或服务号
- **Lark**：绑定你的飞书工作空间
- **YouMind 网页**：默认就行，在 board 里看「02-每日浸泡记录」即可
