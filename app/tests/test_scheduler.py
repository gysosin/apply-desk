import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path

from app.scheduler import Runner, Schedules, next_run


def sched(**kw):
    base = {"id": "s", "name": "n", "task": "daily_run", "kind": "daily", "time": "10:07", "days": [],
            "every_min": 60, "enabled": True, "last_run": None, "created": "2026-10-05T08:00:00"}
    base.update(kw)
    return base


class NextRunTest(unittest.TestCase):
    def test_daily_same_day_later(self):
        self.assertEqual(next_run(sched()), datetime(2026, 10, 5, 10, 7))

    def test_daily_after_last_run_goes_to_tomorrow(self):
        s = sched(last_run="2026-10-05T10:07:30")
        self.assertEqual(next_run(s), datetime(2026, 10, 6, 10, 7))

    def test_weekdays_only(self):
        # 2026-10-09 is a Friday; next weekday slot after Friday's run is Monday 12th
        s = sched(days=[0, 1, 2, 3, 4], last_run="2026-10-09T10:08:00")
        self.assertEqual(next_run(s), datetime(2026, 10, 12, 10, 7))

    def test_missed_run_catches_up_once(self):
        s = sched(last_run="2026-10-01T10:07:00")  # PC was off for days
        nr = next_run(s)
        self.assertEqual(nr, datetime(2026, 10, 2, 10, 7))  # in the past -> due now
        s["last_run"] = "2026-10-06T09:00:00"  # ran at startup
        self.assertEqual(next_run(s), datetime(2026, 10, 6, 10, 7))

    def test_interval(self):
        s = sched(kind="interval", every_min=90, last_run="2026-10-05T10:00:00")
        self.assertEqual(next_run(s), datetime(2026, 10, 5, 11, 30))

    def test_disabled(self):
        self.assertIsNone(next_run(sched(enabled=False)))


class SchedulesStoreTest(unittest.TestCase):
    def test_crud_validation(self):
        with tempfile.TemporaryDirectory() as d:
            st = Schedules(Path(d) / "s.json")
            s = st.create({"name": "Morning", "task": "daily_run", "kind": "daily", "time": "10:07", "days": [0, 1], "every_min": 60, "enabled": True})
            self.assertEqual(len(st.list()), 1)
            with self.assertRaises(ValueError):
                st.create({**s, "time": "25:00"})
            with self.assertRaises(ValueError):
                st.create({**s, "kind": "interval", "every_min": 5})
            with self.assertRaises(ValueError):
                st.create({**s, "task": "rm_rf"})
            st.update(s["id"], {**s, "enabled": False})
            self.assertFalse(st.list()[0]["enabled"])
            st.delete(s["id"])
            self.assertEqual(st.list(), [])


class RunnerTest(unittest.TestCase):
    def test_run_lifecycle_and_dedupe(self):
        gate = threading.Event()
        done = threading.Event()

        def slow(ctx):
            ctx.log("working")
            gate.wait(5)
            return "1 drafted"

        def boom(ctx):
            raise RuntimeError("no network")

        with tempfile.TemporaryDirectory() as d:
            r = Runner(Path(d), {"daily_run": slow, "gmail_check": boom}, on_finish=lambda run: done.set() if run["task"] == "gmail_check" else None)
            r.start()
            a = r.submit("daily_run")
            with self.assertRaises(ValueError):
                r.submit("daily_run")  # already queued/running
            b = r.submit("gmail_check")
            gate.set()
            self.assertTrue(done.wait(5))
            self.assertEqual(r.get(a["id"])["status"], "done")
            self.assertEqual(r.get(a["id"])["summary"], "1 drafted")
            self.assertEqual(r.get(b["id"])["status"], "failed")
            self.assertIn("no network", r.get(b["id"])["error"])
            self.assertIn("working", r.log_path(a["id"]).read_text())
            r.stop()

    def test_restart_marks_orphans_failed(self):
        with tempfile.TemporaryDirectory() as d:
            r = Runner(Path(d), {"daily_run": lambda ctx: "x"})
            run = r.submit("daily_run")  # never started
            r2 = Runner(Path(d), {"daily_run": lambda ctx: "x"})
            self.assertEqual(r2.get(run["id"])["status"], "failed")


if __name__ == "__main__":
    unittest.main()
