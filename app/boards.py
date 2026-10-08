"""Company career boards: the public Greenhouse, Lever and Ashby job APIs, read directly.

These are the employers' own listings, so there is no aggregator or staffing reposter in between.
Only engineering roles that are remote and open to India, published in the last MAX_AGE days, are kept.
"""
import html
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone

from app.companies import UA
from app.instahyre import _text

MAX_AGE = 30
URLS = {"greenhouse": "https://boards-api.greenhouse.io/v1/boards/{}/jobs?content=true",
        "lever": "https://api.lever.co/v0/postings/{}?mode=json",
        "ashby": "https://api.ashbyhq.com/posting-api/job-board/{}"}
# (ats, board token, company). Checked 2026-10-08: each had remote or India engineering roles open.
# Lever is supported, but no listed company uses it yet.
BOARDS = [
    ("greenhouse", t, c) for t, c in [
        ("gitlab", "GitLab"), ("elastic", "Elastic"), ("twilio", "Twilio"), ("grafanalabs", "Grafana Labs"),
        ("canonical", "Canonical"), ("coinbase", "Coinbase"), ("cloudflare", "Cloudflare"), ("neo4j", "Neo4j"),
        ("mongodb", "MongoDB"), ("databricks", "Databricks"), ("starburst", "Starburst"), ("singlestore", "SingleStore"),
        ("yugabyte", "Yugabyte"), ("launchdarkly", "LaunchDarkly"), ("fivetran", "Fivetran"), ("zscaler", "Zscaler"),
        ("newrelic", "New Relic"), ("okta", "Okta"), ("cockroachlabs", "Cockroach Labs"), ("druva", "Druva"),
        ("rubrik", "Rubrik"), ("sumologic", "Sumo Logic"), ("datadog", "Datadog"), ("stripe", "Stripe"),
        ("jfrog", "JFrog"), ("vercel", "Vercel"), ("anthropic", "Anthropic"), ("samsara", "Samsara")]
] + [
    ("ashby", t, c) for t, c in [
        ("openai", "OpenAI"), ("notion", "Notion"), ("atlan", "Atlan"), ("harvey", "Harvey"), ("elevenlabs", "ElevenLabs"),
        ("temporal", "Temporal"), ("deel", "Deel"), ("vanta", "Vanta"), ("cursor", "Cursor"), ("sentry", "Sentry"),
        ("supabase", "Supabase"), ("posthog", "PostHog")]
]

REMOTE = re.compile(r"remote|anywhere|worldwide|home.?based|work from home|wfh|distributed", re.I)
INDIA = re.compile(r"\bindia\b|bengaluru|bangalore|hyderabad|pune|mumbai|delhi|gurgaon|gurugram|noida|chennai|kolkata|ahmedabad", re.I)
WIDE = re.compile(r"anywhere|worldwide|global|apac|asia", re.I)
OFFICE = re.compile(r"hybrid|on-?site|in-office", re.I)
ENG = re.compile(r"engineer|developer|architect|\bsre\b|scientist|\bml\b|\bai\b|devops|programmer", re.I)
NOT_ENG = re.compile(r"sales|account|manager|director|head of|\bvp\b|recruit|intern|marketing|designer|counsel|\bqa\b|"
                     r"\bsdet\b|\btest|support", re.I)


def remote_for_india(loc, remote=False):
    if OFFICE.search(loc or ""):
        return False
    if not (remote or REMOTE.search(loc or "")):
        return False
    return bool(INDIA.search(loc) or WIDE.search(loc) or re.fullmatch(r"\W*remote\W*", loc, re.I))


def engineering(title):
    return bool(ENG.search(title) and not NOT_ENG.search(title))


def _job(title, company, url, loc, posted, text, now):
    if (date.fromisoformat(now) - date.fromisoformat(posted)).days > MAX_AGE:
        return None
    return {"id": url, "title": title.strip(), "company": company, "url": url, "location": loc, "date": posted,
            "portal": "boards", "description": f"Location: {loc}\n\n{text}",
            "note": f"Listed on {company}'s own career page; location: {loc}"}


def parse(ats, data, company, now=None):
    now = now or date.today().isoformat()
    out = []
    if ats == "greenhouse":
        for j in data.get("jobs", []):
            loc = j["location"]["name"] or ""
            if engineering(j["title"]) and remote_for_india(loc):
                out.append(_job(j["title"], company, j["absolute_url"], loc, (j.get("first_published") or j["updated_at"])[:10],
                                _text(html.unescape(j.get("content") or "")), now))
    elif ats == "lever":
        for j in data:
            cat = j.get("categories") or {}
            loc = "; ".join(cat.get("allLocations") or [cat.get("location") or ""])
            if engineering(j["text"]) and remote_for_india(loc, j.get("workplaceType") == "remote"):
                text = "\n\n".join([j.get("descriptionPlain") or ""] + [f"{li['text']}: {_text(li['content'])}" for li in j.get("lists") or []]
                                   + [j.get("additionalPlain") or ""])
                posted = datetime.fromtimestamp(j["createdAt"] / 1000, timezone.utc).date().isoformat()
                out.append(_job(j["text"], company, j["hostedUrl"], loc, posted, text, now))
    else:
        for j in data.get("jobs", []):
            loc = "; ".join([j.get("location") or ""] + [s.get("location", "") for s in j.get("secondaryLocations") or []])
            if engineering(j["title"]) and remote_for_india(loc, j.get("isRemote") is True):
                out.append(_job(j["title"], company, j["jobUrl"], loc, j["publishedAt"][:10], j.get("descriptionPlain") or "", now))
    return [j for j in out if j]


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch(log=print):
    def one(board):
        ats, token, company = board
        try:
            return parse(ats, _get(URLS[ats].format(token)), company)
        except Exception as e:
            log(f"{company} board failed: {e}")
            return []

    with ThreadPoolExecutor(8) as ex:
        return [j for jobs in ex.map(one, BOARDS) for j in jobs]
