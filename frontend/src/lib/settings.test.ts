import { describe, expect, it } from 'vitest'
import type { AutomationRunRow } from '@/api/types'
import { ruleSentence } from './filters'
import { lastRunSummary } from './runlog'

describe('filter rules in plain words', () => {
  it('reads each rule as one sentence', () => {
    expect(ruleSentence({ type: 'title_contains', value: 'Senior, Lead, Manager' })).toBe('Hide jobs whose title contains Senior, Lead or Manager.')
    expect(ruleSentence({ type: 'title_must_contain_one_of', value: 'software' })).toBe('Hide jobs whose title has none of software.')
    expect(ruleSentence({ type: 'company_equals', value: 'Syarikat Contoh Bhd' })).toBe('Hide jobs from Syarikat Contoh Bhd.')
    expect(ruleSentence({ type: 'min_years_over', value: ' 3 ' })).toBe('Hide jobs asking for more than 3 years.')
    expect(ruleSentence({ type: 'min_salary_below', value: '3000' })).toBe('Hide jobs paying under RM 3000 (jobs with no salary shown stay).')
    expect(ruleSentence({ type: 'keyword_in_jd', value: 'night shift, , weekends' })).toBe('Hide jobs whose ad mentions night shift or weekends.')
    expect(ruleSentence({ type: 'title_contains', value: '' })).toBe('Hide jobs whose title contains ….')
  })
})

const run = (over: Partial<AutomationRunRow>): AutomationRunRow => ({
  id: 1, automation_key: 'fetch_jobs', trigger: 'manual', started_at: '2026-11-13T03:10:00', finished_at: null, result: 'ok',
  items_processed: 0, message: '', error: '', ...over,
})
const detail = (source: string, status: 'ok' | 'error' | 'skipped', n: number) => ({
  source, status, profiles: [], cap: null, fetched: n, new: n, merged: 0, hidden: 0, requests: 1, notes: [], error: '',
})

describe('last run in one line', () => {
  it('sums a fetch over its sources, names problems, and never ends in a dangling colon', () => {
    expect(lastRunSummary(run({ details: [detail('jobstreet', 'ok', 5), detail('indeed', 'error', 0), detail('glassdoor', 'skipped', 0)] })))
      .toBe('2 sources, 5 new jobs, 1 with problems')
    expect(lastRunSummary(run({ details: [detail('jobstreet', 'ok', 1)] }))).toBe('1 source, 1 new job')
    expect(lastRunSummary(run({ automation_key: 'score_new_jobs', message: 'scored 13 new jobs\nmore' }))).toBe('Scored 13 new jobs')
    expect(lastRunSummary(run({ message: '' }))).toBe('Nothing to do')
    expect(lastRunSummary(run({ result: 'error', error: 'RuntimeError: boom' }))).toBe('RuntimeError: boom')
    expect(lastRunSummary(run({ result: 'running' }))).toBe('Running now')
  })
})

describe('score check wording', () => {
  it('says how often the score matched, and how it missed', async () => {
    const { agreementSentence, missSentence } = await import('./scoreCheck')
    expect(agreementSentence({ rated: 0, about_right: 0, agree_pct: null })).toBe('No jobs rated yet.')
    expect(agreementSentence({ rated: 10, about_right: 7, agree_pct: 70 })).toBe('The score felt about right for 7 of 10 jobs you rated (70%).')
    expect(agreementSentence({ rated: 1, about_right: 1, agree_pct: 100 })).toBe('The score felt about right for 1 of 1 job you rated (100%).')
    expect(missSentence({ too_high: 3, too_low: 2 })).toBe('It was too high 3 times and too low twice.')
    expect(missSentence({ too_high: 1, too_low: 0 })).toBe('It was too high once.')
    expect(missSentence({ too_high: 0, too_low: 0 })).toBe('')
  })
})
