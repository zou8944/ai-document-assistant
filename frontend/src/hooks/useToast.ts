/**
 * useToast — convenience hook for firing toasts from anywhere.
 *
 * Returns `{ success, error, warning, info }` each of which accepts either
 * a string title or a partial Toast object.
 */

import { useToastStore, type ToastKind, type Toast } from '../store/toastStore'

type ToastInput =
  | string
  | (Partial<Omit<Toast, 'id' | 'kind'>> & { title?: string })

function call(kind: ToastKind, input: ToastInput) {
  const opts: ToastInput extends string ? never : Partial<Toast> = typeof input === 'string'
    ? { title: input }
    : input
  return useToastStore.getState().add({
    kind,
    title: (opts.title as string) ?? '',
    description: opts.description,
    duration: opts.duration,
  })
}

export function useToast() {
  return {
    success: (input: ToastInput) => call('success', input),
    error: (input: ToastInput) => call('error', input),
    warning: (input: ToastInput) => call('warning', input),
    info: (input: ToastInput) => call('info', input),
  }
}

/** For non-React contexts (event handlers in stores, etc.). */
export const toast = {
  success: (input: ToastInput) => call('success', input),
  error: (input: ToastInput) => call('error', input),
  warning: (input: ToastInput) => call('warning', input),
  info: (input: ToastInput) => call('info', input),
}
