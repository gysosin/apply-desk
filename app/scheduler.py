"""In-app scheduler and single-worker run queue (stdlib only).

ponytail: daily/weekday/interval schedules only, no cron syntax; swap in croniter if needed.
"""
import json
import queue
import re
import secrets
import threading
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

SCHEDULABLE = {"daily_run", "gmail_check", "deadline_alert"}
LABELS = {"daily_run": "Daily search", "gmail_check": "Gmail check", "deadline_alert": "Deadline alert",
          "draft_url": "Draft from URL", "interview": "Interview prep", "why_roles": "Why-this-role answers"}


def _now():
    return datetime.now().replace(microsecond=0)


def _dt(s):
    return datetime.fromisoformat(s) if s else None


def next_run(s):
    """Next due time strictly after the last run (or creation). May be in the past = due now."""
    if not s.get("enabled"):
        return None
    base = _dt(s.get("last_run")) or _dt(s.get("created")) or _now()
    if s["kind"] == "interval":
        return base + timedelta(minutes=int(s["every_min"]))
    hh, mm = map(int, s["time"].split(":"))
    days = set(s.get("days") or range(7))
    cand = base.replace(hour=hh, minute=mm, second=0)
    if cand <= base:
        cand += timedelta(days=1)
    while cand.weekday() not in days:
        cand += timedelta(days=1)
    return cand


def _validate(s):
    if s.get("task") not in SCHEDULABLE:
        raise ValueError(f"task must be one of {sorted(SCHEDULABLE)}")
    if s.get("kind") not in ("daily", "interval"):
        raise ValueError("kind must be daily or interval")
    if not str(s.get("name", "")).strip():
        raise ValueError("name is required")
    if s["kind"] == "daily":
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(s.get("time", ""))):
            raise ValueError("time must be HH:MM (24h)")
        if any(d not in range(7) for d in s.get("days") or []):
            raise ValueError("days must be 0 (Mon) to 6 (Sun)")
    elif int(s.get("every_min", 0)) < 15:
        raise ValueError("interval must be at least 15 minutes")
    return {k: s.get(k) for k in ("name", "task", "kind", "time", "days", "every_min", "enabled")} | {
        "name": s["name"].strip(), "days": sorted(set(s.get("days") or [])),
        "every_min": int(s.get("every_min") or 60), "time": s.get("time") or "09:00", "enabled": bool(s.get("enabled", True))}


class Schedules:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()

    def _load(self):
        return json.loads(self.path.read_text()) if self.path.exists() else []

    def _save(self, items):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, indent=2))
        tmp.replace(self.path)

    def list(self):
        with self.lock:
            items = self._load()
        for s in items:
            nr = next_run(s)
            s["next_run"] = max(nr, _now()).isoformat() if nr else None
        return items

    def create(self, body):
        s = _validate(body) | {"id": secrets.token_hex(4), "last_run": None, "created": _now().isoformat()}
        with self.lock:
            items = self._load()
            items.append(s)
            self._save(items)
        return s

    def update(self, sid, body):
        clean = _validate(body)
        with self.lock:
            items = self._load()
            for s in items:
                if s["id"] == sid:
                    if (s["kind"], s["time"], s["days"], s["every_min"]) != (clean["kind"], clean["time"], clean["days"], clean["every_min"]):
                        s["created"], s["last_run"] = _now().isoformat(), None  # new timing: don't fire for past slots
                    s.update(clean)
                    self._save(items)
                    return s
        raise KeyError(sid)

    def delete(self, sid):
        with self.lock:
            items = self._load()
            kept = [s for s in items if s["id"] != sid]
            if len(kept) == len(items):
                raise KeyError(sid)
            self._save(kept)

    def mark_ran(self, sid, at):
        with self.lock:
            items = self._load()
            for s in items:
                if s["id"] == sid:
                    s["last_run"] = at.isoformat()
            self._save(items)

    def due(self, now=None):
        now = now or _now()
        with self.lock:
            items = self._load()
        return [s for s in items if (nr := next_run(s)) and nr <= now]


class Ctx:
    """What a task gets: its args, a logger, a cancel flag and a scratch dir."""

    def __init__(self, run, log_file, scratch, cancel_event):
        self.run, self.args, self.scratch = run, run.get("args") or {}, scratch
        self._log, self._cancel = log_file, cancel_event

    def log(self, msg):
        line = f"[{datetime.now():%H:%M:%S}] {msg}"
        with self._log.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def cancelled(self):
        return self._cancel.is_set()


class Runner:
    MAX_KEEP = 300

    def __init__(self, data_dir, tasks, on_finish=None):
        self.dir = Path(data_dir)
        (self.dir / "runs").mkdir(parents=True, exist_ok=True)
        self.index = self.dir / "runs.json"
        self.tasks, self.on_finish = tasks, on_finish
        self.lock = threading.Lock()
        self.q = queue.Queue()
        self.cancels = {}
        self._stop = threading.Event()
        runs = self._load()
        for r in runs:
            if r["status"] in ("queued", "running"):
                r.update(status="failed", error="The app stopped before this run finished.", finished=_now().isoformat())
        self._save(runs)

    def _load(self):
        return json.loads(self.index.read_text()) if self.index.exists() else []

    def _save(self, runs):
        tmp = self.index.with_suffix(".tmp")
        tmp.write_text(json.dumps(runs[-self.MAX_KEEP:], indent=2))
        tmp.replace(self.index)

    def _patch(self, rid, **kw):
        with self.lock:
            runs = self._load()
            for r in runs:
                if r["id"] == rid:
                    r.update(kw)
                    self._save(runs)
                    return r
        return None

    def list(self, limit=50):
        return list(reversed(self._load()))[:limit]

    def get(self, rid):
        return next((r for r in self._load() if r["id"] == rid), None)

    def log_path(self, rid):
        return self.dir / "runs" / f"{rid}.log"

    def submit(self, task, args=None, trigger="manual", label=None):
        if task not in self.tasks:
            raise ValueError(f"unknown task {task}")
        with self.lock:
            runs = self._load()
            if any(r["task"] == task and r.get("args") == (args or None) and r["status"] in ("queued", "running") for r in runs):
                raise ValueError(f"{LABELS.get(task, task)} is already queued or running")
            run = {"id": f"{_now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}", "task": task, "args": args or None,
                   "label": label or LABELS.get(task, task), "status": "queued", "trigger": trigger,
                   "created": _now().isoformat(), "started": None, "finished": None, "summary": None, "error": None}
            runs.append(run)
            self._save(runs)
        self.log_path(run["id"]).touch()
        self.cancels[run["id"]] = threading.Event()
        self.q.put(run["id"])
        return run

    def cancel(self, rid):
        ev = self.cancels.get(rid)
        run = self.get(rid)
        if not run or run["status"] not in ("queued", "running") or not ev:
            raise ValueError("Only queued or running runs can be cancelled")
        ev.set()
        if run["status"] == "queued":
            return self._patch(rid, status="cancelled", finished=_now().isoformat())
        return run

    def start(self):
        threading.Thread(target=self._loop, name="runner", daemon=True).start()

    def stop(self):
        self._stop.set()
        self.q.put(None)

    def _loop(self):
        while not self._stop.is_set():
            rid = self.q.get()
            if rid is None:
                return
            run = self.get(rid)
            if not run or run["status"] != "queued":
                continue
            run = self._patch(rid, status="running", started=_now().isoformat())
            scratch = self.dir / "scratch" / rid
            scratch.mkdir(parents=True, exist_ok=True)
            ctx = Ctx(run, self.log_path(rid), scratch, self.cancels[rid])
            try:
                summary = self.tasks[run["task"]](ctx)
                status = "cancelled" if ctx.cancelled() else "done"
                run = self._patch(rid, status=status, summary=summary, finished=_now().isoformat())
            except Exception as e:  # task failures are recorded on the run, never crash the worker
                ctx.log("ERROR " + "".join(traceback.format_exception_only(e)).strip())
                ctx.log(traceback.format_exc())
                run = self._patch(rid, status="failed", error=str(e) or type(e).__name__, finished=_now().isoformat())
            ctx.log(f"== {run['status']} ==")
            self.cancels.pop(rid, None)
            if self.on_finish:
                try:
                    self.on_finish(run)
                except Exception:
                    pass


def scheduler_loop(schedules, runner, stop, tick=30):
    while not stop.is_set():
        for s in schedules.due():
            try:
                runner.submit(s["task"], trigger="schedule", label=f"{LABELS[s['task']]} ({s['name']})")
            except ValueError:
                pass  # already running; still count the slot as taken
            schedules.mark_ran(s["id"], _now())
        stop.wait(tick)
