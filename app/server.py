"""FastAPI server: JSON API (see app/API.md), SSE run logs, files, and the built SPA."""
import asyncio
from contextlib import asynccontextmanager
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import auth, gmail, notify, pipeline, store
from app.scheduler import Runner, Schedules, scheduler_loop

DIST = Path(__file__).parent / "web" / "dist"
COOKIE = "jd_session"
TASKS = {"daily_run": pipeline.daily_run, "gmail_check": gmail.gmail_check, "deadline_alert": pipeline.deadline_alert,
         "draft_url": pipeline.draft_url, "interview": pipeline.interview, "why_roles": pipeline.why_roles}
DEFAULT_SCHEDULES = [
    {"name": "Morning search", "task": "daily_run", "kind": "daily", "time": "10:07", "days": [], "every_min": 60, "enabled": True},
    {"name": "Deadline check", "task": "deadline_alert", "kind": "daily", "time": "09:03", "days": [], "every_min": 60, "enabled": True},
    {"name": "Gmail replies", "task": "gmail_check", "kind": "interval", "time": "09:00", "days": [], "every_min": 120, "enabled": False},
]

schedules = Schedules(store.DATA / "schedules.json")
runner = Runner(store.DATA, TASKS)
_stop = threading.Event()


@asynccontextmanager
async def lifespan(_app):
    if not schedules.list():
        for s in DEFAULT_SCHEDULES:
            schedules.create(s)
    runner.start()
    threading.Thread(target=scheduler_loop, args=(schedules, runner, _stop), name="scheduler", daemon=True).start()
    yield
    _stop.set()
    runner.stop()


app = FastAPI(title="Apply Desk", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


# ---------- auth ----------

def user(request: Request):
    name = auth.user_for(request.cookies.get(COOKIE))
    if not name:
        raise HTTPException(401, "Sign in to continue")
    if request.method not in ("GET", "HEAD"):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            raise HTTPException(403, "Cross-site request blocked")
    return name


class Login(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=200)


@app.post("/api/login")
def login(body: Login, request: Request, response: Response):
    if not auth.verify(body.username, body.password):
        time.sleep(0.6)  # slow down guessing
        raise HTTPException(401, "Wrong username or password")
    response.set_cookie(COOKIE, auth.login(body.username), httponly=True, samesite="strict", max_age=auth.SESSION_TTL,
                        secure=request.url.scheme == "https")
    return {"username": body.username}


@app.post("/api/logout", status_code=204)
def logout(request: Request, response: Response):
    auth.logout(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE)


@app.get("/api/me")
def me(name=Depends(user)):
    return {"username": name}


# ---------- applications ----------

def _public(a):
    return {k: v for k, v in a.items() if k != "slug"}


@app.get("/api/applications")
def applications(_=Depends(user)):
    return [_public(a) for a in store.applications()]


class StatusBody(BaseModel):
    company: str
    role: str
    status: Literal["drafted", "applied", "skipped"]


@app.post("/api/applications/{idx}/status")
def set_status(idx: int, body: StatusBody, _=Depends(user)):
    try:
        return _public(store.set_status(idx, body.company, body.role, body.status))
    except store.Conflict as e:
        raise HTTPException(409, str(e))


@app.get("/api/summary")
def summary(_=Depends(user)):
    s = store.summary(store.applications())
    runs = runner.list(1)
    upcoming = [x for x in schedules.list() if x["next_run"]]
    nxt = min(upcoming, key=lambda x: x["next_run"], default=None)
    s["replies"] = len(gmail.load_replies())
    s["last_run"] = runs[0] if runs else None
    s["next_run"] = {"schedule_id": nxt["id"], "name": nxt["name"], "at": nxt["next_run"]} if nxt else None
    return s


@app.get("/api/answers")
def answers(_=Depends(user)):
    return [{"label": k, "value": v} for k, v in store.ANSWERS]


@app.get("/api/replies")
def replies(_=Depends(user)):
    return [{k: v for k, v in r.items() if k != "id"} for r in gmail.load_replies()]


# ---------- runs ----------

class RunBody(BaseModel):
    task: Literal["daily_run", "gmail_check", "deadline_alert", "draft_url", "interview", "why_roles"]
    url: str | None = Field(default=None, max_length=2000)
    application_id: int | None = None


@app.get("/api/runs")
def runs(limit: int = 50, _=Depends(user)):
    return runner.list(min(max(limit, 1), 300))


@app.post("/api/runs", status_code=201)
def create_run(body: RunBody, _=Depends(user)):
    args, label = None, None
    if body.task == "draft_url":
        if not body.url or urlparse(body.url).scheme not in ("http", "https"):
            raise HTTPException(422, "Paste a full job link starting with https://")
        args, label = {"url": body.url}, f"Draft: {urlparse(body.url).netloc}"
    elif body.task == "interview":
        app_ = next((a for a in store.applications() if a["id"] == body.application_id), None)
        if not app_:
            raise HTTPException(422, "Pick an application")
        args, label = {"application_id": body.application_id}, f"Interview prep: {app_['company']}"
    try:
        return runner.submit(body.task, args, label=label)
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.post("/api/runs/{rid}/cancel")
def cancel_run(rid: str, _=Depends(user)):
    try:
        return runner.cancel(rid)
    except ValueError as e:
        raise HTTPException(409, str(e))


def _run_or_404(rid):
    run = runner.get(rid)
    if not run:
        raise HTTPException(404, "No such run")
    return run


@app.get("/api/runs/{rid}/log", response_class=PlainTextResponse)
def run_log(rid: str, _=Depends(user)):
    _run_or_404(rid)
    p = runner.log_path(rid)
    return p.read_text(encoding="utf-8") if p.exists() else ""


@app.get("/api/runs/{rid}/stream")
async def run_stream(rid: str, _=Depends(user)):
    _run_or_404(rid)
    path = runner.log_path(rid)

    async def events():
        pos = 0
        while True:
            if path.exists():
                with path.open(encoding="utf-8") as f:
                    f.seek(pos)
                    chunk = f.read()
                    pos = f.tell()
                for line in chunk.splitlines():
                    yield f"data: {line}\n\n"
            status = runner.get(rid)["status"]
            if status not in ("queued", "running"):
                yield f"event: end\ndata: {status}\n\n"
                return
            await asyncio.sleep(0.7)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


# ---------- schedules ----------

class ScheduleBody(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    task: Literal["daily_run", "gmail_check", "deadline_alert"]
    kind: Literal["daily", "interval"]
    time: str = "09:00"
    days: list[int] = []
    every_min: int = 60
    enabled: bool = True


def _sched(fn):
    try:
        return fn()
    except ValueError as e:
        raise HTTPException(422, str(e))
    except KeyError:
        raise HTTPException(404, "No such schedule")


def _with_next(s):
    return next((x for x in schedules.list() if x["id"] == s["id"]), s)


@app.get("/api/schedules")
def list_schedules(_=Depends(user)):
    return schedules.list()


@app.post("/api/schedules", status_code=201)
def create_schedule(body: ScheduleBody, _=Depends(user)):
    return _with_next(_sched(lambda: schedules.create(body.model_dump())))


@app.put("/api/schedules/{sid}")
def update_schedule(sid: str, body: ScheduleBody, _=Depends(user)):
    return _with_next(_sched(lambda: schedules.update(sid, body.model_dump())))


@app.delete("/api/schedules/{sid}", status_code=204)
def delete_schedule(sid: str, _=Depends(user)):
    _sched(lambda: schedules.delete(sid))


# ---------- settings ----------

class Models(BaseModel):
    triage: str = Field(max_length=80)
    score: str = Field(max_length=80)
    draft: str = Field(max_length=80)


class SettingsBody(BaseModel):
    min_score: int = Field(ge=0, le=100)
    max_drafts: int = Field(ge=0, le=50)
    min_company_size: int = Field(default=500, ge=0, le=1_000_000)
    keep_unknown_size: bool = False
    models: Models
    notify_enabled: bool
    ntfy_topic: str = Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")
    gmail_enabled: bool
    gmail_user: str = Field(max_length=200)
    gmail_app_password: str | None = Field(default=None, max_length=64)


@app.get("/api/settings")
def get_settings(_=Depends(user)):
    cfg = store.load_config()
    store.save_config(cfg)  # persists the generated ntfy topic
    return store.public_settings(cfg)


@app.put("/api/settings")
def put_settings(body: SettingsBody, _=Depends(user)):
    cfg = store.load_config()
    data = body.model_dump()
    pw = data.pop("gmail_app_password")
    cfg.update(data)
    if pw:
        cfg["gmail_app_password"] = pw.replace(" ", "")
    store.save_config(cfg)
    return store.public_settings(cfg)


@app.post("/api/settings/test-notify")
def test_notify(_=Depends(user)):
    cfg = store.load_config()
    try:
        notify.send(cfg, f"Test from Apply Desk at {datetime.now():%H:%M}. Notifications work.", force=True)
    except OSError as e:
        raise HTTPException(502, f"Could not reach ntfy.sh: {e}")
    return {"ok": True}


# ---------- files + SPA ----------

@app.get("/files/{path:path}")
def files(path: str, _=Depends(user)):
    p = store.safe_file(path)
    if not p:
        raise HTTPException(404, "File not found")
    media = "application/pdf" if p.suffix == ".pdf" else "text/plain; charset=utf-8"
    return FileResponse(p, media_type=media, headers={"Content-Disposition": f'inline; filename="{p.name}"'})


@app.get("/{full:path}", include_in_schema=False)
def spa(full: str):
    if full.startswith("api/"):
        raise HTTPException(404, "Not found")
    f = (DIST / full).resolve()
    if full and f.is_file() and f.is_relative_to(DIST):
        return FileResponse(f)
    index = DIST / "index.html"
    if not index.exists():
        return PlainTextResponse("Frontend not built yet: cd app/web && bun install && bun run build", status_code=503)
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
