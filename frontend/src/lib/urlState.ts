import { useSearchParams } from 'react-router-dom'

/**
 * One piece of page state kept in the query string (?q=react&min=60), so Back, reload and shared links keep it.
 * The default value is left out of the URL; updates replace the history entry instead of adding one per keystroke.
 */
export function useQueryParam(key: string, fallback = ''): [string, (v: string) => void] {
  const [params, setParams] = useSearchParams()
  const value = params.get(key) ?? fallback
  const set = (v: string) =>
    setParams(() => {
      // Start from the address bar, not the params of the last render: two quick changes (type, then pick a sort)
      // would otherwise overwrite each other.
      const next = new URLSearchParams(window.location.search)
      if (v === fallback || v === '') next.delete(key)
      else next.set(key, v)
      return next
    }, { replace: true })
  return [value, set]
}
