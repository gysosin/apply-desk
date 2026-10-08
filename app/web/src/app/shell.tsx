import {
  CalendarDots,
  CaretUpDown,
  CheckSquareOffset,
  ClipboardText,
  Gear,
  LinkSimple,
  List,
  MagnifyingGlass,
  Monitor,
  Moon,
  SignOut,
  SunHorizon,
  Sun,
  Terminal,
  Tray,
  type Icon,
} from '@phosphor-icons/react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/app/auth'
import { AnswersSheet } from '@/components/answers-sheet'
import { CommandPalette } from '@/components/command-palette'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import { api } from '@/lib/api'
import { useApplications } from '@/lib/queries'
import { useTheme, type Theme } from '@/lib/theme'
import { cn } from '@/lib/utils'

type NavItem = { to: string; label: string; icon: Icon; end?: boolean; count?: 'ready' }
export const NAV: NavItem[] = [
  { to: '/', label: 'Today', icon: SunHorizon, end: true },
  { to: '/ready', label: 'Ready', icon: Tray, count: 'ready' },
  { to: '/applied', label: 'Applied', icon: CheckSquareOffset },
  { to: '/draft', label: 'Draft from URL', icon: LinkSimple },
  { to: '/runs', label: 'Runs', icon: Terminal },
  { to: '/schedules', label: 'Schedules', icon: CalendarDots },
  { to: '/settings', label: 'Settings', icon: Gear },
]

const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

export function BrandMark({ className }: { className?: string }) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <img src="/favicon.svg" alt="" width={32} height={32} className="size-8 rounded-[0.6rem]" />
      <span className="text-[0.95rem] font-semibold tracking-tight">Apply Desk</span>
    </div>
  )
}

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  const apps = useApplications()
  const ready = apps.data?.filter((a) => a.status === 'drafted').length
  return (
    <nav aria-label="Main" className="grid gap-0.5 px-2">
      {NAV.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.end} onClick={onNavigate}
          className={({ isActive }) => cn(
            'group flex h-9 items-center gap-2.5 rounded-xl px-3 text-sm outline-none transition-[color,background-color,box-shadow] duration-300 ease-spring focus-visible:ring-3 focus-visible:ring-ring/50',
            isActive
              ? 'bg-card font-medium text-foreground shadow-[0_1px_2px_rgb(0_0_0/0.06),inset_0_0_0_1px_color-mix(in_oklch,var(--foreground)_7%,transparent)]'
              : 'text-muted-foreground hover:bg-foreground/[0.04] hover:text-foreground',
          )}>
          {({ isActive }) => (
            <>
              <n.icon className={cn('size-4.5 transition-colors', isActive && 'text-brand')} weight={isActive ? 'fill' : 'regular'} aria-hidden />
              {n.label}
              {n.count && ready ? (
                <span className="ml-auto rounded-full bg-foreground/[0.06] px-2 py-0.5 text-xs font-medium num text-foreground" aria-label={`${ready} ready`}>
                  {ready}
                </span>
              ) : null}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

const THEME_ICON: Record<Theme, Icon> = { light: Sun, dark: Moon, system: Monitor }

function AccountMenu({ compact }: { compact?: boolean }) {
  const { user } = useAuth()
  const [theme, setTheme] = useTheme()
  const qc = useQueryClient()
  const navigate = useNavigate()
  const logout = useMutation({
    mutationFn: api.logout,
    onSettled: () => {
      qc.clear()
      qc.setQueryData(['me'], null)
      navigate('/login', { replace: true })
    },
  })
  if (!user) return null
  const ThemeIcon = THEME_ICON[theme]
  const avatar = (
    <span className="grid size-8 shrink-0 place-items-center rounded-full bg-primary text-[11px] font-semibold text-primary-foreground uppercase">
      {user.username.slice(0, 2)}
    </span>
  )
  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={compact ? (
        <Button variant="ghost" size="icon" className="size-9 p-0" aria-label="Account and theme">{avatar}</Button>
      ) : (
        <button type="button" aria-label="Account and theme"
          className="flex w-full items-center gap-2.5 rounded-xl p-1.5 text-left outline-none transition-colors duration-300 ease-spring hover:bg-foreground/[0.04] focus-visible:ring-3 focus-visible:ring-ring/50">
          {avatar}
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">{user.username}</span>
            <span className="flex items-center gap-1 truncate text-xs text-muted-foreground">
              <ThemeIcon className="size-3" aria-hidden />{{ system: 'Match system', light: 'Light', dark: 'Dark' }[theme]}
            </span>
          </span>
          <CaretUpDown className="size-4 text-muted-foreground" aria-hidden />
        </button>
      )} />
      <DropdownMenuContent align={compact ? 'end' : 'start'} side={compact ? 'bottom' : 'top'} className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel className="flex items-center gap-2 text-xs">
            <ThemeIcon className="size-3.5" aria-hidden /> Appearance
          </DropdownMenuLabel>
          <DropdownMenuRadioGroup value={theme} onValueChange={(v) => setTheme(v as Theme)}>
            <DropdownMenuRadioItem value="system">Match system</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="light">Light</DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="dark">Dark</DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={() => logout.mutate()}>
          <SignOut /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** Sidebar buttons for the palette and the answers drawer. */
function ToolButton({ icon: IconCmp, label, kbd, onClick }: { icon: Icon; label: string; kbd?: string; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick}
      className="flex h-9 w-full items-center gap-2.5 rounded-xl px-3 text-sm text-muted-foreground outline-none transition-[color,background-color] duration-300 ease-spring hover:bg-foreground/[0.04] hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50">
      <IconCmp className="size-4.5" aria-hidden />
      {label}
      {kbd && <kbd className="ml-auto rounded-md bg-foreground/[0.06] px-1.5 py-0.5 font-mono text-[0.7rem] text-muted-foreground">{kbd}</kbd>}
    </button>
  )
}

export function Shell() {
  const [drawer, setDrawer] = useState(false)
  const [palette, setPalette] = useState(false)
  const [answers, setAnswers] = useState(false)
  const location = useLocation()
  const kbd = isMac ? '⌘K' : 'Ctrl K'

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPalette((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[248px_minmax(0,1fr)] lg:gap-2 lg:p-3">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-full focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:text-primary-foreground">
        Skip to content
      </a>
      {/* Desktop: a floating tray. */}
      <aside className="bezel sticky top-3 hidden h-[calc(100dvh-1.5rem)] lg:block">
        <div className="flex h-full flex-col rounded-[calc(1.25rem-0.3125rem)] bg-sidebar/60">
          <BrandMark className="h-16 px-4" />
          <div className="grid gap-0.5 px-2 pb-3">
            <ToolButton icon={MagnifyingGlass} label="Search or jump" kbd={kbd} onClick={() => setPalette(true)} />
            <ToolButton icon={ClipboardText} label="Form answers" onClick={() => setAnswers(true)} />
          </div>
          <div className="mx-4 mb-3 border-t border-foreground/[0.06]" />
          <div className="flex-1 overflow-y-auto"><Nav /></div>
          <div className="border-t border-foreground/[0.06] p-2"><AccountMenu /></div>
        </div>
      </aside>

      {/* Phone and tablet: slim bar plus a drawer. */}
      <header className="sticky top-0 z-20 flex h-14 items-center gap-1 border-b bg-background/80 px-3 backdrop-blur-md lg:hidden">
        <Button variant="ghost" size="icon" aria-label="Open navigation" onClick={() => setDrawer(true)}>
          <List className="size-5" />
        </Button>
        <BrandMark className="ml-1" />
        <div className="flex-1" />
        <Button variant="ghost" size="icon" aria-label="Search or jump" onClick={() => setPalette(true)}>
          <MagnifyingGlass className="size-5" />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Form answers" onClick={() => setAnswers(true)}>
          <ClipboardText className="size-5" />
        </Button>
        <AccountMenu compact />
      </header>
      <Sheet open={drawer} onOpenChange={setDrawer}>
        <SheetContent side="left" className="w-72 bg-sidebar p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <BrandMark className="h-16 px-5" />
          <Nav onNavigate={() => setDrawer(false)} />
        </SheetContent>
      </Sheet>

      <main id="main" tabIndex={-1} key={location.pathname} style={{ outline: 'none' }}
        className="rise mx-auto grid w-full max-w-[1400px] min-w-0 content-start gap-6 px-4 py-6 sm:px-6 lg:py-6 [&>*]:min-w-0">
        <Outlet />
      </main>

      <CommandPalette open={palette} onOpenChange={setPalette} />
      <AnswersSheet open={answers} onOpenChange={setAnswers} />
    </div>
  )
}
