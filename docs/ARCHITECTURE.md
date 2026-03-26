# Architecture

`daily-reminder_VPS` 采用的是“skill + 调度器 + 运行态状态文件 + 历史归档”的四段式结构。

## 目标

把 OpenClaw 中一套口语化的“每日提醒”交互，落成稳定的日内提醒流程，并在每天结束后留下可供后续统计的历史结果：

- 用户通过自然语言描述任务
- OpenClaw 负责理解命令和必要确认
- Python 脚本负责状态更新、归档保存和历史汇总
- Cron 负责按时间触发
- 飞书作为消息出口

## 组件

### 1. `SKILL.md`

职责：

- 约束触发协议
- 约束命令语义
- 要求模型把模糊解析结果先确认后落库
- 约束安装前的 cron 健康检查方式
- 将归档和汇总类自然语言命令映射到脚本参数

它不负责自行记忆当天状态，也不负责自行判断复杂的跨时间逻辑。

### 2. `scripts/daily_reminder_state.py`

职责：

- 状态持久化
- 每日结果归档
- 单日归档读取
- 周期汇总聚合
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

- 优先通过 `openclaw cron add/rm` 把任务注册进 live scheduler
- 在没有可用 CLI 时，把本 skill 需要的 cron 任务写入 OpenClaw 配置文件
- 清理旧的非 `_VPS` job id
- 在文件模式下保留无关 cron 任务
- 在文件模式发生变更时生成备份

### 4. OpenClaw Cron

本 skill 使用两个 job：

- `daily-reminder-checker_VPS`
- `daily-reminder-midnight-clear_VPS`

当前默认结构是：

- checker：`sessionTarget: "isolated"` + `payload.kind: "agentTurn"` + `delivery.mode: "announce"`
- midnight clear：`sessionTarget: "isolated"` + `payload.kind: "agentTurn"` + `delivery.mode: "none"`

这样 checker job 会自己完成提醒判断和投递，不再依赖 `systemEvent -> 主会话 -> 再投递` 这条在部分环境中不稳定的链路。

## 数据流

### 用户命令流

1. 用户发送 `每日提醒 + 动词`
2. `SKILL.md` 指导 OpenClaw 解析任务
3. 如果拆分或时间不确定，OpenClaw 先确认
4. OpenClaw 调用 `daily_reminder_state.py`
5. 脚本写入 `state.json`
6. OpenClaw 将脚本返回结果回显给用户

### 定时提醒流

1. Cron 每分钟触发 checker isolated agent turn
2. agent turn 直接运行 `build-reminder`
3. 脚本根据 `last_check_at`、任务状态、专项时间和当前时间决定是否需要提醒
4. `kind == "none"` 时只输出 `HEARTBEAT_OK`
5. `kind != "none"` 时只输出完整消息文本
6. Cron `delivery.mode = "announce"` 把该消息直接投递到飞书

### 零点清空流

1. Cron 在 `00:00` 触发 midnight clear isolated agent turn
2. agent turn 直接运行 `clear-day`
3. 脚本先归档前一天结果，再清空当天状态
4. Cron `delivery.mode = "none"`，不投递任何结束消息

### 归档查询流

1. 用户发送 `每日提醒 归档 ...` 或 `每日提醒 汇总 ...`
2. `SKILL.md` 将自然语言时间范围映射到脚本参数
3. 脚本读取 archive 目录中的单日文件
4. 脚本输出单日查看或周期汇总文本
5. OpenClaw 将结果发回用户

### 安装与注册流

1. `install.sh` 调用 `scripts/install_cron.py`
2. 如果本机存在可用的 `openclaw` CLI，则通过 Gateway RPC 把任务注册到 live scheduler
3. 如果没有 CLI，则退回到写 `~/.openclaw/cron/jobs.json`
4. 在 live sync 失败时，脚本会显式返回失败，而不是假装安装成功

## 状态模型

### 运行态状态

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

### 历史归档

归档目录：

```text
~/.openclaw/workspace/.daily-reminder_VPS/archive/YYYY/MM/YYYY-MM-DD.json
```

每个归档文件保存：

- 日期
- 归档原因
- 当天任务总数、完成数、未完成数、完成率
- 完整任务明细

归档原因包括：

- `midnight_clear`
- `manual_stop`
- `rollover`

## 提醒与归档决策逻辑

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

### 跨天归档

当命令层发现 `state.json` 还是昨天日期时，先把旧状态归档为 `rollover`，再切换到今天的空状态。

## 边界设计

- 同一天再次 `开始`：按追加处理
- 改专项时间到过去：拒绝直接写入，并提示改成今天稍后时间
- 专项提醒时该条已完成：仍发送完整清单
- OpenClaw 重启：依赖状态文件恢复，不依赖上下文记忆
- 跨天：命令层先归档旧状态，再切换到新日期的空状态
- 空任务日：不生成空归档文件

## 已知限制

- 本仓库不直接处理飞书渠道配置，依赖 OpenClaw 现有消息发送能力
- 任务文本的自然语言拆分与时间识别由 OpenClaw 侧完成，不在 Python 脚本里做 NLP
- 当前版本只支持“完成”和“改时间”，不支持直接“改任务内容”
- 如果本机没有可用的 `openclaw` CLI，安装器只能做文件级降级写入；在 Gateway 已经运行的情况下，仍然需要人工重启才能让 scheduler 重新加载
- 如果 checker job 没有显式配置 `channel/to/account`，则投递目标仍依赖 OpenClaw 的 last-route；在跨机器或多账号场景中，建议安装时显式传入
- 历史归档是本地 JSON 文件而不是数据库；适合个人统计和回顾，不适合复杂多用户并发场景
