# 每日浸泡推送任务

YouMind 的 scheduled task 配置，配合 `读后无书每日浸泡` skill 使用。

## 任务定义

```yaml
name: 读后无书 · 每日之道推送
schedule:
  cron: "0 8 * * *"            # 每天早上 8:00（本地时区）
  # 也可以写成自然语言："every day at 8am"
skill: 读后无书每日浸泡        # 触发的 skill 名（要先创建）
prompt: |
  请按 `读后无书每日浸泡` skill 的步骤 1-4 跑一遍，
  生成今日浸泡卡片。无需等待我的回应，直接 dispatch 出去。
dispatch:
  - youmind                    # 保存到本 board
  - telegram                   # 推送到 Telegram（要预先绑定）
  # - wechat                   # 微信（要绑定企业微信/个人微信 bot）
  # - lark                     # 飞书
```

## 三种推送形态

### A. 仅 YouMind（最轻量）

每天在 board 里生成一张「今日浸泡」document。用户主动打开 YouMind 看。

合适场景：用户习惯每天打开 YouMind 网页。

### B. YouMind + Telegram（推荐）

YouMind 生成 document，同时 dispatch 卡片到 Telegram。用户在手机上看到，可以直接回复——回复触发 chat 进入 skill 的 step 5+，自动追问 + 沉淀。

合适场景：想要"无需打开应用"的浸泡。

### C. YouMind + 微信（最像每日斯多葛）

类似 Telegram 但 dispatch 到微信。

注意：YouMind 的微信对接通常要绑定企业微信或个人微信 bot，配置成本比 Telegram 高。

## 部署命令（伪代码，给 Hermes 用）

```typescript
// 用 YouMind MCP 的 createScheduledTask
await youmind.createScheduledTask({
  name: "读后无书 · 每日之道推送",
  cron: "0 8 * * *",
  skill_id: "<上一步 createSkill 返回的 ID>",
  prompt: "请按步骤 1-4 跑一遍今日浸泡卡片。不等回应。",
  dispatch: ["youmind", "telegram"]
})
```

## 用户回应回路

scheduled task 推送只跑 skill 的步骤 1-4（生成卡片）。

如果用户被卡片打动、想回应——他们在 Telegram/微信里回复一句话或一段思考。
- YouMind 接收到回应后，应该自动进入同一 skill 的步骤 5-7（接住回应、追问、沉淀）。
- 这需要 YouMind 的 chat continuation 配置正确。

如果你的 YouMind 版本不支持 dispatch 的回应回路，降级方案：
- 推送只是单向通知
- 用户想浸泡时主动在 YouMind/agent 里调用 skill
