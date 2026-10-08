import { ArrowsClockwise, CircleNotch } from '@phosphor-icons/react'
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { isActive, useRuns, useStartRun } from '@/lib/queries'

/** Runs the Gmail check now: confirmation emails move Ready rows to Applied, replies update the rest. */
export function CheckEmailButton() {
  const [runId, setRunId] = useState<string>()
  const start = useStartRun()
  const runs = useRuns()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const run = runId ? runs.data?.find((r) => r.id === runId) : undefined
  const busy = start.isPending || (!!runId && (!run || isActive(run)))

  useEffect(() => {
    if (!run || isActive(run)) return
    setRunId(undefined)
    for (const key of ['applications', 'replies', 'summary']) qc.invalidateQueries({ queryKey: [key] })
    const off = run.summary?.includes('is off')
    if (run.status === 'done' && !off) toast.success(`Email checked: ${run.summary ?? 'done'}`)
    else toast.error(off ? 'Gmail check is off. Add an app password in Settings.' : `Email check ${run.status}: ${run.error ?? ''}`, {
      action: off ? { label: 'Settings', onClick: () => navigate('/settings') } : { label: 'Log', onClick: () => navigate(`/runs/${run.id}`) },
    })
  }, [run, qc, navigate])

  return (
    <span className="inline-flex items-center gap-3" aria-live="polite">
      {busy && runId && (
        <Link to={`/runs/${runId}`} className="text-sm font-medium text-primary underline-offset-4 hover:underline">
          View progress
        </Link>
      )}
      <Button variant="secondary" className="h-10 px-4" disabled={busy}
        onClick={() => start.mutate({ task: 'gmail_check' }, { onSuccess: (r) => setRunId(r.id) })}>
        {busy ? <CircleNotch className="animate-spin" aria-hidden /> : <ArrowsClockwise aria-hidden />}
        {busy ? 'Checking email…' : 'Check email'}
      </Button>
    </span>
  )
}
