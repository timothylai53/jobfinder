import { describe, expect, it } from 'vitest'
import type { AutomationRunRow, BaseResume, ExperienceItem, Skill } from '@/api/types'
import { defaultStartFrom, groupItems, splitLeftOut, toggleGroup, typeSummary } from './baseResumes'
import { dateRange } from './score'
import { addTown, findTowns, removeTown, resetState, statesWith } from './locations'
import { metaText, parseLegacyLine, plainNote, runRows } from './runlog'
import { skillCategories, visibleSkills } from './skills'

const item = (id: number, type: ExperienceItem['type'], title: string, organization = '', skills: string[] = []): ExperienceItem =>
  ({ id, code: `B${id}`, type, title, organization, start: '', end: '', bullets: [], skills, resume_ids: [] })

describe('base resumes', () => {
  const bank = [item(1, 'education', 'BSc Software Engineering', 'Universiti Contoh'), item(2, 'project', 'Kedai App', '', ['React']),
    item(3, 'project', 'Bus Tracker'), item(4, 'work', 'Intern', 'Syarikat Contoh Bhd'), item(5, 'achievement', 'Dean’s list')]
  it('summarises the types in resume order, with plain plurals', () => {
    expect(typeSummary(bank)).toBe('1 education · 1 work · 2 projects · 1 achievement')
    expect(typeSummary([])).toBe('No items yet')
  })
  it('groups by type and searches title, organisation, code and skills', () => {
    expect(groupItems(bank, '').map((g) => g.label)).toEqual(['Education', 'Experience', 'Projects', 'Achievements'])
    expect(groupItems(bank, 'react').flatMap((g) => g.items.map((i) => i.id))).toEqual([2])
    expect(groupItems(bank, 'contoh').map((g) => g.label)).toEqual(['Education', 'Experience'])
    expect(groupItems(bank, 'b3')[0].items[0].title).toBe('Bus Tracker')
  })
  it('selects or clears a whole group', () => {
    const on = toggleGroup(new Set([1]), [2, 3], true)
    expect([...on].sort()).toEqual([1, 2, 3])
    expect([...toggleGroup(on, [2, 3], false)]).toEqual([1])
  })
})

const run = (over: Partial<AutomationRunRow>): AutomationRunRow => ({
  id: 7, automation_key: 'fetch_jobs', trigger: 'manual', started_at: '2026-11-13T03:10:00', finished_at: null, result: 'ok',
  items_processed: 0, message: '', error: '', ...over,
})

describe('run log', () => {
  it('words warnings plainly', () => {
    expect(plainNote('linkedin', "JobSpy warning: job_type fulltime isn't supported, ignoring it"))
      .toBe("LinkedIn doesn't support the job type filter, so it was ignored.")
    expect(plainNote('linkedin', "JobSpy warning: is_remote isn't supported, ignoring it")).toBe("LinkedIn doesn't support the remote filter, so it was ignored.")
    expect(plainNote('indeed', "JobSpy warning: location 'Bangsar' not found, searching the country"))
      .toBe("Indeed didn't recognise “Bangsar”, so it searched the country instead.")
    expect(plainNote('jobstreet', 'job details blocked: saved 4 job(s) from their search summary'))
      .toBe('JobStreet blocked the job pages, so 4 job(s) were saved from the search results only.')
    expect(plainNote('indeed', 'something new')).toBe('Something new.')
    expect(metaText(['Smoke test'], 5)).toBe('Smoke test · limit 5')
  })
  it('uses the stored per-source details: one aligned row per source', () => {
    const rows = runRows(run({ details: [
      { source: 'linkedin', status: 'ok', profiles: ['Smoke test'], cap: 5, fetched: 5, new: 3, merged: 1, hidden: 1, requests: 2,
        notes: ["JobSpy warning: job_type fulltime isn't supported, ignoring it"], error: '' },
      { source: 'glassdoor', status: 'skipped', profiles: [], cap: null, fetched: 0, new: 0, merged: 0, hidden: 0, requests: 0,
        notes: [], error: 'no enabled search profile uses this source' },
    ] }), 'Fetch jobs')
    expect(rows.map((r) => [r.name, r.status, r.meta])).toEqual([['LinkedIn', 'ok', 'Smoke test · limit 5'], ['Glassdoor', 'skipped', '']])
    expect(rows[0].numbers).toEqual({ fetched: 5, new: 3, merged: 1, hidden: 1, requests: 2 })
    expect(rows[0].details).toEqual(["LinkedIn doesn't support the job type filter, so it was ignored."])
    expect(rows[1].numbers).toBeNull()
    expect(rows[1].details).toEqual(['Skipped: no enabled search profile uses this source.'])
  })
  it('reads the text lines of older runs', () => {
    expect(parseLegacyLine('indeed (limit 5, profile Smoke test): ok: 4 fetched, 3 new, 1 merged, 0 hidden by filters. ' +
      "JobSpy warning: job_type fulltime isn't supported, ignoring it (2 request(s))")).toMatchObject({
      source: 'indeed', status: 'ok', cap: 5, profiles: ['Smoke test'], fetched: 4, new: 3, merged: 1, hidden: 0, requests: 2,
      notes: ["JobSpy warning: job_type fulltime isn't supported, ignoring it"], error: '' })
    expect(parseLegacyLine('jobstreet (limit 50, profiles A, B): error: HTTP 403. Saved before stopping: 2 fetched, 2 new, 0 merged, 0 hidden by filters (3 request(s))'))
      .toMatchObject({ status: 'error', profiles: ['A', 'B'], fetched: 2, error: 'HTTP 403' })
    expect(runRows(run({ message: 'glassdoor: skipped: no enabled search profile uses this source (0 request(s))' }), 'Fetch jobs')[0].status).toBe('skipped')
  })
  it('shows other automations as one row with the message under Details', () => {
    const [r] = runRows(run({ automation_key: 'score_new_jobs', trigger: 'chain', items_processed: 3, message: 'scored 3 jobs' }), 'Score new jobs')
    expect([r.name, r.meta, r.numbers, r.details]).toEqual(['Score new jobs', 'After Fetch jobs · 3 processed', null, ['Scored 3 jobs.']])
  })
})

describe('location map editor', () => {
  const map = { 'Kuala Lumpur': ['Cheras', 'Bangsar'], Selangor: ['Petaling Jaya'] }
  it('adds towns, rejects duplicates within a state, allows one area in two states', () => {
    expect(addTown(map, 'Kuala Lumpur', ' cheras ').error).toBe('cheras is already in Kuala Lumpur.')
    expect(addTown(map, 'Selangor', '  ').error).toBeTruthy()
    const both = addTown(map, 'Selangor', 'Cheras').map
    expect(both.Selangor).toEqual(['Petaling Jaya', 'Cheras'])
    expect(statesWith(both, 'cheras')).toEqual(['Kuala Lumpur', 'Selangor'])
    expect(removeTown(both, 'Selangor', 'Cheras').Selangor).toEqual(['Petaling Jaya'])
    expect(map.Selangor).toEqual(['Petaling Jaya']) // never mutated
  })
  it('finds a town across states and resets one state', () => {
    expect(findTowns(map, 'ban')).toEqual([{ state: 'Kuala Lumpur', town: 'Bangsar' }])
    expect(findTowns(map, ' ')).toEqual([])
    expect(resetState({ ...map, Selangor: [] }, { Selangor: ['Shah Alam'] }, 'Selangor').Selangor).toEqual(['Shah Alam'])
  })
})

describe('skill dictionary', () => {
  const skills: Skill[] = [
    { id: 1, name: 'React', category: 'framework', aliases: ['React.js', 'ReactJS'] },
    { id: 2, name: 'Python', category: 'language', aliases: ['py'] },
    { id: 3, name: 'Angular', category: 'framework', aliases: [] },
  ]
  it('searches names and aliases, filters by category and sorts', () => {
    expect(visibleSkills(skills, 'reactjs', '', 'name', false).map((s) => s.id)).toEqual([1])
    expect(visibleSkills(skills, '', 'framework', 'name', false).map((s) => s.name)).toEqual(['Angular', 'React'])
    expect(visibleSkills(skills, '', '', 'category', false).map((s) => s.name)).toEqual(['Angular', 'React', 'Python'])
    expect(visibleSkills(skills, '', '', 'name', true).map((s) => s.name)).toEqual(['React', 'Python', 'Angular'])
    expect(skillCategories([...skills, { id: 4, name: 'X', category: 'custom', aliases: [] }])).toContain('custom')
  })
})

describe('tailoring from a base resume', () => {
  const r = (id: number, last: string | null, items: number[]): BaseResume =>
    ({ id, name: `R${id}`, original_file_path: '', created_at: '', updated_at: '', last_used_at: last, item_ids: items })
  it('defaults to the most recently used base resume that has items, else the whole bank', () => {
    expect(defaultStartFrom([r(1, '2026-11-01T10:00:00', [1]), r(2, '2026-11-20T10:00:00', [2]), r(3, null, [3])])).toBe(2)
    expect(defaultStartFrom([r(1, '2026-11-01T10:00:00', [1]), r(2, '2026-11-20T10:00:00', [])])).toBe(1)
    expect(defaultStartFrom([r(1, null, [1])])).toBeNull()
  })
  it('lists the base resume’s own left-out items first, then the rest of the bank', () => {
    expect(splitLeftOut(['B2', 'B4', 'B5'], new Set(['B1', 'B2']))).toEqual({ inBase: ['B2'], others: ['B4', 'B5'] })
    expect(splitLeftOut(['B2', 'B4'], null)).toEqual({ inBase: ['B2', 'B4'], others: [] })
  })
  it('prints a same-year range once', () => {
    expect(dateRange('2024', '2024')).toBe('2024')
    expect(dateRange('Jan 2024', 'jan  2024')).toBe('Jan 2024')
    expect(dateRange('Jun 2025', 'Sep 2025')).toBe('Jun 2025 – Sep 2025')
    expect(dateRange('', '2024')).toBe('2024')
  })
})
