/**
 * Global toast notification store.
 *
 * Replaces blocking `window.alert(...)` with non-blocking Glass toasts that
 * stack in the bottom-right corner, auto-dismiss, and can be manually
 * closed. Not persisted — toasts are ephemeral.
 */

import { create } from 'zustand'

export type ToastKind = 'success' | 'error' | 'warning' | 'info'

export interface Toast {
  id: string
  kind: ToastKind
  title: string
  description?: string
  /** Auto-dismiss after this many ms. Defaults: 3000 (success/info), 5000 (error/warning). */
  duration?: number
}

interface ToastState {
  toasts: Toast[]
  add: (toast: Omit<Toast, 'id'>) => string
  remove: (id: string) => void
  clear: () => void
}

const DEFAULT_DURATIONS: Record<ToastKind, number> = {
  success: 3000,
  info: 3000,
  warning: 5000,
  error: 5000,
}

const MAX_TOASTS = 5

let counter = 0
const nextId = () => `toast_${Date.now()}_${++counter}`

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  add: (toast) => {
    const id = nextId()
    const full: Toast = { id, ...toast }
    set((state) => {
      // Cap the stack — drop oldest if exceeded
      const next = [...state.toasts, full]
      if (next.length > MAX_TOASTS) {
        next.splice(0, next.length - MAX_TOASTS)
      }
      return { toasts: next }
    })
    const duration = toast.duration ?? DEFAULT_DURATIONS[toast.kind]
    if (duration > 0) {
      setTimeout(() => {
        if (get().toasts.find((t) => t.id === id)) {
          get().remove(id)
        }
      }, duration)
    }
    return id
  },
  remove: (id) => {
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }))
  },
  clear: () => set({ toasts: [] }),
}))
