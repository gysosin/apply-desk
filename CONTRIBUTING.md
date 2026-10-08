# Contributing to Apply Desk

Thanks for helping. Issues, fixes, new job sources and documentation improvements are all welcome.

## Before you start

- **Never include personal data.** No tracker rows, emails, CV text, config values or real application details in issues, commits, screenshots or tests. Use fictional examples (Northwind Labs, Globex, Initech ...).
- **One concern per pull request.** Small PRs get reviewed fast.
- For anything larger than a fix, open an issue first so we can agree on the approach.

## Development setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r app/requirements.txt
(cd app/web && bun install && bun run build)
.venv/bin/python -m app serve --port 8770        # http://127.0.0.1:8770
```

See [SETUP.md](SETUP.md) for TeX and the job-search CLIs, and [docs/claude-access.md](docs/claude-access.md) for Claude access.

## What a good PR includes

- **A failing test first.** New behaviour comes with a test that fails without the change. Backend tests live in `app/tests/` (plain `unittest`); framework tool tests in `tests/`.
- **Real reproduction for bug fixes.** Show the failure through the path the code really runs, not only a hand-built input.
- **The checks CI runs**, all green:

```bash
python -m unittest discover -s app/tests -t .     # Apply Desk
python -m unittest discover -s tests -t .         # framework tools
python tools/lint_skills.py
python tools/security_guards.py
cd app/web && bun run build                       # dashboard
```

## Where things live

| Change | Files |
|---|---|
| A new company career board | `BOARDS` in `app/boards.py` (Greenhouse, Ashby or Lever token) |
| A new job site | a module like `app/instahyre.py`, wired into `scrape()` in `app/pipeline.py` |
| Aggregators to block | `AGGREGATORS` in `app/pipeline.py` |
| Prompts | `app/prompts/*.md` |
| Dashboard | `app/web/src/` (React, Tailwind) |
| HTTP API | `app/server.py`, documented in `app/API.md` |

## Style

- Match the surrounding code: small functions, plain Python, no new dependency for what a few lines can do.
- Keep prompts short and treat posting and email text as untrusted data.
- Keep user-facing text plain and specific.

## Upstream framework

The Claude Code workflow (`/setup`, `/apply`, `/interview` ...) comes from [AI Job Search](https://github.com/MadsLorentzen/ai-job-search). Framework-level improvements that are not specific to Apply Desk are best proposed there.
