import type { Breakdown as BreakdownT } from '@/api/types'
import { StatusMark } from './common'

/** The detail without a repeat of the item's own name ("fresh graduates welcome; you have 0.5" -> "you have 0.5"). */
const detailOf = (name: string, detail: string) =>
  detail.toLowerCase().startsWith(name.toLowerCase()) ? detail.slice(name.length).replace(/^[;:,\s]+/, '') : detail

/** Quick-score breakdown: every point traced to a category, item and evidence. Sections split by dividers. */
export default function Breakdown({ data }: { data: BreakdownT }) {
  return (
    <div className="flex flex-col gap-4">
      {data.gates.length > 0 && (
        <div role="alert" className="rounded-lg bg-danger-bg px-4 py-3 text-[15px] text-danger">
          {data.capped && <p className="font-medium">Score capped at {data.total} (it would be {data.raw_total}) because a hard requirement failed:</p>}
          <ul className="mt-1 flex flex-col gap-1">
            {data.gates.map((g) => <li key={g.key} className="flex items-center gap-2"><StatusMark status="not_met" />{g.message}</li>)}
          </ul>
        </div>
      )}
      <div className="divide-y">
        {data.categories.map((c) => (
          <section key={c.key} className="py-4 first:pt-0" aria-label={c.label}>
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
              <h3 className="flex items-center gap-2 self-center font-semibold"><StatusMark status={c.status} />{c.label}</h3>
              <p className="text-sm tabular-nums text-muted-foreground">
                <span className="font-semibold text-foreground">{Math.round(c.points * 10) / 10}</span> of {c.max} points
                {(c.not_specified || c.note) && <span>: {c.not_specified ? 'not stated in the ad, full points' : c.note}</span>}
              </p>
            </div>
            {c.items.length > 0 && (
              <ul className="mt-2 flex flex-col gap-1.5 pl-6 text-[15px]">
                {c.items.map((i, idx) => (
                  <li key={idx} className="flex items-start gap-2" title={c.key.endsWith('_skills') ? undefined : i.evidence.join('\n')}>
                    <StatusMark status={i.status} className="mt-1" />
                    <span><span className="font-medium">{i.name}</span>{detailOf(i.name, i.detail) && <span className="text-muted-foreground"> {detailOf(i.name, i.detail)}</span>}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}
        {data.soft_skills && data.soft_skills.length > 0 && (
          <section className="py-4" aria-label="Soft skills">
            <h3 className="font-semibold">Soft skills <span className="font-normal text-muted-foreground">(listed, not scored)</span></h3>
            <p className="text-sm text-muted-foreground">Turn on “Score soft skills” in Settings → Scoring to count them.</p>
            <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1.5 pl-6 text-[15px]">
              {data.soft_skills.map((s) => (
                <li key={s.name} className="flex items-center gap-1.5">
                  <StatusMark status={s.status} />
                  <span className="font-medium">{s.name}</span>
                  <span className="text-muted-foreground">{s.status === 'met' ? s.detail : s.kind === 'preferred' ? 'preferred' : 'asked for'}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
      <p className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t pt-3 text-sm text-muted-foreground">
        <span className="flex items-center gap-1.5"><StatusMark status="met" /> met</span>
        <span className="flex items-center gap-1.5"><StatusMark status="partial" /> partly met</span>
        <span className="flex items-center gap-1.5"><StatusMark status="not_met" /> not met</span>
        <span className="flex items-center gap-1.5"><StatusMark status="not_specified" /> not in the ad (full points)</span>
        <span>Hover an item to see the line of the ad it came from.</span>
      </p>
    </div>
  )
}
