import { describe, expect, it } from 'vitest'
import { buildOptions, mapToText, textToMap } from './locations'

describe('location map text', () => {
  it('parses State: towns lines and skips junk', () => {
    expect(textToMap('Selangor: Shah Alam, Cyberjaya,  Puchong\n\nnot a line\n: orphan\nSabah: KK')).toEqual({
      Selangor: ['Shah Alam', 'Cyberjaya', 'Puchong'],
      Sabah: ['KK'],
    })
  })
  it('round-trips', () => {
    const m = { 'Kuala Lumpur': ['KL', 'Bangsar'], Penang: ['George Town'] }
    expect(textToMap(mapToText(m))).toEqual(m)
  })
})

describe('buildOptions', () => {
  const map = { Selangor: ['Shah Alam', 'Cyberjaya'], 'Kuala Lumpur': ['KL', 'Bangsar'] }
  it('lists Remote, then each state followed by its towns', () => {
    expect(buildOptions(map, '').map((o) => o.value)).toEqual(['Remote', 'Selangor', 'Shah Alam', 'Cyberjaya', 'Kuala Lumpur', 'KL', 'Bangsar'])
  })
  it('a matching town is shown under its state', () => {
    expect(buildOptions(map, 'cyber').map((o) => `${o.kind}:${o.value}`)).toEqual(['state:Selangor', 'town:Cyberjaya'])
  })
  it('a matching state shows all of its towns', () => {
    expect(buildOptions(map, 'kuala').map((o) => o.value)).toEqual(['Kuala Lumpur', 'KL', 'Bangsar'])
  })
  it('remote is searchable', () => {
    expect(buildOptions(map, 'rem').map((o) => o.value)).toEqual(['Remote'])
  })
})
