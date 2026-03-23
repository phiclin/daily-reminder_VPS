# daily-reminder_VPS

`daily-reminder_VPS` 是一个面向 OpenClaw 的每日提醒 skill，用来把你口语化输入的当天任务，整理成一套可持续到当天 `24:00` 的飞书提醒流程。

它的设计目标不是“做一个待办清单”，而是把你每天早上和 OpenClaw 的那段固定协作流程稳定下来：

- 任务支持口语化输入
- 编号固定，不重排
- 已完成任务保留并显示删除线
- 常规提醒只在整点和半点触发
- 单条任务可附带一个专项提醒时间
- 专项提醒与整点/半点撞上时自动合并
- 全部完成后自动暂停，后续新增任务时自动恢复
- `00:00` 自动清空，不保留前一天状态
- OpenClaw 重启后自动恢复，并补发一次错过的汇总提醒

## 仓库内容

- `SKILL.md`：给 OpenClaw 读取的技能说明
- `scripts/daily_reminder_state.py`：状态管理与提醒决策主脚本
- `scripts/install_cron.py`：安装或修复 OpenClaw cron 配置
- `tests/test_daily_reminder_state.py`：单元测试
- `references/cron-json-shape.md`：当前 cron JSON 结构参考
- `docs/INSTALL.md`：安装说明
- `docs/OPERATIONS.md`：运行与排障说明
- `docs/ARCHITECTURE.md`：架构设计说明
- `config-examples/`：配置示例
- `install.sh`：一键安装脚本

## 触发协议

只在消息明确匹配 `每日提醒 + 动词` 时进入本 skill。

当前支持：

- `每日提醒 开始 ...`
- `每日提醒 新增 ...`
- `每日提醒 第N条完成`
- `每日提醒 第N条改到 HH:mm`
- `每日提醒 查看`
- `每日提醒 停止`

说明：

- 同一天再次发送 `开始`，按追加任务处理，不会开启第二套提醒。
- 输入内容可以很口语化。
- 如果系统对任务拆分或时间解析没有把握，应该先向你确认，再写入状态。

## 提醒行为

### 常规提醒

- 固定在每个整点和半点触发
- 每次都发送完整清单
- 完成项保留并显示删除线

### 专项提醒

- 每条任务最多允许一个专项提醒时间
- 到点时也发送完整清单
- 如果与整点/半点撞上，只发送一条合并提醒

### 当天结束

- `00:00` 静默清空状态
- 不保留前一天日志
- 第二天重新发 `每日提醒 开始 ...` 即重新开始

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/phiclin/daily-reminder_VPS.git
cd daily-reminder_VPS
```

### 2. 执行安装脚本

```bash
bash install.sh
```

安装脚本会完成下面几件事：

- 把仓库链接到 `~/.newmax/skills/daily-reminder_VPS`
- 在 `~/.openclaw/openclaw.json` 中启用该 skill
- 优先通过 `openclaw` CLI live sync 正在运行的 Gateway scheduler
- 在无法 live sync 时，回写 `~/.openclaw/cron/jobs.json` 作为降级方案
- 初始化 `~/.openclaw/workspace/.daily-reminder_VPS/state.json`

推荐让 `openclaw` CLI 可以在 `PATH` 中直接使用；如果路径特殊，也可以在运行前设置：

```bash
export OPENCLAW_CLI="/custom/path/to/openclaw"
```

如果安装输出里出现 `scheduler.mode = "file_only"`，说明 cron 定义已经写入文件，但运行中的 Gateway 还没有热加载，需要重启 Gateway 或补上可用的 `openclaw` CLI 后重新执行安装。

### 3. 重启 OpenClaw

让新的 skill 配置和 cron 配置生效。

### 4. 开始使用

```text
每日提醒 开始
今天先写日报，下午三点半提醒我跟进客户，晚上把方案再过一遍
```

## 命令示例

```text
每日提醒 开始
今天要做 4 件事：先写日报，再给客户回消息，下午 3 点提醒我跟进客户，晚上整理明天安排
```

```text
每日提醒 新增
再加一条，六点提醒我交电费
```

```text
每日提醒 第3条完成
```

```text
每日提醒 第2条改到 15:30
```

```text
每日提醒 查看
```

```text
每日提醒 停止
```

## 提醒消息示例

```text
【每日提醒｜合并提醒】
时间：15:30
今天共 5 条，已完成 2 条，未完成 3 条
到点任务：第 2 条

1. 写日报
~~2. 跟进客户 @15:30~~
3. 整理方案
~~4. 回消息~~
5. 过一遍明天安排
```

如果 OpenClaw 当前消息链路支持富文本或卡片，可把同样内容渲染为飞书富文本；如果不支持，直接发送纯文本也可以。

## 存储位置

运行状态保存在：

```text
~/.openclaw/workspace/.daily-reminder_VPS/state.json
```

状态不依赖聊天上下文，因此支持中途重启恢复。

## 测试

运行全部测试：

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

校验脚本语法：

```bash
python3 -m py_compile scripts/daily_reminder_state.py scripts/install_cron.py
```

如果本机安装了 `openclaw` CLI，还可以检查 live scheduler：

```bash
openclaw cron status --json
openclaw cron list --all --json
```

## 文档

- 安装说明：`docs/INSTALL.md`
- 运维说明：`docs/OPERATIONS.md`
- 架构说明：`docs/ARCHITECTURE.md`

## 许可

本项目采用 MIT License，详见 `LICENSE`。
