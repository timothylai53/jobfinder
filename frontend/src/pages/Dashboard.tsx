import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Circle, Clock, EyeOff, ListTodo } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import type { Dashboard as DashboardT, ExperienceItem, Profile } from '@/api/types'
import { ErrorText, PageHeader } from '@/components/common'
import ImportJobDialog from '@/components/ImportJobDialog'
import { useToast } from '@/components/Toast'
import { useProfileStatus } from '@/components/ProfileGaps'
import { Button } from '@/components/ui/button'
import { formatDate, formatDateTime } from '@/lib/score'
import { isFirstRun, nextSteps, setupSteps, type NextStep } from '@/lib/today'
import { cn } from '@/lib/utils'

/** Today: what to do next, then how the search is going. */
export default function Dashboard() {
  const q = useQuery({ queryKey: ['dashboard'], queryFn: () => api.get<DashboardT>('/api/dashboard') })
  const profile = useQuery({ queryKey: ['profile'], queryFn: () => api.get<Profile>('/api/profile') })
  const bank = useQuery({ queryKey: ['experience'], queryFn: () => api.get<ExperienceItem[]>('/api/experience') })
  const status = useProfileStatus()
  const d = q.data
  const loaded = d && profile.data && bank.data
  const state = { profileFilled: !!profile.data?.name, bankCount: bank.data?.length ?? 0, jobCount: d?.total_jobs ?? 0 }
  const firstRun = loaded && isFirstRun(state)

  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="Today" lead={formatDate(new Date().toISOString())}>
        <ImportJobDialog variant="outline" />
      </PageHeader>
      <ErrorText error={q.error || profile.error || bank.error} />
      {!loaded ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : firstRun ? (
        <FirstRun steps={setupSteps(state)} />
      ) : (
        <>
          <NextSteps steps={nextSteps(d, status.data?.missing ?? [])} />
          <Stats d={d} />
          <WeeklyChart weeks={d.applications_per_week} />
          <SourceLine sources={d.sources} />
        </>
      )}
    </div>
  )
}

function NextSteps({ steps }: { steps: NextStep[] }) {
  const qc = useQueryClient()
  const toast = useToast()
  const refresh = () => { for (const k of [['dashboard'], ['jobs']]) qc.invalidateQueries({ queryKey: k }) }
  const snooze = useMutation({
    mutationFn: (s: NextStep) => api.post('/api/dashboard/snooze', { key: s.key, days: 3 }),
    onSuccess: (_d, s) => {
      refresh()
      toast({ message: 'Snoozed for 3 days.', undo: () => api.del(`/api/dashboard/snooze/${encodeURIComponent(s.key)}`).then(refresh) })
    },
  })
  const notInterested = useMutation({
    mutationFn: (s: NextStep) => api.patch(`/api/jobs/${s.jobId}`, { hidden: true, hidden_reason: 'Not interested' }),
    onSuccess: (_d, s) => {
      refresh()
      toast({ message: 'Job hidden: not interested.', undo: () => api.patch(`/api/jobs/${s.jobId}`, { hidden: false }).then(refresh) })
    },
  })
  return (
    <section aria-labelledby="next-steps">
      <h2 id="next-steps" className="mb-3 text-lg font-semibold">Next steps</h2>
      <ErrorText error={snooze.error || notInterested.error} />
      {steps.length === 0 ? (
        <div className="rounded-xl border bg-background px-5 py-6">
          <p className="font-medium">Nothing waiting on you.</p>
          <p className="mt-1 text-muted-foreground">New matches and follow-ups show up here. Fetch jobs or import one to keep going.</p>
          <Button asChild variant="outline" className="mt-4"><Link to="/jobs">Go to jobs</Link></Button>
        </div>
      ) : (
        <ol className="divide-y rounded-xl border bg-background">
          {steps.map((s, i) => (
            <li key={s.key} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-5 py-3">
              {s.tone === 'fix'
                ? <AlertTriangle role="img" className="size-[18px] shrink-0 text-attention" aria-label="Needs fixing" />
                : <ListTodo className="size-[18px] shrink-0 text-muted-foreground" aria-hidden />}
              <span className="min-w-0 flex-1 basis-64 text-[15px]">{s.text}</span>
              <div className="ml-auto flex items-center gap-1">
                {s.jobId !== undefined && (
                  <Button size="sm" variant="ghost" className="text-muted-foreground" disabled={notInterested.isPending}
                    aria-label={`Not interested: ${s.text}`} onClick={() => notInterested.mutate(s)}>
                    <EyeOff className="size-4" aria-hidden /> Not interested
                  </Button>
                )}
                <Button size="sm" variant="ghost" className="text-muted-foreground" disabled={snooze.isPending}
                  aria-label={`Snooze for 3 days: ${s.text}`} onClick={() => snooze.mutate(s)}>
                  <Clock className="size-4" aria-hidden /> Snooze 3 days
                </Button>
                <Button asChild size="sm" variant={i === 0 ? 'default' : 'outline'} className="ml-1">
                  <Link to={s.to} aria-label={`${s.action}: ${s.text}`}>{s.action}</Link>
                </Button>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function Stats({ d }: { d: DashboardT }) {
  const items: [string, string | number][] = [
    ['Saved', d.status_counts.Saved ?? 0],
    ['Applied', d.status_counts.Applied ?? 0],
    ['Interview', d.status_counts.Interview ?? 0],
    ['Offer', d.status_counts.Offer ?? 0],
    ['Response rate', d.response_rate === null ? '–' : `${d.response_rate}%`],
  ]
  return (
    <section aria-label="Applications so far">
      <Link to="/tracker" className="group flex flex-wrap rounded-xl border bg-background transition-colors hover:border-primary/40">
        {items.map(([label, value], i) => (
          <div key={label} className={cn('min-w-28 flex-1 px-5 py-3.5', i > 0 && 'border-l')}>
            <div className="text-sm text-muted-foreground">{label}</div>
            <div className="text-2xl font-semibold tabular-nums">{value}</div>
          </div>
        ))}
      </Link>
    </section>
  )
}

function WeeklyChart({ weeks }: { weeks: DashboardT['applications_per_week'] }) {
  const max = Math.max(1, ...weeks.map((w) => w.count))
  const total = weeks.reduce((n, w) => n + w.count, 0)
  return (
    <section aria-labelledby="per-week" className="max-w-3xl">
      <h2 id="per-week" className="text-lg font-semibold">Applications per week</h2>
      <p className="mb-3 text-sm text-muted-foreground">{total} in the last {weeks.length} weeks</p>
      <div className="flex h-32 items-end gap-3" role="img" aria-label={weeks.map((w) => `week of ${formatDate(w.week_start)}: ${w.count}`).join(', ')}>
        {weeks.map((w) => (
          <div key={w.week_start} className="flex flex-1 flex-col items-center gap-1">
            <span className="text-sm tabular-nums text-muted-foreground">{w.count || ''}</span>
            <div className="w-full rounded-t bg-primary/75" style={{ height: `${(w.count / max) * 88}px`, minHeight: w.count ? 4 : 1 }} />
          </div>
        ))}
      </div>
      <div className="mt-1 flex gap-3 border-t pt-1">
        {weeks.map((w) => <span key={w.week_start} className="flex-1 text-center text-[13px] text-muted-foreground">{formatDate(w.week_start).replace(/ \d{4}$/, '')}</span>)}
      </div>
    </section>
  )
}

function SourceLine({ sources }: { sources: DashboardT['sources'] }) {
  const ok = sources.filter((s) => s.status === 'ok').map((s) => s.label)
  const off = sources.filter((s) => s.status === 'disabled').map((s) => s.label)
  const bad = sources.filter((s) => s.status === 'paused' || s.status === 'error')
  return (
    <p className="text-sm text-muted-foreground">
      Job sources:{' '}
      {ok.length > 0 && <span>{ok.join(', ')} ready</span>}
      {bad.map((s) => (
        <span key={s.key} className="text-attention">
          {'; '}{s.label} {s.status === 'paused' && s.paused_until ? `paused until ${formatDateTime(s.paused_until)}` : 'had an error'}
        </span>
      ))}
      {off.length > 0 && <span>; {off.join(', ')} off</span>}
      {'. '}
      <Link to="/settings?section=sources" className="text-foreground underline underline-offset-2">Manage sources</Link>
    </p>
  )
}

function FirstRun({ steps }: { steps: ReturnType<typeof setupSteps> }) {
  const next = steps.find((s) => !s.done)
  return (
    <section aria-labelledby="get-started" className="max-w-3xl">
      <h2 id="get-started" className="text-lg font-semibold">Get started in three steps</h2>
      <p className="mb-4 text-muted-foreground">Scores and AI only ever use what you add here.</p>
      <ol className="divide-y rounded-xl border bg-background">
        {steps.map((s, i) => (
          <li key={s.key} className="flex items-start gap-4 px-5 py-4">
            {s.done
              ? <CheckCircle2 role="img" className="mt-0.5 size-5 shrink-0 text-primary" aria-label="Done" />
              : <Circle role="img" className="mt-0.5 size-5 shrink-0 text-muted-foreground" aria-label="To do" />}
            <div className="min-w-0 flex-1">
              <p className={cn('font-medium', s.done && 'text-muted-foreground line-through decoration-1')}>{i + 1}. {s.title}</p>
              <p className="text-sm text-muted-foreground">{s.detail}</p>
            </div>
            {!s.done && (
              <Button asChild size="sm" variant={s === next ? 'default' : 'outline'}><Link to={s.to}>{s.action}</Link></Button>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}
