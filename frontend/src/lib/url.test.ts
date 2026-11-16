import { describe, expect, it } from 'vitest'
import { isUrl } from './url'

describe('isUrl', () => {
  it('accepts one http(s) link', () => {
    expect(isUrl('https://my.jobstreet.com/job/95667394')).toBe(true)
    expect(isUrl('  http://example.com/a?b=1  ')).toBe(true)
  })
  it('rejects pasted page text and non-links', () => {
    expect(isUrl('Skip to content\nJobstreet\nJunior Software Engineer')).toBe(false)
    expect(isUrl('https://a.com and more text')).toBe(false)
    expect(isUrl('my.jobstreet.com/job/1')).toBe(false)
    expect(isUrl('')).toBe(false)
  })
})
