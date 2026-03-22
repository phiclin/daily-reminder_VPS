# Cron JSON Shape

`daily-reminder_VPS` installs two OpenClaw jobs into `~/.openclaw/cron/jobs.json`.

## Checker Job

```json
{
  "id": "daily-reminder-checker_VPS",
  "description": "每分钟检查每日提醒是否需要发飞书提醒",
  "schedule": {
    "kind": "cron",
    "expr": "* * * * *",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "main",
  "wakeMode": "now",
  "payload": {
    "kind": "systemEvent",
    "text": "__DAILY_REMINDER_CHECK__"
  },
  "enabled": true
}
```

## Midnight Clear Job

```json
{
  "id": "daily-reminder-midnight-clear_VPS",
  "description": "每天 00:00 清空每日提醒状态",
  "schedule": {
    "kind": "cron",
    "expr": "0 0 * * *",
    "tz": "Asia/Shanghai"
  },
  "sessionTarget": "main",
  "wakeMode": "now",
  "payload": {
    "kind": "systemEvent",
    "text": "__DAILY_REMINDER_CLEAR__"
  },
  "enabled": true
}
```
