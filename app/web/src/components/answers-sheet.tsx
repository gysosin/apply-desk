/* Copy panel for application forms: name, email, notice period, CTC and the rest. */
import { ClipboardText, Copy } from '@phosphor-icons/react'
import { useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { EmptyState, QueryError } from '@/components/kit'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { api } from '@/lib/api'

/** Clipboard API, with the old textarea trick for plain-http LAN origins where it is missing. */
async function copyText(text: string) {
  if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text)
  const ta = document.createElement('textarea')
  ta.value = text
  ta.setAttribute('readonly', '')
  ta.style.position = 'fixed'
  ta.style.opacity = '0'
  document.body.appendChild(ta)
  ta.select()
  const ok = document.execCommand('copy')
  ta.remove()
  if (!ok) throw new Error('copy failed')
}

export function AnswersSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const answers = useQuery({ queryKey: ['answers'], queryFn: api.answers, enabled: open, staleTime: 5 * 60_000 })
  const copy = async (label: string, value: string) => {
    try {
      await copyText(value)
      toast.success(`Copied ${label}`)
    } catch {
      toast.error(`Could not copy ${label}. Select the text and copy it by hand.`)
    }
  }
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full gap-0 bg-background sm:max-w-md">
        <SheetHeader className="border-b px-5 pt-5 pb-4">
          <SheetTitle className="text-base font-semibold">Form answers</SheetTitle>
          <SheetDescription>Click a row to copy it, then paste into the employer's form.</SheetDescription>
        </SheetHeader>
        <div className="flex-1 overflow-y-auto p-3">
          {answers.isPending ? (
            <div className="grid gap-2 p-2" aria-busy="true" aria-label="Loading">
              {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-14 rounded-xl" />)}
            </div>
          ) : answers.isError ? (
            <QueryError error={answers.error} onRetry={() => answers.refetch()} />
          ) : answers.data.length === 0 ? (
            <EmptyState icon={ClipboardText} title="No saved answers"
              body="The server reads them from your candidate profile. Fill it in and they show up here." />
          ) : (
            <ul className="grid gap-1">
              {answers.data.map((a) => (
                <li key={a.label}>
                  <button type="button" onClick={() => copy(a.label, a.value)}
                    aria-label={`Copy ${a.label}: ${a.value}`}
                    className="group flex w-full items-start gap-3 rounded-xl px-3 py-2.5 text-left outline-none transition-colors duration-300 ease-spring hover:bg-foreground/[0.04] focus-visible:ring-3 focus-visible:ring-ring/50 active:scale-[0.99]">
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs text-muted-foreground">{a.label}</span>
                      <span className="mt-0.5 block text-sm break-words whitespace-pre-wrap">{a.value}</span>
                    </span>
                    <Copy className="mt-1 size-4 shrink-0 text-muted-foreground opacity-60 transition-opacity group-hover:opacity-100" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
