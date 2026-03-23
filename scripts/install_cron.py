#!/usr/bin/env python3
"""Install or repair OpenClaw cron jobs for the daily reminder VPS skill."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Sequence


DEFAULT_JOBS_PATH = Path("~/.openclaw/cron/jobs.json").expanduser()
DEFAULT_TZ = "Asia/Shanghai"
CHECKER_ID = "daily-reminder-checker_VPS"
CLEAR_ID = "daily-reminder-midnight-clear_VPS"
LEGACY_IDS = {"daily-reminder-checker", "daily-reminder-midnight-clear"}
CLI_ENV_VAR = "OPENCLAW_CLI"

Runner = Callable[[list[str]], tuple[int, str, str]]


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
            "tz": DEFAULT_TZ,
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
            "tz": DEFAULT_TZ,
        },
        "sessionTarget": "main",
        "wakeMode": "now",
        "payload": {
            "kind": "systemEvent",
            "text": "__DAILY_REMINDER_CLEAR__",
        },
        "enabled": True,
    }


def expected_jobs() -> list[dict[str, Any]]:
    return [checker_job(), clear_job()]


def expected_scheduler_specs() -> list[dict[str, str]]:
    specs: list[dict[str, str]] = []
    for job in expected_jobs():
        specs.append(
            {
                "name": job["id"],
                "expr": job["schedule"]["expr"],
                "tz": job["schedule"]["tz"],
                "system_event": job["payload"]["text"],
                "wake_mode": job["wakeMode"],
            }
        )
    return specs


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


def install_file(path: Path) -> dict[str, Any]:
    current = load_jobs(path)
    original = json.dumps(current, ensure_ascii=False, sort_keys=True)
    jobs = remove_legacy(current.get("jobs", []))
    for expected in expected_jobs():
        jobs = upsert(jobs, expected)
    updated = {"version": current.get("version", 1), "jobs": jobs}
    changed = json.dumps(updated, ensure_ascii=False, sort_keys=True) != original
    backup = None
    if changed and path.exists():
        backup = backup_path(path)
        backup.write_text(path.read_text())
    save_jobs(path, updated)
    return {"changed": changed, "backup": str(backup) if backup else None, "jobs": updated["jobs"]}


def discover_cli_command(cli_command: Sequence[str] | str | None) -> list[str] | None:
    if isinstance(cli_command, str):
        parts = shlex.split(cli_command)
        return parts or None
    if cli_command is not None:
        parts = [str(part) for part in cli_command if str(part).strip()]
        return parts or None

    from_env = os.environ.get(CLI_ENV_VAR, "").strip()
    if from_env:
        parts = shlex.split(from_env)
        if parts:
            return parts

    for candidate in ("openclaw", "clawdbot"):
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved]

    for path in (
        Path("/opt/homebrew/bin/openclaw"),
        Path("/usr/local/bin/openclaw"),
        Path("~/bin/openclaw").expanduser(),
    ):
        if path.exists():
            return [str(path)]

    return None


def default_runner(argv: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    return completed.returncode, completed.stdout, completed.stderr


def quoted_command(argv: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in argv)


def run_cli(cli_command: Sequence[str], runner: Runner, *args: str) -> str:
    argv = [*cli_command, "cron", *args]
    code, stdout, stderr = runner(argv)
    if code != 0:
        detail = stderr.strip() or stdout.strip() or f"exit {code}"
        raise RuntimeError(f"{quoted_command(argv)} failed: {detail}")
    return stdout.strip()


def parse_json_output(raw: str) -> Any:
    if not raw:
        return {}
    return json.loads(raw)


def scheduler_jobs_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("jobs", "items", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def scheduler_job_key(job: dict[str, Any]) -> str | None:
    for key in ("jobId", "id", "name"):
        value = job.get(key)
        if value:
            return str(value)
    return None


def scheduler_job_matches_name(job: dict[str, Any], name: str) -> bool:
    for key in ("name", "jobId", "id"):
        value = job.get(key)
        if value and str(value) == name:
            return True
    return False


def scheduler_job_matches_spec(job: dict[str, Any], spec: dict[str, str]) -> bool:
    schedule = job.get("schedule") or {}
    payload = job.get("payload") or {}
    wake_mode = job.get("wakeMode") or "now"
    enabled = job.get("enabled")
    return (
        schedule.get("kind") == "cron"
        and schedule.get("expr") == spec["expr"]
        and schedule.get("tz") == spec["tz"]
        and job.get("sessionTarget") == "main"
        and payload.get("kind") == "systemEvent"
        and payload.get("text") == spec["system_event"]
        and wake_mode == spec["wake_mode"]
        and enabled is not False
    )


def add_scheduler_job(cli_command: Sequence[str], runner: Runner, spec: dict[str, str]) -> None:
    run_cli(
        cli_command,
        runner,
        "add",
        "--name",
        spec["name"],
        "--cron",
        spec["expr"],
        "--tz",
        spec["tz"],
        "--session",
        "main",
        "--system-event",
        spec["system_event"],
        "--wake",
        spec["wake_mode"],
    )


def remove_scheduler_job(cli_command: Sequence[str], runner: Runner, job: dict[str, Any]) -> None:
    key = scheduler_job_key(job)
    if not key:
        raise RuntimeError(f"cannot remove scheduler job without identifier: {job!r}")
    run_cli(cli_command, runner, "rm", key)


def sync_scheduler(cli_command: Sequence[str], runner: Runner) -> dict[str, Any]:
    status_before = parse_json_output(run_cli(cli_command, runner, "status", "--json"))
    jobs_before = scheduler_jobs_from_payload(parse_json_output(run_cli(cli_command, runner, "list", "--all", "--json")))
    actions: list[dict[str, str]] = []

    for spec in expected_scheduler_specs():
        matches = [job for job in jobs_before if scheduler_job_matches_name(job, spec["name"])]
        exact = [job for job in matches if scheduler_job_matches_spec(job, spec)]
        if len(matches) == 1 and len(exact) == 1:
            actions.append({"job": spec["name"], "action": "kept"})
            continue
        for job in matches:
            remove_scheduler_job(cli_command, runner, job)
        add_scheduler_job(cli_command, runner, spec)
        actions.append({"job": spec["name"], "action": "replaced" if matches else "added"})

    status_after = parse_json_output(run_cli(cli_command, runner, "status", "--json"))
    jobs_after = scheduler_jobs_from_payload(parse_json_output(run_cli(cli_command, runner, "list", "--all", "--json")))
    missing = [spec["name"] for spec in expected_scheduler_specs() if not any(scheduler_job_matches_name(job, spec["name"]) for job in jobs_after)]
    if missing:
        raise RuntimeError(f"scheduler still missing expected jobs after sync: {', '.join(missing)}")

    return {
        "mode": "cli_synced",
        "cli_command": quoted_command(cli_command),
        "changed": any(action["action"] != "kept" for action in actions),
        "actions": actions,
        "status_before": status_before,
        "status_after": status_after,
        "jobs_before": len(jobs_before),
        "jobs_after": len(jobs_after),
        "loaded_names": sorted({job.get("name") or job.get("jobId") or job.get("id") for job in jobs_after if (job.get("name") or job.get("jobId") or job.get("id"))}),
    }


def install(
    path: Path,
    *,
    allow_cli_sync: bool = True,
    cli_command: Sequence[str] | str | None = None,
    runner: Runner | None = None,
) -> dict[str, Any]:
    runner = runner or default_runner
    warnings: list[str] = []

    if allow_cli_sync:
        resolved_cli = discover_cli_command(cli_command)
        if resolved_cli:
            try:
                scheduler = sync_scheduler(resolved_cli, runner)
                return {
                    "ok": True,
                    "changed": scheduler["changed"],
                    "backup": None,
                    "jobs": expected_jobs(),
                    "scheduler": scheduler,
                    "warnings": warnings,
                }
            except Exception as exc:
                file_result = install_file(path)
                warnings.append(
                    "OpenClaw cron scheduler live sync failed. The jobs file was updated as a fallback, "
                    "but a running Gateway may still need restart or a working openclaw CLI to load these jobs."
                )
                return {
                    "ok": False,
                    "changed": file_result["changed"],
                    "backup": file_result["backup"],
                    "jobs": file_result["jobs"],
                    "scheduler": {
                        "mode": "cli_failed",
                        "cli_command": quoted_command(resolved_cli),
                        "error": str(exc),
                    },
                    "warnings": warnings,
                }

    file_result = install_file(path)
    warnings.append(
        "OpenClaw CLI was not available, so only ~/.openclaw/cron/jobs.json was updated. "
        "If the Gateway is already running, restart it or rerun this installer with a working openclaw CLI."
    )
    return {
        "ok": True,
        "changed": file_result["changed"],
        "backup": file_result["backup"],
        "jobs": file_result["jobs"],
        "scheduler": {
            "mode": "file_only",
            "cli_command": None,
            "warnings": warnings,
        },
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs-path", default=str(DEFAULT_JOBS_PATH))
    parser.add_argument("--openclaw-cli")
    parser.add_argument("--no-cli-sync", action="store_true")
    args = parser.parse_args()
    result = install(
        Path(args.jobs_path),
        allow_cli_sync=not args.no_cli_sync,
        cli_command=args.openclaw_cli,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
