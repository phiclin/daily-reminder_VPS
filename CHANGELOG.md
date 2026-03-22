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

### Changed

- Renamed the published skill to `daily-reminder_VPS`.
- Switched cron examples to the current OpenClaw main-session `systemEvent` structure.
- Standardized the state path to `~/.openclaw/workspace/.daily-reminder_VPS/state.json`.
