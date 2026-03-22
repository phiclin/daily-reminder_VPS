#!/usr/bin/env python3
"""Install or repair OpenClaw cron jobs for the daily reminder VPS skill."""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_JOBS_PATH = Path("~/.openclaw/cron/jobs.json").expanduser()
CHECKER_ID = "daily-reminder-checker_VPS"
CLEAR_ID = "daily-reminder-midnight-clear_VPS"
LEGACY_IDS = {"daily-reminder-checker", "daily-reminder-midnight-clear"}


def backup_path(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.name}.{timestamp}.bak")


def checker_job() -> dict[str, Any]:
    return {
        "id": CHECKER_ID,
        "description": "每分钟检查每日提醒是否需要发飞书提醒",
        "schedule": {
            "kind": "cron",
            "expr": "* * * * *",
            "tz": "Asia/Shanghai",
        },
        "sessionTarget": "main",
        "wakeMode": "now",
        "payload": {
            "kind": "systemEvent",
            "text": "__DAILY_REMINDER_CHECK__",
        },
        "enabled": True,
    }


def clear_job() -> dict[str, Any]:
    return {
        "id": CLEAR_ID,
        "description": "每天 00:00 清空每日提醒状态",
        "schedule": {
            "kind": "cron",
            "expr": "0 0 * * *",
            "tz": "Asia/Shanghai",
        },
        "sessionTarget": "main",
        "wakeMode": "now",
        "payload": {
            "kind": "systemEvent",
            "text": "__DAILY_REMINDER_CLEAR__",
        },
        "enabled": True,
    }


def load_jobs(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "jobs": []}
    return json.loads(path.read_text())


def save_jobs(path: Path, jobs: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jobs, ensure_ascii=False, indent=2) + "\n")


def upsert(jobs: list[dict[str, Any]], job: dict[str, Any]) -> list[dict[str, Any]]:
    updated: list[dict[str, Any]] = []
    replaced = False
    for current in jobs:
        if current.get("id") == job["id"]:
            updated.append(deepcopy(job))
            replaced = True
        else:
            updated.append(current)
    if not replaced:
        updated.append(deepcopy(job))
    return updated


def remove_legacy(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [job for job in jobs if job.get("id") not in LEGACY_IDS]


def install(path: Path) -> dict[str, Any]:
    current = load_jobs(path)
    original = json.dumps(current, ensure_ascii=False, sort_keys=True)
    jobs = remove_legacy(current.get("jobs", []))
    jobs = upsert(jobs, checker_job())
    jobs = upsert(jobs, clear_job())
    updated = {"version": current.get("version", 1), "jobs": jobs}
    changed = json.dumps(updated, ensure_ascii=False, sort_keys=True) != original
    backup = None
    if changed and path.exists():
        backup = backup_path(path)
        backup.write_text(path.read_text())
    save_jobs(path, updated)
    return {"ok": True, "changed": changed, "backup": str(backup) if backup else None, "jobs": updated["jobs"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs-path", default=str(DEFAULT_JOBS_PATH))
    args = parser.parse_args()
    result = install(Path(args.jobs_path))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
