# Deployment

本文档用于把 `daily-reminder_VPS` 部署到目标机，并验证提醒链路真的可用。

## 推荐部署方式

如果目标机已经配置好 OpenClaw 和飞书渠道，优先使用：

```bash
git clone https://github.com/phiclin/daily-reminder_VPS.git
cd daily-reminder_VPS
DAILY_REMINDER_CHANNEL="feishu" \
DAILY_REMINDER_TO="user:YOUR_TARGET" \
DAILY_REMINDER_ACCOUNT="main" \
bash install.sh
```

说明：

- `DAILY_REMINDER_CHANNEL` / `DAILY_REMINDER_TO` / `DAILY_REMINDER_ACCOUNT` 用于显式指定提醒投递目标
- 对跨机器、多账号或 last-route 不稳定的环境，强烈建议显式设置

## 部署后检查

### 1. 确认 skill 已启用

```bash
rg -n '"daily-reminder_VPS"' ~/.openclaw/openclaw.json
```

### 2. 确认 cron 文件已写入

```bash
rg -n 'daily-reminder-(checker|midnight-clear)_VPS' ~/.openclaw/cron/jobs.json
```

### 3. 确认 live scheduler 已加载

如果目标机可执行 `openclaw` CLI：

```bash
openclaw cron status --json
openclaw cron list --all --json
```

期望：

- checker job 存在
- clear job 存在
- `sessionTarget = "isolated"`
- `payload.kind = "agentTurn"`
- checker `delivery.mode = "announce"`
- clear `delivery.mode = "none"`

### 4. 试跑一条开始命令

在 OpenClaw 中发送：

```text
每日提醒 开始
写日报，半小时后核对一下专项提醒链路
```

### 5. 观察首个提醒窗口

重点看：

- 飞书是否收到提醒
- checker 的 `deliveryStatus` 是否为 `delivered`
- 是否不再出现 `lastDeliveryStatus = not-requested`

## 验收标准

目标机部署后，至少应满足：

1. `每日提醒 开始` 可以正常录入状态
2. 整点或半点提醒能真正投递到飞书
3. 专项提醒能真正投递到飞书
4. 午夜清理不会再发出“静默”或其他占位词
5. 重启 OpenClaw 后，状态仍能恢复
6. 当天执行 `停止` 或经过零点后，会生成对应日期的 archive JSON 文件

## 典型上线问题

### 问题：`jobs.json` 对了，但 scheduler 里没有任务

处理方式：

1. 确保 `openclaw` CLI 可用
2. 重新运行 `bash install.sh`
3. 如果仍是 `file_only`，重启 Gateway

### 问题：checker 运行成功，但 Feishu 没收到消息

先看 delivery 状态：

- `not-requested`：大概率是旧 cron 结构或未走 announce
- `delivered`：说明 cron 已投递，请检查 OpenClaw 与飞书链路本身

### 问题：午夜仍收到无意义文本

当前正确行为应是午夜清理不投递任何消息。如果目标机仍有这类现象，优先重新安装并确认 clear job 为：

- `sessionTarget = "isolated"`
- `payload.kind = "agentTurn"`
- `delivery.mode = "none"`

## 回滚建议

如果部署后需要临时回滚：

1. 备份当前 `~/.openclaw/cron/jobs.json`
2. 用安装脚本生成的 `.bak` 文件恢复
3. 重启 Gateway
4. 重新确认 scheduler 中已切回预期版本
