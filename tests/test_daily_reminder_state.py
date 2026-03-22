from __future__ import annotations

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

            result = cron.install(jobs_path)

            self.assertTrue(result["changed"])
            saved = json.loads(jobs_path.read_text())
            ids = [job["id"] for job in saved["jobs"]]
            self.assertEqual(ids, ["other-job", cron.CHECKER_ID, cron.CLEAR_ID])
            checker = next(job for job in saved["jobs"] if job["id"] == cron.CHECKER_ID)
            self.assertEqual(checker["sessionTarget"], "main")
            self.assertEqual(checker["payload"]["kind"], "systemEvent")


if __name__ == "__main__":
    unittest.main()
