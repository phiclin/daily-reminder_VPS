---
name: daily-reminder_VPS
description: 每日提醒技能_VPS。用于 OpenClaw 中的“每日提醒”命令式工作流：接收“每日提醒 + 动词”的口语化任务输入，维护当天任务状态，在整点或半点以及单个专项时间点通过飞书提醒，并在 00:00 自动清空。适用于开始提醒、追加任务、标记完成、改时间和查看状态。
---

# Daily Reminder

使用这个 skill 时，把自然语言理解交给模型，把状态修改和调度判断交给脚本。

## Commands

只在消息明确匹配 `每日提醒 + 动词` 时触发，支持：

- `每日提醒 开始 ...`
- `每日提醒 新增 ...`
- `每日提醒 第N条完成`
- `每日提醒 第N条改到 HH:mm`
- `每日提醒 查看`
- `每日提醒 停止`

如果用户表达里包含多个任务或模糊时间：

- 能确定就拆成结构化任务后写入状态。
- 拿不准就先确认，不要猜。
- 对疑似重复任务先追问，不要自动合并或自动新增。

## Storage

状态文件固定在：

```text
~/.openclaw/workspace/.daily-reminder_VPS/state.json
```

不要把状态写进聊天上下文。每次处理都重新读取状态文件。

## One-Time Setup

先确保 cron 任务安装正确：

```bash
python3 {baseDir}/scripts/install_cron.py
```

脚本会优先通过 `openclaw cron add/rm` 把任务注册进正在运行的 Gateway scheduler；如果本机没有可用的 `openclaw` CLI，则只会回写 `~/.openclaw/cron/jobs.json`，这种情况下运行中的 Gateway 不会热加载任务。

如果你需要固定投递到某个飞书目标，而不是依赖 last-route，可以改用：

```bash
python3 {baseDir}/scripts/install_cron.py --channel feishu --to user:YOUR_TARGET --account main
```

## Cron Health Check

在处理这些会修改当天提醒状态的命令前：

- `每日提醒 开始`
- `每日提醒 新增`
- `每日提醒 第N条完成`
- `每日提醒 第N条改到 HH:mm`
- `每日提醒 停止`

先运行：

```bash
python3 {baseDir}/scripts/install_cron.py
```

读取返回 JSON：

- `ok == true` 且 `scheduler.mode == "cli_synced"`：说明 scheduler 已经加载了任务，可以继续。
- `ok == true` 且 `scheduler.mode == "file_only"`：说明只写了 `jobs.json`，但当前这次 live session 所在的 Gateway 可能还没加载任务。此时先明确提醒用户需要重启 Gateway 或安装可用的 `openclaw` CLI，再继续配置每日提醒。
- `ok == false`：说明 live sync 失败。不要继续处理每日提醒内容，先把错误原样告诉用户。

`每日提醒 查看` 可以跳过这个预检，因为它只读状态，不依赖 scheduler 写入。

## Structured Task Payload

在调用状态脚本前，先把用户本轮确认后的任务解析成 JSON 数组：

```json
[
  {"text": "写日报", "special_time": null},
  {"text": "跟进客户", "special_time": "15:30"}
]
```

每条任务最多一个 `special_time`。如果新时间已经过去，先追问，不直接写入。

## State Script

主脚本：

```bash
python3 {baseDir}/scripts/daily_reminder_state.py ...
```

常用命令：

### Start or Add

```bash
python3 {baseDir}/scripts/daily_reminder_state.py add-tasks \
  --command start \
  --tasks-json '[{"text":"写日报","special_time":null}]'
```

```bash
python3 {baseDir}/scripts/daily_reminder_state.py add-tasks \
  --command add \
  --tasks-json '[{"text":"跟进客户","special_time":"15:30"}]'
```

规则：

- 同一天重复 `开始` 也按追加处理，除非当前状态已经是手动 `停止` 后的新一轮重建。
- 新任务编号永远递增。
- 已完成任务保留，不重排编号。

### Complete

```bash
python3 {baseDir}/scripts/daily_reminder_state.py complete-task --task-id 3
```

如果这是最后一个未完成任务，脚本会把状态切到 `paused_all_done`。这时立即发送脚本返回的完整“今日已全部完成”消息。

### Reschedule

```bash
python3 {baseDir}/scripts/daily_reminder_state.py reschedule-task \
  --task-id 2 \
  --special-time 15:30
```

如果脚本返回 `past_time`，先向用户确认新的今天稍后时间，再重试。

### View

```bash
python3 {baseDir}/scripts/daily_reminder_state.py status
```

直接把返回的 `message` 发给用户。

### Stop

```bash
python3 {baseDir}/scripts/daily_reminder_state.py stop-day
```

手动停止后，今天的任务立刻清空。

## Cron Delivery Model

本 skill 依赖安装器生成的两个 cron job，但它们不再走主会话 `systemEvent`：

- checker job：`isolated + agentTurn + announce`
- midnight clear job：`isolated + agentTurn + no-deliver`

checker job 会直接运行：

```bash
python3 {baseDir}/scripts/daily_reminder_state.py build-reminder
```

处理规则：

- `kind == "none"`：只输出 `HEARTBEAT_OK`，不会投递提醒。
- `kind != "none"`：只输出返回 JSON 中的 `message`，由 cron delivery 直接发到飞书。

midnight clear job 会直接运行：

```bash
python3 {baseDir}/scripts/daily_reminder_state.py clear-day
```

处理规则：

- 只负责清空当天状态。
- `delivery.mode = "none"`，不会额外投递任何结束消息。
- 不要在 prompt 或输出中使用“静默”这类占位词，避免被错误发送给用户。

## Formatting Rules

每次提醒都发送完整清单，不只发未完成项。格式保持稳定：

```text
【每日提醒｜常规提醒】
时间：10:00
今天共 5 条，已完成 2 条，未完成 3 条

1. 写日报
~~2. 跟进客户 @15:30~~
3. 整理方案
```

## Guardrails

- 不要自己发明任务编号，编号以脚本状态为准。
- 不要在模型里手写跨天清理逻辑，统一走脚本。
- 不要在未经确认时写入模糊任务拆分结果。
- 不要把重复提醒做成多条刷屏；checker 每次最多发一条汇总提醒。
- 如果同一天全部完成后用户又新增任务，先正常追加，再恢复提醒。
- 不要继续依赖主会话 `systemEvent -> 二次处理 -> 飞书投递` 这条链路；cron 应直接完成判断和投递。
- 不要在 Gateway 运行中只改 `~/.openclaw/cron/jobs.json` 就假设 scheduler 已经生效；要么看到 `scheduler.mode == "cli_synced"`，要么明确要求用户重启 Gateway。
