// Query hooks shared by more than one page.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { ApiError, api, type Application, type Run, type Task } from '@/lib/api'

export const isActive = (r: Run) => r.status === 'queued' || r.status === 'running'

export function useApplications() {
  return useQuery({ queryKey: ['applications'], queryFn: api.applications, refetchInterval: 60_000 })
}

/** Runs poll every 3s while one is queued or running, else every 30s. */
export function useRuns() {
  return useQuery({
    queryKey: ['runs'],
    queryFn: () => api.runs(50),
    refetchInterval: (q) => (q.state.data?.some(isActive) ? 3_000 : 30_000),
  })
}

export const TASK_LABEL: Record<Task, string> = {
  daily_run: 'Daily search',
  gmail_check: 'Gmail check',
  why_roles: 'Why-this-role answers',
  deadline_alert: 'Deadline alert',
  draft_url: 'Draft from URL',
  interview: 'Interview prep',
}

/** Starts a run. A 409 (the same task is already queued or running) toasts with a link to the runs page. */
export function useStartRun() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: api.startRun,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['runs'] }),
    onError: (e, v) => {
      if (e instanceof ApiError && e.status === 409) {
        toast.warning(`${TASK_LABEL[v.task]} is already queued or running`, {
          action: { label: 'See runs', onClick: () => navigate('/runs') },
        })
      } else if (!(e instanceof ApiError && e.status === 401)) {
        toast.error(e.message)
      }
    },
  })
}

type Target = 'drafted' | 'applied' | 'skipped'
const VERB: Record<Target, string> = { applied: 'Marked as applied', skipped: 'Skipped', drafted: 'Moved back to Ready' }

/** Changes a tracker row's status optimistically, then toasts with Undo (back to 'drafted').
 *  The toast lives in the mutation's own onSuccess: the card that started it has usually unmounted
 *  by then (the optimistic update moved it off the list), and per-call callbacks would be skipped. */
export function useSetStatus() {
  const qc = useQueryClient()
  const m = useMutation({
    mutationFn: ({ app, status }: { app: Application; status: Target }) => api.setStatus(app, status),
    onMutate: async ({ app, status }) => {
      await qc.cancelQueries({ queryKey: ['applications'] })
      const prev = qc.getQueryData<Application[]>(['applications'])
      qc.setQueryData<Application[]>(['applications'], (rows) =>
        rows?.map((r) => (r.id === app.id ? { ...r, status } : r)))
      return { prev }
    },
    onSuccess: (_row, { app, status }) => {
      toast.success(`${VERB[status]}: ${app.company}`, {
        description: app.role,
        action: status === 'drafted' ? undefined : {
          label: 'Undo',
          onClick: () => m.mutate({ app: { ...app, status }, status: 'drafted' }),
        },
      })
    },
    onError: (e, _v, ctx) => {
      qc.setQueryData(['applications'], ctx?.prev)
      if (e instanceof ApiError && e.status === 409) toast.error('The tracker changed on disk, so the list was reloaded. Try again.')
      else if (!(e instanceof ApiError && e.status === 401)) toast.error(e.message)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['applications'] })
      qc.invalidateQueries({ queryKey: ['summary'] })
    },
  })
  return { set: (app: Application, status: Target) => m.mutate({ app, status }), pending: m.isPending }
}

/** Ready rows first by deadline (none last), then by fit, best first. */
export function byDeadlineThenFit(a: Application, b: Application) {
  if (a.deadline !== b.deadline) {
    if (!a.deadline) return 1
    if (!b.deadline) return -1
    return a.deadline < b.deadline ? -1 : 1
  }
  return (b.fit ?? -1) - (a.fit ?? -1)
}
