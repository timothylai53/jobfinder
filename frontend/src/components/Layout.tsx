import { useQuery } from '@tanstack/react-query'
import { Briefcase, FileText, GraduationCap, KanbanSquare, Menu, Settings, Sun, Timer, X } from 'lucide-react'
import { Suspense, useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import type { ExperienceItem, Profile } from '@/api/types'
import { SETUP_DONE_KEY } from '@/pages/Setup'
import { api } from '@/api/client'
import { cn } from '@/lib/utils'
import NotificationBell from './NotificationBell'
import { ToastProvider } from './Toast'
import { Button } from './ui/button'
import { LogoMark } from './common'

// The four places a job search happens, then the tools you visit now and then.
const MAIN = [
  { to: '/', label: 'Today', icon: Sun, end: true },
  { to: '/jobs', label: 'Jobs', icon: Briefcase },
  { to: '/tracker', label: 'Tracker', icon: KanbanSquare },
  { to: '/resume', label: 'Resume', icon: FileText },
]
const MORE = [
  { to: '/skill-gaps', label: 'Skill gaps', icon: GraduationCap },
  { to: '/automations', label: 'Automations', icon: Timer },
  { to: '/settings', label: 'Settings', icon: Settings },
]

function Item({ to, label, icon: Icon, end, small }: { to: string; label: string; icon: typeof Sun; end?: boolean; small?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-2.5 rounded-md px-2.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground',
          small ? 'py-1.5 text-sm' : 'py-2 text-[15px]',
          isActive && 'bg-selected font-medium text-foreground hover:bg-selected',
        )
      }
    >
      <Icon className={small ? 'size-4' : 'size-[18px]'} aria-hidden />
      {label}
    </NavLink>
  )
}

export default function Layout() {
  const health = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<{ ok: boolean }>('/api/health'),
    refetchInterval: 15_000,
  })
  // First run: an empty profile and an empty bank open the setup wizard (once, until finished or skipped).
  const navigate = useNavigate()
  const profile = useQuery({ queryKey: ['profile'], queryFn: () => api.get<Profile>('/api/profile') })
  const bank = useQuery({ queryKey: ['experience'], queryFn: () => api.get<ExperienceItem[]>('/api/experience') })
  useEffect(() => {
    let done = false
    try { done = localStorage.getItem(SETUP_DONE_KEY) === '1' } catch { /* storage blocked */ }
    if (!done && profile.data && bank.data && !profile.data.name && bank.data.length === 0) navigate('/setup')
  }, [profile.data, bank.data, navigate])

  // The narrow-window menu closes whenever a page is opened (adjusted while rendering, not in an effect).
  const { pathname } = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [seenPath, setSeenPath] = useState(pathname)
  if (pathname !== seenPath) {
    setSeenPath(pathname)
    setMenuOpen(false)
  }

  return (
    <ToastProvider>
    <div className="flex min-h-screen flex-col bg-fog md:flex-row">
      <a href="#main" className="sr-only z-50 rounded-md border bg-background px-3 py-2 focus:not-sr-only focus:fixed focus:top-2 focus:left-2">Skip to content</a>
      {/* Narrow windows: a top bar with the logo, the bell and a Menu button instead of the sidebar. */}
      <header className="sticky top-0 z-30 border-b bg-background md:hidden">
        <div className="flex items-center gap-2 px-4 py-2.5">
          <span className="flex flex-1 items-center gap-2 font-heading text-[18px] leading-none font-semibold tracking-[-0.01em]"><LogoMark />JobFinder</span>
          <NotificationBell />
          <Button variant="outline" size="sm" aria-expanded={menuOpen} aria-controls="mobile-menu" onClick={() => setMenuOpen((o) => !o)}>
            {menuOpen ? <X className="size-4" aria-hidden /> : <Menu className="size-4" aria-hidden />} Menu
          </Button>
        </div>
        {menuOpen && (
          <div id="mobile-menu" className="flex flex-col gap-0.5 border-t px-3 pt-2 pb-3">
            <nav aria-label="Main" className="flex flex-col gap-0.5">
              {MAIN.map((n) => <Item key={n.to} {...n} />)}
            </nav>
            <nav aria-label="Tools" className="mt-2 flex flex-col gap-0.5 border-t pt-2">
              {MORE.map((n) => <Item key={n.to} {...n} small />)}
            </nav>
          </div>
        )}
      </header>
      <aside className="sticky top-0 z-30 hidden h-screen w-52 shrink-0 flex-col border-r bg-background px-3 py-4 md:flex">
        <div className="mb-5 flex items-center justify-between px-2.5">
          <span className="flex items-center gap-2 font-heading text-[19px] leading-none font-semibold tracking-[-0.01em]"><LogoMark />JobFinder</span>
          <NotificationBell />
        </div>
        <nav aria-label="Main" className="flex flex-col gap-0.5">
          {MAIN.map((n) => <Item key={n.to} {...n} />)}
        </nav>
        <nav aria-label="Tools" className="mt-auto flex flex-col gap-0.5 border-t pt-3">
          {MORE.map((n) => <Item key={n.to} {...n} small />)}
        </nav>
        <p className="mt-3 px-2.5 text-[13px] leading-snug text-muted-foreground">
          {health.isError ? (
            <span className="text-danger">Backend not reachable. Is start.bat running?</span>
          ) : (
            'Runs on this laptop only'
          )}
        </p>
      </aside>
      <main id="main" className="min-w-0 flex-1 px-4 py-5 sm:px-8 sm:py-7">
        <div className="mx-auto max-w-[88rem]">
          <Suspense fallback={<p className="text-muted-foreground">Loading…</p>}>
            <Outlet />
          </Suspense>
        </div>
      </main>
    </div>
    </ToastProvider>
  )
}
