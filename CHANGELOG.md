# Changelog

All notable changes to `daily-reminder_VPS` will be documented in this file.

## 2026-03-23

### Added

- Published the first working `daily-reminder_VPS` skill repository.
- Added `daily_reminder_state.py` for daily task state, reminder decisions, and midnight reset.
- Added `install_cron.py` to install OpenClaw main-session `systemEvent` cron jobs.
- Added unit tests covering task append, completion, merged reminders, catch-up reminders, past-time rejection, and midnight clear.
- Added a complete repository documentation pack:
  - `README.md`
  - `docs/INSTALL.md`
  - `docs/OPERATIONS.md`
  - `docs/ARCHITECTURE.md`
  - `config-examples/*`
  - `install.sh`

### Fixed

- Fixed the installer gap where writing `~/.openclaw/cron/jobs.json` alone did not register jobs into a running Gateway scheduler.
- Added live scheduler sync through `openclaw cron add/rm` when a usable CLI is available.
- Added explicit `file_only` fallback warnings so cron installation can no longer fail silently on running gateways.
- Added regression tests for CLI-backed cron sync and file-only fallback behavior.

### Changed

- Renamed the published skill to `daily-reminder_VPS`.
- Switched cron examples to the current OpenClaw main-session `systemEvent` structure.
- Standardized the state path to `~/.openclaw/workspace/.daily-reminder_VPS/state.json`.
