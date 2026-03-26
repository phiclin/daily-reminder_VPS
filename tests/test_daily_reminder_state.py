from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path("/Users/phiclin/.openclaw/skills/daily-reminder_VPS")
STATE_SCRIPT = ROOT / "scripts" / "daily_reminder_state.py"
CRON_SCRIPT = ROOT / "scripts" / "install_cron.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


dr = load_module(STATE_SCRIPT, "daily_reminder_state")
cron = load_module(CRON_SCRIPT, "install_cron")


class DailyReminderStateTests(unittest.TestCase):
    def test_add_tasks_appends_and_preserves_ids(self):
        state = dr.empty_state("2026-03-23")
        now = dr.parse_iso("2026-03-23T09:05:00+08:00")
        state = dr.add_tasks(
            state,
            now,
            [{"text": "写日报", "special_time": None}, {"text": "跟进客户", "special_time": "15:30"}],
            "start",
        )
        later = dr.parse_iso("2026-03-23T10:05:00+08:00")
        state = dr.add_tasks(state, later, [{"text": "整理方案", "special_time": None}], "start")

        self.assertEqual([task["id"] for task in state["tasks"]], [1, 2, 3])
        self.assertEqual(state["tasks"][1]["special_time"], "15:30")
        self.assertEqual(state["status"], dr.STATUS_RUNNING)

    def test_complete_last_task_pauses_future_reminders(self):
        state = dr.empty_state("2026-03-23")
        now = dr.parse_iso("2026-03-23T09:00:00+08:00")
        state = dr.add_tasks(state, now, [{"text": "交电费", "special_time": "15:30"}], "start")

        result = dr.complete_task(state, dr.parse_iso("2026-03-23T09:10:00+08:00"), 1)

        self.assertTrue(result["all_done"])
        self.assertEqual(result["state"]["status"], dr.STATUS_PAUSED_ALL_DONE)

        reminder = dr.build_reminder(result["state"], dr.parse_iso("2026-03-23T15:30:00+08:00"))
        self.assertEqual(reminder["kind"], "none")

    def test_build_reminder_merges_periodic_and_special_due(self):
        state = dr.empty_state("2026-03-23")
        now = dr.parse_iso("2026-03-23T09:50:00+08:00")
        state = dr.add_tasks(
            state,
            now,
            [{"text": "写日报", "special_time": None}, {"text": "跟进客户", "special_time": "10:00"}],
            "start",
        )
        state["last_check_at"] = "2026-03-23T09:59:00+08:00"

        result = dr.build_reminder(state, dr.parse_iso("2026-03-23T10:00:00+08:00"))

        self.assertEqual(result["kind"], "merged")
        self.assertIn("到点任务：第 2 条", result["message"])
        self.assertIn("1. 写日报", result["message"])
        self.assertIn("2. 跟进客户 @10:00", result["message"])

    def test_build_reminder_catches_up_missed_periodic_slot(self):
        state = dr.empty_state("2026-03-23")
        now = dr.parse_iso("2026-03-23T09:00:00+08:00")
        state = dr.add_tasks(state, now, [{"text": "写日报", "special_time": None}], "start")
        state["last_check_at"] = "2026-03-23T09:31:00+08:00"

        result = dr.build_reminder(state, dr.parse_iso("2026-03-23T10:05:00+08:00"))

        self.assertEqual(result["kind"], "catchup")
        self.assertIn("【每日提醒｜补发提醒】", result["message"])

    def test_reschedule_rejects_past_time(self):
        state = dr.empty_state("2026-03-23")
        now = dr.parse_iso("2026-03-23T16:10:00+08:00")
        state = dr.add_tasks(state, now, [{"text": "回消息", "special_time": None}], "start")

        result = dr.reschedule_task(state, now, 1, "15:00")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "past_time")

    def test_complete_missing_task_returns_error(self):
        state = dr.empty_state("2026-03-23")
        now = dr.parse_iso("2026-03-23T10:00:00+08:00")

        result = dr.complete_task(state, now, 99)

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "task_not_found")

    def test_complete_already_done_task_is_idempotent(self):
        state = dr.empty_state("2026-03-23")
        now = dr.parse_iso("2026-03-23T09:00:00+08:00")
        state = dr.add_tasks(state, now, [{"text": "写日报", "special_time": None}], "start")

        first = dr.complete_task(state, dr.parse_iso("2026-03-23T09:05:00+08:00"), 1)
        second = dr.complete_task(first["state"], dr.parse_iso("2026-03-23T09:06:00+08:00"), 1)

        self.assertTrue(second["ok"])
        self.assertTrue(second["already_done"])
        self.assertEqual(second["state"]["status"], dr.STATUS_PAUSED_ALL_DONE)

    def test_clear_day_resets_tasks(self):
        state = dr.empty_state("2026-03-23")
        now = dr.parse_iso("2026-03-23T18:00:00+08:00")
        state = dr.add_tasks(state, now, [{"text": "写日报", "special_time": None}], "start")

        cleared = dr.clear_day(state, dr.parse_iso("2026-03-24T00:00:00+08:00"))

        self.assertEqual(cleared["date"], "2026-03-24")
        self.assertEqual(cleared["tasks"], [])
        self.assertEqual(cleared["status"], dr.STATUS_STOPPED)

    def test_clear_day_archives_previous_day_before_reset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            archive_root = Path(tmpdir) / "archive"
            state = dr.empty_state("2026-03-25")
            start = dr.parse_iso("2026-03-25T09:00:00+08:00")
            state = dr.add_tasks(state, start, [{"text": "写日报", "special_time": "15:30"}], "start")
            dr.save_state(state_path, state)

            result = dr.command_clear_day(
                argparse.Namespace(
                    state=str(state_path),
                    archive_root=str(archive_root),
                    now="2026-03-26T00:00:00+08:00",
                )
            )

            archived = json.loads((archive_root / "2026" / "03" / "2026-03-25.json").read_text())
            self.assertTrue(result["ok"])
            self.assertEqual(result["state"]["date"], "2026-03-26")
            self.assertEqual(archived["archive_reason"], "midnight_clear")
            self.assertEqual(archived["total_tasks"], 1)
            self.assertEqual(archived["tasks"][0]["text"], "写日报")

    def test_stop_day_archives_same_day_before_reset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            archive_root = Path(tmpdir) / "archive"
            state = dr.empty_state("2026-03-26")
            start = dr.parse_iso("2026-03-26T09:00:00+08:00")
            state = dr.add_tasks(state, start, [{"text": "整理方案", "special_time": None}], "start")
            dr.save_state(state_path, state)

            result = dr.command_stop_day(
                argparse.Namespace(
                    state=str(state_path),
                    archive_root=str(archive_root),
                    now="2026-03-26T18:00:00+08:00",
                )
            )

            archived = json.loads((archive_root / "2026" / "03" / "2026-03-26.json").read_text())
            self.assertTrue(result["ok"])
            self.assertEqual(archived["archive_reason"], "manual_stop")
            self.assertEqual(archived["tasks"][0]["id"], 1)
            self.assertEqual(result["state"]["tasks"], [])

    def test_ensure_state_rollover_archives_stale_day(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "state.json"
            archive_root = Path(tmpdir) / "archive"
            state = dr.empty_state("2026-03-25")
            start = dr.parse_iso("2026-03-25T21:00:00+08:00")
            state = dr.add_tasks(state, start, [{"text": "收尾工作", "special_time": None}], "start")
            dr.save_state(state_path, state)

            result = dr.command_ensure_state(
                argparse.Namespace(
                    state=str(state_path),
                    archive_root=str(archive_root),
                    now="2026-03-26T08:00:00+08:00",
                )
            )

            archived = json.loads((archive_root / "2026" / "03" / "2026-03-25.json").read_text())
            self.assertTrue(result["ok"])
            self.assertEqual(result["state"]["date"], "2026-03-26")
            self.assertEqual(archived["archive_reason"], "rollover")
            self.assertEqual(archived["pending_tasks"], 1)

    def test_show_archive_renders_saved_day(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            (archive_root / "2026" / "03").mkdir(parents=True)
            record = {
                "date": "2026-03-26",
                "timezone": "Asia/Shanghai",
                "archived_at": "2026-03-27T00:00:00+08:00",
                "archive_reason": "midnight_clear",
                "status_before_archive": "paused_all_done",
                "total_tasks": 2,
                "completed_tasks": 1,
                "pending_tasks": 1,
                "completion_rate": 50.0,
                "tasks": [
                    {"id": 1, "text": "写日报", "done": True, "special_time": None, "created_at": "x", "updated_at": "x"},
                    {"id": 2, "text": "跟进客户", "done": False, "special_time": "15:30", "created_at": "x", "updated_at": "x"},
                ],
            }
            (archive_root / "2026" / "03" / "2026-03-26.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")

            result = dr.command_show_archive(
                argparse.Namespace(
                    archive_root=str(archive_root),
                    date="2026-03-26",
                    now="2026-03-27T09:00:00+08:00",
                )
            )

            self.assertTrue(result["ok"])
            self.assertIn("【每日提醒｜归档查看】", result["message"])
            self.assertIn("归档原因：零点清空", result["message"])
            self.assertIn("~~1. 写日报~~", result["message"])
            self.assertIn("2. 跟进客户 @15:30", result["message"])

    def test_summary_aggregates_multiple_archived_days(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            (archive_root / "2026" / "03").mkdir(parents=True)
            for date, total, completed, reason in (
                ("2026-03-24", 3, 2, "midnight_clear"),
                ("2026-03-25", 2, 2, "manual_stop"),
            ):
                record = {
                    "date": date,
                    "timezone": "Asia/Shanghai",
                    "archived_at": f"{date}T23:59:00+08:00",
                    "archive_reason": reason,
                    "status_before_archive": "running",
                    "total_tasks": total,
                    "completed_tasks": completed,
                    "pending_tasks": total - completed,
                    "completion_rate": round((completed / total) * 100, 2),
                    "tasks": [],
                }
                (archive_root / "2026" / "03" / f"{date}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")

            result = dr.command_summary(
                argparse.Namespace(
                    archive_root=str(archive_root),
                    preset=None,
                    from_date="2026-03-24",
                    to_date="2026-03-25",
                    now="2026-03-26T09:00:00+08:00",
                )
            )

            self.assertTrue(result["ok"])
            self.assertIn("【每日提醒｜汇总查看】", result["message"])
            self.assertIn("归档天数：2", result["message"])
            self.assertIn("总任务数：5", result["message"])
            self.assertIn("已完成：4", result["message"])
            self.assertIn("2026-03-24", result["message"])
            self.assertIn("2026-03-25", result["message"])


class InstallCronTests(unittest.TestCase):
    def test_install_cron_upserts_and_preserves_unrelated_jobs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs.json"
            jobs_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "jobs": [
                            {
                                "id": "other-job",
                                "schedule": {"kind": "cron", "expr": "0 9 * * *"},
                                "payload": {"kind": "systemEvent", "text": "noop"},
                            },
                            {"id": "daily-reminder-checker", "schedule": {"kind": "cron", "expr": "* * * * *"}},
                            {"id": "daily-reminder-midnight-clear", "schedule": {"kind": "cron", "expr": "0 0 * * *"}},
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n"
            )

            result = cron.install(jobs_path, allow_cli_sync=False)

            self.assertTrue(result["changed"])
            saved = json.loads(jobs_path.read_text())
            ids = [job["id"] for job in saved["jobs"]]
            self.assertEqual(ids, ["other-job", cron.CHECKER_ID, cron.CLEAR_ID])
            checker = next(job for job in saved["jobs"] if job["id"] == cron.CHECKER_ID)
            self.assertEqual(checker["sessionTarget"], "isolated")
            self.assertEqual(checker["payload"]["kind"], "agentTurn")
            self.assertIn("build-reminder", checker["payload"]["message"])
            self.assertEqual(checker["delivery"]["mode"], "announce")
            clear = next(job for job in saved["jobs"] if job["id"] == cron.CLEAR_ID)
            self.assertEqual(clear["sessionTarget"], "isolated")
            self.assertEqual(clear["payload"]["kind"], "agentTurn")
            self.assertIn("clear-day", clear["payload"]["message"])
            self.assertNotIn("静默", clear["payload"]["message"])
            self.assertEqual(clear["delivery"]["mode"], "none")

    def test_install_cron_syncs_live_scheduler_when_cli_is_available(self):
        calls: list[list[str]] = []
        list_responses = [
            [],
            [
                {
                    "jobId": "job-checker",
                    "name": cron.CHECKER_ID,
                    "schedule": {"kind": "cron", "expr": "* * * * *", "tz": "Asia/Shanghai"},
                    "sessionTarget": "isolated",
                    "wakeMode": "next-heartbeat",
                    "payload": {"kind": "agentTurn", "message": cron.checker_prompt()},
                    "delivery": {"mode": "announce", "channel": "feishu", "to": "user:123", "accountId": "main"},
                    "enabled": True,
                },
                {
                    "jobId": "job-clear",
                    "name": cron.CLEAR_ID,
                    "schedule": {"kind": "cron", "expr": "0 0 * * *", "tz": "Asia/Shanghai"},
                    "sessionTarget": "isolated",
                    "wakeMode": "next-heartbeat",
                    "payload": {"kind": "agentTurn", "message": cron.clear_prompt()},
                    "delivery": {"mode": "none"},
                    "enabled": True,
                },
            ],
        ]

        def runner(argv: list[str]) -> tuple[int, str, str]:
            calls.append(argv)
            if argv == ["fake-openclaw", "cron", "status", "--json"]:
                return 0, json.dumps({"jobs": 0}), ""
            if argv == ["fake-openclaw", "cron", "list", "--all", "--json"]:
                return 0, json.dumps(list_responses.pop(0)), ""
            if argv[:3] == ["fake-openclaw", "cron", "add"]:
                return 0, json.dumps({"ok": True}), ""
            self.fail(f"unexpected argv: {argv}")

        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs.json"
            result = cron.install(
                jobs_path,
                cli_command=["fake-openclaw"],
                runner=runner,
                delivery_channel="feishu",
                delivery_to="user:123",
                delivery_account="main",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["scheduler"]["mode"], "cli_synced")
        add_calls = [argv for argv in calls if argv[:3] == ["fake-openclaw", "cron", "add"]]
        self.assertEqual(len(add_calls), 2)
        checker_add = next(argv for argv in add_calls if cron.CHECKER_ID in argv)
        clear_add = next(argv for argv in add_calls if cron.CLEAR_ID in argv)
        self.assertIn("--session", checker_add)
        self.assertIn("isolated", checker_add)
        self.assertIn("--message", checker_add)
        self.assertIn("--announce", checker_add)
        self.assertIn("--channel", checker_add)
        self.assertIn("feishu", checker_add)
        self.assertIn("--to", checker_add)
        self.assertIn("user:123", checker_add)
        self.assertIn("--account", checker_add)
        self.assertIn("main", checker_add)
        self.assertIn("--no-deliver", clear_add)

    def test_install_cron_warns_when_only_file_install_is_possible(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_path = Path(tmpdir) / "jobs.json"

            result = cron.install(jobs_path, cli_command=[], allow_cli_sync=True)

            self.assertTrue(result["ok"])
            self.assertEqual(result["scheduler"]["mode"], "file_only")
            self.assertTrue(result["scheduler"]["warnings"])
            self.assertTrue(jobs_path.exists())

    def test_checker_job_can_store_explicit_delivery_target(self):
        job = cron.checker_job(delivery_channel="feishu", delivery_to="user:abc", delivery_account="main")

        self.assertEqual(job["delivery"]["mode"], "announce")
        self.assertEqual(job["delivery"]["channel"], "feishu")
        self.assertEqual(job["delivery"]["to"], "user:abc")
        self.assertEqual(job["delivery"]["accountId"], "main")


if __name__ == "__main__":
    unittest.main()
