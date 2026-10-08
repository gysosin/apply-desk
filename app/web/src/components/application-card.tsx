/* A drafted application: fit, deadline, notes, the files, and the two decisions. */
import {
  ArrowUpRight,
  CalendarBlank,
  CheckCircle,
  Copy,
  FilePdf,
  FileText,
  Hourglass,
  SkipForward,
  WarningCircle,
} from '@phosphor-icons/react'
import { useLayoutEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { ConfirmDialog } from '@/components/kit'
import { Button, buttonVariants } from '@/components/ui/button'
import type { Application } from '@/lib/api'
import { day, daysUntil } from '@/lib/format'
import { useSetStatus } from '@/lib/queries'
import { cn } from '@/lib/utils'

export function fitBand(fit: number | null): string {
  if (fit == null) return 'Not scored'
  if (fit >= 75) return 'Strong'
  if (fit >= 60) return 'Good'
  return 'Below bar'
}

export function FitBadge({ fit }: { fit: number | null }) {
  const strong = fit != null && fit >= 75
  return (
    <span className={cn('inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full pr-2.5 pl-1 text-xs font-medium',
      strong ? 'bg-primary/10 text-primary' : 'bg-foreground/[0.05] text-muted-foreground')}
      title={fit == null ? 'No fit score' : `Fit ${fit} out of 100`}>
      <span className={cn('grid h-5 min-w-7 place-items-center rounded-full px-1.5 text-[0.72rem] font-semibold num',
        strong ? 'bg-primary text-primary-foreground' : 'bg-foreground/[0.08] text-foreground')}>
        {fit ?? '-'}
      </span>
      {fitBand(fit)}
      <span className="sr-only"> fit</span>
    </span>
  )
}

export function DeadlineChip({ deadline }: { deadline: string | null }) {
  if (!deadline) return <span className="text-xs text-muted-foreground">No deadline listed</span>
  const d = daysUntil(deadline)
  const base = 'inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full px-2.5 text-xs font-medium whitespace-nowrap'
  if (d < 0) {
    return <span className={cn(base, 'bg-destructive/10 text-destructive')}><WarningCircle className="size-3.5" weight="bold" aria-hidden />Closed {day(deadline)}</span>
  }
  if (d <= 3) {
    const when = d === 0 ? 'Closes today' : d === 1 ? 'Closes tomorrow' : `Closes in ${d} days`
    return <span className={cn(base, 'bg-warning/12 text-warning')} title={day(deadline)}><Hourglass className="size-3.5" weight="bold" aria-hidden />{when}</span>
  }
  return <span className={cn(base, 'text-muted-foreground')}><CalendarBlank className="size-3.5" aria-hidden />Closes {day(deadline)}</span>
}

/** Free text clamped to three lines; "more" only shows when it actually overflows. */
export function Notes({ text }: { text: string }) {
  const ref = useRef<HTMLParagraphElement>(null)
  const [open, setOpen] = useState(false)
  const [overflows, setOverflows] = useState(false)
  useLayoutEffect(() => {
    const el = ref.current
    if (el && !open) setOverflows(el.scrollHeight > el.clientHeight + 1)
  }, [text, open])
  if (!text.trim()) return <p className="text-sm text-muted-foreground">No notes for this one.</p>
  return (
    <div>
      <p ref={ref} className={cn('text-sm leading-relaxed text-pretty whitespace-pre-line text-muted-foreground', !open && 'line-clamp-3')}>{text}</p>
      {(overflows || open) && (
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
          className="mt-1 rounded-md text-xs font-medium text-foreground underline-offset-4 outline-none hover:underline focus-visible:ring-3 focus-visible:ring-ring/50">
          {open ? 'less' : 'more'}
        </button>
      )}
    </div>
  )
}

// Hrefs come from tracker data: only http(s) links go to employers, only /files/ paths to our files.
export const safeHttp = (u: string | null | undefined) => (u && /^https?:\/\//i.test(u) ? u : null)
export const safeFile = (u: string | null | undefined) => (u && u.startsWith('/files/') ? u : null)

/** A link that failed the checks above: a disabled button, so the row still says something is missing. */
export function UnavailableLink({ className }: { className?: string }) {
  return <Button variant="outline" size="sm" disabled className={cn('h-8 px-3', className)}>Link unavailable</Button>
}

/** Opens a generated file (/files/...) in a new tab. Hidden when the file does not exist. */
export function FileLink({ href, label, pdf }: { href: string | null; label: string; pdf?: boolean }) {
  if (!href) return null
  if (!safeFile(href)) return <UnavailableLink />
  const IconCmp = pdf ? FilePdf : FileText
  return (
    <a href={href} target="_blank" rel="noreferrer" className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), 'h-8 px-3')}>
      <IconCmp aria-hidden />{label}<span className="sr-only"> (opens in a new tab)</span>
    </a>
  )
}

/** The drafted "Why this role?" answer, folded by default, with a copy button for the application form. */
function WhyRole({ text }: { text: string }) {
  const copy = () => navigator.clipboard.writeText(text).then(
    () => toast.success('"Why this role?" answer copied'),
    () => toast.error('Could not copy. Select the text and copy it by hand.'),
  )
  return (
    <details className="group rounded-xl border border-border/70 bg-foreground/[0.02] px-3.5 py-2.5">
      <summary className="cursor-pointer text-sm font-medium select-none">Why this role? <span className="font-normal text-muted-foreground">(form answer)</span></summary>
      <p className="mt-2 text-sm text-pretty whitespace-pre-line">{text}</p>
      <Button variant="secondary" size="sm" className="mt-2.5 h-8 px-3" onClick={copy}>
        <Copy aria-hidden /> Copy answer
      </Button>
    </details>
  )
}

export function ApplicationCard({ app }: { app: Application }) {
  const { set } = useSetStatus()
  const [confirm, setConfirm] = useState<null | 'applied' | 'skipped'>(null)
  const meta = [app.sector, app.role_type].filter(Boolean).join(', ')
  const applyUrl = safeHttp(app.apply_url)
  return (
    <article className="bezel" aria-labelledby={`app-${app.id}`}>
      <div className="bezel-core flex h-full flex-col gap-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <FitBadge fit={app.fit} />
          <DeadlineChip deadline={app.deadline} />
        </div>
        <div className="min-w-0">
          <h3 id={`app-${app.id}`} className="truncate text-lg leading-tight font-semibold tracking-tight">{app.company}</h3>
          <p className="mt-1 text-sm text-pretty">{app.role}</p>
          {meta && <p className="mt-1 text-xs text-muted-foreground">{meta}</p>}
        </div>
        <Notes text={app.notes} />
        {app.why_role && <WhyRole text={app.why_role} />}
        <div className="mt-auto grid gap-3 border-t border-foreground/[0.06] pt-4">
          <div className="flex flex-wrap items-center gap-2">
            {applyUrl ? (
            <a href={applyUrl} target="_blank" rel="noreferrer"
              className="group inline-flex h-9 items-center gap-2.5 rounded-full bg-primary pr-1 pl-4 text-sm font-medium text-primary-foreground outline-none transition-[background-color,box-shadow,transform] duration-300 ease-spring hover:bg-primary/90 focus-visible:ring-3 focus-visible:ring-ring/50 active:scale-[0.98]">
              Open application<span className="sr-only"> at {app.company} (opens in a new tab)</span>
              <span className="grid size-7 place-items-center rounded-full bg-primary-foreground/15 transition-transform duration-300 ease-spring group-hover:translate-x-0.5 group-hover:-translate-y-px">
                <ArrowUpRight className="size-3.5" weight="bold" aria-hidden />
              </span>
            </a>
            ) : <UnavailableLink className="h-9" />}
            <FileLink href={app.cv_url} label="CV" pdf />
            <FileLink href={app.cover_url} label="Cover letter" pdf />
            <FileLink href={app.posting_url} label="Posting" />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" className="h-9 px-3.5" onClick={() => setConfirm('applied')}>
              <CheckCircle aria-hidden /> Mark applied
            </Button>
            <Button variant="ghost" className="h-9 px-3 text-muted-foreground" onClick={() => setConfirm('skipped')}>
              <SkipForward aria-hidden /> Skip
            </Button>
          </div>
        </div>
      </div>
      <ConfirmDialog
        open={confirm === 'applied'}
        onOpenChange={(o) => !o && setConfirm(null)}
        title={`Mark ${app.company} as applied?`}
        body="Do this after you have submitted on the employer's site. It moves to Applied, and you can undo it from the toast."
        confirmLabel="Mark applied"
        cancelLabel="Not yet"
        onConfirm={() => { setConfirm(null); set(app, 'applied') }}
      />
      <ConfirmDialog
        open={confirm === 'skipped'}
        onOpenChange={(o) => !o && setConfirm(null)}
        title={`Skip ${app.company}?`}
        body="It moves to Skipped on the Applied page, where you can move it back to Ready."
        confirmLabel="Skip it"
        destructive
        onConfirm={() => { setConfirm(null); set(app, 'skipped') }}
      />
    </article>
  )
}
