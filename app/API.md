# Apply Desk API (contract between app/server.py and app/web)

Same origin. Every `/api/*` route except `POST /api/login` requires the session cookie (`jd_session`, HttpOnly, SameSite=Strict); without it the route returns 401 and the SPA shows the login page. Mutating routes also require the `Origin` header to match. Errors return `{"detail": "<human message>"}` with a 4xx/5xx status.

## Auth
- `POST /api/login` `{username, password}` -> 200 `{username}` and sets the cookie. 401 means wrong credentials.
- `POST /api/logout` -> 204
- `GET /api/me` -> `{username}`

## Applications (rows of job_search_tracker.csv)
- `GET /api/applications` returns `Application[]`:
  ```ts
  type Status = 'drafted' | 'applied' | 'skipped' | 'needs_review' | string  // other tracker values pass through
  type Application = {
    id: number            // row index; send back with company+role for writes
    date: string          // YYYY-MM-DD drafted
    company: string; role: string; sector: string; role_type: string
    status: Status
    fit: number | null    // 0-100
    notes: string         // free text: remote/salary/gaps/form notes
    deadline: string | null   // YYYY-MM-DD
    apply_url: string     // open in a new tab
    cv_url: string | null       // /files/cv/....pdf
    cover_url: string | null    // /files/cover_letters/....pdf
    posting_url: string | null  // /files/documents/applications/<slug>/job_posting.md (text/plain)
    interview_url: string | null // /files/documents/applications/<slug>/interview_prep.md once generated
    applied_on: string | null    // YYYY-MM-DD, parsed from notes
  }
  ```
- `POST /api/applications/{id}/status` `{company, role, status: 'drafted'|'applied'|'skipped'}` -> 200 `Application`. 409 means the tracker changed, so reload.

## Summary (Today page)
`GET /api/summary` returns:
```ts
{
  ready: number; applied: number; applied_this_week: number; needs_review: number; replies: number
  closing_soon: {id: number, company: string, role: string, deadline: string, days_left: number}[]  // ready rows, deadline within 3 days
  applied_by_week: {week: string /* YYYY-MM-DD Monday */, count: number}[]  // last 8 weeks, oldest first
  last_run: Run | null
  next_run: {schedule_id: string, name: string, at: string /* ISO */} | null
}
```

## Form answers
`GET /api/answers` -> `{label: string, value: string}[]`, for the copy panel (name, email, phone, LinkedIn, notice, CTC...).

## Runs
```ts
type Task = 'daily_run' | 'gmail_check' | 'deadline_alert' | 'draft_url' | 'interview'
type Run = {
  id: string; task: Task; label: string        // label e.g. "Daily run", "Draft: https://..."
  status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
  trigger: 'schedule' | 'manual'
  created: string; started: string | null; finished: string | null  // ISO
  summary: string | null      // one line, e.g. "5 drafted, 2 vetoed, 211 scraped"
  error: string | null
}
```
- `GET /api/runs?limit=50` -> `Run[]`, newest first
- `POST /api/runs` `{task, url?: string, application_id?: number}` -> 201 `Run`. `draft_url` needs `url`; `interview` needs `application_id`. 409 means the same task is already queued or running.
- `POST /api/runs/{id}/cancel` -> 200 `Run` (queued runs only; a running run is cancelled cooperatively at the next step)
- `GET /api/runs/{id}/log` -> text/plain full log
- `GET /api/runs/{id}/stream` -> `text/event-stream`. Events are `data: <log line>`, then a final `event: end` with `data: <status>`.

## Schedules (the in-app scheduler)
```ts
type Schedule = {
  id: string; name: string; task: 'daily_run' | 'gmail_check' | 'deadline_alert'
  kind: 'daily' | 'interval'
  time: string            // 'HH:MM' local time (kind=daily)
  days: number[]          // 0=Mon..6=Sun (kind=daily); empty = every day
  every_min: number       // kind=interval, >= 15
  enabled: boolean
  last_run: string | null // ISO
  next_run: string | null // ISO, computed by the server
}
```
- `GET /api/schedules` -> `Schedule[]`
- `POST /api/schedules` with a Schedule minus `id/last_run/next_run` -> 201 `Schedule`
- `PUT /api/schedules/{id}` with the same body -> `Schedule`
- `DELETE /api/schedules/{id}` -> 204

## Settings
```ts
type Settings = {
  min_score: number          // draft threshold, default 60
  max_drafts: number         // per run, default 8
  min_company_size: number   // skip companies with fewer employees (LinkedIn count); 0 = off; default 500
  keep_unknown_size: boolean // keep jobs whose company size can't be found; default false
  models: {triage: string, score: string, draft: string}  // Claude model ids
  notify_enabled: boolean; ntfy_topic: string             // phone push via ntfy.sh
  gmail_enabled: boolean; gmail_user: string; gmail_has_password: boolean
}
```
- `GET /api/settings` -> `Settings`
- `PUT /api/settings` with Settings plus optional `gmail_app_password: string` (write-only, never returned) -> `Settings`
- `POST /api/settings/test-notify` -> 200 `{ok: true}` or 4xx with detail

## Replies (Gmail, read-only)
`GET /api/replies` -> `{date: string, from: string, subject: string, snippet: string, company: string | null, application_id: number | null}[]`, newest first

## Files
`GET /files/<repo-relative path>` (auth required) serves PDFs and .md as text/plain. Only `cv/`, `cover_letters/` and `documents/applications/` are allowed.
