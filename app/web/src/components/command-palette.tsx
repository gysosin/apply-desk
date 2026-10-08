/* ⌘K: run the daily search, draft from a URL, jump to a page or to an application by company. */
import { Buildings, LinkSimple, MagnifyingGlass, Play, type Icon } from '@phosphor-icons/react'
import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { NAV } from '@/app/shell'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { useApplications, useStartRun } from '@/lib/queries'
import { cn } from '@/lib/utils'

type Item = { id: string; group: string; label: string; hint?: string; icon: Icon; run: () => void }

const STATUS_WORD: Record<string, string> = { drafted: 'Ready', applied: 'Applied', skipped: 'Skipped', needs_review: 'Needs review', interview: 'Interview', offer: 'Offer', rejected: 'Rejected' }

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [q, setQ] = useState('')
  const [active, setActive] = useState(0)
  const navigate = useNavigate()
  const apps = useApplications()
  const start = useStartRun()

  const close = () => {
    onOpenChange(false)
    setQ('')
    setActive(0)
  }
  const go = (to: string) => () => navigate(to)

  const items = useMemo(() => {
    const needle = q.trim().toLowerCase()
    const match = (s: string) => !needle || s.toLowerCase().includes(needle)
    const actions: Item[] = [
      {
        id: 'run', group: 'Actions', label: 'Run daily search now', icon: Play,
        run: () => start.mutate({ task: 'daily_run' }, {
          onSuccess: (r) => toast.success('Daily search queued', { action: { label: 'Watch log', onClick: () => navigate(`/runs/${r.id}`) } }),
        }),
      },
      { id: 'draft', group: 'Actions', label: 'Draft from a job URL', icon: LinkSimple, run: go('/draft') },
    ]
    const pages: Item[] = NAV.map((n) => ({ id: `page:${n.to}`, group: 'Go to', label: n.label, icon: n.icon, run: go(n.to) }))
    const rows: Item[] = needle
      ? (apps.data ?? []).filter((a) => match(`${a.company} ${a.role}`)).slice(0, 8).map((a) => {
        const params = new URLSearchParams({ q: a.company })
        if (a.status !== 'drafted' && a.status !== 'applied') params.set('tab', a.status)
        return {
          id: `app:${a.id}`, group: 'Applications', label: a.company, icon: Buildings,
          hint: `${a.role}, ${STATUS_WORD[a.status] ?? a.status}`,
          run: go(`${a.status === 'drafted' ? '/ready' : '/applied'}?${params}`),
        }
      })
      : []
    return [...actions.filter((i) => match(i.label)), ...pages.filter((i) => match(i.label)), ...rows]
  }, [q, apps.data])

  const pick = (i: Item | undefined) => {
    if (!i) return
    close()
    i.run()
  }
  const sel = Math.min(active, Math.max(items.length - 1, 0))

  return (
    <Dialog open={open} onOpenChange={(o) => (o ? onOpenChange(true) : close())}>
      <DialogContent showCloseButton={false} className="top-[14%] translate-y-0 gap-0 overflow-hidden p-0 sm:max-w-lg">
        <DialogTitle className="sr-only">Search or jump</DialogTitle>
        <div className="flex items-center gap-2.5 border-b px-4">
          <MagnifyingGlass className="size-4.5 shrink-0 text-muted-foreground" aria-hidden />
          <input
            autoFocus
            role="combobox"
            aria-expanded
            aria-controls="palette-list"
            aria-activedescendant={items[sel] ? `palette-${items[sel].id}` : undefined}
            aria-label="Search pages, actions and companies"
            placeholder="Search pages, actions, companies"
            className="h-13 w-full bg-transparent text-[0.95rem] outline-none placeholder:text-muted-foreground"
            value={q}
            onChange={(e) => { setQ(e.target.value); setActive(0) }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') { e.preventDefault(); setActive((sel + 1) % Math.max(items.length, 1)) }
              if (e.key === 'ArrowUp') { e.preventDefault(); setActive((sel - 1 + items.length) % Math.max(items.length, 1)) }
              if (e.key === 'Enter') { e.preventDefault(); pick(items[sel]) }
            }}
          />
        </div>
        <ul id="palette-list" role="listbox" aria-label="Results" className="max-h-[min(60dvh,26rem)] overflow-y-auto p-2">
          {items.length === 0 && (
            <li className="px-3 py-8 text-center text-sm text-muted-foreground">No page, action or company matches "{q}".</li>
          )}
          {items.map((i, n) => (
            <li key={i.id} role="presentation">
              {(n === 0 || items[n - 1].group !== i.group) && (
                <p className="px-3 pt-2 pb-1 text-xs font-medium text-muted-foreground">{i.group}</p>
              )}
              <div id={`palette-${i.id}`} role="option" aria-selected={n === sel}
                onMouseMove={() => setActive(n)} onClick={() => pick(i)}
                className={cn('flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2 text-sm', n === sel && 'bg-foreground/[0.06]')}>
                <i.icon className={cn('size-4.5 shrink-0 text-muted-foreground', n === sel && 'text-brand')} aria-hidden />
                <span className="min-w-0 flex-1 truncate">
                  {i.label}
                  {i.hint && <span className="ml-2 text-muted-foreground">{i.hint}</span>}
                </span>
              </div>
            </li>
          ))}
        </ul>
        <p className="flex gap-4 border-t px-4 py-2 text-xs text-muted-foreground">
          <span><kbd className="font-mono">↑↓</kbd> to move</span>
          <span><kbd className="font-mono">Enter</kbd> to open</span>
          <span><kbd className="font-mono">Esc</kbd> to close</span>
        </p>
      </DialogContent>
    </Dialog>
  )
}
