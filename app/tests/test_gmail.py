import tempfile
import unittest
from pathlib import Path

from app import gmail, store

HEADER = "date,company,sector,role,role_type,channel,status,contact_person,fit_rating,notes,cv_file,cover_letter_file,source,deadline\n"


class ApplySignalsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.csv = Path(self.tmp.name) / "t.csv"
        self.csv.write_text(HEADER
            + "2026-10-05,Acme,SaaS,AI Engineer,AI,online,drafted,,82,remote,,,,\n"
            + "2026-10-05,Beta,SaaS,Backend,BE,online,applied,,70,x | applied 2026-10-05,,,,\n"
            + "2026-10-05,Gamma,SaaS,ML,ML,online,offer,,70,x,,,,\n",
            encoding="utf-8")
        self.apps = store.applications(self.csv)
        self.mail = {"m1": {"date": "2026-10-06T03:30:03+00:00", "subject": "Follow up, from Beta", "from": "no-reply@x.io"}}

    def tearDown(self):
        self.tmp.cleanup()

    def run_one(self, app_id, signal, reason=None):
        res = [{"id": "m1", "application_id": app_id, "signal": signal, "reason": reason}]
        return gmail.apply_signals(res, self.mail, self.apps, self.csv)

    def test_rejection_marks_row_and_notes_source(self):
        self.assertEqual(len(self.run_one(1, "rejection")), 1)
        beta = store.applications(self.csv)[1]
        self.assertEqual(beta["status"], "rejected")
        self.assertIn("2026-10-06 gmail: rejection (Follow up from Beta)", beta["notes"])

    def test_outcome_with_reason_is_shown_on_the_row(self):
        self.run_one(1, "rejection", "Role filled, by another candidate")
        out = store.applications(self.csv)[1]["outcome"]
        self.assertEqual(out, {"date": "2026-10-06", "signal": "rejection", "reason": "Role filled by another candidate",
                               "subject": "Follow up from Beta"})
        self.assertIsNone(store.applications(self.csv)[0]["outcome"])

    def test_brackets_in_the_reason_do_not_break_the_outcome(self):
        self.run_one(1, "rejection", "Not moving forward for Backend (Go)")
        out = store.applications(self.csv)[1]["outcome"]
        self.assertEqual((out["reason"], out["subject"]), ("Not moving forward for Backend Go", "Follow up from Beta"))

    def test_ack_on_drafted_marks_applied_with_email_date(self):
        self.run_one(0, "ack")
        acme = store.applications(self.csv)[0]
        self.assertEqual((acme["status"], acme["applied_on"]), ("applied", "2026-10-06"))

    def test_never_downgrades_or_overwrites_an_offer(self):
        self.assertEqual(self.run_one(1, "ack"), [])          # applied stays applied
        self.assertEqual(self.run_one(2, "rejection"), [])    # offer is not overwritten by a later rejection
        self.assertEqual(store.applications(self.csv)[2]["status"], "offer")

    def test_ignores_unknown_ids_and_other_signals(self):
        self.assertEqual(self.run_one(99, "offer"), [])
        self.assertEqual(self.run_one(None, "offer"), [])   # no company named either
        self.assertEqual(self.run_one(1, "other"), [])

    def test_untracked_company_gets_a_row_then_moves_forward(self):
        mails = {"a": {"date": "2026-06-25T16:00:58+00:00", "subject": "Thanks for applying", "from": "x"},
                 "r": {"date": "2026-07-22T19:01:14+00:00", "subject": "Update on Your Application", "from": "x"}}
        new = {"application_id": None, "company": "Sophos", "role": "Senior Software Engineer"}
        changes = gmail.apply_signals([{"id": "r", "signal": "rejection", **new}, {"id": "a", "signal": "ack", **new}],
                                      mails, self.apps, self.csv)
        sophos = store.applications(self.csv)[-1]
        self.assertEqual((sophos["company"], sophos["status"], sophos["date"]), ("Sophos", "rejected", "2026-06-25"))
        self.assertEqual(len(changes), 2)
        self.assertEqual(sophos["applied_on"], "2026-06-25")  # the ack date is the application date

    def test_known_company_with_other_role_wording_reuses_its_row(self):
        res = [{"id": "m1", "signal": "rejection", "application_id": None, "company": "BETA", "role": "Backend Engineer II"}]
        gmail.apply_signals(res, self.mail, [], self.csv)
        rows = store.applications(self.csv)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["status"], "rejected")

    def test_ack_for_another_role_at_same_company_does_not_mark_the_draft(self):
        res = [{"id": "m1", "signal": "ack", "application_id": None, "company": "Acme", "role": "Data Scientist"}]
        gmail.apply_signals(res, self.mail, [], self.csv)
        rows = store.applications(self.csv)
        self.assertEqual(rows[0]["status"], "drafted")                       # AI Engineer draft untouched
        self.assertEqual((rows[-1]["role"], rows[-1]["status"]), ("Data Scientist", "applied"))

    def test_ack_for_a_skipped_row_marks_it_applied(self):
        store.set_status(0, "Acme", "AI Engineer", "skipped", self.csv)
        res = [{"id": "m1", "signal": "ack", "application_id": None, "company": "Acme", "role": "Senior AI Engineer"}]
        gmail.apply_signals(res, self.mail, [], self.csv)
        acme = store.applications(self.csv)[0]
        self.assertEqual((acme["status"], acme["applied_on"]), ("applied", "2026-10-06"))

    def test_skips_banned_names(self):
        self.assertTrue(gmail.banned("Interview Invitation from Foo Consultancy", ["foo consultancy"]))
        self.assertFalse(gmail.banned("Update from Sophos", ["foo consultancy"]))


if __name__ == "__main__":
    unittest.main()


class IncrementalSearchTest(unittest.TestCase):
    def test_only_asks_gmail_for_emails_after_the_last_checked_one(self):
        q = gmail.QUERY.format(days=30).replace('"', '\\"')
        self.assertEqual(gmail.search_args({"uidvalidity": "7", "last_uid": 500}, "7", True),
                         ["UID", "501:*", "X-GM-RAW", f'"{q}"'])

    def test_full_search_when_mailbox_changed_or_first_pass_unfinished(self):
        full = gmail.QUERY.format(days=gmail.FIRST_RUN_DAYS).replace('"', '\\"')
        self.assertEqual(gmail.search_args({"uidvalidity": "6", "last_uid": 500}, "7", False), ["X-GM-RAW", f'"{full}"'])
        self.assertEqual(gmail.search_args({}, "7", False), ["X-GM-RAW", f'"{full}"'])
        q = gmail.QUERY.format(days=30).replace('"', '\\"')
        self.assertEqual(gmail.search_args({"uidvalidity": "6", "last_uid": 500}, "7", True), ["X-GM-RAW", f'"{q}"'])


class ReadingTest(unittest.TestCase):
    def test_html_only_email_body_is_read(self):
        from email.message import EmailMessage
        msg = EmailMessage()
        msg.set_content("<html><head><style>p{color:red}</style></head><body><p>We will not be moving&nbsp;forward.</p></body></html>",
                        subtype="html")
        self.assertEqual(gmail._text(msg), "We will not be moving forward.")

    def test_classify_sends_short_ids_and_maps_them_back(self):
        from unittest import mock
        fresh = [{"id": "<long-1@mail>", "date": "d", "from": "f", "subject": "s", "body": "b"},
                 {"id": "<long-2@mail>", "date": "d", "from": "f", "subject": "s", "body": "b"}]
        seen = {}

        def fake_run(text, **kw):
            seen.update(kw, text=text)
            return {"results": [{"id": "1", "signal": "rejection", "application_id": None, "company": "X", "role": "Y", "reason": "r"}]}
        with mock.patch.object(gmail.agent, "run", side_effect=fake_run), \
             mock.patch.object(gmail.store, "load_config", return_value={"models": {"triage": "m", "score": "m"}}):
            out = gmail.classify(fresh, [], type("C", (), {"scratch": None, "log": print, "cancelled": lambda: False}))
        self.assertEqual([r["id"] for r in out], ["<long-2@mail>"])
        self.assertNotIn("<long-1@mail>", seen["text"])
        self.assertTrue(seen["lean"])


class BodyChoiceTest(unittest.TestCase):
    def test_link_only_plain_part_loses_to_the_real_html_text(self):
        from email.message import EmailMessage
        msg = EmailMessage()
        msg.set_content("Your update https://www.linkedin.com/help/x?trk=a_very_long_tracking_value_that_goes_on_and_on Unsubscribe: https://l.in/u")
        msg.add_alternative("<p>Thank you for applying. Unfortunately the company decided not to move forward with your application.</p>", subtype="html")
        self.assertIn("decided not to move forward", gmail._text(msg))
