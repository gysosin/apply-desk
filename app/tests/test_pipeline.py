import unittest
from datetime import date

from app import pipeline


class DedupTest(unittest.TestCase):
    def test_new_only(self):
        seen = {"acme_ai-engineer": {"url": "https://a/1?utm=x", "company": "Acme", "title": "AI Engineer"}}
        pool = [
            {"title": "AI Engineer", "company": "Acme", "url": "https://a/1", "portal": "x"},          # same url
            {"title": "ai engineer", "company": "ACME ", "url": "https://a/other", "portal": "x"},    # same company+title
            {"title": "Backend", "company": None, "url": "https://b/2", "portal": "x"},               # new, no company
            {"title": "Backend", "company": None, "url": "https://b/2", "portal": "y"},               # dup within pool
            {"title": "Data", "company": "Tracked", "url": "https://t/3", "portal": "x"},             # in tracker
        ]
        new = pipeline.dedup(pool, seen, tracker={("tracked", "data")})
        self.assertEqual([j["url"] for j in new.values()], ["https://b/2"])
        self.assertEqual(next(iter(new.values()))["company"], "Unknown")


class SelectTest(unittest.TestCase):
    def test_select_drafts(self):
        ranked = [
            {"key": "a", "score": 80, "location_verdict": "PASS", "gaps": [], "deadline": None},
            {"key": "b", "score": 90, "location_verdict": "FLAG", "gaps": [], "deadline": None},
            {"key": "c", "score": 59, "location_verdict": "PASS", "gaps": [], "deadline": None},
            {"key": "d", "score": 70, "location_verdict": "PASS", "gaps": ["SALARY FAIL: 6-9 LPA"], "deadline": None},
            {"key": "e", "score": 61, "location_verdict": "PASS", "gaps": [], "deadline": "2026-10-06"},
            {"key": "f", "score": 65, "location_verdict": "PASS", "gaps": [], "deadline": None},
        ]
        got = [r["key"] for r in pipeline.select_drafts(ranked, min_score=60, limit=2)]
        self.assertEqual(got, ["e", "a"])  # deadline first, then score; b/c/d excluded


class SlugTest(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(pipeline.slugify("Gather AI", "SDE II - Full Stack (India)"), "gather_ai_sde_ii_full_stack_india")
        self.assertLessEqual(len(pipeline.slugify("A" * 80, "B" * 80)), 70)


class BannedTest(unittest.TestCase):
    def test_banned_hits(self):
        self.assertEqual(pipeline.banned_hits("Built for Globex and Initech", ["globex", "initech", "umbrella co"]), ["globex", "initech"])
        self.assertEqual(pipeline.banned_hits("Umbrella company", ["umbrella co"]), [])  # word boundary


class SourcesTest(unittest.TestCase):
    def test_aggregators_and_reposters_are_dropped(self):
        pool = [
            {"title": "AI Engineer", "company": "Jobgether", "url": "https://jobs.lever.co/jobgether/1"},
            {"title": "AI Engineer", "company": "Acme", "url": "https://jobs.lever.co/jobgether/2"},   # reposted under client name
            {"title": "Backend", "company": "weekday-1", "url": "https://x/3"},
            {"title": "Backend", "company": "GitLab", "url": "https://job-boards.greenhouse.io/gitlab/jobs/4"},
        ]
        got = pipeline.drop_blocked(pool, ["jobgether", "weekday"])
        self.assertEqual([j["company"] for j in got], ["GitLab"])

    def test_instahyre_posting_text_comes_from_the_job_page(self):
        from unittest import mock
        new = {"k": {"title": "AI Engineer", "company": "Acme", "url": "https://www.instahyre.com/job-1/", "portal": "instahyre"}}
        ctx = type("C", (), {"cancelled": lambda: False, "log": print})
        with mock.patch.object(pipeline.instahyre, "posting", return_value={"date": date.today().isoformat(), "text": "Remote, FastAPI"}):
            jobs = pipeline.details(ctx, new, {"k"})
        self.assertEqual(jobs[0]["posting_text"], "Remote, FastAPI")


if __name__ == "__main__":
    unittest.main()


class WhyRolesTest(unittest.TestCase):
    """Backfill writes an answer per Ready draft that lacks one, and rejects side-work names."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        for slug in ("acme_ai", "beta_be", "gamma_ml"):
            (root / "documents" / "applications" / slug).mkdir(parents=True)
            (root / "documents" / "applications" / slug / "job_posting.md").write_text("posting")
        (root / "documents" / "applications" / "gamma_ml" / "why_role.md").write_text("already here")
        apps = [{"status": "drafted", "slug": "acme_ai", "company": "Acme", "role": "AI", "why_role": None},
                {"status": "drafted", "slug": "beta_be", "company": "Beta", "role": "BE", "why_role": None},
                {"status": "drafted", "slug": "gamma_ml", "company": "Gamma", "role": "ML", "why_role": "already here"},
                {"status": "applied", "slug": "acme_ai", "company": "Acme", "role": "AI", "why_role": None}]
        answers = {"Acme": "I build agents.", "Beta": "I led work at SideCo."}
        self.patches = [mock.patch.object(pipeline.store, "ROOT", root),
                        mock.patch.object(pipeline.store, "applications", return_value=apps),
                        mock.patch.object(pipeline, "_banned_names", return_value=["sideco"]),
                        mock.patch.object(pipeline.agent, "run", side_effect=lambda text, **kw: {
                            "answer": next(v for k, v in answers.items() if k in text)})]
        for p in self.patches:
            p.start()
        self.root = root

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_fills_missing_answers_only(self):
        class Ctx:
            scratch, log, cancelled = None, staticmethod(lambda m: None), staticmethod(lambda: False)
        out = pipeline.why_roles(Ctx())
        apps = self.root / "documents" / "applications"
        self.assertEqual((apps / "acme_ai" / "why_role.md").read_text(), "I build agents.\n")
        self.assertFalse((apps / "beta_be" / "why_role.md").exists())       # names side work: not written
        self.assertEqual((apps / "gamma_ml" / "why_role.md").read_text(), "already here")
        self.assertIn("1 written", out)
