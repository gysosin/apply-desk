"""Instahyre job source: the public search API the site itself uses, plus the JobPosting JSON-LD on each job page.

robots.txt allows both. No login, no captcha bypass. Search is filtered to "Work From Home"; Instahyre has no
recency filter, so the caller drops stale postings by `datePosted`.
"""
import html
import json
import re
import urllib.parse
import urllib.request

from app.companies import UA

API = "https://www.instahyre.com/api/v1/job_search"
QUERIES = ["AI Engineer", "LLM", "Generative AI", "Machine Learning", "Python", "Full Stack", "Golang", "Kubernetes"]
YEARS = 5  # candidate's experience; Instahyre returns jobs whose range includes it


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/html"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read(3_000_000).decode("utf-8", "replace")


def search_url(query, limit=35):
    return API + "?" + urllib.parse.urlencode({"skills": query, "jobLocations": "Work From Home", "years": YEARS,
                                               "job_type": 0, "offset": 0, "limit": limit})


def parse_search(data):
    jobs = []
    for o in data.get("objects", []):
        emp = o.get("employer") or {}
        n = emp.get("employee_count")
        jobs.append({"id": o["id"], "title": o["title"], "company": emp.get("company_name") or "Unknown",
                     "url": o["public_url"], "location": o.get("locations"), "portal": "instahyre",
                     # Instahyre buckets sizes (1/10/50/200/500/1000) and is often stale (Atlan shows 50); trust only the ends
                     "employees": n if n is not None and (n >= 1000 or n <= 10) else None})
    return jobs


def search(query):
    return parse_search(json.loads(_get(search_url(query))))


def _text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment or ""))).strip()


def parse_posting(page):
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        if d.get("@type") != "JobPosting":
            continue
        where = ", ".join(c.get("name", "") for c in d.get("applicantLocationRequirements") or [])
        remote = "Remote (telecommute)" if d.get("jobLocationType") == "TELECOMMUTE" else "Not marked remote"
        text = re.sub(r"\s+:", ":", _text(d.get("description")))
        return {"date": d.get("datePosted"), "text": f"{remote}, applicants from: {where or 'not stated'}\n\n{text}"}
    return None


def posting(url):
    return parse_posting(_get(url))
