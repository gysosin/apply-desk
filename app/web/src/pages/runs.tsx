import {
  ArrowLeft,
  CalendarDots,
  ChatText,
  CircleNotch,
  EnvelopeSimple,
  Hand,
  Hourglass,
  Pause,
  Play,
  Prohibit,
  Terminal,
} from '@phosphor-icons/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Callout, ConfirmDialog, EmptyState, PageHeader, Panel, QueryError, RunStatusBadge } from '@/components/kit'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { api, type Run, type Task } from '@/lib/api'
import { ago, dateTime, duration } from '@/lib/format'
import { isActive, TASK_LABEL, useRuns, useStartRun } from '@/lib/queries'
import { cn } from '@/lib/utils'

function took(r: Run) {
  if (!r.started) return '-'
  const end = r.finished ? new Date(r.finished).getTime() : Date.now()
  return duration((end - new Date(r.started).getTime()) / 1000)
}

function Trigger({ trigger }: { trigger: Run['trigger'] }) {
  const IconCmp = trigger === 'schedule' ? CalendarDots : Hand
  return (
    <span className="inline-flex items-center gap-1.5 text-muted-foreground">
      <IconCmp className="size-4" aria-hidden />{trigger === 'schedule' ? 'Schedule' : 'Manual'}
    </span>
  )
}

const RUN_NOW: { task: Task; label: string; icon: typeof Play }[] = [
  { task: 'daily_run', label: 'Daily search', icon: Play },
  { task: 'gmail_check', label: 'Gmail check', icon: EnvelopeSimple },
  { task: 'deadline_alert', label: 'Deadline alert', icon: Hourglass },
  { task: 'why_roles', label: 'Why-this-role answers', icon: ChatText },
]

export function RunsPage() {
  const runs = useRuns()
  const start = useStartRun()
  const navigate = useNavigate()
  const active = runs.data?.filter(isActive).length ?? 0

  return (
    <>
      <PageHeader title="Runs"
        description={runs.data ? `Last ${runs.data.length} runs, newest first.${active ? ` ${active} in progress.` : ''}` : 'Every search, check and draft the app has run.'}
        actions={RUN_NOW.map((r, i) => (
          <Button key={r.task} variant={i === 0 ? 'default' : 'outline'} className="h-9 px-3.5"
            disabled={start.isPending && start.variables?.task === r.task}
            onClick={() => start.mutate({ task: r.task }, { onSuccess: (run) => navigate(`/runs/${run.id}`) })}>
            {start.isPending && start.variables?.task === r.task ? <CircleNotch className="animate-spin" /> : <r.icon weight={i === 0 ? 'fill' : 'regular'} />}
            {r.label}
          </Button>
        ))}
      />
      <Panel flush>
        {runs.isPending ? (
          <div className="grid gap-2 p-5" aria-busy="true" aria-label="Loading">
            {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-11 rounded-xl" />)}
          </div>
        ) : runs.isError ? <QueryError error={runs.error} onRetry={() => runs.refetch()} /> : runs.data.length === 0 ? (
          <EmptyState icon={Terminal} title="No runs yet" body="Start a daily search above, or add a schedule so it runs every morning." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-b border-foreground/[0.06] text-left text-xs text-muted-foreground [&>th]:px-5 [&>th]:py-3 [&>th]:font-medium">
                  <th>Task</th><th>Status</th><th>Trigger</th><th>Started</th><th className="text-right">Took</th><th>Summary</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-foreground/[0.05]">
                {runs.data.map((r) => (
                  <tr key={r.id} className="transition-colors hover:bg-foreground/[0.025] [&>td]:px-5 [&>td]:py-3">
                    <td className="max-w-72">
                      <Link to={`/runs/${r.id}`} className="block truncate font-medium underline-offset-4 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50 rounded-sm" title={r.label}>
                        {r.label || TASK_LABEL[r.task]}
                      </Link>
                    </td>
                    <td><RunStatusBadge status={r.status} /></td>
                    <td><Trigger trigger={r.trigger} /></td>
                    <td className="whitespace-nowrap num" title={dateTime(r.started ?? r.created)}>
                      {r.started ? ago(r.started) : <span className="text-muted-foreground">queued {ago(r.created)}</span>}
                    </td>
                    <td className="text-right whitespace-nowrap num">{took(r)}</td>
                    <td className="max-w-96 truncate text-muted-foreground" title={r.error ?? r.summary ?? undefined}>
                      {r.status === 'failed' && r.error ? <span className="text-destructive">{r.error}</span> : r.summary ?? '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  )
}

/** Streams a live run's log; a finished run (or a dropped stream) loads the whole log once. */
function useRunLog(id: string, live: boolean | undefined) {
  const [lines, setLines] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const qc = useQueryClient()
  useEffect(() => {
    if (live === undefined) return
    setLines([])
    setError(null)
    let closed = false
    const loadAll = () => api.runLog(id)
      .then((t) => !closed && setLines(t ? t.replace(/\n$/, '').split('\n') : []))
      .catch((e: Error) => !closed && setError(e.message))
    if (!live) {
      loadAll()
      return () => { closed = true }
    }
    const es = new EventSource(api.runStreamUrl(id), { withCredentials: true })
    let got = 0
    es.onmessage = (e) => { got++; setLines((l) => [...l, e.data]) }
    es.addEventListener('end', () => {
      es.close()
      for (const key of ['runs', 'applications', 'summary']) qc.invalidateQueries({ queryKey: [key] })
      if (!got) loadAll()
    })
    // A dropped connection (or a 401) would make EventSource replay from the start: load the full log instead.
    es.onerror = () => { es.close(); loadAll() }
    return () => { closed = true; es.close() }
  }, [id, live, qc])
  return { lines, error }
}

export function RunPage() {
  const { id = '' } = useParams()
  const runs = useRuns()
  const run = runs.data?.find((r) => r.id === id)
  // Decide stream-or-fetch once, when the run list first arrives, so a run finishing mid-stream keeps its lines.
  const [live, setLive] = useState<boolean>()
  useEffect(() => {
    if (live === undefined && runs.data) setLive(run ? isActive(run) : false)
  }, [runs.data, run, live])
  const { lines, error } = useRunLog(id, live)
  const [paused, setPaused] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const logRef = useRef<HTMLDivElement>(null)
  const qc = useQueryClient()

  useEffect(() => {
    const el = logRef.current
    if (el && !paused) el.scrollTop = el.scrollHeight
  }, [lines.length, paused])

  const cancel = useMutation({
    mutationFn: () => api.cancelRun(id),
    onSettled: () => { setConfirm(false); qc.invalidateQueries({ queryKey: ['runs'] }) },
  })

  const back = (
    <Link to="/runs" className="inline-flex items-center gap-1.5 rounded-md text-sm text-muted-foreground outline-none hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50">
      <ArrowLeft className="size-4" aria-hidden /> All runs
    </Link>
  )

  return (
    <>
      <div className="grid gap-3">
        {back}
        <PageHeader
          title={run ? (run.label || TASK_LABEL[run.task]) : runs.isPending ? <Skeleton className="h-8 w-64" /> : 'Run log'}
          actions={run && isActive(run) && (
            <Button variant="destructive" className="h-9 px-3.5" onClick={() => setConfirm(true)}>
              <Prohibit /> Cancel run
            </Button>
          )}>
          {run && (
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
              <RunStatusBadge status={run.status} />
              <Trigger trigger={run.trigger} />
              <span className="num text-muted-foreground" title={dateTime(run.started ?? run.created)}>
                {run.started ? `Started ${dateTime(run.started)}` : `Queued ${ago(run.created)}`}
              </span>
              {run.started && <span className="num text-muted-foreground">Took {took(run)}</span>}
            </div>
          )}
          {!run && runs.data && <p className="mt-1.5 text-sm text-muted-foreground">This run is older than the last 50, so only its log is shown.</p>}
        </PageHeader>
      </div>

      {run?.status === 'failed' && <Callout tone="destructive" title="This run failed">{run.error ?? 'The log below says where it stopped.'}</Callout>}
      {run?.summary && run.status !== 'failed' && <Callout tone="info" title={run.summary} />}

      <Panel flush title="Log"
        description={live ? (run && isActive(run) ? 'Streaming live' : 'Stream ended') : 'Full log'}
        actions={
          <Button variant="outline" size="sm" className="h-8 px-3" aria-pressed={paused} onClick={() => setPaused(!paused)}>
            {paused ? <Play /> : <Pause />}{paused ? 'Resume auto-scroll' : 'Pause auto-scroll'}
          </Button>
        }>
        <div ref={logRef} role="log" aria-live="off" aria-label="Run log" tabIndex={0}
          className="mx-1 mb-1 h-[min(62dvh,40rem)] overflow-auto rounded-[0.9rem] bg-foreground/[0.035] p-4 font-mono text-[0.78rem] leading-relaxed outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
          {error ? (
            <p className="text-destructive">Could not load the log: {error}</p>
          ) : lines.length === 0 ? (
            <p className="text-muted-foreground">{live === undefined || (run && isActive(run)) ? 'Waiting for the first log line...' : 'This run wrote no log.'}</p>
          ) : (
            lines.map((l, i) => (
              <div key={i} className={cn('flex gap-4 whitespace-pre-wrap break-all', /error|traceback|failed/i.test(l) && 'text-destructive')}>
                <span aria-hidden className="w-8 shrink-0 text-right text-muted-foreground/60 select-none num">{i + 1}</span>
                <span className="min-w-0">{l}</span>
              </div>
            ))
          )}
        </div>
      </Panel>

      <ConfirmDialog open={confirm} onOpenChange={setConfirm} title="Cancel this run?"
        body={run?.status === 'running' ? 'It is already running, so it stops at its next step. Drafts already written stay.' : 'It has not started yet, so nothing is lost.'}
        confirmLabel="Cancel run" cancelLabel="Let it run" destructive pending={cancel.isPending} onConfirm={() => cancel.mutate()} />
      {cancel.isError && <Callout tone="destructive" title="Could not cancel">{cancel.error.message}</Callout>}
    </>
  )
}
