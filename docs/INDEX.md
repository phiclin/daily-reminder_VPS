# Documentation Index

本文档用于快速定位 `daily-reminder_VPS` 的各类说明文件。

## 推荐阅读顺序

1. `README.md`
2. `docs/INSTALL.md`
3. `docs/COMMANDS.md`
4. `docs/DEPLOYMENT.md`
5. `docs/OPERATIONS.md`
6. `docs/ARCHITECTURE.md`

## 文档清单

### 对首次使用者

- `README.md`
  - 仓库总览、能力边界、快速开始。
- `docs/INSTALL.md`
  - 安装步骤、升级方式、常见安装问题。
- `docs/COMMANDS.md`
  - 日常命令格式、输入示例、状态变化规则。

### 对部署和运维

- `docs/DEPLOYMENT.md`
  - 目标机部署、显式飞书路由、验收检查项、回滚建议。
- `docs/OPERATIONS.md`
  - 运行期排障、状态文件检查、手工运维命令。

### 对开发和维护

- `docs/ARCHITECTURE.md`
  - 组件划分、数据流、设计取舍、已知限制。
- `docs/specs/2026-03-26-archive-and-summary.md`
  - 本次归档与汇总功能的设计说明。
- `docs/plans/2026-03-26-archive-and-summary.md`
  - 本次归档与汇总功能的实现计划。
- `references/cron-json-shape.md`
  - 当前 cron JSON 结构参考。
- `CHANGELOG.md`
  - 发布和修订记录。

### 对本次修订追踪

- `docs/INCIDENT-2026-03-23.md`
  - 跨机器运行后发现的提醒投递问题、根因、修复动作和验证结果。

## 快速定位

- 想知道怎么装：看 `docs/INSTALL.md`
- 想知道怎么用：看 `docs/COMMANDS.md`
- 想知道归档和汇总怎么设计的：看 `docs/specs/2026-03-26-archive-and-summary.md`
- 想知道目标机怎么验收：看 `docs/DEPLOYMENT.md`
- 想知道提醒为什么没发出来：看 `docs/OPERATIONS.md`
- 想知道为什么这次会改 cron 架构：看 `docs/INCIDENT-2026-03-23.md`
