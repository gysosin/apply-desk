import tempfile
import unittest
from datetime import date
from pathlib import Path

from app import store

HEADER = "date,company,sector,role,role_type,channel,status,contact_person,fit_rating,notes,cv_file,cover_letter_file,source,deadline\n"


class TrackerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.csv = Path(self.tmp.name) / "t.csv"
        self.csv.write_text(HEADER
            + "2026-10-05,Acme,SaaS,AI Engineer,AI,online,drafted,,82,remote,cv/main_acme_ai.tex,cover_letters/cover_acme_ai.tex,https://acme/apply,2026-10-07\n"
            + "2026-09-28,Beta,SaaS,Backend,BE,online,applied,,70,x | applied 2026-09-30,cv/main_beta.tex,cover_letters/cover_beta.tex,https://beta,\n",
            encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_applications_view(self):
        apps = store.applications(self.csv)
        self.assertEqual(apps[0]["fit"], 82)
        self.assertEqual(apps[0]["apply_url"], "https://acme/apply")
        self.assertEqual(apps[0]["deadline"], "2026-10-07")
        self.assertEqual(apps[1]["applied_on"], "2026-09-30")
        self.assertIsNone(apps[1]["deadline"])

    def test_set_status_guards_stale_index(self):
        store.set_status(0, "Acme", "AI Engineer", "applied", self.csv, today=date(2026, 10, 6))
        app = store.applications(self.csv)[0]
        self.assertEqual(app["status"], "applied")
        self.assertEqual(app["applied_on"], "2026-10-06")
        with self.assertRaises(store.Conflict):
            store.set_status(0, "Beta", "AI Engineer", "applied", self.csv)
        with self.assertRaises(ValueError):
            store.set_status(0, "Acme", "AI Engineer", "hacked", self.csv)

    def test_undo_removes_applied_marker(self):
        store.set_status(0, "Acme", "AI Engineer", "applied", self.csv, today=date(2026, 10, 6))
        store.set_status(0, "Acme", "AI Engineer", "drafted", self.csv)
        app = store.applications(self.csv)[0]
        self.assertIsNone(app["applied_on"])
        self.assertEqual(app["notes"], "remote")

    def test_add_row_dedups(self):
        row = {"company": "Gamma", "role": "ML", "status": "drafted", "source": "https://g"}
        self.assertTrue(store.add_row(row, self.csv))
        self.assertFalse(store.add_row(row, self.csv))
        self.assertEqual(len(store.applications(self.csv)), 3)

    def test_summary(self):
        s = store.summary(store.applications(self.csv), today=date(2026, 10, 6))
        self.assertEqual(s["ready"], 1)
        self.assertEqual(s["closing_soon"][0]["days_left"], 1)
        self.assertEqual(len(s["applied_by_week"]), 8)
        self.assertEqual(sum(w["count"] for w in s["applied_by_week"]), 1)


class FilesTest(unittest.TestCase):
    def test_safe_file(self):
        self.assertIsNone(store.safe_file("../CLAUDE.md"))
        self.assertIsNone(store.safe_file("cv/../CLAUDE.md"))
        self.assertIsNone(store.safe_file("job_search_tracker.csv"))
        self.assertIsNotNone(store.safe_file("cv/main_example.tex"))


if __name__ == "__main__":
    unittest.main()


class WhyRoleTest(unittest.TestCase):
    def test_view_carries_the_drafted_why_role_answer(self):
        slug = "zz_test_why_role"
        folder = store.ROOT / "documents" / "applications" / slug
        folder.mkdir(parents=True, exist_ok=True)
        try:
            (folder / "why_role.md").write_text("  I build agent runtimes.\n", encoding="utf-8")
            row = {"company": "Acme", "role": "AI", "cv_file": f"cv/main_{slug}.tex"}
            self.assertEqual(store._view(0, row)["why_role"], "I build agent runtimes.")
            self.assertIsNone(store._view(0, {"company": "B", "role": "x"})["why_role"])
        finally:
            (folder / "why_role.md").unlink(missing_ok=True)
            folder.rmdir()
