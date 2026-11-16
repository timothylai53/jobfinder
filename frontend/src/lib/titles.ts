/** Loose title comparison: does a pasted page look like the same job? (case, punctuation and order ignored) */
const words = (s: string) => s.toLowerCase().match(/[a-z0-9+#]+/g) ?? []

export function titlesMatch(a: string, b: string): boolean {
  const wa = new Set(words(a))
  const wb = new Set(words(b))
  if (wa.size === 0 || wb.size === 0) return true // nothing to compare: don't raise a false alarm
  const [small, big] = wa.size <= wb.size ? [wa, wb] : [wb, wa]
  let shared = 0
  for (const w of small) if (big.has(w)) shared++
  return shared / small.size >= 0.6
}
