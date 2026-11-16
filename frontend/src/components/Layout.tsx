import { useQuery } from '@tanstack/react-query'
import { Briefcase, FileText, GraduationCap, KanbanSquare, Settings, Sun, Timer } from 'lucide-react'
import { useEffect } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import type { ExperienceItem, Profile } from '@/api/types'
import { SETUP_DONE_KEY } from '@/pages/Setup'
import { api } from '@/api/client'
import { cn } from '@/lib/utils'
import NotificationBell from './NotificationBell'

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
          'flex items-center gap-2.5 rounded-md px-2.5 text-foreground/80 transition-colors hover:bg-muted hover:text-foreground',
          small ? 'py-1.5 text-sm' : 'py-2 text-[15px]',
          isActive && 'bg-accent font-medium text-accent-foreground hover:bg-accent hover:text-accent-foreground',
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

  return (
    <div className="flex min-h-screen bg-fog">
      <a href="#main" className="sr-only z-50 rounded bg-background px-3 py-2 focus:not-sr-only focus:fixed focus:top-2 focus:left-2">Skip to content</a>
      <aside className="sticky top-0 z-30 flex h-screen w-52 shrink-0 flex-col border-r bg-background px-3 py-4">
        <div className="mb-5 flex items-center justify-between px-2.5">
          <span className="text-lg font-semibold tracking-tight">JobFinder</span>
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
            <span className="text-red-700">Backend not reachable. Is start.bat running?</span>
          ) : (
            'Runs on this laptop only'
          )}
        </p>
      </aside>
      <main id="main" className="min-w-0 flex-1 px-8 py-7">
        <div className="mx-auto max-w-[88rem]">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
