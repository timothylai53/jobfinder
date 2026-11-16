import type { Breakdown as BreakdownT } from '@/api/types'
import { STATUS_ICON, STATUS_LABEL } from '@/lib/score'
import { ScoreBadge } from './common'

/** Quick-score breakdown: every point traced to a category, item and evidence. */
export default function Breakdown({ data }: { data: BreakdownT }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <ScoreBadge score={data.total} gated={data.gates.length > 0} />
        <span className="text-sm text-muted-foreground">
          {data.gates.length > 0 && data.capped
            ? `Raw ${data.raw_total} capped because a hard gate failed`
            : `Sum of categories: ${data.raw_total}`}
        </span>
      </div>
      {data.gates.length > 0 && (
        <div className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-900">
          {data.gates.map((g) => (
            <div key={g.key}>❌ Hard gate: {g.message}</div>
          ))}
        </div>
      )}
      {data.categories.map((c) => (
        <div key={c.key} className="rounded-md border bg-background">
          <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5 border-b px-3 py-2">
            <div className="font-medium whitespace-nowrap">
              {STATUS_ICON[c.status]} {c.label}
            </div>
            <div className="text-sm tabular-nums">
              <span className="font-semibold">{c.points}</span> / {c.max}
              <span className="ml-2 text-muted-foreground">{c.not_specified ? 'not specified' : c.note}</span>
            </div>
          </div>
          {c.items.length > 0 && (
            <ul className="divide-y text-sm">
              {c.items.map((i, idx) => (
                <li key={idx} className="flex gap-2 px-3 py-1.5" title={c.key.endsWith('_skills') ? undefined : i.evidence.join('\n')}>
                  <span aria-label={STATUS_LABEL[i.status]}>{STATUS_ICON[i.status]}</span>
                  <span className="font-medium">{i.name}</span>
                  <span className="text-muted-foreground">{i.detail}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
      {data.soft_skills && data.soft_skills.length > 0 && (
        <div className="rounded-md border border-dashed bg-background">
          <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-dashed px-3 py-2">
            <div className="font-medium">Soft skills (not scored)</div>
            <div className="text-sm text-muted-foreground">Turn on “Score soft skills” in Settings → Scoring to count them</div>
          </div>
          <ul className="flex flex-wrap gap-x-4 gap-y-1 px-3 py-2 text-sm">
            {data.soft_skills.map((s) => (
              <li key={s.name} className="flex gap-1.5">
                <span aria-label={STATUS_LABEL[s.status]}>{STATUS_ICON[s.status]}</span>
                <span className="font-medium">{s.name}</span>
                <span className="text-muted-foreground">{s.status === 'met' ? s.detail : s.kind === 'preferred' ? 'preferred' : 'asked for'}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs text-muted-foreground">
        ✅ met · ⚠️ partial · ❌ not met · ➖ not specified (full points). Hover an item to see the JD line it came from.
      </p>
    </div>
  )
}
