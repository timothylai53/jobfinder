/** A single http(s) link and nothing else (pasted page text is never a URL). */
export const isUrl = (s: string) => /^https?:\/\/[^\s]+$/.test(s.trim())
