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
  "sessionTarget": "isolated",
  "wakeMode": "next-heartbeat",
  "payload": {
    "kind": "agentTurn",
    "message": "Run the daily reminder checker script.\nExecute: python3 /path/to/daily_reminder_state.py build-reminder\nParse the JSON result from stdout.\nIf \"kind\" is \"none\", output exactly HEARTBEAT_OK.\nOtherwise output exactly the value of \"message\" with no extra text."
  },
  "delivery": {
    "mode": "announce"
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
  "sessionTarget": "isolated",
  "wakeMode": "next-heartbeat",
  "payload": {
    "kind": "agentTurn",
    "message": "Run the daily reminder day-clear script.\nExecute: python3 /path/to/daily_reminder_state.py clear-day\nIgnore the JSON result and output exactly HEARTBEAT_OK."
  },
  "delivery": {
    "mode": "none"
  },
  "enabled": true
}
```
