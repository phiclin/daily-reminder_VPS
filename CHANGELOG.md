# Changelog

All notable changes to `daily-reminder_VPS` will be documented in this file.

## 2026-03-26

### Added

- Added local per-day archive storage under `~/.openclaw/workspace/.daily-reminder_VPS/archive/YYYY/MM/YYYY-MM-DD.json`.
- Added archive query support for `每日提醒 归档 YYYY-MM-DD`.
- Added summary query support for weekly, monthly, recent-day, and custom date-range reports.
- Added design and implementation docs for the archive-and-summary feature.

### Changed

- Changed `clear-day`, `stop-day`, and cross-day rollover to archive the previous day before resetting runtime state.
- Extended documentation and skill instructions to cover archive storage and historical reporting.

## 2026-03-23

### Added

- Published the first working `daily-reminder_VPS` skill repository.
- Added `daily_reminder_state.py` for daily task state, reminder decisions, and midnight reset.
- Added `install_cron.py` to install OpenClaw cron jobs for the reminder checker and midnight clear flow.
- Added unit tests covering task append, completion, merged reminders, catch-up reminders, past-time rejection, and midnight clear.
- Added a complete repository documentation pack:
  - `README.md`
  - `docs/INSTALL.md`
  - `docs/INDEX.md`
  - `docs/COMMANDS.md`
  - `docs/DEPLOYMENT.md`
  - `docs/INCIDENT-2026-03-23.md`
  - `docs/OPERATIONS.md`
  - `docs/ARCHITECTURE.md`
  - `config-examples/*`
  - `install.sh`

### Fixed

- Fixed the installer gap where writing `~/.openclaw/cron/jobs.json` alone did not register jobs into a running Gateway scheduler.
- Added live scheduler sync through `openclaw cron add/rm` when a usable CLI is available.
- Added explicit `file_only` fallback warnings so cron installation can no longer fail silently on running gateways.
- Added regression tests for CLI-backed cron sync and file-only fallback behavior.
- Replaced the checker default from `main + systemEvent` with `isolated + agentTurn + announce`, so reminder delivery no longer depends on a second hop through the main session.
- Changed the midnight clear job to `delivery.mode = "none"` and removed prompt wording that could leak placeholder text like “静默” to users.
- Added optional `--channel` / `--to` / `--account` delivery routing support to `install_cron.py` and `install.sh`.

### Changed

- Renamed the published skill to `daily-reminder_VPS`.
- Switched cron examples and architecture docs to the current isolated direct-delivery structure.
- Standardized the state path to `~/.openclaw/workspace/.daily-reminder_VPS/state.json`.
