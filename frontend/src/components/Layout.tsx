import { useQuery } from '@tanstack/react-query'
import { Briefcase, FileText, GraduationCap, KanbanSquare, LayoutDashboard, Settings, Timer } from 'lucide-react'
import { useEffect } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import type { ExperienceItem, Profile } from '@/api/types'
import { SETUP_DONE_KEY } from '@/pages/Setup'
import { api } from '@/api/client'
import { cn } from '@/lib/utils'
import NotificationBell from './NotificationBell'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/jobs', label: 'Jobs', icon: Briefcase },
  { to: '/tracker', label: 'Tracker', icon: KanbanSquare },
  { to: '/resume', label: 'Resume & Bank', icon: FileText },
  { to: '/skill-gaps', label: 'Skill gaps', icon: GraduationCap },
  { to: '/automations', label: 'Automations', icon: Timer },
  { to: '/settings', label: 'Settings', icon: Settings },
]

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
      <aside className="sticky top-0 z-30 flex h-screen w-52 shrink-0 flex-col border-r bg-background p-3">
        <div className="mb-4 flex items-center justify-between px-2">
          <span className="text-lg font-semibold">JobFinder</span>
          <NotificationBell />
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 rounded-md px-2 py-1.5 text-[15px] hover:bg-muted',
                  isActive && 'bg-accent font-medium text-accent-foreground',
                )
              }
            >
              <Icon className="size-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto px-2 text-xs text-muted-foreground">
          {health.isError ? (
            <span className="text-red-600">Backend not reachable. Is start.bat running?</span>
          ) : (
            'Local only · nothing leaves this laptop'
          )}
        </div>
      </aside>
      <main className="min-w-0 flex-1 p-6">
        <Outlet />
      </main>
    </div>
  )
}
