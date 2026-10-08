import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app import auth, scheduler, store

HEADER = "date,company,sector,role,role_type,channel,status,contact_person,fit_rating,notes,cv_file,cover_letter_file,source,deadline\n"


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        (cls.tmp / "t.csv").write_text(HEADER + "2026-10-05,Acme,SaaS,AI Engineer,AI,online,drafted,,82,remote,cv/main_example.tex,,javascript:alert(1),\n")
        cls.patches = [
            mock.patch.object(store, "TRACKER", cls.tmp / "t.csv"),
            mock.patch.object(store, "CONFIG", cls.tmp / "config.json"),
            mock.patch.object(store, "DATA", cls.tmp),
        ]
        for p in cls.patches:
            p.start()
        auth.set_password("admin", "correct horse")
        from app import server
        server.schedules = scheduler.Schedules(cls.tmp / "schedules.json")
        server.runner = scheduler.Runner(cls.tmp, {"daily_run": lambda ctx: "ok", "gmail_check": lambda ctx: "ok",
                                                   "deadline_alert": lambda ctx: "ok", "draft_url": lambda ctx: "ok",
                                                   "interview": lambda ctx: "ok"})
        cls.server = server
        cls.c = TestClient(server.app, base_url="http://127.0.0.1:8765")

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()
        shutil.rmtree(cls.tmp)

    def login(self):
        r = self.c.post("/api/login", json={"username": "admin", "password": "correct horse"})
        self.assertEqual(r.status_code, 200)

    def test_auth_required(self):
        c = TestClient(self.server.app)
        self.assertEqual(c.get("/api/applications").status_code, 401)
        self.assertEqual(c.get("/files/cv/main_example.tex").status_code, 401)
        self.assertEqual(c.post("/api/login", json={"username": "admin", "password": "nope"}).status_code, 401)

    def test_applications_and_status(self):
        self.login()
        apps = self.c.get("/api/applications").json()
        acme = apps[0]
        self.assertEqual(acme["apply_url"], "")  # javascript: link blanked
        r = self.c.post(f"/api/applications/{acme['id']}/status", json={"company": "Acme", "role": "AI Engineer", "status": "applied"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "applied")
        r = self.c.post(f"/api/applications/{acme['id']}/status", json={"company": "Other", "role": "AI Engineer", "status": "applied"})
        self.assertEqual(r.status_code, 409)
        r = self.c.post(f"/api/applications/{acme['id']}/status", json={"company": "Acme", "role": "AI Engineer", "status": "applied"},
                        headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)

    def test_files_guard(self):
        self.login()
        self.assertEqual(self.c.get("/files/cv/main_example.tex").status_code, 200)
        self.assertEqual(self.c.get("/files/cv/../CLAUDE.md").status_code, 404)
        self.assertEqual(self.c.get("/files/job_search_tracker.csv").status_code, 404)

    def test_schedules_crud(self):
        self.login()
        body = {"name": "Evening", "task": "gmail_check", "kind": "interval", "every_min": 30, "enabled": True}
        s = self.c.post("/api/schedules", json=body).json()
        self.assertTrue(s["next_run"])
        bad = self.c.post("/api/schedules", json=body | {"every_min": 5})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.c.put(f"/api/schedules/{s['id']}", json=body | {"enabled": False}).json()["enabled"], False)
        self.assertEqual(self.c.delete(f"/api/schedules/{s['id']}").status_code, 204)

    def test_runs_validation(self):
        self.login()
        self.assertEqual(self.c.post("/api/runs", json={"task": "draft_url", "url": "javascript:x"}).status_code, 422)
        self.assertEqual(self.c.post("/api/runs", json={"task": "rm_rf"}).status_code, 422)
        r = self.c.post("/api/runs", json={"task": "deadline_alert"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.c.get(f"/api/runs/{r.json()['id']}/log").status_code, 200)

    def test_settings_hide_password(self):
        self.login()
        s = self.c.get("/api/settings").json()
        s["gmail_app_password"] = "abcd efgh ijkl mnop"
        out = self.c.put("/api/settings", json=s).json()
        self.assertTrue(out["gmail_has_password"])
        self.assertNotIn("gmail_app_password", out)
        self.assertEqual(store.load_config()["gmail_app_password"], "abcdefghijklmnop")


if __name__ == "__main__":
    unittest.main()
