/** Jobs deleted but still inside their 5 s Undo window: lists hide them until the delete really happens or is undone. */
import { useSyncExternalStore } from 'react'

let pending = new Set<number>()
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())

export const pendingDeletes = {
  add(id: number) { pending = new Set(pending).add(id); emit() },
  remove(id: number) { const next = new Set(pending); next.delete(id); pending = next; emit() },
}

export function usePendingDeletes(): Set<number> {
  return useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l) }, () => pending)
}
