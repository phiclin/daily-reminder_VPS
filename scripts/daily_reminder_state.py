#!/usr/bin/env python3
"""Daily reminder state manager for OpenClaw."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


TZ_NAME = "Asia/Shanghai"
TZ = ZoneInfo(TZ_NAME)
DEFAULT_STATE_PATH = Path("~/.openclaw/workspace/.daily-reminder_VPS/state.json").expanduser()
STATUS_RUNNING = "running"
STATUS_PAUSED_ALL_DONE = "paused_all_done"
STATUS_STOPPED = "stopped"


def _now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=TZ)
    return parsed.astimezone(TZ)


def parse_task_list(raw: str) -> list[dict[str, Any]]:
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("tasks payload must be a JSON list")
    parsed: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("each task must be an object")
        text = str(item.get("text", "")).strip()
        if not text:
            raise ValueError("task text cannot be empty")
        special_time = item.get("special_time")
        if special_time is not None:
            special_time = normalize_time(str(special_time))
        parsed.append({"text": text, "special_time": special_time})
    return parsed


def normalize_time(value: str) -> str:
    stripped = value.strip()
    for fmt in ("%H:%M", "%H.%M"):
        try:
            parsed = datetime.strptime(stripped, fmt)
            return parsed.strftime("%H:%M")
        except ValueError:
            continue
    raise ValueError(f"invalid time format: {value}")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def empty_state(today: str | None = None) -> dict[str, Any]:
    return {
        "date": today or datetime.now(TZ).date().isoformat(),
        "timezone": TZ_NAME,
        "status": STATUS_STOPPED,
        "next_task_id": 1,
        "last_check_at": None,
        "last_periodic_slot": None,
        "all_done_announced_at": None,
        "tasks": [],
        "updated_at": _now_iso(),
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_state()
    data = json.loads(path.read_text())
    return normalize_state(data)


def save_state(path: Path, state: dict[str, Any]) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    normalized = empty_state(state.get("date"))
    normalized.update({k: v for k, v in state.items() if k in normalized})
    normalized["tasks"] = []
    max_id = 0
    for raw_task in state.get("tasks", []):
        task = {
            "id": int(raw_task["id"]),
            "text": str(raw_task["text"]).strip(),
            "done": bool(raw_task.get("done", False)),
            "special_time": normalize_time(raw_task["special_time"]) if raw_task.get("special_time") else None,
            "special_notified_at": raw_task.get("special_notified_at"),
            "created_at": raw_task.get("created_at") or _now_iso(),
            "updated_at": raw_task.get("updated_at") or _now_iso(),
        }
        max_id = max(max_id, task["id"])
        normalized["tasks"].append(task)
    normalized["next_task_id"] = max(max_id + 1, int(state.get("next_task_id", max_id + 1)))
    normalized["updated_at"] = state.get("updated_at") or _now_iso()
    return normalized


def local_now(override: str | None) -> datetime:
    return parse_iso(override) if override else datetime.now(TZ)


def ensure_today(state: dict[str, Any], now: datetime) -> tuple[dict[str, Any], bool]:
    today = now.date().isoformat()
    if state["date"] == today:
        return state, False
    return empty_state(today), True


def find_task(state: dict[str, Any], task_id: int) -> dict[str, Any]:
    for task in state["tasks"]:
        if task["id"] == task_id:
            return task
    raise KeyError(f"task {task_id} not found")


def all_tasks_done(state: dict[str, Any]) -> bool:
    return bool(state["tasks"]) and all(task["done"] for task in state["tasks"])


def task_line(task: dict[str, Any]) -> str:
    suffix = f" @{task['special_time']}" if task["special_time"] else ""
    line = f"{task['id']}. {task['text']}{suffix}"
    if task["done"]:
        return f"~~{line}~~"
    return line


def render_message(state: dict[str, Any], title: str, now: datetime, reason_detail: str | None = None) -> str:
    total = len(state["tasks"])
    completed = sum(1 for task in state["tasks"] if task["done"])
    pending = total - completed
    lines = [
        f"【每日提醒｜{title}】",
        f"时间：{now.strftime('%H:%M')}",
        f"今天共 {total} 条，已完成 {completed} 条，未完成 {pending} 条",
    ]
    if reason_detail:
        lines.append(reason_detail)
    lines.append("")
    if state["tasks"]:
        lines.extend(task_line(task) for task in state["tasks"])
    else:
        lines.append("今天还没有任务。")
    return "\n".join(lines).strip()


def slot_at(dt: datetime, slot_time: time) -> datetime:
    return datetime.combine(dt.date(), slot_time, tzinfo=TZ)


def periodic_slots_between(start: datetime, end: datetime) -> list[datetime]:
    if end <= start:
        return []
    cursor = start.replace(second=0, microsecond=0)
    cursor -= timedelta(minutes=cursor.minute % 30)
    if cursor <= start:
        cursor += timedelta(minutes=30)
    slots: list[datetime] = []
    while cursor <= end:
        if cursor.minute in (0, 30):
            slots.append(cursor)
        cursor += timedelta(minutes=30)
    return slots


def special_due_events(state: dict[str, Any], start: datetime, end: datetime) -> list[tuple[dict[str, Any], datetime]]:
    if end <= start:
        return []
    due: list[tuple[dict[str, Any], datetime]] = []
    for task in state["tasks"]:
        if not task["special_time"]:
            continue
        hour, minute = map(int, task["special_time"].split(":"))
        target = slot_at(end, time(hour=hour, minute=minute))
        if not (start < target <= end):
            continue
        notified = task.get("special_notified_at")
        if notified:
            notified_dt = parse_iso(notified)
            if notified_dt.date() == end.date() and notified_dt.hour == target.hour and notified_dt.minute == target.minute:
                continue
        due.append((task, target))
    return due


def add_tasks(state: dict[str, Any], now: datetime, tasks: list[dict[str, Any]], command: str) -> dict[str, Any]:
    state, _ = ensure_today(state, now)
    if command == "start" and state["status"] == STATUS_STOPPED:
        state = empty_state(now.date().isoformat())
    for item in tasks:
        state["tasks"].append(
            {
                "id": state["next_task_id"],
                "text": item["text"],
                "done": False,
                "special_time": item["special_time"],
                "special_notified_at": None,
                "created_at": now.isoformat(timespec="seconds"),
                "updated_at": now.isoformat(timespec="seconds"),
            }
        )
        state["next_task_id"] += 1
    if tasks:
        state["status"] = STATUS_RUNNING
        state["all_done_announced_at"] = None
    state["updated_at"] = now.isoformat(timespec="seconds")
    return state


def complete_task(state: dict[str, Any], now: datetime, task_id: int) -> dict[str, Any]:
    state, _ = ensure_today(state, now)
    try:
        task = find_task(state, task_id)
    except KeyError:
        return {
            "ok": False,
            "error": "task_not_found",
            "message": f"找不到第 {task_id} 条任务。",
            "state": state,
        }
    was_done = task["done"]
    task["done"] = True
    task["updated_at"] = now.isoformat(timespec="seconds")
    result = {
        "ok": True,
        "task_id": task_id,
        "already_done": was_done,
        "all_done": False,
        "message": f"已将第 {task_id} 条标记为完成。" if not was_done else f"第 {task_id} 条之前已经是完成状态。",
    }
    if all_tasks_done(state):
        state["status"] = STATUS_PAUSED_ALL_DONE
        state["all_done_announced_at"] = now.isoformat(timespec="seconds")
        result["all_done"] = True
        result["message"] = "今日任务已全部完成。"
    state["updated_at"] = now.isoformat(timespec="seconds")
    result["state"] = state
    return result


def reschedule_task(state: dict[str, Any], now: datetime, task_id: int, special_time: str) -> dict[str, Any]:
    state, _ = ensure_today(state, now)
    normalized_time = normalize_time(special_time)
    hour, minute = map(int, normalized_time.split(":"))
    target = slot_at(now, time(hour=hour, minute=minute))
    if target <= now:
        return {
            "ok": False,
            "error": "past_time",
            "message": "该时间已经过去，请改成今天稍后的具体时间。",
        }
    try:
        task = find_task(state, task_id)
    except KeyError:
        return {
            "ok": False,
            "error": "task_not_found",
            "message": f"找不到第 {task_id} 条任务。",
        }
    task["special_time"] = normalized_time
    task["special_notified_at"] = None
    task["updated_at"] = now.isoformat(timespec="seconds")
    state["updated_at"] = now.isoformat(timespec="seconds")
    return {
        "ok": True,
        "task_id": task_id,
        "special_time": normalized_time,
        "message": f"已将第 {task_id} 条改到 {normalized_time}。",
        "state": state,
    }


def stop_day(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    cleared = empty_state(now.date().isoformat())
    cleared["updated_at"] = now.isoformat(timespec="seconds")
    return cleared


def clear_day(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    cleared = empty_state(now.date().isoformat())
    cleared["updated_at"] = now.isoformat(timespec="seconds")
    return cleared


def build_reminder(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    state, was_stale = ensure_today(state, now)
    if was_stale:
        state["updated_at"] = now.isoformat(timespec="seconds")
        state["last_check_at"] = now.isoformat(timespec="seconds")
        return {"ok": True, "kind": "none", "message": "", "state": state}

    previous_check = parse_iso(state["last_check_at"]) if state["last_check_at"] else now - timedelta(minutes=1)
    periodic_due_slots = periodic_slots_between(previous_check, now)
    special_due = special_due_events(state, previous_check, now)

    if state["status"] != STATUS_RUNNING or not state["tasks"]:
        state["last_check_at"] = now.isoformat(timespec="seconds")
        state["updated_at"] = now.isoformat(timespec="seconds")
        return {"ok": True, "kind": "none", "message": "", "state": state}

    if all_tasks_done(state):
        state["status"] = STATUS_PAUSED_ALL_DONE
        state["last_check_at"] = now.isoformat(timespec="seconds")
        state["updated_at"] = now.isoformat(timespec="seconds")
        return {"ok": True, "kind": "none", "message": "", "state": state}

    missed_periodic = any(slot < now.replace(second=0, microsecond=0) for slot in periodic_due_slots)
    missed_special = any(target < now.replace(second=0, microsecond=0) for _, target in special_due)
    catchup = missed_periodic or missed_special

    kind = "none"
    title = ""
    reason_detail = None
    if periodic_due_slots or special_due:
        if catchup:
            kind = "catchup"
            title = "补发提醒"
        elif periodic_due_slots and special_due:
            kind = "merged"
            title = "合并提醒"
        elif special_due:
            kind = "special"
            title = "专项提醒"
        else:
            kind = "periodic"
            title = "常规提醒"

    due_ids = [task["id"] for task, _ in special_due]
    if due_ids:
        reason_detail = "到点任务：" + "、".join(f"第 {task_id} 条" for task_id in due_ids)

    if periodic_due_slots:
        state["last_periodic_slot"] = periodic_due_slots[-1].isoformat(timespec="seconds")
    for task, target in special_due:
        task["special_notified_at"] = target.isoformat(timespec="seconds")
        task["updated_at"] = now.isoformat(timespec="seconds")

    state["last_check_at"] = now.isoformat(timespec="seconds")
    state["updated_at"] = now.isoformat(timespec="seconds")
    return {
        "ok": True,
        "kind": kind,
        "message": render_message(state, title, now, reason_detail) if kind != "none" else "",
        "state": state,
    }


def status_payload(state: dict[str, Any], now: datetime) -> dict[str, Any]:
    state, _ = ensure_today(state, now)
    return {"ok": True, "kind": "status", "message": render_message(state, "状态查看", now), "state": state}


def command_ensure_state(args: argparse.Namespace) -> dict[str, Any]:
    now = local_now(args.now)
    state = load_state(Path(args.state))
    state, _ = ensure_today(state, now)
    state["updated_at"] = now.isoformat(timespec="seconds")
    save_state(Path(args.state), state)
    return {"ok": True, "state": state}


def command_add_tasks(args: argparse.Namespace) -> dict[str, Any]:
    now = local_now(args.now)
    path = Path(args.state)
    state = load_state(path)
    state = add_tasks(state, now, parse_task_list(args.tasks_json), args.command)
    save_state(path, state)
    payload = status_payload(state, now)
    payload["command"] = args.command
    return payload


def command_complete_task(args: argparse.Namespace) -> dict[str, Any]:
    now = local_now(args.now)
    path = Path(args.state)
    state = load_state(path)
    result = complete_task(state, now, args.task_id)
    save_state(path, result["state"])
    if result["all_done"]:
        result["message"] = render_message(result["state"], "今日已全部完成", now)
    return result


def command_reschedule_task(args: argparse.Namespace) -> dict[str, Any]:
    now = local_now(args.now)
    path = Path(args.state)
    state = load_state(path)
    result = reschedule_task(state, now, args.task_id, args.special_time)
    if result["ok"]:
        save_state(path, result["state"])
    return result


def command_stop_day(args: argparse.Namespace) -> dict[str, Any]:
    now = local_now(args.now)
    path = Path(args.state)
    state = stop_day(load_state(path), now)
    save_state(path, state)
    return {"ok": True, "state": state, "message": "已停止今天的每日提醒并清空任务。"}


def command_clear_day(args: argparse.Namespace) -> dict[str, Any]:
    now = local_now(args.now)
    path = Path(args.state)
    state = clear_day(load_state(path), now)
    save_state(path, state)
    return {"ok": True, "state": state, "message": ""}


def command_build_reminder(args: argparse.Namespace) -> dict[str, Any]:
    now = local_now(args.now)
    path = Path(args.state)
    state = load_state(path)
    result = build_reminder(state, now)
    save_state(path, result["state"])
    return result


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    now = local_now(args.now)
    path = Path(args.state)
    state = load_state(path)
    return status_payload(state, now)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    ensure_parser = subparsers.add_parser("ensure-state")
    ensure_parser.add_argument("--now")
    ensure_parser.set_defaults(func=command_ensure_state)

    add_parser = subparsers.add_parser("add-tasks")
    add_parser.add_argument("--now")
    add_parser.add_argument("--command", choices=["start", "add"], required=True)
    add_parser.add_argument("--tasks-json", required=True)
    add_parser.set_defaults(func=command_add_tasks)

    complete_parser = subparsers.add_parser("complete-task")
    complete_parser.add_argument("--now")
    complete_parser.add_argument("--task-id", type=int, required=True)
    complete_parser.set_defaults(func=command_complete_task)

    reschedule_parser = subparsers.add_parser("reschedule-task")
    reschedule_parser.add_argument("--now")
    reschedule_parser.add_argument("--task-id", type=int, required=True)
    reschedule_parser.add_argument("--special-time", required=True)
    reschedule_parser.set_defaults(func=command_reschedule_task)

    stop_parser = subparsers.add_parser("stop-day")
    stop_parser.add_argument("--now")
    stop_parser.set_defaults(func=command_stop_day)

    clear_parser = subparsers.add_parser("clear-day")
    clear_parser.add_argument("--now")
    clear_parser.set_defaults(func=command_clear_day)

    build_parser_cmd = subparsers.add_parser("build-reminder")
    build_parser_cmd.add_argument("--now")
    build_parser_cmd.set_defaults(func=command_build_reminder)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--now")
    status_parser.set_defaults(func=command_status)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
