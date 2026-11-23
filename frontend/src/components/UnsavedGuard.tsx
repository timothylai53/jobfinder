import { useEffect } from 'react'
import { useBlocker } from 'react-router-dom'
import { hasUnsavedChanges, LEAVE_MESSAGE } from '@/lib/unsaved'

/** Asks before leaving a page with unsaved edits (links, the sidebar, Back), and lets the browser warn on close/reload. */
export default function UnsavedGuard() {
  // Only a change of page counts: query-string changes (filters, tabs) keep the form on screen.
  const blocker = useBlocker(({ currentLocation, nextLocation }) =>
    hasUnsavedChanges() && currentLocation.pathname !== nextLocation.pathname)
  useEffect(() => {
    if (blocker.state !== 'blocked') return
    if (window.confirm(LEAVE_MESSAGE)) blocker.proceed()
    else blocker.reset()
  }, [blocker])
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges()) return
      e.preventDefault()
      e.returnValue = '' // older browsers need a value to show their own "Leave site?" prompt
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [])
  return null
}
