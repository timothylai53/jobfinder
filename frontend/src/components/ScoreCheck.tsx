import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/api/client'
import { ErrorText, ScoreBadge } from '@/components/common'
import { Button } from '@/components/ui/button'
import { formatDate } from '@/lib/score'
import { agreementSentence, missSentence, RATING_LABEL, type ScoreCheckReport } from '@/lib/scoreCheck'

/** Settings → Score check: how often the quick score matches my own judgement, and where it doesn't. */
export default function ScoreCheck() {
  const q = useQuery({ queryKey: ['score-check'], queryFn: () => api.get<ScoreCheckReport>('/api/score-check') })
  const r = q.data
  if (!r) return <ErrorText error={q.error} />
  if (r.rated === 0) {
    return (
      <div className="rounded-lg border bg-background px-5 py-5">
        <p>Rate a few jobs' scores ("Does this score feel right?" on each job) and the results show up here.</p>
        <Button asChild variant="outline" className="mt-4"><Link to="/jobs">Go to jobs</Link></Button>
      </div>
    )
  }
  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-lg border bg-background px-5 py-4">
        <p className="text-[17px]">{agreementSentence(r)}</p>
        {missSentence(r) && <p className="mt-1 text-muted-foreground">{missSentence(r)}</p>}
      </div>

      <section aria-labelledby="by-band">
        <h3 id="by-band" className="mb-2 font-semibold">By score band</h3>
        <div className="relative overflow-x-auto rounded-lg border bg-background">
          <table className="w-full text-[15px]">
            <thead className="border-b text-left text-sm text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Score when rated</th>
                {(['Rated', 'About right', 'Too high', 'Too low'] as const).map((h) => (
                  <th key={h} scope="col" className="px-4 py-2 text-right font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {r.bands.map((b) => (
                <tr key={b.band} className="border-t first:border-t-0">
                  <td className="px-4 py-2">{b.band}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{b.rated}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{b.rated ? `${b.about_right} (${b.agree_pct}%)` : '–'}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{b.rated ? b.too_high : '–'}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{b.rated ? b.too_low : '–'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="misses">
        <h3 id="misses" className="mb-2 font-semibold">Where the score missed</h3>
        {r.misses.length === 0 ? (
          <p className="text-muted-foreground">None so far: every job you rated felt about right.</p>
        ) : (
          <ul className="divide-y rounded-lg border bg-background">
            {r.misses.map((m) => (
              <li key={m.job_id} className="flex flex-wrap items-start gap-x-4 gap-y-1 px-4 py-3">
                <ScoreBadge score={m.score_at} />
                <div className="min-w-0 flex-1 basis-60">
                  <Link to={`/jobs/${m.job_id}?tab=score`} className="font-medium hover:underline">{m.title}</Link>
                  <span className="text-muted-foreground"> · {m.company}</span>
                  <p className="text-sm">
                    <span className="font-medium">{RATING_LABEL[m.rating]}</span>
                    {m.note && <span className="text-muted-foreground">: {m.note}</span>}
                  </p>
                </div>
                <span className="text-sm text-muted-foreground">
                  {m.score_now !== null && m.score_now !== m.score_at ? `now ${m.score_now} · ` : ''}{formatDate(m.updated_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="text-sm text-muted-foreground">
        <a href="/api/score-check.csv" className="text-foreground underline underline-offset-2">Download the ratings (CSV)</a>{' '}
        to look at them in a spreadsheet. Ratings are yours only; they never change the score by themselves.
      </p>
    </div>
  )
}
