# Daily Reminder Archive And Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local per-day archive storage plus single-day and ranged summary views for `daily-reminder_VPS`.

**Architecture:** Keep `state.json` as the live day state, add a per-day JSON archive tree under the workspace, and extend `daily_reminder_state.py` with archive-write and archive-query commands. Route new OpenClaw commands through `SKILL.md` and document the new storage and reporting behavior.

**Tech Stack:** Python 3 standard library, JSON files, unittest, OpenClaw skill docs

---

### Task 1: Add failing tests for archive writing

**Files:**
- Modify: `tests/test_daily_reminder_state.py`
- Modify: `scripts/daily_reminder_state.py`

- [ ] **Step 1: Write failing tests for `clear-day`, `stop-day`, and rollover archiving**
- [ ] **Step 2: Run `python3 -m unittest discover -s tests -p 'test_*.py' -v` and verify the new tests fail for the expected missing behavior**
- [ ] **Step 3: Implement minimal archive-path and archive-write helpers in `scripts/daily_reminder_state.py`**
- [ ] **Step 4: Re-run the test suite and verify the new archive-writing tests pass**

### Task 2: Add failing tests for archive queries and summaries

**Files:**
- Modify: `tests/test_daily_reminder_state.py`
- Modify: `scripts/daily_reminder_state.py`

- [ ] **Step 1: Write failing tests for single-day archive rendering and ranged summary rendering**
- [ ] **Step 2: Run `python3 -m unittest discover -s tests -p 'test_*.py' -v` and verify the new tests fail for the expected missing commands**
- [ ] **Step 3: Implement archive-load, preset-range, and summary-render helpers plus new CLI subcommands**
- [ ] **Step 4: Re-run the test suite and verify query tests pass**

### Task 3: Wire the new commands into the skill contract

**Files:**
- Modify: `SKILL.md`
- Modify: `docs/COMMANDS.md`

- [ ] **Step 1: Extend the supported command list with `每日提醒 归档 ...` and `每日提醒 汇总 ...`**
- [ ] **Step 2: Document how OpenClaw should map natural-language periods to script presets and date ranges**
- [ ] **Step 3: Verify the docs reflect the implemented CLI shape**

### Task 4: Update operational and architecture documentation

**Files:**
- Modify: `README.md`
- Modify: `docs/OPERATIONS.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add archive directory, retention behavior, and summary capabilities to repo docs**
- [ ] **Step 2: Add troubleshooting notes for missing archive files or empty summary ranges**
- [ ] **Step 3: Update changelog with the new archive-and-summary feature set**

### Task 5: Verify and publish

**Files:**
- No code changes expected unless verification fails

- [ ] **Step 1: Run `python3 -m unittest discover -s tests -p 'test_*.py' -v`**
- [ ] **Step 2: Run `python3 -m py_compile scripts/daily_reminder_state.py scripts/install_cron.py`**
- [ ] **Step 3: Review `git diff --stat` for expected scope only**
- [ ] **Step 4: Commit with a focused message**
- [ ] **Step 5: Push `main` to GitHub**
