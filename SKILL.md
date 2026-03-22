---
name: daily-reminder_VPS
description: 每日提醒技能_VPS。用于 OpenClaw 中的“每日提醒”命令式工作流：接收“每日提醒 + 动词”的口语化任务输入，维护当天任务状态，在整点或半点以及单个专项时间点通过飞书提醒，并在 00:00 自动清空。适用于开始提醒、追加任务、标记完成、改时间、查看状态、处理定时 system event。
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

脚本会修正为 OpenClaw 官方推荐的 main-session `systemEvent` 结构。参考 `references/cron-json-shape.md`。

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

## Cron Events

该 skill 必须识别两个 system event：

- `__DAILY_REMINDER_CHECK__`
- `__DAILY_REMINDER_CLEAR__`

### `__DAILY_REMINDER_CHECK__`

运行：

```bash
python3 {baseDir}/scripts/daily_reminder_state.py build-reminder
```

读取返回 JSON：

- `kind == "none"`：不发消息。
- `kind == "periodic"`：发送 `message`，标题已是“常规提醒”。
- `kind == "special"`：发送 `message`，标题已是“专项提醒”。
- `kind == "merged"`：发送 `message`，标题已是“合并提醒”。
- `kind == "catchup"`：发送 `message`，标题已是“补发提醒”。

消息内容已经是完整清单：

- 已完成项保留并用 `~~删除线~~` 形式表达。
- 专项时间会显示为 `@15:30`。
- 如果有到点任务，会追加“到点任务：第 N 条”。

### `__DAILY_REMINDER_CLEAR__`

运行：

```bash
python3 {baseDir}/scripts/daily_reminder_state.py clear-day
```

零点清空是静默动作，不额外发送结束消息。

## Message Delivery

提醒目标是飞书。对于需要真的发出的提醒，调用 message 工具把脚本返回的 `message` 发送到飞书渠道。

如果当前 OpenClaw 链路支持富文本或卡片，可以把每行任务作为 `lark_md` 渲染；如果不支持，直接发送脚本返回的纯文本也可以，因为内容已经可读。

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
