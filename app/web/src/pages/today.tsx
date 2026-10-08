import {
  ArrowRight,
  CircleNotch,
  Clock,
  EnvelopeSimple,
  Hourglass,
  MagnifyingGlass,
  PaperPlaneTilt,
  Play,
  Tray,
  UserFocus,
  XCircle,
  type Icon,
} from '@phosphor-icons/react'
import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useAuth } from '@/app/auth'
import { ApplicationCard } from '@/components/application-card'
import { CardSkeletons, EmptyState, Panel, PageHeader, QueryError, StatTile } from '@/components/kit'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'
import { ago, count, dateTime, daysUntil } from '@/lib/format'
import { byDeadlineThenFit, useApplications, useStartRun } from '@/lib/queries'

// ECharts is most of the bundle and only this page needs it.
const AppliedChart = lazy(() => import('@/components/applied-chart').then((m) => ({ default: m.AppliedChart })))

function greeting() {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

function AttentionRow({ icon: IconCmp, tone, to, children }: { icon: Icon; tone: string; to: string; children: ReactNode }) {
  return (
    <li>
      <Link to={to}
        className="group flex items-start gap-3 rounded-xl px-3 py-2.5 outline-none transition-colors duration-300 ease-spring hover:bg-foreground/[0.04] focus-visible:ring-3 focus-visible:ring-ring/50">
        <IconCmp className={`mt-0.5 size-4.5 shrink-0 ${tone}`} weight="bold" aria-hidden />
        <span className="min-w-0 flex-1 text-sm [overflow-wrap:anywhere]">{children}</span>
        <ArrowRight className="mt-1 size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" aria-hidden />
      </Link>
    </li>
  )
}

export function TodayPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const summary = useQuery({ queryKey: ['summary'], queryFn: api.summary, refetchInterval: 60_000 })
  const replies = useQuery({ queryKey: ['replies'], queryFn: api.replies, staleTime: 5 * 60_000 })
  const apps = useApplications()
  const start = useStartRun()
  const s = summary.data

  const ready = (apps.data ?? []).filter((a) => a.status === 'drafted').sort(byDeadlineThenFit)
  const closingThisWeek = ready.filter((a) => a.deadline != null && daysUntil(a.deadline) >= 0 && daysUntil(a.deadline) <= 7).length
  const failedRun = s?.last_run?.status === 'failed' ? s.last_run : null
  const recentReplies = (replies.data ?? []).slice(0, 3)
  const attentionCount = (s?.closing_soon.length ?? 0) + (s?.needs_review ? 1 : 0) + recentReplies.length + (failedRun ? 1 : 0)

  const runNow = () => start.mutate({ task: 'daily_run' }, {
    onSuccess: (r) => toast.success('Daily search queued', {
      description: 'Scrape, score and draft. Usually takes a few minutes.',
      action: { label: 'Watch log', onClick: () => navigate(`/runs/${r.id}`) },
    }),
  })

  const date = new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <>
      <PageHeader
        title={`${greeting()}, ${user?.username ?? 'there'}`}
        description={
          s ? <>{date}. {count(s.ready, 'application')} ready{closingThisWeek ? <>, {closingThisWeek} closing this week</> : null}.</> : date
        }
        actions={
          <Button className="h-10 px-4" onClick={runNow} disabled={start.isPending}>
            {start.isPending ? <CircleNotch className="animate-spin" /> : <Play weight="fill" />}
            Run daily search now
          </Button>
        }
      />

      {summary.isError ? (
        <Panel><QueryError error={summary.error} onRetry={() => summary.refetch()} /></Panel>
      ) : !s ? (
        <div className="grid gap-3 lg:grid-cols-5" aria-busy="true" aria-label="Loading">
          <Skeleton className="h-56 rounded-[1.25rem] lg:col-span-2" />
          <Skeleton className="h-56 rounded-[1.25rem] lg:col-span-3" />
        </div>
      ) : (
        <>
          {attentionCount > 0 && (
            <Panel title={<span className="inline-flex items-center gap-2">Needs attention
              <span className="rounded-full bg-warning/12 px-2 py-0.5 text-xs font-medium text-warning num">{attentionCount}</span></span>}>
              <ul className="-mx-3 -mt-1 grid grid-cols-1 gap-x-4 md:grid-cols-2">
                {s.closing_soon.map((c) => (
                  <AttentionRow key={c.id} icon={Hourglass} tone="text-warning" to={`/ready?q=${encodeURIComponent(c.company)}`}>
                    <span className="font-medium">{c.company}</span> closes {c.days_left === 0 ? 'today' : c.days_left === 1 ? 'tomorrow' : `in ${c.days_left} days`}
                    <span className="block truncate text-xs text-muted-foreground">{c.role}</span>
                  </AttentionRow>
                ))}
                {s.needs_review > 0 && (
                  <AttentionRow icon={UserFocus} tone="text-warning" to="/applied?tab=needs_review">
                    <span className="font-medium">{count(s.needs_review, 'draft')}</span> {s.needs_review === 1 ? 'needs' : 'need'} your review
                    <span className="block text-xs text-muted-foreground">Flagged by the pipeline before sending</span>
                  </AttentionRow>
                )}
                {recentReplies.map((r) => (
                  <AttentionRow key={`${r.date}${r.subject}`} icon={EnvelopeSimple} tone="text-primary"
                    to={r.application_id != null && r.company ? `/applied?q=${encodeURIComponent(r.company)}` : '/applied'}>
                    <span className="font-medium">{r.company ?? r.from}</span> {r.signal ? `(${r.signal})` : 'replied'}: {r.subject}
                    <span className="block truncate text-xs text-muted-foreground">{ago(r.date)}, {r.snippet}</span>
                  </AttentionRow>
                ))}
                {failedRun && (
                  <AttentionRow icon={XCircle} tone="text-destructive" to={`/runs/${failedRun.id}`}>
                    <span className="font-medium">{failedRun.label} failed</span> {ago(failedRun.finished ?? failedRun.created)}
                    <span className="block truncate text-xs text-muted-foreground">{failedRun.error ?? 'Open the log to see why.'}</span>
                  </AttentionRow>
                )}
              </ul>
            </Panel>
          )}

          <div className="grid gap-3 lg:grid-cols-5">
            <Panel className="lg:col-span-2">
              <div className="grid grid-cols-2 gap-x-6 gap-y-7 py-1">
                <StatTile icon={Tray} label="Ready" value={s.ready}
                  hint={s.closing_soon.length ? `${s.closing_soon.length} closing within 3 days` : 'None closing within 3 days'} />
                <StatTile icon={PaperPlaneTilt} label="Applied this week" value={s.applied_this_week} hint={`${s.applied} in total`} />
                <StatTile icon={EnvelopeSimple} label="Replies" value={s.replies} hint="From Gmail" />
                <StatTile icon={Clock} label="Next run" value={s.next_run ? ago(s.next_run.at) : 'None'}
                  hint={s.next_run ? <span title={dateTime(s.next_run.at)}>{s.next_run.name}, {dateTime(s.next_run.at)}</span>
                    : <Link className="underline underline-offset-4" to="/schedules">Add a schedule</Link>} />
              </div>
            </Panel>
            <Panel className="lg:col-span-3" title="Sent per week" description="Applications marked applied, last 8 weeks">
              <Suspense fallback={<Skeleton className="h-48 rounded-2xl" />}><AppliedChart weeks={s.applied_by_week} /></Suspense>
            </Panel>
          </div>
        </>
      )}

      <section aria-labelledby="ready-heading" className="grid gap-3">
        <div className="flex items-end justify-between gap-3">
          <h2 id="ready-heading" className="text-lg font-semibold tracking-tight">Ready to send</h2>
          {ready.length > 6 && (
            <Link to="/ready" className="inline-flex items-center gap-1 rounded-md text-sm font-medium text-primary underline-offset-4 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50">
              All {ready.length} ready <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          )}
        </div>
        {apps.isPending ? <CardSkeletons n={3} /> : apps.isError ? (
          <Panel><QueryError error={apps.error} onRetry={() => apps.refetch()} /></Panel>
        ) : ready.length === 0 ? (
          <Panel>
            <EmptyState icon={MagnifyingGlass} title="Nothing ready yet"
              body="The daily search drafts a CV and cover letter for every role that clears your score bar. Start it above or wait for the schedule." />
          </Panel>
        ) : (
          <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
            {ready.slice(0, 6).map((a) => <ApplicationCard key={a.id} app={a} />)}
          </div>
        )}
      </section>
    </>
  )
}

