# Claude access: with or without a subscription

Apply Desk calls Claude through the [Claude Agent SDK](https://docs.claude.com/en/docs/agent-sdk/overview), which ships its own copy of the Claude Code CLI. There are three ways to give it access. Pick one.

| Option | You need | You pay | Best for |
|---|---|---|---|
| **A. Subscription login** | Claude Pro or Max plan | Nothing extra; usage counts against your plan's limits | People who already use Claude Code |
| **B. Subscription token** | Claude Pro or Max plan | Same as A | Docker, servers, anything without a browser |
| **C. API key** | An Anthropic Console account | Per token, billed to the Console | No subscription, or you want separate billing |

If `ANTHROPIC_API_KEY` is set, it is used instead of a subscription login.

---

## A. Subscription login (Claude Pro / Max)

1. Install Claude Code once: `curl -fsSL https://claude.ai/install.sh | bash` (or `npm install -g @anthropic-ai/claude-code`).
2. Run `claude`, type `/login`, and sign in with your Claude account in the browser.
3. Check it: `.venv/bin/python -m app selftest` should print `ok  Claude login works`.

The login is stored in `~/.claude/`. Apply Desk reuses it, and the Docker setup mounts that folder into the container, so nothing else is needed.

## B. Subscription token (headless)

1. On any machine with a browser: `claude setup-token`. It prints a long-lived token for your subscription.
2. Give it to Apply Desk:
   - running directly: `export CLAUDE_CODE_OAUTH_TOKEN=<token>` before `python -m app serve`
   - Docker: copy `app/.env.example` to `app/.env` and set `CLAUDE_CODE_OAUTH_TOKEN=<token>`
3. Run `selftest` to check it.

## C. API key (no subscription)

1. Create a key at [console.anthropic.com](https://console.anthropic.com) → API Keys, and add credit under Billing.
2. Give it to Apply Desk:
   - running directly: `export ANTHROPIC_API_KEY=sk-ant-...`
   - Docker: in `app/.env`, set `ANTHROPIC_API_KEY=sk-ant-...`
3. Run `selftest` to check it.

You don't need to install Claude Code for this option; the SDK brings its own CLI. You still need Claude Code once to run the `/setup` profile interview, or you can fill `CLAUDE.md` and `.claude/skills/job-application-assistant/01-candidate-profile.md` by hand.

`app/.env` is git-ignored. Never commit a key or token.

### Other providers

The CLI also supports Amazon Bedrock and Google Vertex AI. Set the usual Claude Code variables (for example `CLAUDE_CODE_USE_BEDROCK=1` plus your AWS credentials) in the environment or `app/.env`. The model IDs in Settings must then be valid for that provider.

---

## Choosing models and keeping costs down

**Settings → Drafting** has one model per step:

| Step | Default | What it does | Volume |
|---|---|---|---|
| Triage model | Claude Haiku | First pass over every scraped title | Many short calls |
| Scoring model | Claude Sonnet | Reads full postings and scores fit. Also classifies Gmail replies. | Tens per day |
| Drafting model | Claude Opus | Writes the CV, cover letter and "Why this role?" answer | Up to "Drafts per run" |

Drafting is by far the largest cost. To spend less:

- Lower **Drafts per run** (default 8) or raise **Minimum fit score** (default 60).
- Set the **Drafting model** to Sonnet.
- Raise **Minimum company size** so fewer postings reach scoring.
- Turn off schedules you don't need on the Schedules page.

Every run's log (Runs page) shows each step, so you can see where the calls go.
