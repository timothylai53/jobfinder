import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import { STATUSES, type Dashboard as DashboardT } from '@/api/types'
import { ErrorText, PageHeader, ScoreBadge } from '@/components/common'
import ImportJobDialog from '@/components/ImportJobDialog'
import ProfileGaps from '@/components/ProfileGaps'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate } from '@/lib/score'

function Stat({ label, value, to }: { label: string; value: string | number; to?: string }) {
  const body = (
    <div className="rounded-lg border bg-background p-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold tabular-nums">{value}</div>
    </div>
  )
  return to ? <Link to={to}>{body}</Link> : body
}

export default function Dashboard() {
  const q = useQuery({ queryKey: ['dashboard'], queryFn: () => api.get<DashboardT>('/api/dashboard') })
  const d = q.data
  const maxWeek = Math.max(1, ...(d?.applications_per_week.map((w) => w.count) ?? [1]))
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Dashboard">
        <ImportJobDialog />
      </PageHeader>
      <ProfileGaps />
      <ErrorText error={q.error} />
      {d && (
        <>
          <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
            {STATUSES.map((s) => (
              <Stat key={s} label={s} value={d.status_counts[s] ?? 0} to="/tracker" />
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Response rate" value={d.response_rate === null ? '–' : `${d.response_rate}%`} />
            <Stat label="Follow-ups due" value={d.follow_ups_due} to="/tracker" />
            <Stat label="Jobs (not hidden)" value={d.total_jobs} to="/jobs" />
            <Stat label="Unread notifications" value={d.unread_notifications} />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Applications per week</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex h-36 items-end gap-2">
                  {d.applications_per_week.map((w) => (
                    <div key={w.week_start} className="flex flex-1 flex-col items-center gap-1" title={`Week of ${formatDate(w.week_start)}: ${w.count}`}>
                      <span className="text-xs tabular-nums">{w.count || ''}</span>
                      <div className="w-full rounded-t bg-primary/80" style={{ height: `${(w.count / maxWeek) * 100}px`, minHeight: w.count ? 4 : 1 }} />
                      <span className="text-[10px] text-muted-foreground">{w.week_start.slice(5)}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>New high-match jobs (≥ {d.high_match_threshold}, last 7 days, not tracked)</CardTitle>
              </CardHeader>
              <CardContent>
                {d.high_match_jobs.length === 0 ? (
                  <p className="text-sm text-muted-foreground">None right now.</p>
                ) : (
                  <ul className="flex flex-col gap-1">
                    {d.high_match_jobs.map((j) => (
                      <li key={j.id} className="flex items-center gap-2 text-sm">
                        <ScoreBadge score={j.score} />
                        <Link to={`/jobs/${j.id}`} className="hover:underline">
                          {j.title}
                        </Link>
                        <span className="text-muted-foreground">{j.company}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
          <Card>
            <CardHeader>
              <CardTitle>Sources</CardTitle>
            </CardHeader>
            <CardContent className="text-sm">
              <ul className="flex flex-col gap-1.5">
                {d.sources.map((s) => (
                  <li key={s.key} className="flex flex-wrap items-baseline gap-x-2 text-[15px]">
                    <span className="w-24 font-medium">{s.label}</span>
                    <span className={
                      s.status === 'ok' ? 'rounded bg-accent px-1.5 text-xs text-accent-foreground'
                        : s.status === 'paused' ? 'rounded bg-red-100 px-1.5 text-xs text-red-800'
                          : s.status === 'error' ? 'rounded bg-attention-bg px-1.5 text-xs text-attention'
                            : 'rounded bg-muted px-1.5 text-xs text-muted-foreground'}>
                      {s.status === 'paused' && s.paused_until ? `paused until ${new Date(s.paused_until).toLocaleString('en-MY')}` : s.status}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground" title={s.note}>{s.note}</span>
                  </li>
                ))}
              </ul>
              <Link to="/settings?section=sources" className="mt-2 inline-block text-sm text-primary underline">Manage sources</Link>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
