import { CircleNotch, LinkSimple } from '@phosphor-icons/react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Field, PageHeader, Panel, inputClass } from '@/components/kit'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ApiError } from '@/lib/api'
import { useStartRun } from '@/lib/queries'

function validUrl(s: string) {
  try {
    const u = new URL(s)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

export function DraftPage() {
  const [url, setUrl] = useState('')
  const [touched, setTouched] = useState(false)
  const navigate = useNavigate()
  const start = useStartRun()
  const bad = touched && url.trim() !== '' && !validUrl(url.trim())
  const conflict = start.error instanceof ApiError && start.error.status === 409

  return (
    <>
      <PageHeader title="Draft from URL"
        description="Paste a job posting you found yourself. The pipeline reads it, scores the fit and drafts a CV and cover letter, as it does for the daily search." />
      <Panel className="max-w-2xl">
        <form className="grid gap-5" noValidate onSubmit={(e) => {
          e.preventDefault()
          setTouched(true)
          if (!validUrl(url.trim())) return
          start.mutate({ task: 'draft_url', url: url.trim() }, { onSuccess: (r) => navigate(`/runs/${r.id}`) })
        }}>
          <Field label="Job posting URL"
            hint="LinkedIn, Naukri, Wellfound or the company's careers page. Login-only pages may not be readable."
            error={bad ? 'Enter a full link starting with https://' : conflict ? 'A draft is already queued or running. Wait for it to finish.' : undefined}>
            <div className="relative">
              <LinkSimple className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
              <Input type="url" inputMode="url" autoFocus required placeholder="https://www.linkedin.com/jobs/view/..."
                aria-invalid={bad || undefined} className={`${inputClass} pl-10`} value={url}
                onChange={(e) => setUrl(e.target.value)} onBlur={() => setTouched(true)} />
            </div>
          </Field>
          <div className="flex items-center gap-3">
            <Button type="submit" className="h-10 px-4" disabled={start.isPending || !url.trim()}>
              {start.isPending && <CircleNotch className="animate-spin" />}
              Draft application
            </Button>
            <span className="text-xs text-muted-foreground">You will see the run's log next.</span>
          </div>
        </form>
      </Panel>
    </>
  )
}
