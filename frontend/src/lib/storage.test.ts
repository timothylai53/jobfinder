import { afterEach, describe, expect, it, vi } from 'vitest'
import { readLocal, writeLocal } from './storage'

describe('local storage that never throws', () => {
  afterEach(() => vi.unstubAllGlobals())
  it('reads and writes when storage works', () => {
    const data = new Map<string, string>()
    vi.stubGlobal('localStorage', { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => data.set(k, v) })
    writeLocal('trackerView', 'table')
    expect(readLocal('trackerView')).toBe('table')
  })
  it('falls back quietly when storage is blocked', () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('SecurityError') }, setItem: () => { throw new Error('QuotaExceeded') } })
    expect(readLocal('trackerView')).toBeNull()
    expect(() => writeLocal('trackerView', 'table')).not.toThrow()
  })
})
