/** Score check: my verdict on a job's score, and the report built from those verdicts. */

export type Rating = 'too_high' | 'about_right' | 'too_low'

export interface ScoreRating {
  job_id: number
  rating: Rating
  note: string
  score_at: number | null
  created_at: string
  updated_at: string
}

interface Summary { rated: number; too_high: number; about_right: number; too_low: number; agree_pct: number | null }

export interface ScoreCheckReport extends Summary {
  bands: (Summary & { band: string })[]
  misses: (ScoreRating & { title: string; company: string; score_now: number | null })[]
}

export const RATING_LABEL: Record<Rating, string> = { too_high: 'Too high', about_right: 'About right', too_low: 'Too low' }

/** "The score felt about right for 7 of 10 jobs you rated (70%)." */
export function agreementSentence(r: Pick<Summary, 'rated' | 'about_right' | 'agree_pct'>): string {
  if (r.rated === 0) return 'No jobs rated yet.'
  const jobs = r.rated === 1 ? 'job' : 'jobs'
  return `The score felt about right for ${r.about_right} of ${r.rated} ${jobs} you rated (${r.agree_pct}%).`
}

/** "Too high by your judgement 3 times, too low twice." (empty when the score was never off). */
export function missSentence(r: Pick<Summary, 'too_high' | 'too_low'>): string {
  const times = (n: number) => (n === 1 ? 'once' : n === 2 ? 'twice' : `${n} times`)
  const parts = [r.too_high ? `too high ${times(r.too_high)}` : '', r.too_low ? `too low ${times(r.too_low)}` : ''].filter(Boolean)
  return parts.length ? `It was ${parts.join(' and ')}.` : ''
}
