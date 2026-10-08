import unittest

from app import companies


class SizeTest(unittest.TestCase):
    def test_parse_linkedin(self):
        html = '<script>{"@type":"Organization","numberOfEmployees":{"value":16857,"@type":"QuantitativeValue"}}</script>'
        self.assertEqual(companies.parse_linkedin(html), 16857)
        self.assertIsNone(companies.parse_linkedin("<html>authwall</html>"))

    def test_big_enough(self):
        sizes = {"atlassian": 16857, "coderound ai": 15, "mystery": None}
        self.assertTrue(companies.big_enough("Atlassian", sizes, 500))
        self.assertFalse(companies.big_enough("CodeRound AI", sizes, 500))
        self.assertFalse(companies.big_enough("Mystery", sizes, 500))  # unknown size is dropped
        self.assertTrue(companies.big_enough("Mystery", sizes, 500, keep_unknown=True))
        self.assertTrue(companies.big_enough("Anyone", sizes, 0))  # filter off

    def test_size_given_by_the_job_source_skips_the_lookup(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        with tempfile.TemporaryDirectory() as d, mock.patch.object(companies, "CACHE", Path(d) / "c.json"), \
             mock.patch.object(companies.store, "DATA", Path(d)), mock.patch.object(companies.agent, "run") as run:
            got = companies.sizes_for(None, [{"company": "Tiny Co", "url": "u", "employees": 50}], {})
        run.assert_not_called()
        self.assertEqual(got["tiny co"], 50)


if __name__ == "__main__":
    unittest.main()
