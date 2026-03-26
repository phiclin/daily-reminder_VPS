# Daily Reminder Archive And Summary Design

## Goal

为 `daily-reminder_VPS` 增加“每日结果本地归档”和“周期汇总展示”能力，让每天的任务明细在清空后仍可保留，并支持后续按单日、周、月和自定义日期范围查看整体完成情况。

## Scope

本次设计覆盖：

- 每日结果归档落盘
- 单日归档查看
- 周期汇总查看
- skill 命令协议扩展
- 文档与运维说明更新

本次不覆盖：

- 事后修改历史归档
- 将旧数据回填到归档
- 使用数据库替代本地文件

## Design Summary

继续保留当前 `state.json` 作为“当天运行态”，新增本地归档目录保存“历史结果”。每天结束前，先把当天完整任务结果写入归档文件，再清空当天状态。归档文件按天单独保存，后续通过脚本读取归档目录并生成单日展示或周期汇总文本。

## Storage Model

### Runtime State

当前运行态仍保存在：

```text
~/.openclaw/workspace/.daily-reminder_VPS/state.json
```

### Archive Root

历史归档新增目录：

```text
~/.openclaw/workspace/.daily-reminder_VPS/archive/YYYY/MM/YYYY-MM-DD.json
```

按天独立文件的原因：

- 便于人工查看和备份
- 便于按日期范围扫描
- 不需要引入数据库
- 覆盖和幂等行为简单

## Archive Record Shape

每个归档文件保存一整天的完整快照，包含：

- `date`
- `timezone`
- `archived_at`
- `archive_reason`
- `status_before_archive`
- `total_tasks`
- `completed_tasks`
- `pending_tasks`
- `completion_rate`
- `tasks`

每条任务保留：

- `id`
- `text`
- `done`
- `special_time`
- `created_at`
- `updated_at`

## Archive Triggers

归档时机固定为以下三类：

1. `clear-day` 在清空当天状态之前
2. `stop-day` 在手动停止当天提醒之前
3. 脚本发现跨天 rollover 时，在丢弃旧日期状态之前

归档原因统一记录为：

- `midnight_clear`
- `manual_stop`
- `rollover`

## Archive Rules

- 只有当天状态中存在任务时才写归档文件
- 同一天重复归档时，允许覆盖同一归档文件
- 归档是只读历史记录，不提供修改命令
- 功能上线前未保存的历史日期不补录

## Query Model

新增两类查询能力。

### Single Day Archive

支持查看某一天的完整归档：

- `每日提醒 归档 2026-03-26`

脚本侧提供按日期读取归档记录的命令，返回完整展示文本。

### Summary Queries

支持以下汇总：

- `每日提醒 汇总 本周`
- `每日提醒 汇总 本月`
- `每日提醒 汇总 最近7天`
- `每日提醒 汇总 最近30天`
- `每日提醒 汇总 从 2026-03-01 到 2026-03-31`

脚本侧统一转成“日期范围查询”。

## Summary Rendering

汇总展示先输出总体概览，再输出逐日简表。

总体概览包含：

- 查询范围
- 命中天数
- 总任务数
- 完成数
- 未完成数
- 整体完成率

逐日简表包含：

- 日期
- 任务总数
- 完成数
- 未完成数
- 完成率
- 归档原因

## Single Day Rendering

单日归档展示应输出：

- 日期
- 归档原因
- 当天任务总数、完成数、未完成数、完成率
- 完整任务清单

已完成任务继续使用删除线文本形式展示。

## CLI Extension

在 `daily_reminder_state.py` 中新增：

- `show-archive --date YYYY-MM-DD`
- `summary --preset this-week|this-month|last-7-days|last-30-days`
- `summary --from YYYY-MM-DD --to YYYY-MM-DD`

skill 侧负责把自然语言命令映射到这些脚本命令。

## Error Handling

- 查询不存在的归档日期时，返回友好提示，不抛未处理异常
- 查询日期范围没有任何归档时，返回“该时间范围内暂无归档记录”
- 非法日期参数直接返回明确错误

## Testing Strategy

新增测试至少覆盖：

- `clear-day` 前会归档当天任务
- `stop-day` 前会归档当天任务
- 跨天 rollover 时会归档旧状态
- 空任务日不会产生归档文件
- 单日归档可正确读取和渲染
- 周期汇总可正确聚合总数和逐日简表

## Docs Impact

需要同步更新：

- `README.md`
- `SKILL.md`
- `docs/COMMANDS.md`
- `docs/OPERATIONS.md`
- `docs/ARCHITECTURE.md`
- `CHANGELOG.md`
