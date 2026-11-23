import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import type { SkillGapRow } from '@/api/types'
import { ErrorText, PageHeader, ScoreBadge } from '@/components/common'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

interface GapsResponse { scope: string; min_score: number; jobs_considered: number; gaps: SkillGapRow[]; soft_skills: SkillGapRow[] }

function GapList({ rows, max }: { rows: SkillGapRow[]; max: number }) {
  const [open, setOpen] = useState<string | null>(null)
  return (
    <ol className="flex flex-col divide-y rounded-lg border bg-card">
      {rows.map((g, i) => (
        <li key={g.skill} className="px-4 py-3">
          <button className="flex w-full flex-wrap items-center gap-x-3 gap-y-1 text-left sm:flex-nowrap" onClick={() => setOpen(open === g.skill ? null : g.skill)} aria-expanded={open === g.skill}>
            <span className="w-6 text-right text-sm text-muted-foreground tabular-nums">{i + 1}</span>
            <span className="min-w-0 flex-1 font-medium sm:w-64 sm:flex-none sm:shrink-0">{g.skill}</span>
            <span className="order-last flex h-3 w-full overflow-hidden rounded-full bg-muted sm:order-none sm:w-auto sm:flex-1" aria-hidden>
              <span className="bg-chart-4" style={{ width: `${(g.required / max) * 100}%` }} />
              <span className="bg-chart-1" style={{ width: `${(g.preferred / max) * 100}%` }} />
            </span>
            <span className="w-28 text-right text-sm tabular-nums sm:w-48">
              {g.required > 0 && <>required in {g.required}</>}
              {g.required > 0 && g.preferred > 0 && ', '}
              {g.preferred > 0 && <>preferred in {g.preferred}</>}
            </span>
          </button>
          {open === g.skill && (
            <ul className="mt-2 ml-9 flex flex-col gap-1 text-sm">
              {g.jobs.map((j) => (
                <li key={j.id} className="flex items-center gap-2">
                  <ScoreBadge score={j.score} />
                  <Link to={`/jobs/${j.id}`} className="hover:underline">{j.title}</Link>
                  <span className="text-muted-foreground">{j.company}</span>
                  <span className="text-xs text-muted-foreground">({j.kind})</span>
                </li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ol>
  )
}

export default function SkillGaps() {
  const [scope, setScope] = useState<'saved' | 'scored'>('saved')
  const [minScore, setMinScore] = useState(60)
  const q = useQuery({
    queryKey: ['skill-gaps', scope, minScore],
    queryFn: () => api.get<GapsResponse>(`/api/skill-gaps?scope=${scope}&min_score=${minScore}`),
  })
  const d = q.data
  const max = Math.max(1, ...(d?.gaps ?? []).map((g) => g.total))
  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="Skill gaps" lead="What to learn next: skills the jobs ask for that your Experience Bank and profile don't show yet." />
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex rounded-lg border bg-background p-0.5 text-[15px]">
          {(['saved', 'scored'] as const).map((s) => (
            <button key={s} onClick={() => setScope(s)} className={cn('rounded-md px-3 py-1', scope === s && 'bg-selected font-medium text-foreground')}>
              {s === 'saved' ? 'Jobs in my tracker' : 'All jobs scoring at least'}
            </button>
          ))}
        </div>
        {scope === 'scored' && (
          <Input type="number" min={0} max={100} className="w-20" aria-label="Minimum score" value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} />
        )}
        {d && <span className="text-sm text-muted-foreground">{d.jobs_considered} job(s) considered</span>}
      </div>
      <ErrorText error={q.error} />
      {d && d.gaps.length === 0 && (
        <p className="rounded-lg border border-dashed px-4 py-6 text-center text-muted-foreground">
          {d.jobs_considered === 0 ? (scope === 'saved' ? 'Save some jobs to your tracker to see what they ask for.' : 'No jobs at this score yet.') : 'No missing skills in these jobs. Nice.'}
        </p>
      )}
      {d && d.gaps.length > 0 && <GapList rows={d.gaps} max={max} />}
      {d && d.soft_skills.length > 0 && (
        <details className="rounded-lg border border-dashed bg-card px-4 py-3">
          <summary className="cursor-pointer font-medium">Soft skills asked for ({d.soft_skills.length}), not scored</summary>
          <p className="mt-1 text-sm text-muted-foreground">Listed apart because soft skills don't count toward the score unless you turn on “Score soft skills”.</p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {d.soft_skills.map((s) => <li key={s.skill} className="rounded-sm bg-secondary px-2 py-0.5 text-sm">{s.skill} · {s.total}</li>)}
          </ul>
        </details>
      )}
    </div>
  )
}
