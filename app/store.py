"""Tracker CSV, config and file access. The tracker stays the single source of truth."""
import csv
import json
import os
import re
import secrets
import threading
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACKER = ROOT / "job_search_tracker.csv"
DATA = ROOT / "app" / "data"
# Secrets (login hash, Gmail app password) live outside the repo so agents can never read them.
CONFIG = Path.home() / ".config" / "applydesk" / "config.json"
SERVABLE = ("cv", "cover_letters", "documents/applications")
WRITABLE_STATUSES = {"drafted", "applied", "skipped", "needs_review", "interview", "offer", "rejected"}
# How far along an application is; an email may only move a row forward. A rejection never overwrites an offer.
PROGRESS = {"drafted": 0, "skipped": 0, "needs_review": 0, "applied": 1, "interview": 2, "offer": 3, "rejected": 3}
APPLIED_RE = re.compile(r"\s*\|?\s*applied (\d{4}-\d{2}-\d{2})")
# Notes entry the Gmail check writes: "2026-07-22 gmail: rejection - <reason> (<subject>)"
OUTCOME_RE = re.compile(r"(\d{4}-\d{2}-\d{2}) gmail: (\w+)(?: - ([^(|]+?))? \(([^|]*)\)")
_lock = threading.Lock()


class Conflict(Exception):
    """The tracker row at that index is no longer the one the client saw."""


# ---------- tracker ----------

def _read(path):
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return r.fieldnames, list(r)


def _write(path, fields, rows):
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def _http(u):
    """Only http(s) links reach the UI (blocks javascript: and similar)."""
    return u if re.match(r"^https?://", u or "", re.I) else ""


def _url(rel):
    return f"/files/{rel}" if rel and (ROOT / rel).is_file() else None


def _why_role(slug):
    """The drafted answer to "Why this role?" for this application, if the draft step wrote one."""
    f = ROOT / "documents" / "applications" / slug / "why_role.md"
    return f.read_text(encoding="utf-8").strip() or None if slug and f.is_file() else None


def _view(i, r):
    cv = (r.get("cv_file") or "").replace(".tex", ".pdf")
    cl = (r.get("cover_letter_file") or "").replace(".tex", ".pdf")
    slug = Path(r.get("cv_file") or "").stem.removeprefix("main_")
    m = APPLIED_RE.search(r.get("notes") or "")
    o = OUTCOME_RE.findall(r.get("notes") or "")
    fit = (r.get("fit_rating") or "").strip()
    return {
        "id": i, "date": r.get("date", ""), "company": r["company"], "role": r["role"],
        "sector": r.get("sector", ""), "role_type": r.get("role_type", ""), "status": r.get("status", ""),
        "fit": int(fit) if fit.isdigit() else None, "notes": r.get("notes", ""),
        "deadline": r.get("deadline") or None, "apply_url": _http(r.get("source", "")),
        "cv_url": _url(cv), "cover_url": _url(cl),
        "posting_url": _url(f"documents/applications/{slug}/job_posting.md") if slug else None,
        "interview_url": _url(f"documents/applications/{slug}/interview_prep.md") if slug else None,
        "applied_on": m.group(1) if m else None, "slug": slug, "why_role": _why_role(slug),
        "outcome": dict(zip(("date", "signal", "reason", "subject"), o[-1])) | {"reason": o[-1][2] or None} if o else None,
    }


def applications(path=None):
    _, rows = _read(path or TRACKER)
    return [_view(i, r) for i, r in enumerate(rows)]


def set_status(idx, company, role, status, path=None, today=None):
    path = path or TRACKER
    if status not in WRITABLE_STATUSES:
        raise ValueError(f"unknown status {status!r}")
    with _lock:
        fields, rows = _read(path)
        if not 0 <= idx < len(rows) or rows[idx]["company"] != company or rows[idx]["role"] != role:
            raise Conflict("The tracker changed since this page loaded. Reload and try again.")
        row = rows[idx]
        row["status"] = status
        notes = APPLIED_RE.sub("", row.get("notes") or "").strip()
        if status == "applied":
            notes = f"{notes} | applied {(today or date.today()).isoformat()}".lstrip(" |")
        row["notes"] = notes
        _write(path, fields, rows)
        return _view(idx, row)


def advance(company, role, status, note, when, path=None):
    """Move a row forward to `status` (never back) and append a dated note. Returns True if it changed."""
    path = path or TRACKER
    with _lock:
        fields, rows = _read(path)
        row = next((r for r in rows if r["company"] == company and r["role"] == role), None)
        if row is None or row["status"] not in PROGRESS or PROGRESS[status] <= PROGRESS[row["status"]]:
            return False
        notes = row.get("notes") or ""
        if status == "applied":
            notes = f"{APPLIED_RE.sub('', notes).strip()} | applied {when}"
        row["status"], row["notes"] = status, f"{notes} | {when} {note}".lstrip(" |")
        _write(path, fields, rows)
        return True


def add_row(row, path=None):
    """Append a tracker row unless company+role already exists. Returns True if added."""
    path = path or TRACKER
    with _lock:
        fields, rows = _read(path)
        key = (row["company"].strip().lower(), row["role"].strip().lower())
        if any((r["company"].strip().lower(), r["role"].strip().lower()) == key for r in rows):
            return False
        rows.append({k: row.get(k, "") for k in fields})
        _write(path, fields, rows)
        return True


def summary(apps, today=None):
    today = today or date.today()
    ready = [a for a in apps if a["status"] == "drafted"]
    applied = [a for a in apps if a["status"] == "applied"]
    monday = today - timedelta(days=today.weekday())
    weeks = [monday - timedelta(weeks=n) for n in range(7, -1, -1)]
    counts = {w: 0 for w in weeks}
    for a in applied:
        if a["applied_on"]:
            d = date.fromisoformat(a["applied_on"])
            wk = d - timedelta(days=d.weekday())
            if wk in counts:
                counts[wk] += 1
    soon = []
    for a in ready:
        try:
            left = (date.fromisoformat(a["deadline"]) - today).days if a["deadline"] else None
        except ValueError:
            left = None
        if left is not None and 0 <= left <= 3:
            soon.append({"id": a["id"], "company": a["company"], "role": a["role"], "deadline": a["deadline"], "days_left": left})
    return {
        "ready": len(ready), "applied": len(applied), "applied_this_week": counts[monday],
        "needs_review": sum(a["status"] == "needs_review" for a in apps),
        "closing_soon": sorted(soon, key=lambda s: s["days_left"]),
        "applied_by_week": [{"week": w.isoformat(), "count": counts[w]} for w in weeks],
    }


def safe_file(rel):
    p = (ROOT / rel.lstrip("/")).resolve()
    if not any(p.is_relative_to(ROOT / d) for d in SERVABLE) or not p.is_file():
        return None
    return p


# ---------- config ----------

DEFAULTS = {
    "min_score": 60, "max_drafts": 8, "min_company_size": 500, "keep_unknown_size": False,
    "models": {"triage": "claude-haiku-4-5-20251001", "score": "claude-sonnet-5-5", "draft": "claude-opus-5-5"},
    "notify_enabled": False, "ntfy_topic": "",
    "cv_email": "",
    "gmail_enabled": False, "gmail_user": "", "gmail_app_password": "",
    "auth": {}, "session_secret": "",
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULTS))
    if CONFIG.exists():
        saved = json.loads(CONFIG.read_text(encoding="utf-8"))
        cfg.update({k: v for k, v in saved.items() if k != "models"})
        cfg["models"].update(saved.get("models", {}))
    if not cfg["ntfy_topic"]:
        cfg["ntfy_topic"] = "applydesk-" + secrets.token_hex(8)
    return cfg


def save_config(cfg):
    CONFIG.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = CONFIG.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    tmp.replace(CONFIG)


def public_settings(cfg):
    return {
        "min_score": cfg["min_score"], "max_drafts": cfg["max_drafts"], "models": cfg["models"],
        "min_company_size": cfg["min_company_size"], "keep_unknown_size": cfg["keep_unknown_size"],
        "notify_enabled": cfg["notify_enabled"], "ntfy_topic": cfg["ntfy_topic"],
        "gmail_enabled": cfg["gmail_enabled"], "gmail_user": cfg["gmail_user"],
        "gmail_has_password": bool(cfg["gmail_app_password"]),
    }


# Standard application-form answers shown on the dashboard. Fill these in from your 01-candidate-profile.md.
ANSWERS = [
    ("Full name", "[YOUR_NAME]"),
    ("Email", "[YOUR_EMAIL]"),
    ("Phone", "[YOUR_PHONE]"),
    ("Location", "[CITY, COUNTRY]"),
    ("LinkedIn", "[YOUR_LINKEDIN_URL]"),
    ("GitHub", "[YOUR_GITHUB_URL]"),
    ("Website", "[YOUR_WEBSITE]"),
    ("Current company / title", "[COMPANY - TITLE]"),
    ("Total experience", "[N years]"),
    ("Notice period", "[N days]"),
    ("Current salary", "[CURRENT]"),
    ("Expected salary", "[EXPECTED]"),
    ("Work authorization", "[e.g. Yes - no sponsorship needed]"),
    ("Government official / relative / referral questions", "No"),
]
