import { describe, expect, it } from 'vitest'
import type { Breakdown, Dashboard } from '@/api/types'
import { formatDate, formatDateTime } from './score'
import { isFirstRun, nextSteps, setupSteps } from './today'
import { safeHttpUrl } from './url'
import { gapNote, gaps, missingTitle, primaryStep, scoreVerdict } from './verdict'

const dash = (over: Partial<Dashboard> = {}): Dashboard => ({
  status_counts: { Saved: 0, Applied: 0, Interview: 0, Offer: 0, Rejected: 0, Withdrawn: 0 },
  applications_per_week: [], response_rate: null, high_match_jobs: [], high_match_threshold: 70,
  unread_notifications: 0, follow_ups_due: 0, total_jobs: 0, sources: [], ready_to_apply: [], saved_without_resume: [], snoozed: {},
  ...over,
})

describe('next steps', () => {
  it('is empty when there is nothing to do', () => {
    expect(nextSteps(dash(), [])).toEqual([])
  })
  it('lists real state, most urgent first, each linking to where to act', () => {
    const steps = nextSteps(dash({
      follow_ups_due: 1,
      ready_to_apply: [{ job_id: 4, title: 'Junior Dev', company: 'Contoh Sdn Bhd', document_id: 9, version: 1 }],
      high_match_jobs: [{ id: 1, title: 'A', company: 'X', score: 91 }, { id: 2, title: 'B', company: 'Y', score: 74 }, { id: 3, title: 'C', company: 'Z', score: 70 }],
      saved_without_resume: [{ job_id: 5, title: 'QA', company: 'Kedai Contoh' }],
      sources: [{ key: 'jobstreet', label: 'JobStreet', status: 'paused', note: '', paused_until: null, last_run_at: null }],
    }), [{ key: 'preferred_locations', label: 'preferred locations', fix: '/settings?section=locations', hint: '' }])
    expect(steps.map((s) => [s.text, s.to])).toEqual([
      ['1 follow-up due', '/tracker'],
      ['Resume v1 ready for Junior Dev, Contoh Sdn Bhd', '/jobs/4'],
      ['3 new jobs scored 70+', '/jobs'],
      ['No resume yet for QA, Kedai Contoh', '/jobs/5'],
      ['Profile missing preferred locations', '/settings?section=locations'],
      ['JobStreet needs attention', '/settings?section=sources'],
    ])
  })
  it('marks job steps so they can be hidden, and leaves snoozed steps out', () => {
    const d = dash({
      ready_to_apply: [{ job_id: 4, title: 'Junior Dev', company: 'X', document_id: 9, version: 1 }],
      saved_without_resume: [{ job_id: 5, title: 'QA', company: 'Y' }],
      high_match_jobs: [{ id: 1, title: 'A', company: 'X', score: 91 }, { id: 2, title: 'B', company: 'Y', score: 74 }],
      follow_ups_due: 2,
    })
    expect(nextSteps(d, []).map((s) => [s.key, s.jobId])).toEqual([
      ['follow-ups', undefined], ['ready-4', 4], ['high-match-1-2', undefined], ['tailor-5', 5]])
    d.snoozed = { 'tailor-5': '2999-01-01', 'high-match-1-2': '2999-01-01' }
    expect(nextSteps(d, []).map((s) => s.key)).toEqual(['follow-ups', 'ready-4'])
    d.high_match_jobs.push({ id: 3, title: 'C', company: 'Z', score: 80 }) // a new match: the old snooze no longer covers it
    expect(nextSteps(d, []).map((s) => s.key)).toContain('high-match-1-2-3')
  })
  it('names a single high match and links straight to it', () => {
    const [s] = nextSteps(dash({ high_match_jobs: [{ id: 7, title: 'Dev', company: 'X', score: 88 }] }), [])
    expect([s.text, s.to]).toEqual(['New job scored 88: Dev, X', '/jobs/7'])
  })
})

describe('first run', () => {
  it('shows the checklist until both profile and bank exist', () => {
    expect(isFirstRun({ profileFilled: false, bankCount: 3 })).toBe(true)
    expect(isFirstRun({ profileFilled: true, bankCount: 0 })).toBe(true)
    expect(isFirstRun({ profileFilled: true, bankCount: 2 })).toBe(false)
    expect(setupSteps({ profileFilled: true, bankCount: 0, jobCount: 0 }).map((s) => s.done)).toEqual([true, false, false])
  })
})

const breakdown = (over: Partial<Breakdown> = {}): Breakdown => ({
  total: 95, raw_total: 95, capped: false, gates: [], required_skills: [], preferred_skills: [],
  categories: [
    { key: 'required_skills', label: 'Required skills', points: 45, max: 45, status: 'met', not_specified: false, note: '',
      items: ['Python', 'SQL', 'React', 'Git'].map((name) => ({ name, status: 'met' as const, detail: '', evidence: [] })) },
    { key: 'education', label: 'Education', points: 5, max: 10, status: 'partial', not_specified: false, note: '',
      items: [{ name: 'Degree or higher', status: 'partial', detail: 'you have Degree (in progress), from B4', evidence: [] }] },
  ],
  ...over,
})

describe('score verdict', () => {
  it('says how strong the match is and why, in one sentence', () => {
    expect(scoreVerdict(breakdown())).toEqual({ tone: 'strong', text: 'Strong match: all 4 required skills; degree still in progress.' })
  })
  it('counts partial skill matches and names language and years gaps', () => {
    const b = breakdown({ total: 58 })
    b.categories[0].items[3].status = 'not_met'
    b.categories.push({ key: 'language_location', label: 'Language + location', points: 0, max: 10, status: 'not_met', not_specified: false,
      note: '', items: [{ name: 'Mandarin (required)', status: 'not_met', detail: '', evidence: [] }] })
    expect(scoreVerdict(b).text).toBe('Partial match: 3 of 4 required skills; degree still in progress; needs Mandarin.')
  })
  it('puts gates, summary-only and low confidence first', () => {
    expect(scoreVerdict(breakdown({ gates: [{ key: 'years', message: 'Requires 6 years; you have 0.5 (short by 5.5)' }] })).text)
      .toBe('Blocked by a hard requirement: requires 6 years; you have 0.5 (short by 5.5).')
    expect(scoreVerdict(breakdown(), { summaryOnly: true }).tone).toBe('rough')
    expect(scoreVerdict(breakdown(), { lowConfidence: 'No recognised skills in the JD' }).text).toBe('Low confidence: no recognised skills in the JD.')
  })
  it('lists only the partial and missing items as gaps', () => {
    expect(gaps(breakdown()).map((g) => g.item.name)).toEqual(['Degree or higher'])
  })
  it('explains each gap in plain words', () => {
    expect(gapNote('required_skills', 'Required skills', 'not in Experience Bank or profile')).toBe('Required skill, not in your bank yet')
    expect(gapNote('preferred_skills', 'Preferred skills', 'none of these in Experience Bank or profile')).toBe('Nice to have, not in your bank yet')
    expect(gapNote('required_skills', 'Required skills', 'equivalent: Vue, from B3')).toBe('Required skill, close match: Vue, from B3')
    expect(gapNote('education', 'Education', 'you have Degree (in progress)')).toBe('Education: you have Degree (in progress)')
  })
  it('titles the gaps in plain words', () => {
    const allMet = breakdown()
    allMet.categories = [allMet.categories[0]]
    expect(missingTitle(allMet)).toBe('Nothing missing')
    expect(missingTitle(breakdown())).toBe("You're missing 1 requirement")
    const b = breakdown()
    b.categories[0].items[2].status = 'not_met'
    b.categories[0].items[3].status = 'not_met'
    expect(missingTitle(b)).toBe("You're missing 2 skills and 1 other requirement")
    b.categories.pop()
    expect(missingTitle(b)).toBe("You're missing 2 skills")
  })
})

describe('primary action', () => {
  it('follows the job: save, tailor, download, mark as applied, then nothing', () => {
    expect(primaryStep({ tracked: false, hasResume: false, downloaded: false })).toBe('save')
    expect(primaryStep({ tracked: true, status: 'Saved', hasResume: false, downloaded: false })).toBe('tailor')
    expect(primaryStep({ tracked: true, status: 'Saved', hasResume: true, downloaded: false })).toBe('download')
    expect(primaryStep({ tracked: true, status: 'Saved', hasResume: true, downloaded: true })).toBe('mark_applied')
    expect(primaryStep({ tracked: true, status: 'Interview', hasResume: true, downloaded: true })).toBe('done')
  })
})

describe('dates', () => {
  it('uses one format everywhere', () => {
    expect(formatDate('2026-11-15')).toBe('15 Nov 2026')
    expect(formatDateTime('2026-11-15T22:48:40')).toBe('15 Nov 2026, 10:48 pm')
    expect(formatDateTime('2026-11-15T00:05:00')).toBe('15 Nov 2026, 12:05 am')
    expect(formatDate('')).toBe('')
  })
})

describe('untrusted links', () => {
  it('only plain http(s) addresses become links', () => {
    expect(safeHttpUrl('https://my.jobstreet.com/job/1')).toBe('https://my.jobstreet.com/job/1')
    expect(safeHttpUrl('javascript:alert(1)')).toBeNull()
    expect(safeHttpUrl(' JavaScript:alert(1)')).toBeNull()
    expect(safeHttpUrl('data:text/html,<script>alert(1)</script>')).toBeNull()
    expect(safeHttpUrl('file:///C:/Windows')).toBeNull()
    expect(safeHttpUrl('')).toBeNull()
  })
})
