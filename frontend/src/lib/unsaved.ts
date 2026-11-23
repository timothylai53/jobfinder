import { useEffect, useRef } from 'react'

/**
 * Which forms have unsaved edits right now. Each form registers itself with useUnsavedChanges(dirty); one guard
 * (components/UnsavedGuard) asks before in-app navigation and the browser warns on close/reload.
 */
const dirtyForms = new Set<symbol>()

export const LEAVE_MESSAGE = 'You have unsaved changes. Leave anyway?'

export function hasUnsavedChanges(): boolean {
  return dirtyForms.size > 0
}

/** For in-page switches that aren't navigation (e.g. another Settings section): true if it's fine to go on. */
export function confirmLeave(): boolean {
  return !hasUnsavedChanges() || window.confirm(LEAVE_MESSAGE)
}

export function useUnsavedChanges(dirty: boolean): void {
  const token = useRef(Symbol('unsaved-form'))
  useEffect(() => {
    const t = token.current
    if (dirty) dirtyForms.add(t)
    else dirtyForms.delete(t)
    return () => { dirtyForms.delete(t) }
  }, [dirty])
}
