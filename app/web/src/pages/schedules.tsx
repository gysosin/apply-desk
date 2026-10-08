import { CalendarDots, CircleNotch, PencilSimple, Plus, Trash } from '@phosphor-icons/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { toast } from 'sonner'
import { ConfirmDialog, Dropdown, EmptyState, Field, PageHeader, Panel, QueryError, Segmented, inputClass } from '@/components/kit'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { api, type Schedule, type ScheduleInput, type ScheduleTask } from '@/lib/api'
import { ago, dateTime } from '@/lib/format'
import { TASK_LABEL } from '@/lib/queries'
import { cn } from '@/lib/utils'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const TASKS: { key: ScheduleTask; label: string }[] = (['daily_run', 'gmail_check', 'deadline_alert'] as const)
  .map((t) => ({ key: t, label: TASK_LABEL[t] }))
const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/

/** "Every day at 07:30", "Weekdays at 09:00", "Mon, Thu at 18:00", "Every 30 min". */
function cadence(s: Pick<Schedule, 'kind' | 'time' | 'days' | 'every_min'>) {
  if (s.kind === 'interval') return s.every_min % 60 === 0 ? `Every ${s.every_min / 60} h` : `Every ${s.every_min} min`
  const d = [...s.days].sort((a, b) => a - b)
  const when = d.length === 0 || d.length === 7 ? 'Every day'
    : d.join() === '0,1,2,3,4' ? 'Weekdays'
    : d.join() === '5,6' ? 'Weekends'
    : d.map((i) => DAYS[i]).join(', ')
  return `${when} at ${s.time}`
}

const BLANK: ScheduleInput = { name: '', task: 'daily_run', kind: 'daily', time: '07:30', days: [], every_min: 60, enabled: true }

function ScheduleDialog({ open, onOpenChange, editing }: { open: boolean; onOpenChange: (o: boolean) => void; editing: Schedule | null }) {
  const qc = useQueryClient()
  const [form, setForm] = useState<ScheduleInput>(BLANK)
  const [tried, setTried] = useState(false)
  const [lastOpen, setLastOpen] = useState(false)
  // Reset the form each time the dialog opens (adjusting state during render, no effect needed).
  if (open !== lastOpen) {
    setLastOpen(open)
    if (open) {
      setTried(false)
      setForm(editing ? { name: editing.name, task: editing.task, kind: editing.kind, time: editing.time, days: editing.days, every_min: editing.every_min, enabled: editing.enabled } : BLANK)
    }
  }
  const set = <K extends keyof ScheduleInput>(k: K, v: ScheduleInput[K]) => setForm((f) => ({ ...f, [k]: v }))
  const errors = {
    name: form.name.trim() ? undefined : 'Give it a name, like "Morning search".',
    time: form.kind === 'daily' && !HHMM.test(form.time) ? 'Use 24-hour HH:MM, like 07:30.' : undefined,
    every_min: form.kind === 'interval' && !(Number.isInteger(form.every_min) && form.every_min >= 15) ? 'At least 15 minutes, in whole minutes.' : undefined,
  }
  const save = useMutation({
    mutationFn: (body: ScheduleInput) => (editing ? api.updateSchedule(editing.id, body) : api.createSchedule(body)),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ['schedules'] })
      qc.invalidateQueries({ queryKey: ['summary'] })
      toast.success(editing ? `Saved ${s.name}` : `Added ${s.name}`, { description: s.next_run ? `Next run ${ago(s.next_run)}` : undefined })
      onOpenChange(false)
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-5 rounded-2xl p-6 sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{editing ? 'Edit schedule' : 'Add schedule'}</DialogTitle>
          <DialogDescription>Times are this machine's local time. The app has to be running for a schedule to fire.</DialogDescription>
        </DialogHeader>
        <form id="schedule-form" className="grid gap-5" noValidate onSubmit={(e) => {
          e.preventDefault()
          setTried(true)
          if (Object.values(errors).some(Boolean)) return
          save.mutate({ ...form, name: form.name.trim() })
        }}>
          <Field label="Name" error={tried ? errors.name : undefined}>
            <Input className={inputClass} value={form.name} onChange={(e) => set('name', e.target.value)} aria-invalid={(tried && !!errors.name) || undefined} />
          </Field>
          <Field label="Task">
            <Dropdown label="Task" value={form.task} options={TASKS} onChange={(v) => set('task', v)} />
          </Field>
          <div className="grid gap-2 text-sm">
            <span className="font-medium leading-none">Repeats</span>
            <Segmented label="Repeats" value={form.kind} onChange={(v) => set('kind', v)}
              options={[{ key: 'daily', label: 'At a time' }, { key: 'interval', label: 'Every few minutes' }]} />
          </div>
          {form.kind === 'daily' ? (
            <>
              <Field label="Time" hint="24-hour, HH:MM" error={tried ? errors.time : undefined}>
                <Input type="time" className={cn(inputClass, 'w-36 num')} value={form.time} onChange={(e) => set('time', e.target.value)}
                  aria-invalid={(tried && !!errors.time) || undefined} />
              </Field>
              <div className="grid gap-2 text-sm">
                <span id="days-label" className="font-medium leading-none">Days</span>
                <div role="group" aria-labelledby="days-label" className="flex flex-wrap gap-1.5">
                  {DAYS.map((d, i) => {
                    const on = form.days.includes(i)
                    return (
                      <button key={d} type="button" aria-pressed={on}
                        onClick={() => set('days', on ? form.days.filter((x) => x !== i) : [...form.days, i].sort((a, b) => a - b))}
                        className={cn('h-8 min-w-11 rounded-full px-3 text-sm outline-none ring-1 transition-[color,background-color,box-shadow] duration-300 ease-spring focus-visible:ring-3 focus-visible:ring-ring/50',
                          on ? 'bg-primary font-medium text-primary-foreground ring-primary' : 'text-muted-foreground ring-foreground/10 hover:text-foreground hover:ring-foreground/20')}>
                        {d}
                      </button>
                    )
                  })}
                </div>
                <span className="text-xs text-muted-foreground">{form.days.length ? cadence(form) : 'None picked means every day.'}</span>
              </div>
            </>
          ) : (
            <Field label="Every (minutes)" hint="15 or more" error={tried ? errors.every_min : undefined}>
              <Input type="number" inputMode="numeric" min={15} step={5} className={cn(inputClass, 'w-36 num')}
                value={Number.isNaN(form.every_min) ? '' : form.every_min} onChange={(e) => set('every_min', e.target.valueAsNumber)}
                aria-invalid={(tried && !!errors.every_min) || undefined} />
            </Field>
          )}
          <label className="flex items-center justify-between gap-4 text-sm">
            <span>
              <span className="block font-medium">Enabled</span>
              <span className="block text-xs text-muted-foreground">Turn off to keep it without running it.</span>
            </span>
            <Switch checked={form.enabled} onCheckedChange={(v) => set('enabled', v)} aria-label="Enabled" />
          </label>
          {save.isError && <p role="alert" className="text-sm text-destructive">{save.error.message}</p>}
        </form>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={save.isPending}>Cancel</Button>
          <Button type="submit" form="schedule-form" disabled={save.isPending}>
            {save.isPending && <CircleNotch className="animate-spin" />}{editing ? 'Save' : 'Add schedule'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function Row({ s, onEdit, onDelete }: { s: Schedule; onEdit: () => void; onDelete: () => void }) {
  const qc = useQueryClient()
  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api.updateSchedule(s.id, { name: s.name, task: s.task, kind: s.kind, time: s.time, days: s.days, every_min: s.every_min, enabled }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['schedules'] }); qc.invalidateQueries({ queryKey: ['summary'] }) },
    onError: (e) => toast.error(e.message),
  })
  return (
    <li className="grid gap-3 px-5 py-4 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center sm:gap-5">
      <Switch checked={toggle.isPending ? toggle.variables : s.enabled} disabled={toggle.isPending}
        onCheckedChange={(v) => toggle.mutate(v)} aria-label={`${s.name} enabled`} />
      <div className={cn('min-w-0', !s.enabled && 'opacity-60')}>
        <p className="font-medium">{s.name} <span className="ml-1 text-sm font-normal text-muted-foreground">{TASK_LABEL[s.task]}</span></p>
        <p className="mt-0.5 text-sm num text-muted-foreground">{cadence(s)}</p>
        <p className="mt-1 text-xs num text-muted-foreground">
          {s.enabled
            ? s.next_run ? <>Next <span className="text-foreground">{ago(s.next_run)}</span>, {dateTime(s.next_run)}</> : 'Next run not computed yet'
            : 'Paused'}
          {s.last_run && <>. Last ran {ago(s.last_run)}</>}
        </p>
      </div>
      <div className="flex gap-1">
        <Button variant="ghost" size="icon" aria-label={`Edit ${s.name}`} onClick={onEdit}><PencilSimple /></Button>
        <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive" aria-label={`Delete ${s.name}`} onClick={onDelete}><Trash /></Button>
      </div>
    </li>
  )
}

export function SchedulesPage() {
  const qc = useQueryClient()
  const schedules = useQuery({ queryKey: ['schedules'], queryFn: api.schedules, refetchInterval: 60_000 })
  const [dialog, setDialog] = useState<{ open: boolean; editing: Schedule | null }>({ open: false, editing: null })
  const [deleting, setDeleting] = useState<Schedule | null>(null)
  const del = useMutation({
    mutationFn: (s: Schedule) => api.deleteSchedule(s.id),
    onSuccess: (_d, s) => {
      qc.invalidateQueries({ queryKey: ['schedules'] })
      qc.invalidateQueries({ queryKey: ['summary'] })
      toast.success(`Deleted ${s.name}`)
    },
    onError: (e) => toast.error(e.message),
    onSettled: () => setDeleting(null),
  })
  const add = () => setDialog({ open: true, editing: null })
  const on = schedules.data?.filter((s) => s.enabled).length ?? 0

  return (
    <>
      <PageHeader title="Schedules"
        description={schedules.data ? `${on} of ${schedules.data.length} on. The in-app scheduler starts these runs while the server is up.` : 'When the app runs searches and checks on its own.'}
        actions={<Button className="h-10 px-4" onClick={add}><Plus weight="bold" /> Add schedule</Button>} />
      <Panel flush>
        {schedules.isPending ? (
          <div className="grid gap-2 p-5" aria-busy="true" aria-label="Loading">
            {Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-16 rounded-xl" />)}
          </div>
        ) : schedules.isError ? <QueryError error={schedules.error} onRetry={() => schedules.refetch()} /> : schedules.data.length === 0 ? (
          <EmptyState icon={CalendarDots} title="No schedules"
            body="Add one to run the daily search every morning, check Gmail every hour, or get a deadline alert before work." />
        ) : (
          <ul className="divide-y divide-foreground/[0.06]">
            {schedules.data.map((s) => (
              <Row key={s.id} s={s} onEdit={() => setDialog({ open: true, editing: s })} onDelete={() => setDeleting(s)} />
            ))}
          </ul>
        )}
      </Panel>
      <ScheduleDialog open={dialog.open} editing={dialog.editing} onOpenChange={(o) => setDialog((d) => ({ ...d, open: o }))} />
      <ConfirmDialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}
        title={`Delete ${deleting?.name ?? 'schedule'}?`} body="Runs it already started stay in the run history."
        confirmLabel="Delete" destructive pending={del.isPending} onConfirm={() => deleting && del.mutate(deleting)} />
    </>
  )
}
