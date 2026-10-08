# Security Policy

## Reporting a vulnerability

Report security findings privately through **[GitHub private vulnerability reporting](https://github.com/gysosin/apply-desk/security/advisories/new)**, not a public issue. You will get a reply within a few days, credit in the fix unless you prefer otherwise, and disclosure coordinated with the patch.

If the private form is unavailable, open a public issue that describes only the *class* of problem, without a working recipe, and say that you have details to share privately.

## Threat model, honestly stated

Apply Desk is an agentic app: an LLM with limited file access reads untrusted content (job postings, recruiter emails) next to your personal data (profile, CVs, application history). That combination is the main risk surface. It can be narrowed, not eliminated. What the app does about it:

- **Untrusted input stays data.** Every prompt that reads a posting or an email treats it as data, never as instructions. Agents do not fetch URLs found inside posting text.
- **A tool guard on every agent call.** `app/guards.py` runs before each tool use: no browser or form tools, no git, `curl` GET only, writes only to `cv/`, `cover_letters/`, `documents/applications/` and `company_research/`. Agents cannot submit applications.
- **Sandboxed TeX.** Agent-written LaTeX compiles only through `app/texc.py` inside `bubblewrap`: no network, home directory hidden, only the document folder writable, TeX file I/O set to paranoid.
- **Secrets outside the repo.** The dashboard login hash and the Gmail app password live in `~/.config/applydesk/config.json` (mode 600), which the agents cannot read. Gmail access is read-only IMAP.
- **Personal data is git-ignored.** The tracker, generated documents, Gmail state and run logs never enter git.
- **The dashboard** uses a salted password hash, `HttpOnly` + `SameSite=Strict` session cookies (`Secure` over HTTPS) and an origin check on state-changing requests. By default it listens on `127.0.0.1` only.
- **CI guards** (`security-guards`) fail any change that widens the Claude Code permission allowlist, adds package lifecycle scripts or weakens the personal-data gitignore rules.

Instruction-level rules raise the bar; they are not a sandbox on their own. If you point the app at sources you do not trust at all, review what it fetched and wrote before you send anything.

## Scope notes

- Job-source scrapers make live requests only when a search runs; CI never does.
- Exposing the dashboard beyond your machine (`--host 0.0.0.0`, a reverse proxy, a tunnel) is your responsibility. Use HTTPS and a strong password.
