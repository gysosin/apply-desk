import json
import unittest

from app import instahyre

SEARCH = {"meta": {"total_count": 3}, "objects": [
    {"id": 1, "title": "SDE III - Python + AI", "locations": "Work From Home",
     "public_url": "https://www.instahyre.com/job-1-sde-iii-at-swiggy-work-from-home/",
     "employer": {"company_name": "Swiggy", "employee_count": 1000}},
    {"id": 2, "title": "Python Developer", "locations": "Bangalore,Work From Home",
     "public_url": "https://www.instahyre.com/job-2/", "employer": {"company_name": "Tiny Co", "employee_count": 50}},
    {"id": 3, "title": "Backend Engineer", "locations": "Work From Home",
     "public_url": "https://www.instahyre.com/job-3/", "employer": {"company_name": "Midsize", "employee_count": 500}},
]}

PAGE = """<html><script type="application/ld+json">{"@type": "Organization", "name": "Instahyre"}</script>
<script type="application/ld+json">{"@type": "JobPosting", "title": "Tech Lead",
 "description": "<p><strong>Requirements:</strong></p><ul><li>FastAPI &amp; PostgreSQL</li></ul>",
 "datePosted": "2026-09-30", "jobLocationType": "TELECOMMUTE",
 "applicantLocationRequirements": [{"@type": "Country", "name": "India"}]}</script></html>"""


class InstahyreTest(unittest.TestCase):
    def test_parse_search(self):
        jobs = instahyre.parse_search(SEARCH)
        self.assertEqual([j["company"] for j in jobs], ["Swiggy", "Tiny Co", "Midsize"])
        self.assertEqual(jobs[0]["url"], "https://www.instahyre.com/job-1-sde-iii-at-swiggy-work-from-home/")
        self.assertEqual(jobs[0]["portal"], "instahyre")
        self.assertEqual(jobs[0]["location"], "Work From Home")
        # employee buckets: 1000 means 1000+, <=200 is clearly small, 500 is ambiguous -> look it up
        self.assertEqual([j.get("employees") for j in jobs], [1000, None, None])  # Atlan shows as 50 there: only the ends are trusted

    def test_parse_posting(self):
        p = instahyre.parse_posting(PAGE)
        self.assertEqual(p["date"], "2026-09-30")
        self.assertIn("Requirements: FastAPI & PostgreSQL", p["text"])
        self.assertIn("Remote (telecommute), applicants from: India", p["text"])
        self.assertNotIn("<", p["text"])
        self.assertIsNone(instahyre.parse_posting("<html>no posting</html>"))

    def test_search_url(self):
        url = instahyre.search_url("Generative AI")
        self.assertIn("jobLocations=Work+From+Home", url)
        self.assertIn("skills=Generative+AI", url)
        json.dumps(url)


if __name__ == "__main__":
    unittest.main()
