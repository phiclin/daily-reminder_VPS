# Operations

本文档面向日常运行和排障。

## 运行时文件

- Skill 根目录：`~/.newmax/skills/daily-reminder_VPS`
- 状态文件：`~/.openclaw/workspace/.daily-reminder_VPS/state.json`
- OpenClaw 配置：`~/.openclaw/openclaw.json`
- Cron 配置：`~/.openclaw/cron/jobs.json`

## 日常运行流程

### 启动当天提醒

你在 OpenClaw 中发：

```text
每日提醒 开始
今天先写日报，下午三点提醒我跟进客户，晚上把方案过一遍
```

然后 skill 会：

1. 解析任务与专项时间
2. 让你确认不确定的拆分或时间
3. 写入状态文件
4. 等待整点、半点或专项时间的 cron 检查触发提醒

### 增加任务

```text
每日提醒 新增
再加一条，六点提醒我交电费
```

新增任务会继续使用当天编号序列，不会重排旧编号。

### 完成任务

```text
每日提醒 第3条完成
```

对应任务会被标记为完成，并在后续消息中保留删除线。

### 改专项时间

```text
每日提醒 第2条改到 15:30
```

如果时间已经过去，脚本会返回 `past_time`，这时应由 OpenClaw 追问你新的今天稍后时间。

## 状态文件说明

当前状态文件示例见 `config-examples/state.json`。

核心字段：

- `date`：当天日期
- `timezone`：固定为 `Asia/Shanghai`
- `status`：`running`、`paused_all_done` 或 `stopped`
- `next_task_id`：下一个要分配的编号
- `last_check_at`：上一次 cron 检查时间
- `last_periodic_slot`：最近一次周期提醒对应的整点或半点
- `all_done_announced_at`：全部完成时的记录时间
- `tasks`：任务列表

单条任务字段：

- `id`
- `text`
- `done`
- `special_time`
- `special_notified_at`
- `created_at`
- `updated_at`

## 手工运维命令

### 检查 scheduler 是否真的已加载任务

如果本机有 `openclaw` CLI：

```bash
openclaw cron status --json
openclaw cron list --all --json
```

如果 `jobs.json` 已经有内容，但 `cron status` 仍显示 `jobs: 0` 或 `list` 为空，说明当前 Gateway 还没把文件内容注册进内存调度器。

对 `daily-reminder-checker_VPS` 来说，健康状态应至少满足：

- `sessionTarget = "isolated"`
- `payload.kind = "agentTurn"`
- `delivery.mode = "announce"`

对 `daily-reminder-midnight-clear_VPS` 来说，健康状态应至少满足：

- `sessionTarget = "isolated"`
- `payload.kind = "agentTurn"`
- `delivery.mode = "none"`

### 查看当前状态

```bash
python3 scripts/daily_reminder_state.py status
```

### 补建状态文件

```bash
python3 scripts/daily_reminder_state.py ensure-state
```

### 模拟新增任务

```bash
python3 scripts/daily_reminder_state.py add-tasks \
  --command add \
  --tasks-json '[{"text":"写日报","special_time":null}]'
```

### 模拟完成任务

```bash
python3 scripts/daily_reminder_state.py complete-task --task-id 1
```

### 模拟改时间

```bash
python3 scripts/daily_reminder_state.py reschedule-task --task-id 2 --special-time 15:30
```

### 模拟提醒决策

```bash
python3 scripts/daily_reminder_state.py build-reminder
```

### 重新同步 cron 到 live scheduler

```bash
python3 scripts/install_cron.py
```

期望结果：

- `scheduler.mode = "cli_synced"`：live scheduler 已加载
- `scheduler.mode = "file_only"`：只更新了文件，运行中的 Gateway 可能还需要重启

### 手工清空当天状态

```bash
python3 scripts/daily_reminder_state.py clear-day
```

## 典型排障

### 问题：到了整点或半点没有提醒

检查顺序：

1. 确认 `~/.openclaw/cron/jobs.json` 中两个 `_VPS` 任务存在且启用
2. 如果本机有 `openclaw` CLI，先确认 `openclaw cron list --all --json` 里真的存在这两个任务
3. 确认状态文件中的 `status` 是 `running`
4. 确认任务列表不是空数组
5. 手工运行 `python3 scripts/daily_reminder_state.py build-reminder` 查看返回的 `kind`
6. 查看 cron run 或 `list --all --json` 里的 `delivery` / `lastDeliveryStatus`
7. 如果脚本返回了消息，但 `lastDeliveryStatus = not-requested`，说明当前 checker job 仍在走旧链路，重新运行安装器修正 job
8. 如果 `deliveryStatus = delivered` 但飞书没收到，再检查 OpenClaw 的飞书消息链路本身

如果第 1 步通过、第 2 步失败，就是典型的“文件在但 scheduler 没加载”问题。此时重新运行 `python3 scripts/install_cron.py`，或者直接重启 Gateway。

如果第 2 步通过，但 checker job 仍是 `main + systemEvent`，说明这台机器上的 cron 还是旧结构。重新运行：

```bash
python3 scripts/install_cron.py --channel feishu --to user:YOUR_TARGET --account main
```

### 问题：所有任务完成后不再提醒

这是设计行为。全部完成后状态会变成 `paused_all_done`。如果当天后来又新增任务，提醒会自动恢复。

### 问题：专项提醒错过了

如果 OpenClaw 中途重启，恢复后下一次检查会补发一次汇总提醒，而不是把所有错过的时间点逐条补刷。

### 问题：第二天还残留昨天任务

手工执行：

```bash
python3 scripts/daily_reminder_state.py clear-day --now 2026-03-24T00:00:00+08:00
```

然后确认 `daily-reminder-midnight-clear_VPS` cron 任务存在。

### 问题：午夜收到了“静默”之类无意义消息

这是旧版午夜清理 prompt 的副作用，不是正确行为。当前版本的 midnight clear job 应满足：

- `delivery.mode = "none"`
- prompt 中不包含“静默”这种占位词

重新运行安装器后，这类消息应当消失：

```bash
python3 scripts/install_cron.py
```

### 问题：手工停止后又想重新开始

直接重新发送：

```text
每日提醒 开始
...
```

skill 会把新内容作为当天新的运行状态写入。

## 恢复与回滚

### 恢复 cron 备份

`scripts/install_cron.py` 在改写 `jobs.json` 时会自动生成 `.bak` 备份文件。需要回滚时，直接把备份内容拷回即可。

### 清空并重建状态

如果状态文件被手工改坏，最稳的办法是：

1. 备份当前 `state.json`
2. 删除或移走它
3. 执行 `python3 scripts/daily_reminder_state.py ensure-state`
4. 在 OpenClaw 中重新发一遍当天 `开始` 命令
