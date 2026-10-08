import unittest

from app import boards

NOW = "2026-10-08"


class ParseTest(unittest.TestCase):
    def test_greenhouse(self):
        data = {"jobs": [
            {"title": "Senior Software Engineer", "location": {"name": "Remote, India"}, "company_name": "GitLab",
             "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/1", "first_published": "2026-10-01T10:00:00-04:00",
             "content": "&lt;p&gt;Build &amp;amp; ship&lt;/p&gt;"},
            {"title": "Account Executive", "location": {"name": "Remote, India"}, "company_name": "GitLab",
             "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/2", "first_published": "2026-10-01T10:00:00-04:00"},
        ]}
        jobs = boards.parse("greenhouse", data, "GitLab", NOW)
        self.assertEqual(len(jobs), 1)
        j = jobs[0]
        self.assertEqual((j["title"], j["company"], j["url"], j["date"], j["portal"]),
                         ("Senior Software Engineer", "GitLab", "https://job-boards.greenhouse.io/gitlab/jobs/1", "2026-10-01", "boards"))
        self.assertIn("Build & ship", j["description"])
        self.assertIn("Remote, India", j["description"])

    def test_lever_uses_workplace_type(self):
        data = [
            {"text": "Backend Engineer", "categories": {"location": "Bengaluru", "allLocations": ["Bengaluru"]},
             "workplaceType": "remote", "hostedUrl": "https://jobs.lever.co/x/1", "createdAt": 1791400000000,
             "descriptionPlain": "Go and Python", "lists": [{"text": "You have", "content": "<li>Kubernetes</li>"}]},
            {"text": "Backend Engineer", "categories": {"location": "Bengaluru", "allLocations": ["Bengaluru"]},
             "workplaceType": "onsite", "hostedUrl": "https://jobs.lever.co/x/2", "createdAt": 1791400000000},
        ]
        jobs = boards.parse("lever", data, "X", NOW)
        self.assertEqual([j["url"] for j in jobs], ["https://jobs.lever.co/x/1"])
        self.assertIn("Kubernetes", jobs[0]["description"])

    def test_ashby_uses_is_remote(self):
        data = {"jobs": [
            {"title": "AI Engineer", "location": "India", "secondaryLocations": [], "isRemote": True,
             "jobUrl": "https://jobs.ashbyhq.com/a/1", "publishedAt": "2026-09-30T11:00:00+00:00", "descriptionPlain": "LLM agents"},
            {"title": "AI Engineer", "location": "Bengaluru", "secondaryLocations": [], "isRemote": False,
             "jobUrl": "https://jobs.ashbyhq.com/a/2", "publishedAt": "2026-09-30T11:00:00+00:00"},
        ]}
        self.assertEqual([j["url"] for j in boards.parse("ashby", data, "A", NOW)], ["https://jobs.ashbyhq.com/a/1"])

    def test_drops_stale_postings(self):
        data = {"jobs": [{"title": "AI Engineer", "location": "India", "isRemote": True, "jobUrl": "u",
                          "publishedAt": "2026-07-01T00:00:00+00:00"}]}
        self.assertEqual(boards.parse("ashby", data, "A", NOW), [])


class FitsTest(unittest.TestCase):
    def test_location(self):
        ok = boards.remote_for_india
        self.assertTrue(ok("Remote, India"))
        self.assertTrue(ok("India (Remote)"))
        self.assertTrue(ok("Home based - Worldwide"))
        self.assertTrue(ok("Remote, APAC"))
        self.assertTrue(ok("Remote"))
        self.assertTrue(ok("Bengaluru", remote=True))
        self.assertFalse(ok("Bengaluru, India"))              # office job
        self.assertFalse(ok("Hybrid - India"))
        self.assertFalse(ok("Remote - US"))
        self.assertFalse(ok("Remote - Indiana, USA"))
        self.assertFalse(ok("Remote, EMEA"))
        self.assertFalse(ok("Hybrid - India", remote=True))

    def test_title(self):
        self.assertTrue(boards.engineering("Senior Software Engineer, Backend"))
        self.assertTrue(boards.engineering("AI Platform Engineer"))
        self.assertTrue(boards.engineering("Site Reliability Engineer"))
        self.assertFalse(boards.engineering("Sales Engineer"))
        self.assertFalse(boards.engineering("Engineering Manager"))
        self.assertFalse(boards.engineering("Account Executive"))


if __name__ == "__main__":
    unittest.main()
