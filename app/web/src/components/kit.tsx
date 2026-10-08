/* Shared building blocks, adapted from the Crawl Hub kit. Icons: Phosphor. */
import {
  ArrowsClockwise,
  CheckCircle,
  CircleNotch,
  Clock,
  Prohibit,
  Warning,
  WarningCircle,
  XCircle,
  type Icon,
} from '@phosphor-icons/react'
import type { ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { RunStatus } from '@/lib/api'
import { cn } from '@/lib/utils'

export function PageHeader({ title, description, actions, children }: {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  children?: ReactNode
}) {
  return (
    <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-[1.75rem] leading-tight font-semibold tracking-tight text-balance">{title}</h1>
        {description && <p className="mt-1.5 max-w-[65ch] text-sm text-muted-foreground">{description}</p>}
        {children}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  )
}

/** Double-bezel panel: outer tray + raised inner plate. */
export function Panel({ title, description, actions, className, children, flush }: {
  title?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
  children: ReactNode
  flush?: boolean
}) {
  return (
    <section className={cn('bezel min-w-0', className)}>
      <div className="bezel-core h-full overflow-hidden">
        {(title || actions) && (
          <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 px-5 pt-4 pb-3">
            <div className="min-w-0">
              {title && <h2 className="text-[0.95rem] font-semibold tracking-tight">{title}</h2>}
              {description && <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>}
            </div>
            {actions && <div className="flex items-center gap-2">{actions}</div>}
          </div>
        )}
        <div className={flush ? '' : cn('px-5 pb-5', !(title || actions) && 'pt-5')}>{children}</div>
      </div>
    </section>
  )
}

export function StatTile({ label, value, hint, icon: IconCmp }: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: Icon
}) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {IconCmp && <IconCmp className="size-4" aria-hidden />}
        {label}
      </div>
      <div className="mt-1.5 text-[1.5rem] leading-tight font-semibold num tracking-tight sm:text-[1.7rem]">{value}</div>
      {hint && <div className="mt-1 text-xs text-pretty text-muted-foreground">{hint}</div>}
    </div>
  )
}

export function EmptyState({ icon: IconCmp, title, body, action, className }: {
  icon: Icon
  title: string
  body?: ReactNode
  action?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex flex-col items-center px-6 py-14 text-center', className)}>
      <div className="bezel !rounded-2xl !p-1">
        <div className="bezel-core grid size-11 place-items-center !rounded-xl">
          <IconCmp className="size-5 text-muted-foreground" weight="light" aria-hidden />
        </div>
      </div>
      <h3 className="mt-4 text-sm font-semibold">{title}</h3>
      {body && <p className="mt-1 max-w-sm text-sm text-muted-foreground">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function QueryError({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center px-6 py-12 text-center">
      <WarningCircle className="size-7 text-destructive" weight="light" aria-hidden />
      <p className="mt-3 text-sm font-semibold">Could not load this</p>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{error.message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          <ArrowsClockwise /> Try again
        </Button>
      )}
    </div>
  )
}

export function Callout({ tone, title, children, action }: {
  tone: 'warning' | 'destructive' | 'info'
  title: string
  children?: ReactNode
  action?: ReactNode
}) {
  const IconCmp = tone === 'info' ? CheckCircle : Warning
  const styles = {
    warning: 'border-warning/30 bg-warning/8 [&>svg]:text-warning',
    destructive: 'border-destructive/30 bg-destructive/6 [&>svg]:text-destructive',
    info: 'border-border bg-muted/50 [&>svg]:text-muted-foreground',
  }
  return (
    <div role={tone === 'info' ? 'status' : 'alert'} className={cn('flex gap-3 rounded-2xl border p-4 text-sm', styles[tone])}>
      <IconCmp className="mt-0.5 size-4.5 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{title}</p>
        {children && <div className="mt-0.5 text-muted-foreground">{children}</div>}
      </div>
      {action && <div className="shrink-0 self-center">{action}</div>}
    </div>
  )
}

const RUN_STATUS: Record<RunStatus, { label: string; icon: Icon; className: string; spin?: boolean }> = {
  queued: { label: 'Queued', icon: Clock, className: 'text-muted-foreground bg-muted' },
  running: { label: 'Running', icon: CircleNotch, className: 'text-primary bg-primary/10', spin: true },
  done: { label: 'Done', icon: CheckCircle, className: 'text-success bg-success/12' },
  failed: { label: 'Failed', icon: XCircle, className: 'text-destructive bg-destructive/10' },
  cancelled: { label: 'Cancelled', icon: Prohibit, className: 'text-muted-foreground bg-muted' },
}

/** Status as icon + word, never colour alone. An unknown status shows as its own word. */
export function RunStatusBadge({ status }: { status: string }) {
  const s = RUN_STATUS[status as RunStatus] ?? { label: status, icon: Clock, className: 'text-muted-foreground bg-muted' }
  return (
    <span className={cn('inline-flex h-6 shrink-0 items-center gap-1 rounded-full pr-2.5 pl-1.5 text-xs font-medium', s.className)}>
      <s.icon className={cn('size-3.5', s.spin && 'animate-spin [animation-duration:2.4s]')} weight="bold" aria-hidden />
      {s.label}
    </span>
  )
}

export function ConfirmDialog({ open, onOpenChange, title, body, confirmLabel, cancelLabel = 'Keep it', destructive, pending, onConfirm }: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  body: ReactNode
  confirmLabel: string
  cancelLabel?: string
  destructive?: boolean
  pending?: boolean
  onConfirm: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{body}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>{cancelLabel}</Button>
          <Button variant={destructive ? 'destructive' : 'default'} onClick={onConfirm} disabled={pending}>
            {pending && <CircleNotch className="animate-spin" />}
            {confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

/** Label above, control, then the error (or the hint) below. */
export function Field({ label, hint, error, className, children }: {
  label: string
  hint?: ReactNode
  error?: string
  className?: string
  children: ReactNode
}) {
  return (
    <label className={cn('grid content-start gap-2 text-sm', className)}>
      <span className="font-medium leading-none">{label}</span>
      {children}
      {error ? <span className="text-xs text-destructive">{error}</span> : hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </label>
  )
}

export const inputClass = 'h-10 rounded-xl px-3.5'

/** The kit's dropdown (no native select). */
export function Dropdown<T extends string>({ value, options, onChange, label }: {
  value: T
  options: readonly { key: T; label: string }[]
  onChange: (key: T) => void
  label: string
}) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as T)} items={options.map((o) => ({ value: o.key, label: o.label }))}>
      <SelectTrigger aria-label={label} className="h-10 w-full rounded-xl px-3.5"><SelectValue /></SelectTrigger>
      <SelectContent>
        {options.map((o) => <SelectItem key={o.key} value={o.key}>{o.label}</SelectItem>)}
      </SelectContent>
    </Select>
  )
}

/** The pill segmented control: one choice out of a few. */
export function Segmented<T extends string>({ label, value, options, onChange }: {
  label: string
  value: T
  options: readonly { key: T; label: ReactNode }[]
  onChange: (key: T) => void
}) {
  return (
    <div role="group" aria-label={label}
      className="inline-flex w-fit max-w-full overflow-x-auto rounded-full bg-foreground/[0.05] p-1 ring-1 ring-foreground/[0.05]">
      {options.map((o) => (
        <button key={o.key} type="button" aria-pressed={value === o.key} onClick={() => onChange(o.key)}
          className={cn(
            'inline-flex h-8 shrink-0 items-center gap-1.5 rounded-full px-3.5 text-sm outline-none transition-[color,background-color,box-shadow] duration-300 ease-spring focus-visible:ring-3 focus-visible:ring-ring/50',
            value === o.key ? 'bg-card font-medium shadow-sm ring-1 ring-foreground/[0.06]' : 'text-muted-foreground hover:text-foreground',
          )}>
          {o.label}
        </button>
      ))}
    </div>
  )
}

/** Skeleton rows shaped like the cards they stand in for. */
export function CardSkeletons({ n = 3 }: { n?: number }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="bezel"><div className="bezel-core h-52 animate-pulse" /></div>
      ))}
    </div>
  )
}
