import { describe, expect, it } from 'vitest'
import { formatSalary, parseList, scoreTone, sortJobs } from './score'

describe('scoreTone', () => {
  it('accent for good matches, amber for partial, neutral for weak, red only for a failed gate', () => {
    expect(scoreTone(85)).toContain('bg-accent')
    expect(scoreTone(55)).toContain('attention')
    expect(scoreTone(30)).not.toMatch(/danger|accent|primary|attention/)
    expect(scoreTone(85, true)).toContain('danger')
    expect(scoreTone(null)).toContain('muted')
  })
})

describe('parseList', () => {
  it('splits, trims and de-duplicates case-insensitively', () => {
    expect(parseList('Kuala Lumpur, selangor,, Selangor\nRemote')).toEqual(['Kuala Lumpur', 'selangor', 'Remote'])
  })
})

describe('formatSalary', () => {
  it('formats ranges and singles', () => {
    expect(formatSalary(3000, 4500, 'MYR')).toBe('MYR 3,000–4,500')
    expect(formatSalary(null, 4000, '')).toBe('RM 4,000')
    expect(formatSalary(null, null, 'MYR')).toBe('')
  })
})

describe('sortJobs', () => {
  const jobs = [
    { title: 'B', company: 'x', score: 50, fetched_at: '2026-11-01', posted_date: null },
    { title: 'A', company: 'y', score: null, fetched_at: '2026-11-03', posted_date: '2026-10-01' },
    { title: 'C', company: 'z', score: 90, fetched_at: '2026-11-02', posted_date: '2026-10-05' },
  ]
  it('sorts by score desc with nulls last', () => {
    expect(sortJobs(jobs, 'score', true).map((j) => j.title)).toEqual(['C', 'B', 'A'])
    expect(sortJobs(jobs, 'score', false).map((j) => j.title)).toEqual(['B', 'C', 'A'])
  })
  it('sorts strings', () => {
    expect(sortJobs(jobs, 'title', false).map((j) => j.title)).toEqual(['A', 'B', 'C'])
  })
})
