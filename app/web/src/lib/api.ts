// Typed client for app/API.md. Same origin, cookie session. A 401 on anything but the login
// call means the session ended: SESSION_ENDED fires and the app shows the login page.

export type Status = 'drafted' | 'applied' | 'skipped' | 'needs_review' | 'interview' | 'offer' | 'rejected' | (string & {})
export type Application = {
  id: number
  date: string
  company: string
  role: string
  sector: string
  role_type: string
  status: Status
  fit: number | null
  notes: string
  deadline: string | null
  apply_url: string
  cv_url: string | null
  cover_url: string | null
  posting_url: string | null
  interview_url: string | null
  applied_on: string | null
  /** Drafted answer for the form's "Why this role?" field. */
  why_role: string | null
  /** Latest employer email the Gmail check recorded for this row. */
  outcome: { date: string; signal: string; reason: string | null; subject: string } | null
}

export type Task = 'daily_run' | 'gmail_check' | 'deadline_alert' | 'draft_url' | 'interview' | 'why_roles'
export type RunStatus = 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
export type Run = {
  id: string
  task: Task
  label: string
  status: RunStatus
  trigger: 'schedule' | 'manual'
  created: string
  started: string | null
  finished: string | null
  summary: string | null
  error: string | null
}

export type Summary = {
  ready: number
  applied: number
  applied_this_week: number
  needs_review: number
  replies: number
  closing_soon: { id: number; company: string; role: string; deadline: string; days_left: number }[]
  applied_by_week: { week: string; count: number }[]
  last_run: Run | null
  next_run: { schedule_id: string; name: string; at: string } | null
}

export type ScheduleTask = 'daily_run' | 'gmail_check' | 'deadline_alert'
export type Schedule = {
  id: string
  name: string
  task: ScheduleTask
  kind: 'daily' | 'interval'
  time: string
  days: number[]
  every_min: number
  enabled: boolean
  last_run: string | null
  next_run: string | null
}
export type ScheduleInput = Omit<Schedule, 'id' | 'last_run' | 'next_run'>

export type Settings = {
  min_score: number
  max_drafts: number
  min_company_size: number
  keep_unknown_size: boolean
  models: { triage: string; score: string; draft: string }
  notify_enabled: boolean
  ntfy_topic: string
  gmail_enabled: boolean
  gmail_user: string
  gmail_has_password: boolean
}

export type Answer = { label: string; value: string }
export type Reply = {
  date: string
  from: string
  subject: string
  snippet: string
  signal?: 'ack' | 'assessment' | 'interview' | 'offer' | 'rejection'
  company: string | null
  application_id: number | null
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export const SESSION_ENDED = 'applydesk:session-ended'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, { credentials: 'same-origin', ...init })
  } catch {
    throw new ApiError(0, 'Could not reach Apply Desk. Is the server running?')
  }
  if (!res.ok) {
    let detail = res.statusText || `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      /* not JSON */
    }
    if (res.status === 401 && path !== '/api/login') window.dispatchEvent(new Event(SESSION_ENDED))
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  const type = res.headers.get('content-type') ?? ''
  return (type.includes('application/json') ? res.json() : res.text()) as Promise<T>
}

const send = <T>(method: string, path: string, body?: unknown) =>
  request<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

export const api = {
  login: (username: string, password: string) => send<{ username: string }>('POST', '/api/login', { username, password }),
  logout: () => send<void>('POST', '/api/logout'),
  me: () => request<{ username: string }>('/api/me'),

  applications: () => request<Application[]>('/api/applications'),
  setStatus: (a: Pick<Application, 'id' | 'company' | 'role'>, status: 'drafted' | 'applied' | 'skipped') =>
    send<Application>('POST', `/api/applications/${a.id}/status`, { company: a.company, role: a.role, status }),

  summary: () => request<Summary>('/api/summary'),
  answers: () => request<Answer[]>('/api/answers'),
  replies: () => request<Reply[]>('/api/replies'),

  runs: (limit = 50) => request<Run[]>(`/api/runs?limit=${limit}`),
  startRun: (body: { task: Task; url?: string; application_id?: number }) => send<Run>('POST', '/api/runs', body),
  cancelRun: (id: string) => send<Run>('POST', `/api/runs/${encodeURIComponent(id)}/cancel`),
  runLog: (id: string) => request<string>(`/api/runs/${encodeURIComponent(id)}/log`),
  runStreamUrl: (id: string) => `/api/runs/${encodeURIComponent(id)}/stream`,

  schedules: () => request<Schedule[]>('/api/schedules'),
  createSchedule: (s: ScheduleInput) => send<Schedule>('POST', '/api/schedules', s),
  updateSchedule: (id: string, s: ScheduleInput) => send<Schedule>('PUT', `/api/schedules/${encodeURIComponent(id)}`, s),
  deleteSchedule: (id: string) => send<void>('DELETE', `/api/schedules/${encodeURIComponent(id)}`),

  settings: () => request<Settings>('/api/settings'),
  saveSettings: (s: Settings & { gmail_app_password?: string }) => send<Settings>('PUT', '/api/settings', s),
  testNotify: () => send<{ ok: true }>('POST', '/api/settings/test-notify'),
}
