import { BellRinging, CheckCircle, CircleNotch, FloppyDisk } from '@phosphor-icons/react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { toast } from 'sonner'
import { Field, PageHeader, Panel, QueryError, inputClass } from '@/components/kit'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Switch } from '@/components/ui/switch'
import { api, type Settings } from '@/lib/api'
import { cn } from '@/lib/utils'

function ToggleRow({ label, hint, checked, onChange }: { label: string; hint: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-4 text-sm">
      <span>
        <span className="block font-medium">{label}</span>
        <span className="block text-xs text-muted-foreground">{hint}</span>
      </span>
      <Switch checked={checked} onCheckedChange={onChange} aria-label={label} />
    </label>
  )
}

function Help({ children }: { children: ReactNode }) {
  return <div className="rounded-xl bg-foreground/[0.035] p-4 text-xs leading-relaxed text-muted-foreground">{children}</div>
}

function SettingsForm({ initial }: { initial: Settings }) {
  const qc = useQueryClient()
  const [form, setForm] = useState(initial)
  const [password, setPassword] = useState('')
  const [tried, setTried] = useState(false)
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setForm((f) => ({ ...f, [k]: v }))
  const setModel = (k: keyof Settings['models'], v: string) => setForm((f) => ({ ...f, models: { ...f.models, [k]: v } }))
  const dirty = JSON.stringify(form) !== JSON.stringify(initial) || password !== ''

  const errors = {
    min_score: Number.isInteger(form.min_score) && form.min_score >= 0 && form.min_score <= 100 ? undefined : 'A whole number from 0 to 100.',
    max_drafts: Number.isInteger(form.max_drafts) && form.max_drafts >= 1 && form.max_drafts <= 50 ? undefined : 'A whole number from 1 to 50.',
    min_company_size: Number.isInteger(form.min_company_size) && form.min_company_size >= 0 ? undefined : 'A whole number; 0 turns the filter off.',
    ntfy_topic: form.notify_enabled && !form.ntfy_topic.trim() ? 'Needed for phone notifications.' : undefined,
    gmail_user: form.gmail_enabled && !/^\S+@\S+\.\S+$/.test(form.gmail_user) ? 'Enter the Gmail address.' : undefined,
    password: form.gmail_enabled && !form.gmail_has_password && !password ? 'Needed once to read Gmail.' : undefined,
  }
  const models = (['triage', 'score', 'draft'] as const)

  const save = useMutation({
    mutationFn: () => api.saveSettings({ ...form, ...(password ? { gmail_app_password: password.replace(/\s+/g, '') } : {}) }),
    onSuccess: (s) => {
      qc.setQueryData(['settings'], s)
      setForm(s)
      setPassword('')
      toast.success('Settings saved')
    },
  })
  const test = useMutation({
    mutationFn: api.testNotify,
    onSuccess: () => toast.success('Test notification sent', { description: 'It should reach your phone within a few seconds.' }),
    onError: (e) => toast.error(e.message),
  })

  const err = (k: keyof typeof errors) => (tried ? errors[k] : undefined)
  return (
    <form className="grid gap-3 lg:grid-cols-2" noValidate onSubmit={(e) => {
      e.preventDefault()
      setTried(true)
      if (!Object.values(errors).some(Boolean)) save.mutate()
    }}>
      <Panel title="Drafting" description="What the daily search drafts, and with which models">
        <div className="grid gap-5">
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Minimum fit score" hint="Roles below this are not drafted. Default 60." error={err('min_score')}>
              <Input type="number" inputMode="numeric" min={0} max={100} className={cn(inputClass, 'num')}
                value={Number.isNaN(form.min_score) ? '' : form.min_score} onChange={(e) => set('min_score', e.target.valueAsNumber)} />
            </Field>
            <Field label="Drafts per run" hint="The best-scoring roles first. Default 8." error={err('max_drafts')}>
              <Input type="number" inputMode="numeric" min={1} max={50} className={cn(inputClass, 'num')}
                value={Number.isNaN(form.max_drafts) ? '' : form.max_drafts} onChange={(e) => set('max_drafts', e.target.valueAsNumber)} />
            </Field>
          </div>
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Minimum company size" hint="Employees on LinkedIn. Smaller companies are skipped before scoring. 0 = off. Default 500." error={err('min_company_size')}>
              <Input type="number" inputMode="numeric" min={0} step={100} className={cn(inputClass, 'num')}
                value={Number.isNaN(form.min_company_size) ? '' : form.min_company_size} onChange={(e) => set('min_company_size', e.target.valueAsNumber)} />
            </Field>
            <ToggleRow label="Keep unknown sizes" hint="Off: a company whose size can't be found is skipped."
              checked={form.keep_unknown_size} onChange={(v) => set('keep_unknown_size', v)} />
          </div>
          {models.map((k) => (
            <Field key={k} label={{ triage: 'Triage model', score: 'Scoring model', draft: 'Drafting model' }[k]}
              hint={{ triage: 'Cheap first pass over every scraped posting.', score: 'Scores the ones that pass triage.', draft: 'Writes the CV and cover letter.' }[k]}>
              <Input className={cn(inputClass, 'font-mono text-[0.85rem]')} spellCheck={false} autoCapitalize="none"
                value={form.models[k]} onChange={(e) => setModel(k, e.target.value)} />
            </Field>
          ))}
        </div>
      </Panel>

      <div className="grid content-start gap-3">
        <Panel title="Phone notifications" description="A push through ntfy.sh when drafts are ready or a deadline is close">
          <div className="grid gap-5">
            <ToggleRow label="Send notifications" hint="Subscribe to the topic in the ntfy app first."
              checked={form.notify_enabled} onChange={(v) => set('notify_enabled', v)} />
            <Field label="ntfy topic" error={err('ntfy_topic')}>
              <Input className={cn(inputClass, 'font-mono text-[0.85rem]')} spellCheck={false} autoCapitalize="none"
                value={form.ntfy_topic} onChange={(e) => set('ntfy_topic', e.target.value)} />
            </Field>
            <Help>
              ntfy topics are public: anyone who knows the name can read the messages. Keep the long generated
              topic rather than something guessable like your name.
            </Help>
            <div className="flex flex-wrap items-center gap-3">
              <Button type="button" variant="outline" className="h-9 px-3.5" onClick={() => test.mutate()}
                disabled={test.isPending || dirty || !initial.notify_enabled}>
                {test.isPending ? <CircleNotch className="animate-spin" /> : <BellRinging />} Send test notification
              </Button>
              {(dirty || !initial.notify_enabled) && (
                <span className="text-xs text-muted-foreground">{dirty ? 'Save your changes first.' : 'Turn notifications on and save first.'}</span>
              )}
            </div>
          </div>
        </Panel>

        <Panel title="Gmail replies" description="Reads your inbox for replies from companies you applied to. Read-only.">
          <div className="grid gap-5">
            <ToggleRow label="Check Gmail" hint="Runs on the Gmail check schedule."
              checked={form.gmail_enabled} onChange={(v) => set('gmail_enabled', v)} />
            <Field label="Gmail address" error={err('gmail_user')}>
              <Input type="email" autoComplete="off" className={inputClass} value={form.gmail_user} onChange={(e) => set('gmail_user', e.target.value)} />
            </Field>
            <Field label="App password" error={err('password')}
              hint={form.gmail_has_password
                ? <span className="inline-flex items-center gap-1 text-success"><CheckCircle weight="fill" className="size-3.5" aria-hidden />Saved. Leave blank to keep it.</span>
                : '16 letters from Google. Spaces are removed for you.'}>
              <Input type="password" autoComplete="new-password" className={cn(inputClass, 'font-mono')}
                placeholder={form.gmail_has_password ? '••••••••••••••••' : ''} value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            <Help>
              To make an app password: turn on 2-Step Verification for the Google account, open
              myaccount.google.com/apppasswords, create one named "Apply Desk" and paste the 16 letters here.
              It is stored on this machine and never shown again.
            </Help>
          </div>
        </Panel>
      </div>

      <div className="sticky bottom-3 z-10 flex flex-wrap items-center gap-3 rounded-full bg-card p-1.5 pl-5 shadow-lg ring-1 ring-foreground/[0.08] lg:col-span-2 lg:w-fit">
        <span className="text-sm text-muted-foreground" aria-live="polite">
          {save.isError ? <span className="text-destructive">{save.error.message}</span> : dirty ? 'Unsaved changes' : 'All changes saved'}
        </span>
        <Button type="submit" className="h-9 px-4" disabled={!dirty || save.isPending}>
          {save.isPending ? <CircleNotch className="animate-spin" /> : <FloppyDisk />} Save settings
        </Button>
      </div>
    </form>
  )
}

export function SettingsPage() {
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.settings, refetchOnWindowFocus: false })
  return (
    <>
      <PageHeader title="Settings" description="How many roles get drafted each day, and how the app reaches you." />
      {settings.isPending ? (
        <div className="grid gap-3 lg:grid-cols-2" aria-busy="true" aria-label="Loading">
          <Skeleton className="h-96 rounded-[1.25rem]" />
          <Skeleton className="h-96 rounded-[1.25rem]" />
        </div>
      ) : settings.isError ? (
        <Panel><QueryError error={settings.error} onRetry={() => settings.refetch()} /></Panel>
      ) : (
        <SettingsForm initial={settings.data} />
      )}
    </>
  )
}
