import { describe, expect, it } from 'vitest'
import { titlesMatch } from './titles'

describe('titlesMatch', () => {
  it('ignores case, punctuation and extra words', () => {
    expect(titlesMatch('Junior Software Engineer', 'junior software engineer')).toBe(true)
    expect(titlesMatch('Software Engineer (Fresh Graduate)', 'Software Engineer - Fresh Graduate')).toBe(true)
    expect(titlesMatch('Software Engineer', 'Junior Software Engineer (Java)')).toBe(true)
  })
  it('flags a different job', () => {
    expect(titlesMatch('Junior Software Engineer', 'Senior Accountant')).toBe(false)
    expect(titlesMatch('Graduate Software Engineer', 'Marketing Executive')).toBe(false)
  })
  it('does not complain when a title is missing', () => {
    expect(titlesMatch('', 'Anything')).toBe(true)
  })
})
