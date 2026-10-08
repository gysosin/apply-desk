import { CircleNotch, Eye, EyeSlash, WarningCircle } from '@phosphor-icons/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '@/app/auth'
import { BrandMark } from '@/app/shell'
import { Field } from '@/components/kit'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ApiError, api } from '@/lib/api'

export function LoginPage() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [capsLock, setCapsLock] = useState(false)
  const next = params.get('next')
  const target = next && next.startsWith('/') && !next.startsWith('//') ? next : '/'

  const login = useMutation({
    mutationFn: () => api.login(username, password),
    onSuccess: (me) => {
      qc.setQueryData(['me'], me)
      navigate(target, { replace: true })
    },
  })

  if (user) return <Navigate to={target} replace />

  return (
    <div className="grid min-h-dvh gap-3 p-3 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      <aside className="relative hidden overflow-hidden rounded-[1.5rem] bg-primary text-primary-foreground lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div aria-hidden className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{ backgroundImage: 'radial-gradient(currentColor 1px, transparent 1px)', backgroundSize: '22px 22px' }} />
        <div aria-hidden className="pointer-events-none absolute -top-40 -right-40 size-[28rem] rounded-full bg-brand/25 blur-3xl" />
        <div className="relative flex items-center gap-2.5">
          <img src="/favicon.svg" alt="" width={36} height={36} className="size-9 rounded-[0.65rem] ring-1 ring-primary-foreground/15" />
          <span className="text-lg font-semibold tracking-tight">Apply Desk</span>
        </div>
        <div className="relative max-w-lg">
          <h1 className="text-5xl leading-[1.05] font-semibold tracking-tight text-balance">
            Drafted overnight.
            <br />
            Sent by you.
          </h1>
          <p className="mt-5 max-w-md text-base leading-relaxed text-primary-foreground/75">
            Every morning's tailored CVs and cover letters, sorted by deadline and fit, ready to review and send.
          </p>
        </div>
        <p className="relative text-sm text-primary-foreground/60">Runs on your own machine. Nothing is sent without your click.</p>
      </aside>

      <main className="flex items-center justify-center px-2 py-10 sm:px-8">
        <div className="rise w-full max-w-[380px]">
          <BrandMark className="mb-10 lg:hidden" />
          <div>
            <h2 className="text-[1.75rem] leading-tight font-semibold tracking-tight">Sign in</h2>
            <p className="mt-1.5 text-sm text-muted-foreground">Use the username and password set in the server's config.</p>
          </div>

          <form className="mt-8 grid gap-5" onSubmit={(e) => { e.preventDefault(); login.mutate() }}>
            <Field label="Username">
              <Input name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} autoFocus required
                className="h-11 rounded-xl px-3.5" value={username} onChange={(e) => setUsername(e.target.value)} />
            </Field>
            <Field label="Password" hint={capsLock ? <span className="font-medium text-warning">Caps Lock is on</span> : undefined}>
              <div className="relative">
                <Input name="password" type={show ? 'text' : 'password'} autoComplete="current-password" required
                  className="h-11 rounded-xl pr-11 pl-3.5" value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onKeyUp={(e) => setCapsLock(e.getModifierState('CapsLock'))} />
                <Button type="button" variant="ghost" size="icon-sm"
                  className="absolute top-1/2 right-2 -translate-y-1/2 text-muted-foreground"
                  aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show}
                  onClick={() => setShow((s) => !s)}>
                  {show ? <EyeSlash /> : <Eye />}
                </Button>
              </div>
            </Field>

            {login.isError && (
              <div role="alert" className="flex items-start gap-2.5 rounded-xl border border-destructive/30 bg-destructive/6 p-3.5 text-sm text-destructive">
                <WarningCircle className="mt-px size-4.5 shrink-0" aria-hidden />
                {login.error instanceof ApiError && login.error.status === 401 ? 'That username and password do not match.' : login.error.message}
              </div>
            )}

            <Button type="submit" className="mt-1 h-11 text-[0.95rem]" disabled={login.isPending || !username || !password}>
              {login.isPending && <CircleNotch className="animate-spin" />}
              Sign in
            </Button>
          </form>
        </div>
      </main>
    </div>
  )
}
