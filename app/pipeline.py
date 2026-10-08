"""Tasks the runner executes: daily_run, draft_url, interview, deadline_alert.

Deterministic steps (scrape, dedup, state, verification, tracker) are plain Python;
judgement steps (triage, score, draft, interview) go to Claude through app.agent.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

from app import agent, boards, companies, instahyre, notify, store
from app.store import ROOT

sys.path.insert(0, str(ROOT / "tools"))
from job_key import make_key  # noqa: E402
from rank_state import load_state, save_state  # noqa: E402
from verify_layout import parse_pdf, report  # noqa: E402
from verify_pdf import VerificationError, verify_pdf  # noqa: E402

SEEN = ROOT / "job_scraper" / "seen_jobs.json"
BANNED = store.DATA / "banned_names.txt"
LINKEDIN_QUERIES = [
    "AI Engineer", "LLM Engineer", "Generative AI Engineer", "Machine Learning Engineer LLM", "RAG", "AI agents",
    "Applied AI Engineer", "AI Platform Engineer", "Full Stack Engineer Python", "Python Full Stack Developer",
    "Full Stack Engineer React FastAPI", "Senior Full Stack Engineer", "Software Engineer Python React",
    "Senior Backend Engineer Python", "Backend Engineer Go", "Platform Engineer Kubernetes",
]
FREEHIRE_QUERIES = ["AI engineer", "LLM", "generative AI", "machine learning engineer", "full stack python",
                    "backend python", "platform engineer kubernetes", "golang"]
PARALLEL = 3
# Aggregators, reposters and staffing firms: they hide or resell the real employer, so their listings are noise
AGGREGATORS = ["jobgether", "weekday", "turing", "crossover", "toptal", "mercor", "braintrust", "uplers", "micro1",
               "andela", "remotebase", "talent500", "hirist", "lensa", "jooble", "dice", "jobot", "cybercoders",
               "insight global", "randstad", "teksystems", "robert half", "hays", "michael page", "adecco", "careernet",
               "xpheno", "quess", "teamlease", "niuro", "hackajob", "outlier", "alignerr", "dataannotation",
               "jobs for humanity", "weekdayworks", "remotestar", "huntingcube", "confidential", "stealth"]


def _cli(portal, *args, timeout=90):
    # stdout goes to a file: bun truncates large piped output when the CLI exits early
    with tempfile.TemporaryFile("w+", encoding="utf-8") as out:
        r = subprocess.run(["bun", "run", f".agents/skills/{portal}/cli/src/cli.ts", *args, "--format", "json"],
                           cwd=ROOT, stdout=out, stderr=subprocess.PIPE, text=True, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip()[:200] or f"{portal} exited {r.returncode}")
        out.seek(0)
        return json.load(out)


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def slugify(company, title):
    s = re.sub(r"[^a-z0-9]+", "_", f"{company} {title}".lower()).strip("_")
    return s if len(s) <= 70 else s[:61].rstrip("_") + "_" + hashlib.sha1(s.encode()).hexdigest()[:8]


def banned_hits(text, names):
    low = text.lower()
    return [n for n in names if re.search(rf"\b{re.escape(n)}\b", low)]


# ---------- scrape / dedup / triage ----------

def drop_blocked(pool, names):
    return [j for j in pool if not banned_hits(f"{j.get('company') or ''} {j['url']}", names)]


def scrape(ctx):
    pool = boards.fetch(ctx.log)
    ctx.log(f"Company career boards: {len(pool)} remote engineering roles")
    for q in instahyre.QUERIES:
        try:
            pool += instahyre.search(q)
        except Exception as e:
            ctx.log(f"instahyre '{q}' failed: {e}")
    for q in LINKEDIN_QUERIES:
        if ctx.cancelled():
            return pool
        try:
            out = _cli("linkedin-search", "search", "--location", "India", "-q", q, "--remote", "remote", "--jobage", "14", "--limit", "20")
            pool += [r | {"portal": "linkedin-search"} for r in out.get("results", [])]
        except Exception as e:
            ctx.log(f"linkedin '{q}' failed: {e}")
    for q in FREEHIRE_QUERIES:
        for geo in (["--country", "IN"], ["--region", "global"]):
            try:
                out = _cli("freehire-search", "search", "-q", q, "--remote", "remote", *geo, "--jobage", "14", "--limit", "20",
                           "--description-format", "text")
                pool += [r | {"portal": "freehire-search"} for r in out.get("results", [])]
            except Exception as e:
                ctx.log(f"freehire '{q}' failed: {e}")
    return pool


def dedup(pool, seen, tracker):
    urls = {(v.get("url") or "").split("?")[0] for v in seen.values()}
    pairs = {(_norm(v.get("company")), _norm(v.get("title"))) for v in seen.values()} | set(tracker)
    new = {}
    for j in pool:
        j = j | {"company": j.get("company") or "Unknown"}
        if j["url"].split("?")[0] in urls or (_norm(j["company"]), _norm(j["title"])) in pairs:
            continue
        key = make_key(j["company"], j["title"], j["url"])
        if key not in new and key not in seen:
            new[key] = j
    return new


def triage(ctx, new, cfg):
    lines = [f"{k} | {j['title']} | {j['company']} | {j.get('location') or ''} | {','.join(j.get('countries') or [])}"
             for k, j in new.items()]
    keep = set()
    for i in range(0, len(lines), 150):
        out = agent.run(agent.prompt("triage.md", listing="\n".join(lines[i:i + 150])), model=cfg["models"]["triage"],
                        schema=agent.TRIAGE, scratch=ctx.scratch, log=ctx.log, cancelled=ctx.cancelled, max_turns=3, tools=[])
        keep |= set(out["keep"]) & set(new)
    return keep


def record_seen(new, keep):
    doc, seen = load_state(SEEN)
    today = date.today().isoformat()
    for k, j in new.items():
        seen.setdefault(k, {
            "title": j["title"], "company": j["company"], "url": j["url"], "first_seen": today,
            "posted_date": (j.get("date") or "")[:10] or None, "deadline": None,
            "fit": "medium" if k in keep else "low", "status": "new" if k in keep else "skipped",
            "portal": j["portal"], "source": "cli", "location": j.get("location")})
    save_state(SEEN, doc)


def details(ctx, new, keep):
    jobs = []
    for k in keep:
        if ctx.cancelled():
            break
        j = new[k]
        text = j.get("description")
        if not text and j["portal"] == "instahyre":
            try:
                p = instahyre.posting(j["url"])
            except Exception as e:
                ctx.log(f"detail failed for {j['company']}: {e}")
                p = None
            stale = (date.today() - timedelta(days=boards.MAX_AGE)).isoformat()
            text = p["text"] if p and (p["date"] or "")[:10] >= stale else None
        elif not text:
            try:
                text = _cli(j["portal"], "detail", str(j["id"])).get("description")
            except Exception as e:
                ctx.log(f"detail failed for {j['company']}: {e}")
        if text:
            note = j.get("note") or ("Found via LinkedIn search filtered to Remote, India" if j["portal"] == "linkedin-search"
                                     else "Found via Instahyre search filtered to Work From Home" if j["portal"] == "instahyre"
                                     else "countries=" + ",".join(j.get("countries") or []))
            jobs.append({"key": k, "title": j["title"], "company": j["company"], "location": j.get("location"),
                         "portal": j["portal"], "note": note, "posting_text": text[:9000]})
    return jobs


# ---------- score ----------

def score(ctx, jobs, cfg):
    batches = [jobs[i:i + 12] for i in range(0, len(jobs), 12)]

    def one(n_batch):
        n, batch = n_batch
        f = ctx.scratch / f"score_batch{n}.json"
        f.write_text(json.dumps(batch, ensure_ascii=False))
        out = agent.run(agent.prompt("score.md", batch_file=str(f)), model=cfg["models"]["score"], schema=agent.SCORE,
                        scratch=ctx.scratch, log=ctx.log, cancelled=ctx.cancelled, max_turns=8, tools=["Read"])
        return out["results"]

    with ThreadPoolExecutor(PARALLEL) as ex:
        results = [r for rs in ex.map(one, enumerate(batches)) for r in rs]
    res_file = ctx.scratch / "score_results.json"
    res_file.write_text(json.dumps(results))
    r = subprocess.run([sys.executable, "tools/rank_state.py", "apply", "--results", str(res_file)],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode not in (0, 1):
        raise RuntimeError(f"rank_state apply failed: {r.stderr[:300]}")
    out = json.loads(r.stdout)
    for e in out.get("errors", []):
        ctx.log(f"unscored: {e}")
    subprocess.run([sys.executable, "tools/rank_state.py", "sweep", "--write"], cwd=ROOT, capture_output=True)
    return out.get("ranked", [])


def select_drafts(ranked, min_score, limit):
    ok = [r for r in ranked if r["score"] >= min_score and r.get("location_verdict") == "PASS"
          and not any(str(g).upper().startswith("SALARY FAIL") for g in r.get("gaps") or [])]
    return sorted(ok, key=lambda r: (r.get("deadline") or "9999-12-31", -r["score"]))[:limit]


# ---------- draft + verify ----------

def _paths(slug):
    return (ROOT / f"cv/main_{slug}.tex", ROOT / f"cover_letters/cover_{slug}.tex",
            ROOT / f"documents/applications/{slug}")


def _banned_names():
    return [n.strip() for n in BANNED.read_text().splitlines() if n.strip()] if BANNED.exists() else []


def why_roles(ctx):
    """Write the missing "Why this role?" answers for Ready drafts (older drafts predate the draft step that writes them)."""
    cfg, names, written, refused = store.load_config(), _banned_names(), 0, []
    todo = [a for a in store.applications() if a["status"] == "drafted" and a["slug"] and not a["why_role"]
            and (store.ROOT / "documents" / "applications" / a["slug"] / "job_posting.md").is_file()]
    ctx.log(f"{len(todo)} Ready draft(s) without an answer")
    for n, a in enumerate(todo, 1):
        if ctx.cancelled():
            raise RuntimeError("cancelled")
        folder = store.ROOT / "documents" / "applications" / a["slug"]
        ctx.log(f"{n}/{len(todo)} {a['company']} - {a['role']}")
        out = agent.run(agent.prompt("why_role.md", company=a["company"], role=a["role"], posting=f"documents/applications/{a['slug']}/job_posting.md"),
                        model=cfg["models"]["score"], schema=agent.WHY_ROLE, scratch=ctx.scratch, log=ctx.log,
                        cancelled=ctx.cancelled, max_turns=8, tools=["Read"])
        text = (out.get("answer") or "").strip()
        hits = banned_hits(text, names)
        if not text or hits:
            refused.append(a["company"])
            ctx.log(f"  not saved: {'names side work' if hits else 'empty answer'}")
            continue
        (folder / "why_role.md").write_text(text + "\n", encoding="utf-8")
        written += 1
    return f"{written} written" + (f", not saved: {', '.join(refused)}" if refused else "")


def post_verify(slug):
    cv, cl, _ = _paths(slug)
    problems = []
    for tex, pages in ((cv, 2), (cl, 1)):
        pdf = tex.with_suffix(".pdf")
        if not pdf.exists():
            problems.append(f"{pdf.name} missing")
            continue
        try:
            verify_pdf(pdf, expected_pages=pages, required_text=(store.load_config()["cv_email"],) if pages == 2 and store.load_config()["cv_email"] else ())
        except VerificationError as e:
            problems.append(f"{pdf.name}: {e}")
    if cv.with_suffix(".pdf").exists():
        try:
            problems += report(cv.with_suffix(".pdf"), parse_pdf(cv.with_suffix(".pdf")))
        except RuntimeError as e:
            problems.append(f"layout check skipped: {e}")
    names = _banned_names()
    why = store.ROOT / "documents" / "applications" / slug / "why_role.md"
    for tex in (cv, cl, why):
        if tex.exists():
            hits = banned_hits(tex.read_text(encoding="utf-8"), names)
            if hits:
                problems.append(f"{tex.name} names side-work: {', '.join(hits)}")
    return problems


def draft(ctx, job, cfg, slug, extra=""):
    ctx.log(f"Drafting {job['company']} - {job['title']}")
    return agent.run(agent.prompt("draft.md", company=job["company"], title=job["title"], url=job["url"], slug=slug, extra=extra),
                     model=cfg["models"]["draft"], schema=agent.DRAFT, scratch=ctx.scratch, log=ctx.log,
                     cancelled=ctx.cancelled, max_turns=80)


def record(ctx, job, res, slug, fit):
    if res["status"] != "READY":
        ctx.log(f"  {res['status']}: {job['company']} - {res.get('reason')}")
        return None
    problems = post_verify(slug)
    status = "needs_review" if problems else "drafted"
    notes = "; ".join(x for x in (res.get("remote_note"), res.get("salary") and f"Pay: {res['salary']}", res.get("fit_note"),
                                  res.get("form_notes") and f"Form: {res['form_notes']}") if x)
    if problems:
        notes = "NEEDS REVIEW: " + " / ".join(problems) + (" | " + notes if notes else "")
        ctx.log(f"  needs review: {problems}")
    store.add_row({"date": date.today().isoformat(), "company": job["company"], "role": job["title"], "channel": "online",
                   "status": status, "fit_rating": str(fit or ""), "notes": notes,
                   "cv_file": f"cv/main_{slug}.tex", "cover_letter_file": f"cover_letters/cover_{slug}.tex",
                   "source": store._http(res.get("apply_url")) or job["url"], "deadline": res.get("deadline") or job.get("deadline") or ""})
    ctx.log(f"  {status}: {job['company']} - {job['title']}")
    return status


def _set_seen_status(key, status):
    doc, seen = load_state(SEEN)
    if key in seen:
        seen[key]["status"] = status
        save_state(SEEN, doc)


def _unique_slug(company, title):
    slug, n = slugify(company, title), 2
    while _paths(slug)[0].exists():
        slug = f"{slugify(company, title)}_{n}"
        n += 1
    return slug


# ---------- tasks ----------

def daily_run(ctx):
    cfg = store.load_config()
    pool = drop_blocked(scrape(ctx), AGGREGATORS)
    _, seen = load_state(SEEN)
    tracker = {(_norm(a["company"]), _norm(a["role"])) for a in store.applications()}
    new = dedup(pool, seen, tracker)
    ctx.log(f"Scraped {len(pool)} results, {len(new)} new")
    if not new or ctx.cancelled():
        return f"{len(pool)} scraped, nothing new"
    keep = triage(ctx, new, cfg)
    ctx.log(f"Triage kept {len(keep)} of {len(new)}")
    if cfg["min_company_size"] and keep:
        sizes = companies.sizes_for(ctx, [new[k] for k in keep], cfg)
        small = {k for k in keep if not companies.big_enough(new[k]["company"], sizes, cfg["min_company_size"], cfg["keep_unknown_size"])}
        for k in sorted(small, key=lambda k: new[k]["company"]):
            n = sizes.get(companies._key(new[k]["company"]))
            ctx.log(f"  too small: {new[k]['company']} ({'size unknown' if n is None else f'{n} employees'})")
        keep -= small
        ctx.log(f"Company size >= {cfg['min_company_size']}: kept {len(keep)}")
    record_seen(new, keep)
    jobs = details(ctx, new, keep)
    ranked = score(ctx, jobs, cfg) if jobs and not ctx.cancelled() else []
    picks = select_drafts(ranked, cfg["min_score"], cfg["max_drafts"])
    ctx.log(f"Scored {len(ranked)}; drafting {len(picks)}")

    def go(r):
        if ctx.cancelled():
            return None
        job = {"company": r["company"], "title": r["title"], "url": r["url"], "deadline": r.get("deadline")}
        slug = _unique_slug(job["company"], job["title"])
        try:
            res = draft(ctx, job, cfg, slug)
        except agent.AgentError as e:
            ctx.log(f"  draft failed for {job['company']}: {e}")
            return None
        if res["status"] in ("EXPIRED", "VETO"):
            _set_seen_status(r["key"], "expired" if res["status"] == "EXPIRED" else "ranked")
        return record(ctx, job, res, slug, r["score"])

    with ThreadPoolExecutor(PARALLEL) as ex:
        outcomes = list(ex.map(go, picks))
    ready = outcomes.count("drafted")
    review = outcomes.count("needs_review")
    summary = f"{ready} ready, {review} need review, {len(ranked)} scored, {len(new)} new of {len(pool)} scraped"
    apps = store.applications()
    notify.send(cfg, f"{ready} new applications ready ({sum(a['status'] == 'drafted' for a in apps)} waiting)",
                title="Apply Desk: daily search", when=ready or review)
    return summary


def draft_url(ctx):
    cfg = store.load_config()
    url = ctx.args["url"]
    tmp = "url_" + hashlib.sha1(url.encode()).hexdigest()[:8]
    extra = (f"Company and title are unknown: read them from the posting and return them in `company` and `title`.\n"
             f"Before drafting, evaluate fit with `.claude/skills/job-application-assistant/04-job-evaluation.md` and return "
             f"the weighted score in `fit_score`. If it is below {cfg['min_score']}, return VETO with the reason and do not draft.")
    res = draft(ctx, {"company": "(from posting)", "title": "(from posting)", "url": url}, cfg, tmp, extra)
    if res["status"] != "READY":
        return f"{res['status']}: {res.get('reason')}"
    company, title = res.get("company") or "Unknown", res.get("title") or "Role"
    slug = _unique_slug(company, title)
    cv, cl, d = _paths(tmp)
    ncv, ncl, nd = _paths(slug)
    for src, dst in ((cv, ncv), (cv.with_suffix(".pdf"), ncv.with_suffix(".pdf")), (cl, ncl), (cl.with_suffix(".pdf"), ncl.with_suffix(".pdf"))):
        if src.exists():
            src.rename(dst)
    if d.exists():
        shutil.move(str(d), str(nd))
    status = record(ctx, {"company": company, "title": title, "url": url}, res, slug, res.get("fit_score"))
    notify.send(cfg, f"Draft ready: {company} - {title}", title="Apply Desk", when=status == "drafted")
    return f"{status}: {company} - {title}"


def interview(ctx):
    cfg = store.load_config()
    app = next((a for a in store.applications() if a["id"] == int(ctx.args["application_id"])), None)
    if not app or not app["slug"]:
        raise ValueError("Application not found")
    agent.run(agent.prompt("interview.md", company=app["company"], role=app["role"], slug=app["slug"],
                           cv_file=f"cv/main_{app['slug']}.tex", cover_file=f"cover_letters/cover_{app['slug']}.tex"),
              model=cfg["models"]["draft"], schema=agent.INTERVIEW, scratch=ctx.scratch, log=ctx.log,
              cancelled=ctx.cancelled, max_turns=40)
    return f"Interview prep ready: {app['company']}"


def deadline_alert(ctx):
    cfg = store.load_config()
    soon = store.summary(store.applications())["closing_soon"]
    if soon:
        msg = "; ".join(f"{s['company']} ({'today' if s['days_left'] == 0 else str(s['days_left']) + 'd'})" for s in soon)
        notify.send(cfg, f"Closing soon: {msg}", title="Apply Desk: deadlines", when=True)
    return f"{len(soon)} closing within 3 days"
