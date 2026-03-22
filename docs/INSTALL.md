# Installation

本文档说明如何把 `daily-reminder_VPS` 安装为本地 OpenClaw skill。

## 前置条件

- 已安装 OpenClaw
- OpenClaw 已配置好可发送飞书消息的渠道
- 本机可使用 `python3`
- 当前用户可写入：
  - `~/.newmax/skills`
  - `~/.openclaw/openclaw.json`
  - `~/.openclaw/cron/jobs.json`
  - `~/.openclaw/workspace`

## 方式一：推荐安装

```bash
git clone https://github.com/phiclin/daily-reminder_VPS.git
cd daily-reminder_VPS
bash install.sh
```

安装脚本会：

- 将当前仓库软链接到 `~/.newmax/skills/daily-reminder_VPS`
- 在 `~/.openclaw/openclaw.json` 中启用 `daily-reminder_VPS`
- 调用 `scripts/install_cron.py` 安装 `_VPS` cron 任务
- 初始化 `~/.openclaw/workspace/.daily-reminder_VPS/state.json`

安装完成后，重启 OpenClaw 即可。

## 方式二：手动安装

### 1. 放置 skill

如果你希望 OpenClaw 直接从用户级 skill 目录读取，推荐使用软链接：

```bash
mkdir -p ~/.newmax/skills
ln -sfn "$(pwd)" ~/.newmax/skills/daily-reminder_VPS
```

如果仓库已经直接位于 `~/.newmax/skills/daily-reminder_VPS`，这一步可以跳过。

### 2. 启用 skill

编辑 `~/.openclaw/openclaw.json`，确保包含：

```json
{
  "skills": {
    "entries": {
      "daily-reminder_VPS": {
        "enabled": true
      }
    }
  }
}
```

可直接参考 `config-examples/openclaw-skill-entry.json`。

### 3. 安装 cron

```bash
python3 scripts/install_cron.py
```

这会把两个任务写入 `~/.openclaw/cron/jobs.json`：

- `daily-reminder-checker_VPS`
- `daily-reminder-midnight-clear_VPS`

脚本会保留无关任务，并在有修改时自动备份旧文件。

### 4. 初始化状态文件

```bash
python3 scripts/daily_reminder_state.py ensure-state
```

完成后，状态文件会出现在：

```text
~/.openclaw/workspace/.daily-reminder_VPS/state.json
```

### 5. 重启 OpenClaw

让新的 skill 配置和 cron 配置生效。

## 升级

如果你已经安装过旧版本：

1. 拉取最新代码
2. 重新运行 `bash install.sh`
3. 重启 OpenClaw

安装脚本会自动把旧的非 `_VPS` cron 任务替换为新的 `_VPS` 任务，不需要手动删。

## 验证安装

### 检查 skill 启用项

```bash
rg -n '"daily-reminder_VPS"' ~/.openclaw/openclaw.json
```

### 检查 cron 任务

```bash
rg -n 'daily-reminder-(checker|midnight-clear)_VPS' ~/.openclaw/cron/jobs.json
```

### 检查状态文件

```bash
cat ~/.openclaw/workspace/.daily-reminder_VPS/state.json
```

### 试跑一条命令

在 OpenClaw 中发送：

```text
每日提醒 开始
写日报，下午三点提醒我跟进客户，晚上整理方案
```

## 常见安装问题

### `openclaw.json` 不存在

先确认 OpenClaw 已经至少启动过一次。安装脚本会尽量创建最小结构，但建议先让 OpenClaw 自己生成基础配置。

### cron 已存在但格式不对

重新运行：

```bash
python3 scripts/install_cron.py
```

该脚本会把本 skill 使用的 cron 配置修正为当前支持的 `systemEvent` 结构。

### 收不到飞书消息

本仓库只负责 skill、状态和调度逻辑。真正的飞书发送仍依赖你的 OpenClaw 消息链路配置，请先确认 OpenClaw 其他飞书消息本身能够正常发送。
