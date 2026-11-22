import { createContext, useContext } from 'react'

export interface ToastOptions {
  message: string
  /** Shows an Undo button; called instead of onExpire if pressed. */
  undo?: () => void
  /** Runs when the toast ends without Undo (e.g. the real delete). Also runs if another toast replaces this one. */
  onExpire?: () => void
  duration?: number
}

export const ToastContext = createContext<(t: ToastOptions) => void>(() => {})

/** Show a toast (rendered by ToastProvider in components/Toast.tsx). */
export const useToast = () => useContext(ToastContext)
