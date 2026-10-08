# Apply Desk

**An AI job-search assistant that runs on your own machine.** Every day it finds new jobs, keeps the ones that fit your profile, writes a tailored CV, cover letter and "Why this role?" answer for each, and shows them on a dashboard. It also reads your Gmail for replies and marks each application applied, rejected, interview or offer, with the reason taken from the email.

You stay in control: **Apply Desk never submits an application.** You open each one and apply yourself.

It is built on [AI Job Search](https://github.com/MadsLorentzen/ai-job-search) by Mads Lorentzen (MIT). That framework's Claude Code slash-command workflow (`/setup`, `/apply`, `/interview` ...) is still here and documented in [FRAMEWORK.md](FRAMEWORK.md). Apply Desk adds a standalone app so the daily work runs on a schedule without you opening Claude Code.

> Independent open-source project, not affiliated with or endorsed by Anthropic.

## What it does

| | |
|---|---|
| **Daily job search** | Pulls jobs from company career boards (Greenhouse, Ashby, Lever), LinkedIn, Instahyre and freehire. Drops aggregators and staffing reposters (Jobgether, Weekday, Turing ...), too-small companies and duplicates. |
| **Fit scoring** | Claude scores each posting against your profile and deal-breakers (location, remote, hours, salary floor). |
| **Drafting** | For the best matches: a tailored 2-page CV, a 1-page cover letter (LaTeX, compiled and checked for layout) and a pasteable "Why this role?" answer. |
| **Dashboard** | Today, Ready to apply, Applied (with outcome and the reason from the email), Runs (live progress), Schedules, Settings. |
| **Gmail tracking** | Reads replies (read-only IMAP) and moves applications forward: confirmation → Applied, assessment/interview → Interview, offer → Offer, rejection → Rejected. Only new mail is fetched each time. |
| **Interview prep** | One click turns an application into interview talking points. |
| **Phone alerts** | Optional push notifications through [ntfy](https://ntfy.sh). |

## Quick start

You need **Linux** (or WSL2 on Windows) for drafting, because the CVs are compiled with TeX inside a `bubblewrap` sandbox. Search, scoring, Gmail and the dashboard work anywhere Python runs.

```bash
git clone https://github.com/<you>/apply-desk.git && cd apply-desk

# 1. Tools: Python 3.11+, bun, TinyTeX (~/.TinyTeX), bubblewrap, poppler-utils
#    Step-by-step: SETUP.md sections 1 and 3
python3 -m venv .venv && .venv/bin/pip install -r app/requirements.txt
(cd app/web && bun install && bun run build)

# 2. Your profile: run the setup interview once in Claude Code
claude        # then type /setup   (fills CLAUDE.md and the candidate profile)

# 3. Claude access: pick ONE (details in docs/claude-access.md)
claude        # then /login with your Claude Pro/Max account      (subscription)
# or
export ANTHROPIC_API_KEY=sk-ant-...                                  (API key, pay per use)

# 4. Dashboard login and a health check
.venv/bin/python -m app set-password --username me
.venv/bin/python -m app selftest

# 5. Run it
.venv/bin/python -m app serve       # open http://127.0.0.1:8770
```

To keep it running all the time with HTTPS at `https://applydesk.localhost`, use Docker: see [docs/apply-desk.md](docs/apply-desk.md#run-it-always-on-with-docker).

## Guides

- **[docs/claude-access.md](docs/claude-access.md):** using it with a Claude subscription or without one (API key), costs and model choices.
- **[docs/apply-desk.md](docs/apply-desk.md):** daily use, every page of the dashboard, Gmail, notifications, job sources, Docker, commands and troubleshooting.
- **[SETUP.md](SETUP.md):** installing Python, bun and TeX, and the `/setup` profile interview.
- **[FRAMEWORK.md](FRAMEWORK.md):** the original Claude Code slash-command workflow.
- **[app/API.md](app/API.md):** the HTTP API the dashboard uses.

## Your data stays local

- The tracker (`job_search_tracker.csv`), generated documents, Gmail state and run logs stay on your disk and are git-ignored.
- Secrets (the dashboard login hash and Gmail app password) live in `~/.config/applydesk/config.json` (mode 600), outside the repo, where the AI agents cannot read them.
- **`/setup` writes your personal details into tracked files** (`CLAUDE.md`, the candidate profile). If you fork this repo, make your fork **private** or never commit those files.

## Safety

- Agents have no browser or form tools and cannot submit anything. Every tool call goes through `app/guards.py`: no git, `curl` GET only, and writes only to `cv/`, `cover_letters/`, `documents/applications/` and `company_research/`.
- TeX written by the agent compiles only through `app/texc.py`, inside `bubblewrap`: no network, home directory hidden, only the document folder writable.
- Job postings and emails are treated as untrusted data in every prompt.

## Development

```bash
.venv/bin/python -m unittest discover -s app/tests -t .     # backend tests
cd app/web && bun run build                                 # frontend (React, Vite, Tailwind)
```

## License

MIT, see [LICENSE](LICENSE). Original framework © Mads Lorentzen.
