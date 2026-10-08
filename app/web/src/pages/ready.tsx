import { MagnifyingGlass, Tray, X } from '@phosphor-icons/react'
import { useSearchParams } from 'react-router-dom'
import { ApplicationCard } from '@/components/application-card'
import { CheckEmailButton } from '@/components/check-email'
import { CardSkeletons, EmptyState, PageHeader, Panel, QueryError, Segmented } from '@/components/kit'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { count, daysUntil } from '@/lib/format'
import { byDeadlineThenFit, useApplications } from '@/lib/queries'

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'urgent', label: 'Closing in 3 days' },
  { key: 'strong', label: 'Strong fit' },
] as const
type Filter = (typeof FILTERS)[number]['key']

const within = (deadline: string | null, days: number) => deadline != null && daysUntil(deadline) >= 0 && daysUntil(deadline) <= days

export function ReadyPage() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const filter = (FILTERS.find((f) => f.key === params.get('show'))?.key ?? 'all') as Filter
  const setParam = (k: string, v: string, empty: string) => setParams((p) => {
    if (v === empty) p.delete(k); else p.set(k, v)
    return p
  }, { replace: true })

  const apps = useApplications()
  const ready = (apps.data ?? []).filter((a) => a.status === 'drafted').sort(byDeadlineThenFit)
  const needle = q.trim().toLowerCase()
  const shown = ready.filter((a) =>
    (!needle || `${a.company} ${a.role} ${a.notes}`.toLowerCase().includes(needle)) &&
    (filter === 'all' || (filter === 'urgent' ? within(a.deadline, 3) : (a.fit ?? 0) >= 75)))
  const closingWeek = ready.filter((a) => within(a.deadline, 7)).length

  return (
    <>
      <PageHeader
        title="Ready"
        description={apps.data
          ? `${count(ready.length, 'application')} ready · ${closingWeek} closing this week. Soonest deadline first, then best fit.`
          : 'Drafted applications waiting for you to send.'}
        actions={<CheckEmailButton />}
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative w-full sm:max-w-xs">
          <MagnifyingGlass className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input type="search" aria-label="Search company, role or notes" placeholder="Search company, role or notes"
            className="h-10 rounded-full bg-card pr-3.5 pl-10" value={q} onChange={(e) => setParam('q', e.target.value, '')} />
        </div>
        <Segmented label="Show" value={filter} options={FILTERS} onChange={(k) => setParam('show', k, 'all')} />
      </div>

      {apps.isPending ? <CardSkeletons n={4} /> : apps.isError ? (
        <Panel><QueryError error={apps.error} onRetry={() => apps.refetch()} /></Panel>
      ) : ready.length === 0 ? (
        <Panel>
          <EmptyState icon={Tray} title="Nothing waiting to be sent"
            body="New drafts land here after each daily search. Everything you have sent or skipped is on the Applied page." />
        </Panel>
      ) : shown.length === 0 ? (
        <Panel>
          <EmptyState icon={MagnifyingGlass} title="No ready application matches"
            body={`${count(ready.length, 'application')} ready, none with these filters.`}
            action={<Button variant="outline" onClick={() => setParams({}, { replace: true })}><X /> Clear filters</Button>} />
        </Panel>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
          {shown.map((a) => <ApplicationCard key={a.id} app={a} />)}
        </div>
      )}
    </>
  )
}
