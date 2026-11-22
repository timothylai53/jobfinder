import { X } from 'lucide-react'
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'

interface ToastOptions {
  message: string
  /** Shows an Undo button; called instead of onExpire if pressed. */
  undo?: () => void
  /** Runs when the toast ends without Undo (e.g. the real delete). Also runs if another toast replaces this one. */
  onExpire?: () => void
  duration?: number
}

const Ctx = createContext<(t: ToastOptions) => void>(() => {})

/** One toast at a time, bottom centre, announced politely to screen readers. The timer pauses on hover or focus. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<(ToastOptions & { id: number }) | null>(null)
  const [paused, setPaused] = useState(false)
  const current = useRef<(ToastOptions & { id: number }) | null>(null)

  const finish = useCallback((undo: boolean) => {
    const t = current.current
    current.current = null
    setToast(null)
    setPaused(false)
    if (!t) return
    if (undo) t.undo?.()
    else t.onExpire?.()
  }, [])

  const show = useCallback((t: ToastOptions) => {
    if (current.current) finish(false) // the previous action goes ahead
    const next = { ...t, id: Date.now() }
    current.current = next
    setToast(next)
  }, [finish])

  useEffect(() => {
    if (!toast || paused) return
    const timer = setTimeout(() => finish(false), toast.duration ?? 5000)
    return () => clearTimeout(timer)
  }, [toast, paused, finish])

  return (
    <Ctx.Provider value={show}>
      {children}
      <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex justify-center px-4">
        {toast && (
          <div
            key={toast.id}
            className="jf-fade-in pointer-events-auto flex items-center gap-3 rounded-lg bg-foreground py-2 pr-2 pl-4 text-[15px] text-background shadow-pop"
            onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}
            onFocus={() => setPaused(true)} onBlur={() => setPaused(false)}
          >
            <span>{toast.message}</span>
            {toast.undo && (
              <Button size="sm" variant="ghost" className="text-background underline underline-offset-2 hover:bg-background/15 hover:text-background" onClick={() => finish(true)}>
                Undo
              </Button>
            )}
            <Button size="icon-sm" variant="ghost" aria-label="Dismiss" className="text-background/80 hover:bg-background/15 hover:text-background" onClick={() => finish(false)}>
              <X className="size-4" aria-hidden />
            </Button>
          </div>
        )}
      </div>
    </Ctx.Provider>
  )
}

export const useToast = () => useContext(Ctx)
