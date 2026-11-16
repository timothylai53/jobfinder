import { describe, expect, it } from 'vitest'
import type { ExperienceItem, GuardFlag, ResumeDraft, TailorResult } from '@/api/types'
import { acceptedSections, flagsAt, flagTone, parsedToDraft, sentences, splitRow, tailorRows, unusedCodes } from './ai'

const result: TailorResult = {
  summary: 'Graduate.',
  skills_order: ['Python'],
  sections: [
    { section: 'Experience', items: [{ source_id: 'B1', text: 'Built APIs' }, { source_id: 'B99', text: 'Led Google' }] },
    { section: 'Certifications', items: [{ source_id: 'B4', text: 'Oracle Java' }] },
  ],
  omitted_ids: [],
  notes: '',
}
const flags: GuardFlag[] = [
  { path: 'sections.0.items.1', kind: 'unknown_id', message: 'B99 is not in your bank' },
  { path: 'sections.1.items.0', kind: 'unknown_skill', message: 'mentions Docker' },
  { path: 'sections.0.items.10', kind: 'missing_id', message: 'other item' },
]

describe('flagsAt', () => {
  it('matches the path and its children, not lookalikes', () => {
    expect(flagsAt(flags, 'sections.0.items.1').map((f) => f.kind)).toEqual(['unknown_id'])
    expect(flagsAt(flags, 'sections.1').length).toBe(1)
  })
})

describe('flag tone', () => {
  const amber: GuardFlag = { path: 'sections.0.items.0', kind: 'skill_not_in_item', message: "Git isn't in B1" }
  const num: GuardFlag = { path: 'sections.0.items.0', kind: 'new_number', message: "'40%' isn't in B1" }
  it('is amber only when every flag is a per-item skill warning', () => {
    expect(flagTone([])).toBeNull()
    expect(flagTone([amber])).toBe('amber')
    expect(flagTone([amber, num])).toBe('red')
  })
  it('amber and number flags keep the row accepted', () => {
    const rows = tailorRows(result, [amber, num])
    expect(rows[0].decision).toBe('accepted')
  })
})

describe('tailor review rows', () => {
  const rows = tailorRows(result, flags)
  it('rejects rows with an unknown ID by default, keeps others accepted', () => {
    expect(rows.map((r) => `${r.source_id}:${r.decision}`)).toEqual(['B1:accepted', 'B99:rejected', 'B4:accepted'])
    expect(rows[2].flags[0].kind).toBe('unknown_skill') // flagged but still the user's call
  })
  it('builds the save body from accepted rows only, keeping sections', () => {
    const edited = rows.map((r) => (r.key === '0.0' ? { ...r, text: '  Built REST APIs  ' } : r))
    expect(acceptedSections(edited)).toEqual([
      { section: 'Experience', items: [{ source_id: 'B1', text: 'Built REST APIs' }] },
      { section: 'Certifications', items: [{ source_id: 'B4', text: 'Oracle Java' }] },
    ])
  })
  it('lists bank items the AI did not use', () => {
    expect(unusedCodes(['B1', 'B2', 'B3', 'B4'], rows)).toEqual(['B2', 'B3'])
  })
})

describe('parsedToDraft', () => {
  it('keeps the file and raw text, replaces items, fills profile gaps', () => {
    const base = {
      file_path: 'f.pdf', raw_text: 'text', suggested_name: 'cv',
      profile: { name: 'Old', email: 'a@b.c', languages: ['English'], skills: [], expected_graduation: '' },
      items: [{ type: 'work', title: 'x', organization: '', start: '', end: '', bullets: [], skills: [], duplicate_of: 'B1' }],
      unparsed_lines: [{ line: 'l', section: 's', reason: 'r' }],
    } as unknown as ResumeDraft
    const d = parsedToDraft({
      profile: { name: 'Ali', email: '', phone: '', location: '', education_level: 'Degree', education_field: '', languages: [], skills: ['Python'] },
      items: [{ type: 'project', title: 'App', organization: '', start: '', end: '', bullets: ['Built it'], skills: [] }],
    }, base)
    expect(d.file_path).toBe('f.pdf')
    expect(d.profile.name).toBe('Ali')
    expect(d.profile.email).toBe('a@b.c')
    expect(d.profile.languages).toEqual(['English'])
    expect(d.items).toHaveLength(1)
    expect(d.items[0].duplicate_of).toBeNull()
    expect(d.unparsed_lines).toEqual([])
  })
  it('marks items already in the bank as duplicates (skipped by default in review)', () => {
    const base = { file_path: 'f', raw_text: '', suggested_name: '', profile: { expected_graduation: '' }, items: [], unparsed_lines: [] } as unknown as ResumeDraft
    const bank = [{ id: 1, code: 'B7', type: 'project', title: 'Campus App!', organization: 'Uni', start: '2023', end: '2023', bullets: [], skills: [], resume_ids: [] }] as ExperienceItem[]
    const d = parsedToDraft({
      profile: { name: '', email: '', phone: '', location: '', education_level: '', education_field: '', languages: [], skills: [] },
      items: [
        { type: 'project', title: 'campus app', organization: 'UNI', start: '2023', end: '2023', bullets: [], skills: [] },
        { type: 'project', title: 'Other', organization: '', start: '', end: '', bullets: [], skills: [] },
      ],
    }, base, bank)
    expect(d.items.map((i) => i.duplicate_of)).toEqual(['B7', null])
  })
})

describe('splitting merged bullets', () => {
  it('splits on sentence ends but not after e.g.', () => {
    expect(sentences('Built APIs in Python, e.g. Flask. Wrote SQL queries; Reduced bugs.')).toEqual(['Built APIs in Python, e.g. Flask.', 'Wrote SQL queries', 'Reduced bugs.'])
    expect(sentences('One bullet only')).toEqual(['One bullet only'])
  })
  it('turns one row into one row per sentence with the same bank ID', () => {
    const merged: GuardFlag[] = [
      { path: 'sections.0.items.0', kind: 'several_bullets', message: '2 bullets in one' },
      { path: 'sections.0.items.0', kind: 'header_removed', message: 'Removed header' },
    ]
    const res: TailorResult = { ...result, sections: [{ section: 'Experience', items: [{ source_id: 'B1', text: 'Built APIs. Wrote tests.' }] }] }
    const rows = splitRow(tailorRows(res, merged), '0.0')
    expect(rows.map((r) => [r.source_id, r.text])).toEqual([['B1', 'Built APIs.'], ['B1', 'Wrote tests.']])
    expect(rows[0].flags.map((f) => f.kind)).toEqual(['header_removed'])
    expect(acceptedSections(rows)).toEqual([{ section: 'Experience', items: [{ source_id: 'B1', text: 'Built APIs.' }, { source_id: 'B1', text: 'Wrote tests.' }] }])
  })
  it('header and merged-bullet warnings are amber', () => {
    expect(flagTone([{ path: 'x', kind: 'header_removed', message: '' }, { path: 'x', kind: 'several_bullets', message: '' }])).toBe('amber')
  })
})
