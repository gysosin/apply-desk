# Apply Desk

A local app that runs the job search without Claude Code: it scrapes, scores and drafts tailored CVs and cover letters, and shows everything on a dashboard. You open each application and submit it yourself; the app never submits anything.

- **Open:** https://applydesk.localhost (http:// redirects there)
- **Runs in Docker, always on:** `docker compose -f app/docker-compose.yml up -d --build` (containers restart on boot via `restart: unless-stopped`). nginx (`router`) terminates TLS on host port 443 (80 redirects) and is the only published service; the app listens only on the internal Docker network.
- **Certificate:** local CA at `~/.config/applydesk-tls/applydesk-ca.crt` (10 years), server cert for applydesk.localhost (825 days). Trust it once: `sudo trust anchor ~/.config/applydesk-tls/applydesk-ca.crt` (Firefox, system); for Chrome also `certutil -d sql:$HOME/.pki/nssdb -A -t C,, -n "Apply Desk Local CA" -i ~/.config/applydesk-tls/applydesk-ca.crt` (needs `nss-tools`).
- **Hostname:** `*.localhost` resolves to this machine automatically (no DNS server or /etc/hosts edit needed).
- **Login:** `.venv/bin/python -m app set-password` changes it (`--generate` prints a random one)
- **Schedules:** edit them on the Schedules page. Defaults: daily search 10:07, deadline check 09:03, Gmail every 2 h (off until you add an app password in Settings)
- **Phone push:** turn it on in Settings, install the ntfy app, subscribe to the topic shown there
- **Logs:** `docker compose -f app/docker-compose.yml logs -f applydesk`; restart after code changes: `docker compose -f app/docker-compose.yml restart applydesk`

## Commands
```
docker compose -f app/docker-compose.yml ps        # status
docker exec applydesk-applydesk-1 python -m app selftest
.venv/bin/python -m app run daily_run --max-drafts 2
.venv/bin/python -m app run draft_url --url https://...
.venv/bin/python -m app selftest                   # tools, login, Claude access
cd app/web && bun install && bun run build         # after frontend changes
.venv/bin/python -m unittest discover -s app/tests -t .
```

## How it works
- Claude runs through `claude-agent-sdk` with your Claude subscription login or an API key (see docs/claude-access.md).
- Every agent tool call passes `app/guards.py`: no browser or form tools, no git, curl GET only, and writes only to `cv/`, `cover_letters/`, `documents/applications/` and `company_research/`.
- TeX compiles only through `app/texc.py`, inside bubblewrap (home hidden, no network, only the document folder writable).
- Secrets (login hash, Gmail app password) live in `~/.config/applydesk/config.json` (mode 600), outside the repo, so agents can't read them.
- `job_search_tracker.csv` stays the single source of truth; the dashboard reads it live.
- Run logs: `app/data/runs/`. Drafts that fail verification (page count, layout, side-work names) show as "Needs review" and never as ready.
