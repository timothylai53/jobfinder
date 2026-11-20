/** A single http(s) link and nothing else (pasted page text is never a URL). */
export const isUrl = (s: string) => /^https?:\/\/[^\s]+$/.test(s.trim())

/** Links from job ads are untrusted: only plain web addresses may become clickable (no javascript:, data:, file:). */
export function safeHttpUrl(url: string | null | undefined): string | null {
  const u = (url ?? '').trim()
  return /^https?:\/\/\S+$/i.test(u) ? u : null
}
