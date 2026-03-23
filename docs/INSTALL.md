# Installation

本文档说明如何把 `daily-reminder_VPS` 安装为本地 OpenClaw skill。

## 前置条件

- 已安装 OpenClaw
- OpenClaw 已配置好可发送飞书消息的渠道
- 本机可使用 `python3`
- 推荐本机可直接执行 `openclaw` CLI；如果不在 `PATH` 中，可通过环境变量 `OPENCLAW_CLI` 指定
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
- 调用 `scripts/install_cron.py` 优先向 live scheduler 注册 `_VPS` cron 任务
- 在没有可用 CLI 时，回写 `jobs.json` 作为降级方案
- 初始化 `~/.openclaw/workspace/.daily-reminder_VPS/state.json`

安装完成后，重启 OpenClaw 即可。

如果你的 `openclaw` CLI 路径不在 `PATH` 中，可以这样执行：

```bash
OPENCLAW_CLI="/custom/path/to/openclaw" bash install.sh
```

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

脚本行为分两种：

- 如果能找到可用的 `openclaw` CLI：直接把任务注册到当前正在运行的 Gateway scheduler
- 如果找不到 CLI：只更新 `~/.openclaw/cron/jobs.json`

第二种模式下，如果 Gateway 已经在运行，仍然需要重启它才能真正开始调度。

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

如果本机有 `openclaw` CLI，建议再确认 scheduler 里真的有任务：

```bash
openclaw cron status --json
openclaw cron list --all --json
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

### `jobs.json` 内容正确，但定时器还是不跑

这通常说明 Gateway 已经启动过，而你只是修改了 `jobs.json` 文件。OpenClaw 的 scheduler 会把任务加载到内存中，运行中不会自动热加载该文件。

优先处理方式：

1. 确保本机能执行 `openclaw` CLI
2. 重新运行 `python3 scripts/install_cron.py`
3. 再用 `openclaw cron list --all --json` 确认任务已加载

如果当前机器没有可用 CLI，就重启 Gateway。

### 收不到飞书消息

本仓库只负责 skill、状态和调度逻辑。真正的飞书发送仍依赖你的 OpenClaw 消息链路配置，请先确认 OpenClaw 其他飞书消息本身能够正常发送。
