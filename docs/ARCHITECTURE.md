# Architecture

`daily-reminder_VPS` 采用的是“skill + 调度器 + 状态文件”的三段式结构。

## 目标

把 OpenClaw 中一套口语化的“每日提醒”交互，落成稳定的日内提醒流程：

- 用户通过自然语言描述任务
- OpenClaw 负责理解命令和必要确认
- Python 脚本负责状态更新和提醒决策
- Cron 负责按时间触发
- 飞书作为消息出口

## 组件

### 1. `SKILL.md`

职责：

- 约束触发协议
- 约束命令语义
- 要求模型把模糊解析结果先确认后落库
- 定义收到 cron `systemEvent` 后该调用哪个脚本命令

它不负责自行记忆当天状态，也不负责自行判断复杂的跨时间逻辑。

### 2. `scripts/daily_reminder_state.py`

职责：

- 状态持久化
- 任务编号分配
- 完成态与删除线保留
- 专项提醒时间校验
- 整点/半点与专项提醒的合并判断
- 全部完成后的暂停逻辑
- 重启后的 catch-up 汇总提醒
- 零点清空

这是整个 skill 的行为核心。

### 3. `scripts/install_cron.py`

职责：

- 将本 skill 需要的 cron 任务写入 OpenClaw 配置
- 清理旧的非 `_VPS` job id
- 保留无关 cron 任务
- 在配置发生变更时生成备份

### 4. OpenClaw Cron

本 skill 使用两个 job：

- `daily-reminder-checker_VPS`
- `daily-reminder-midnight-clear_VPS`

当前采用的不是旧版 `isolated agentTurn`，而是：

- `sessionTarget: "main"`
- `wakeMode: "now"`
- `payload.kind: "systemEvent"`

这样更符合当前 OpenClaw 的主会话唤醒模型。

## 数据流

### 用户命令流

1. 用户发送 `每日提醒 + 动词`
2. `SKILL.md` 指导 OpenClaw 解析任务
3. 如果拆分或时间不确定，OpenClaw 先确认
4. OpenClaw 调用 `daily_reminder_state.py`
5. 脚本写入 `state.json`
6. OpenClaw 将脚本返回结果回显给用户

### 定时提醒流

1. Cron 每分钟触发 `__DAILY_REMINDER_CHECK__`
2. `SKILL.md` 指导 OpenClaw 调用 `build-reminder`
3. 脚本根据 `last_check_at`、任务状态、专项时间和当前时间决定是否需要提醒
4. 如果需要，脚本返回完整消息文本和提醒类型
5. OpenClaw 将该消息转发到飞书

### 零点清空流

1. Cron 在 `00:00` 触发 `__DAILY_REMINDER_CLEAR__`
2. OpenClaw 调用 `clear-day`
3. 脚本清空当天状态
4. 不发送额外结束消息

## 状态模型

顶层字段：

- `date`
- `timezone`
- `status`
- `next_task_id`
- `last_check_at`
- `last_periodic_slot`
- `all_done_announced_at`
- `tasks`
- `updated_at`

任务字段：

- `id`
- `text`
- `done`
- `special_time`
- `special_notified_at`
- `created_at`
- `updated_at`

设计原则：

- 编号稳定，不重排
- 已完成不删除
- 每条任务最多一个专项时间
- 当天内只存在一套提醒状态

## 提醒决策逻辑

### 常规提醒

脚本用 `periodic_slots_between()` 计算上次检查到当前时刻之间，是否跨过整点或半点。

### 专项提醒

脚本用 `special_due_events()` 找出本轮窗口内到点的任务，并通过 `special_notified_at` 防止同一时间重复发。

### 合并提醒

如果当前窗口里既有常规提醒也有专项提醒，就只返回一条 `merged` 消息。

### 补发提醒

如果本轮检查发现已经错过某个应提醒时点，就返回 `catchup`，只补一条汇总消息，避免刷屏。

### 全部完成

当所有任务都完成时，状态切到 `paused_all_done`。之后普通检查不再出提醒；如果当天稍后有新增任务，状态会恢复到 `running`。

## 边界设计

- 同一天再次 `开始`：按追加处理
- 改专项时间到过去：拒绝直接写入，并提示改成今天稍后时间
- 专项提醒时该条已完成：仍发送完整清单
- OpenClaw 重启：依赖状态文件恢复，不依赖上下文记忆
- 跨天：通过 `ensure_today()` 自动识别日期变化并清空旧状态

## 已知限制

- 本仓库不直接处理飞书渠道配置，依赖 OpenClaw 现有消息发送能力
- 任务文本的自然语言拆分与时间识别由 OpenClaw 侧完成，不在 Python 脚本里做 NLP
- 当前版本只支持“完成”和“改时间”，不支持直接“改任务内容”
