export function duration(seconds: number | null | undefined): string {
  if (seconds == null) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.round(seconds % 60)
  if (h) return `${h}h ${m}m`
  if (m) return `${m}m ${s}s`
  return `${Math.max(1, s)}s`
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('en-IN', {
    weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

/** "3 hours ago", "in 20 minutes", "tomorrow". */
export function ago(iso: string | null | undefined): string {
  if (!iso) return 'never'
  const s = (new Date(iso).getTime() - Date.now()) / 1000
  const abs = Math.abs(s)
  if (abs < 45) return 'just now'
  if (abs < 3600) return rtf.format(Math.round(s / 60), 'minute')
  if (abs < 86400) return rtf.format(Math.round(s / 3600), 'hour')
  return rtf.format(Math.round(s / 86400), 'day')
}

/** "1 role", "2 roles". */
export const count = (n: number, word: string) => `${n.toLocaleString('en-IN')} ${word}${n === 1 ? '' : 's'}`

/** A tracker date (YYYY-MM-DD) as a local midnight, so day maths never shifts by the timezone. */
function localDay(ymd: string): Date {
  const [y, m, d] = ymd.split('-').map(Number)
  return new Date(y, (m || 1) - 1, d || 1)
}

/** Whole days from today to a YYYY-MM-DD date: 0 today, 1 tomorrow, -2 two days ago. */
export function daysUntil(ymd: string): number {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return Math.round((localDay(ymd).getTime() - today.getTime()) / 86_400_000)
}

/** "3 Oct", or "3 Oct 2025" outside this year. */
export function day(ymd: string | null | undefined): string {
  if (!ymd) return '-'
  const d = localDay(ymd)
  return d.toLocaleDateString('en-IN', {
    day: 'numeric', month: 'short', year: d.getFullYear() === new Date().getFullYear() ? undefined : 'numeric',
  })
}

/** "today", "tomorrow", "in 5 days", "2 days ago". */
export const relDay = (ymd: string) => rtf.format(daysUntil(ymd), 'day')
