import { describe, expect, it } from 'vitest'
import { anyRunning, confirmAgainText, fetchButtonLabel, fetchedToday, type FetchSource } from './fetchPlan'

const indeed: FetchSource = { key: 'indeed', label: 'Indeed', max_results: 50, runs_today: 0, running: false }
const linkedin: FetchSource = { key: 'linkedin', label: 'LinkedIn', max_results: 15, runs_today: 0, running: false }

describe('fetchButtonLabel', () => {
  it('is plain when a limit is set', () => {
    expect(fetchButtonLabel([indeed], '5')).toBe('Fetch from 1 source')
  })
  it('warns when the limit box is empty', () => {
    expect(fetchButtonLabel([indeed], '')).toBe('Fetch from 1 source, no limit: up to 50 jobs')
    expect(fetchButtonLabel([indeed, linkedin], ' ')).toBe('Fetch from 2 sources, no limit: up to 50 jobs each')
  })
})

describe('second fetch on the same day', () => {
  it('lists the sources already fetched today', () => {
    const again = fetchedToday([{ ...indeed, runs_today: 1 }, linkedin])
    expect(again.map((s) => s.key)).toEqual(['indeed'])
    expect(confirmAgainText(again)).toContain('Already fetched today: Indeed (1 run today).')
  })
  it('needs no confirmation for a first run', () => {
    expect(fetchedToday([indeed, linkedin])).toEqual([])
  })
})

describe('anyRunning', () => {
  it('blocks while a chosen source is being fetched', () => {
    expect(anyRunning([indeed, { ...linkedin, running: true }])).toBe(true)
    expect(anyRunning([indeed])).toBe(false)
  })
})
