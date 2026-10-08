"""python -m app serve | run <task> | set-password | selftest"""
import argparse
import getpass
import secrets
import shutil
import sys


def main():
    p = argparse.ArgumentParser(prog="python -m app", description="Apply Desk")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the dashboard, scheduler and runner")
    s.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to open it from your phone on the same Wi-Fi")
    s.add_argument("--port", type=int, default=8770)
    s.add_argument("--tls", action="store_true", help="serve HTTPS with ~/.config/applydesk-tls/server.{crt,key}")
    s.add_argument("--behind-proxy", action="store_true", help="trust X-Forwarded-* from the nginx router (Docker setup)")
    r = sub.add_parser("run", help="run one task now in the foreground")
    r.add_argument("task", choices=["daily_run", "gmail_check", "deadline_alert", "draft_url", "interview"])
    r.add_argument("--url")
    r.add_argument("--application-id", type=int)
    r.add_argument("--max-drafts", type=int, help="override the per-run draft limit for this run")
    pw = sub.add_parser("set-password", help="set the dashboard login")
    pw.add_argument("--username", default="admin")
    pw.add_argument("--generate", action="store_true", help="generate and print a random password")
    sub.add_parser("selftest", help="check tools, login and Claude access")
    a = p.parse_args()

    if a.cmd == "serve":
        import uvicorn
        from app import store
        tls = store.CONFIG.parent.parent / "applydesk-tls"
        ssl = {"ssl_certfile": str(tls / "server.crt"), "ssl_keyfile": str(tls / "server.key")} if a.tls else {}
        uvicorn.run("app.server:app", host=a.host, port=a.port, log_level="warning",
                    proxy_headers=a.behind_proxy, forwarded_allow_ips="*" if a.behind_proxy else None, **ssl)
    elif a.cmd == "run":
        _run(a)
    elif a.cmd == "set-password":
        from app import auth
        password = secrets.token_urlsafe(12) if a.generate else getpass.getpass("New password: ")
        if len(password) < 8:
            sys.exit("Use at least 8 characters.")
        auth.set_password(a.username, password)
        print(f"Login set. Username: {a.username}" + (f"  Password: {password}" if a.generate else ""))
    elif a.cmd == "selftest":
        _selftest()


def _run(a):
    from app import pipeline, store
    from app.scheduler import Runner
    from app.server import TASKS
    if a.max_drafts is not None:
        orig = store.load_config
        store.load_config = lambda: orig() | {"max_drafts": a.max_drafts}
    args = {"url": a.url} if a.task == "draft_url" else {"application_id": a.application_id} if a.task == "interview" else None
    done = __import__("threading").Event()
    runner = Runner(store.DATA / "cli", TASKS, on_finish=lambda run: done.set())  # own history: never races the service
    runner.start()
    run = runner.submit(a.task, args)
    print(f"Run {run['id']} started; log: {runner.log_path(run['id'])}")
    log = runner.log_path(run["id"])
    pos = 0
    while not done.wait(1):
        text = log.read_text(encoding="utf-8")
        print(text[pos:], end="", flush=True)
        pos = len(text)
    print(log.read_text(encoding="utf-8")[pos:], end="")
    final = runner.get(run["id"])
    print(f"\n{final['status']}: {final['summary'] or final['error']}")
    sys.exit(0 if final["status"] == "done" else 1)


def _selftest():
    from app import agent, store
    ok = True
    for tool in ("bun", "lualatex", "xelatex", "pdftotext", "pdfinfo"):
        found = shutil.which(tool)
        print(f"{'ok ' if found else 'MISSING'} {tool} {found or ''}")
        ok &= bool(found)
    cfg = store.load_config()
    print(f"{'ok ' if cfg.get('auth') else 'MISSING'} dashboard login (python -m app set-password)")
    try:
        out = agent.run("Reply with the single word READY.", model=cfg["models"]["triage"], scratch=store.DATA, max_turns=1, tools=[])
        print(f"ok  Claude login works ({out.strip()[:20]})")
    except Exception as e:
        print(f"FAIL Claude: {e}")
        ok = False
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
