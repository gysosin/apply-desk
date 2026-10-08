import { ArrowCounterClockwise, ArrowUpRight, ArrowsClockwise, CalendarCheck, CheckSquareOffset, CircleNotch, EnvelopeSimple, Exam, MagnifyingGlass, Trophy, XCircle } from '@phosphor-icons/react'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { FileLink, FitBadge, Notes, safeFile, UnavailableLink } from '@/components/application-card'
import { CheckEmailButton } from '@/components/check-email'
import { EmptyState, PageHeader, Panel, QueryError, RunStatusBadge, Segmented } from '@/components/kit'
import { Button, buttonVariants } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import type { Application } from '@/lib/api'
import { day, relDay } from '@/lib/format'
import { isActive, useApplications, useRuns, useSetStatus, useStartRun } from '@/lib/queries'
import { cn } from '@/lib/utils'

const TABS = ['applied', 'interview', 'offer', 'rejected', 'skipped', 'needs_review'] as const
type Tab = (typeof TABS)[number]
// Tabs for rows that were sent; the Gmail check moves them forward from applied.
const SENT: readonly Tab[] = ['applied', 'interview', 'offer', 'rejected']
const TAB_LABEL: Record<Tab, string> = {
  applied: 'Applied', interview: 'Interview', offer: 'Offer', rejected: 'Rejected', skipped: 'Skipped', needs_review: 'Needs review',
}
const EMPTY: Record<Tab, string> = {
  applied: 'Nothing marked as applied yet. Use "Mark applied" on a Ready card after you submit.',
  interview: 'No interviews or assessments yet. The Gmail check moves a row here when one arrives.',
  offer: 'No offers yet.',
  rejected: 'No rejections recorded.',
  skipped: 'Nothing skipped. Roles you pass on from Ready land here.',
  needs_review: 'No drafts are waiting for review.',
}

// Interview-prep runs started in this tab, by application id, so leaving the page keeps the progress.
// ponytail: lost on reload; the server's run list has no application_id to rebuild it from.
const prepRuns = new Map<number, string>()

function InterviewPrep({ app }: { app: Application }) {
  const [runId, setRunId] = useState(() => prepRuns.get(app.id))
  const start = useStartRun()
  const runs = useRuns()
  const qc = useQueryClient()
  const run = runId ? runs.data?.find((r) => r.id === runId) : undefined
  const finished = run && !isActive(run)

  // When the run ends, reload the rows so interview_url shows up.
  useEffect(() => {
    if (finished) qc.invalidateQueries({ queryKey: ['applications'] })
  }, [finished, qc])

  if (app.interview_url) {
    const href = safeFile(app.interview_url)
    if (!href) return <UnavailableLink />
    return (
      <a href={href} target="_blank" rel="noreferrer" className={cn(buttonVariants({ variant: 'secondary', size: 'sm' }), 'h-8 px-3')}>
        <Exam aria-hidden /> Interview prep<ArrowUpRight aria-hidden /><span className="sr-only"> for {app.company} (opens in a new tab)</span>
      </a>
    )
  }
  const begin = () => start.mutate({ task: 'interview', application_id: app.id }, {
    onSuccess: (r) => { prepRuns.set(app.id, r.id); setRunId(r.id) },
  })
  if (run && run.status !== 'failed' && run.status !== 'cancelled') {
    return (
      <span className="inline-flex items-center gap-2" aria-live="polite">
        <RunStatusBadge status={run.status} />
        <Link to={`/runs/${run.id}`} className="text-xs font-medium text-primary underline-offset-4 hover:underline">
          View log
        </Link>
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-2">
      {run && <RunStatusBadge status={run.status} />}
      <Button variant="outline" size="sm" className="h-8 px-3" onClick={begin} disabled={start.isPending}>
        {start.isPending ? <CircleNotch className="animate-spin" /> : run ? <ArrowsClockwise aria-hidden /> : <Exam aria-hidden />}
        {run ? 'Try again' : 'Prepare interview'}
      </Button>
    </span>
  )
}

// What the employer's email said, as icon + word (never colour alone).
const SIGNAL: Record<string, { label: string; icon: typeof XCircle; className: string }> = {
  rejection: { label: 'Rejected', icon: XCircle, className: 'text-destructive bg-destructive/10' },
  offer: { label: 'Offer', icon: Trophy, className: 'text-success bg-success/10' },
  interview: { label: 'Interview', icon: CalendarCheck, className: 'text-primary bg-primary/10' },
  assessment: { label: 'Assessment', icon: Exam, className: 'text-warning bg-warning/10' },
  ack: { label: 'Received', icon: EnvelopeSimple, className: 'text-muted-foreground bg-muted' },
}

function Outcome({ outcome }: { outcome: NonNullable<Application['outcome']> }) {
  const s = SIGNAL[outcome.signal] ?? SIGNAL.ack
  return (
    <div className="mt-2.5 max-w-[70ch] rounded-xl border border-border/70 bg-foreground/[0.02] px-3.5 py-2.5">
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <span className={cn('inline-flex h-6 shrink-0 items-center gap-1 rounded-full pr-2.5 pl-1.5 text-xs font-medium', s.className)}>
          <s.icon className="size-3.5" weight="bold" aria-hidden />{s.label}
        </span>
        <span className="text-xs num text-muted-foreground">{day(outcome.date)} ({relDay(outcome.date)})</span>
      </div>
      {outcome.reason && <p className="mt-1.5 text-sm text-pretty">{outcome.reason}</p>}
      <p className="mt-1 truncate text-xs text-muted-foreground" title={outcome.subject}>Email: {outcome.subject}</p>
    </div>
  )
}

function Row({ app, tab }: { app: Application; tab: Tab }) {
  const { set } = useSetStatus()
  const sent = SENT.includes(tab)
  const when = sent && app.applied_on
    ? <>Applied {day(app.applied_on)} <span className="text-muted-foreground">({relDay(app.applied_on)})</span></>
    : <>{sent ? 'Added' : 'Drafted'} {day(app.date)}</>
  return (
    <li className="grid gap-3 px-5 py-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center lg:gap-6">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <h3 className="font-semibold tracking-tight">{app.company}</h3>
          <FitBadge fit={app.fit} />
        </div>
        <p className="mt-1 text-sm text-pretty">{app.role}</p>
        <p className="mt-1 text-xs num text-muted-foreground">{when}</p>
        {app.outcome && sent && <Outcome outcome={app.outcome} />}
        {!sent && <div className="mt-2 max-w-[70ch]"><Notes text={app.notes} /></div>}
      </div>
      <div className="flex flex-wrap items-center gap-2 lg:justify-end">
        <FileLink href={app.cv_url} label="CV" pdf />
        <FileLink href={app.cover_url} label="Cover letter" pdf />
        <FileLink href={app.posting_url} label="Posting" />
        {tab === 'rejected' ? null : SENT.includes(tab) ? <InterviewPrep app={app} /> : (
          <Button variant="secondary" size="sm" className="h-8 px-3" onClick={() => set(app, 'drafted')}>
            <ArrowCounterClockwise aria-hidden /> Move to Ready
          </Button>
        )}
      </div>
    </li>
  )
}

export function AppliedPage() {
  const [params, setParams] = useSearchParams()
  const tab = (TABS.find((t) => t === params.get('tab')) ?? 'applied') as Tab
  const q = params.get('q') ?? ''
  const setParam = (k: string, v: string, empty: string) => setParams((p) => {
    if (v === empty) p.delete(k); else p.set(k, v)
    return p
  }, { replace: true })

  const apps = useApplications()
  const all = apps.data ?? []
  const counts = Object.fromEntries(TABS.map((t) => [t, all.filter((a) => a.status === t).length])) as Record<Tab, number>
  const needle = q.trim().toLowerCase()
  const rows = all
    .filter((a) => a.status === tab && (!needle || `${a.company} ${a.role}`.toLowerCase().includes(needle)))
    .sort((a, b) => ((b.applied_on ?? b.date) > (a.applied_on ?? a.date) ? 1 : -1))

  return (
    <>
      <PageHeader title="Applied"
        description={apps.data
          ? `${SENT.reduce((n, t) => n + counts[t], 0)} sent: ${counts.applied} waiting, ${counts.interview} in interviews, ${counts.offer} ${counts.offer === 1 ? 'offer' : 'offers'}, ${counts.rejected} rejected. The Gmail check updates these from your email.`
          : 'Applications you have sent, skipped or need to review.'}
        actions={<CheckEmailButton />} />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Segmented label="Status" value={tab} onChange={(k) => setParam('tab', k, 'applied')}
          options={TABS.map((t) => ({
            key: t,
            label: <>{TAB_LABEL[t]}{apps.data && <span className="text-xs text-muted-foreground num">{counts[t]}</span>}</>,
          }))} />
        <div className="relative w-full sm:max-w-xs">
          <MagnifyingGlass className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input type="search" aria-label="Search company or role" placeholder="Search company or role"
            className="h-10 rounded-full bg-card pr-3.5 pl-10" value={q} onChange={(e) => setParam('q', e.target.value, '')} />
        </div>
      </div>

      <Panel flush>
        {apps.isPending ? (
          <div className="grid gap-3 p-5" aria-busy="true" aria-label="Loading">
            {Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
          </div>
        ) : apps.isError ? <QueryError error={apps.error} onRetry={() => apps.refetch()} /> : rows.length === 0 ? (
          <EmptyState icon={needle ? MagnifyingGlass : CheckSquareOffset}
            title={needle ? `No ${TAB_LABEL[tab].toLowerCase()} row matches "${q}"` : `Nothing in ${TAB_LABEL[tab]}`}
            body={needle ? 'Try the company name only.' : EMPTY[tab]} />
        ) : (
          <ul className="divide-y divide-foreground/[0.06]">
            {rows.map((a) => <Row key={a.id} app={a} tab={tab} />)}
          </ul>
        )}
      </Panel>
    </>
  )
}
