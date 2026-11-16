/** The Today page's "Next steps", built from real state. Pure, so it is tested in today.test.ts. */
import type { Dashboard, ProfileStatus } from '@/api/types'

export interface NextStep {
  key: string
  text: string
  action: string
  to: string
  tone: 'act' | 'fix'
}

const plural = (n: number, one: string, many = one + 's') => `${n} ${n === 1 ? one : many}`

export function nextSteps(d: Dashboard, missing: ProfileStatus['missing']): NextStep[] {
  const out: NextStep[] = []
  if (d.follow_ups_due > 0) {
    out.push({ key: 'follow-ups', tone: 'act', to: '/tracker', action: 'Open tracker',
      text: `${plural(d.follow_ups_due, 'follow-up')} due` })
  }
  for (const r of d.ready_to_apply) {
    out.push({ key: `ready-${r.job_id}`, tone: 'act', to: `/jobs/${r.job_id}`, action: 'Mark as applied',
      text: `Resume v${r.version} ready for ${r.title}, ${r.company}` })
  }
  const highs = d.high_match_jobs.length
  if (highs > 0) {
    out.push({ key: 'high-match', tone: 'act', to: highs === 1 ? `/jobs/${d.high_match_jobs[0].id}` : '/jobs', action: 'Review',
      text: highs === 1
        ? `New job scored ${d.high_match_jobs[0].score}: ${d.high_match_jobs[0].title}, ${d.high_match_jobs[0].company}`
        : `${highs} new jobs scored ${d.high_match_threshold}+` })
  }
  for (const r of d.saved_without_resume) {
    out.push({ key: `tailor-${r.job_id}`, tone: 'act', to: `/jobs/${r.job_id}`, action: 'Tailor resume',
      text: `No resume yet for ${r.title}, ${r.company}` })
  }
  for (const m of missing) {
    out.push({ key: `profile-${m.key}`, tone: 'fix', to: m.fix, action: 'Add it', text: `Profile missing ${m.label}` })
  }
  const paused = d.sources.filter((s) => s.status === 'paused' || s.status === 'error')
  if (paused.length > 0) {
    out.push({ key: 'sources', tone: 'fix', to: '/settings?section=sources', action: 'Check sources',
      text: `${paused.map((s) => s.label).join(', ')} ${paused.length === 1 ? 'needs' : 'need'} attention` })
  }
  return out
}

export interface SetupStep {
  key: 'profile' | 'resume' | 'job'
  title: string
  detail: string
  to: string
  action: string
  done: boolean
}

/** First run: Profile -> Resume -> First job. Shown while the profile or the Experience Bank is empty. */
export function setupSteps(s: { profileFilled: boolean; bankCount: number; jobCount: number }): SetupStep[] {
  return [
    { key: 'profile', title: 'Fill in your profile', detail: 'Education, languages and where you want to work. Every score uses it.',
      to: '/settings?section=profile', action: 'Open profile', done: s.profileFilled },
    { key: 'resume', title: 'Upload your resume', detail: 'It becomes your Experience Bank: the only facts scores and AI may use.',
      to: '/resume', action: 'Upload resume', done: s.bankCount > 0 },
    { key: 'job', title: 'Add your first job', detail: 'Paste a job ad, or fetch jobs from your search profiles.',
      to: '/jobs', action: 'Go to jobs', done: s.jobCount > 0 },
  ]
}

export const isFirstRun = (s: { profileFilled: boolean; bankCount: number }) => !s.profileFilled || s.bankCount === 0
