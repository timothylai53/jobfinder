import { useState } from 'react'

/**
 * An editable local copy of a value that still follows outside changes (a refetch, a save elsewhere). It uses React's
 * "adjust state while rendering" pattern instead of an effect, so there is no extra render with stale data.
 */
export function useLocalCopy<T>(source: T): [T, (v: T) => void] {
  const [value, setValue] = useState(source)
  const [seen, setSeen] = useState(source)
  if (source !== seen) {
    setSeen(source)
    setValue(source)
  }
  return [value, setValue]
}
