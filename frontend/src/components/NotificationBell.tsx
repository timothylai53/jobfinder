import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import type { NotificationRow } from '@/api/types'
import { cn } from '@/lib/utils'
import { formatDateTime } from '@/lib/score'

/** Bell with unread count; the panel lists recent notifications and links to what they are about. */
export default function NotificationBell() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  const q = useQuery({
    queryKey: ['notifications'],
    queryFn: () => api.get<{ unread: number; items: NotificationRow[] }>('/api/notifications'),
    refetchInterval: 30_000,
  })
  const read = useMutation({
    mutationFn: (id: number) => api.post(`/api/notifications/${id}/read`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
  const readAll = useMutation({
    mutationFn: () => api.post('/api/notifications/read-all'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
  useEffect(() => {
    const close = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  const unread = q.data?.unread ?? 0
  const items = q.data?.items ?? []

  return (
    <div ref={root} className="relative">
      <button
        onClick={() => setOpen(!open)}
        aria-label={unread ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open}
        className="relative rounded-md p-1.5 hover:bg-muted"
      >
        <Bell className="size-5" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-4 rounded-full bg-primary px-1 text-center text-[11px] leading-4 font-semibold text-primary-foreground">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute top-9 left-0 z-40 w-80 rounded-lg border bg-popover shadow-lg">
          <div className="flex items-center justify-between border-b px-3 py-2">
            <span className="font-semibold">Notifications</span>
            {unread > 0 && (
              <button className="text-sm text-primary hover:underline" onClick={() => readAll.mutate()}>Mark all read</button>
            )}
          </div>
          <ul className="max-h-96 overflow-y-auto">
            {items.length === 0 && <li className="px-3 py-4 text-sm text-muted-foreground">Nothing yet. New high-match jobs, follow-ups and source problems show up here.</li>}
            {items.map((n) => (
              <li key={n.id} className={cn('border-b last:border-0', !n.read && 'bg-accent/50')}>
                <Link
                  to={n.link || '#'}
                  onClick={() => {
                    if (!n.read) read.mutate(n.id)
                    setOpen(false)
                  }}
                  className="block px-3 py-2 text-sm hover:bg-muted"
                >
                  <span className={cn(!n.read && 'font-medium')}>{n.message}</span>
                  <span className="block text-xs text-muted-foreground">{formatDateTime(n.created_at)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
