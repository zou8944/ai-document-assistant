/**
 * ToastContainer — renders the global toast stack.
 *
 * Mount once near the root of the app (e.g. inside <App>). Uses
 * createPortal to escape any local overflow:hidden parents.
 */

import React from 'react'
import { createPortal } from 'react-dom'
import type { ComponentType, SVGProps } from 'react'
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useToastStore, type Toast, type ToastKind } from '../../store/toastStore'

type HeroIcon = ComponentType<SVGProps<SVGSVGElement> & { title?: string; titleId?: string }>

interface KindStyle {
  ring: string
  icon: HeroIcon
  iconClass: string
}

const kindStyles: Record<ToastKind, KindStyle> = {
  success: {
    ring: 'border-l-green-500',
    icon: CheckCircleIcon,
    iconClass: 'text-green-500',
  },
  error: {
    ring: 'border-l-red-500',
    icon: ExclamationCircleIcon,
    iconClass: 'text-red-500',
  },
  warning: {
    ring: 'border-l-yellow-500',
    icon: ExclamationTriangleIcon,
    iconClass: 'text-yellow-500',
  },
  info: {
    ring: 'border-l-accent',
    icon: InformationCircleIcon,
    iconClass: 'text-accent',
  },
}

const ToastCard: React.FC<{ toast: Toast }> = ({ toast }) => {
  const remove = useToastStore((s) => s.remove)
  const styles = kindStyles[toast.kind]
  const Icon = styles.icon

  return (
    <div
      role="status"
      aria-live="polite"
      className={clsx(
        'glass-morph rounded-xl border border-white/40 border-l-4 shadow-lg',
        'p-4 pr-10 min-w-[280px] max-w-md relative',
        'animate-slide-in-right',
        styles.ring
      )}
    >
      <div className="flex items-start gap-3">
        <Icon className={clsx('w-5 h-5 mt-0.5 flex-shrink-0', styles.iconClass)} />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-ink break-words">{toast.title}</div>
          {toast.description && (
            <div className="text-xs text-ink/65 mt-1 break-words">{toast.description}</div>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={() => remove(toast.id)}
        aria-label="关闭通知"
        className="absolute top-2 right-2 p-1 rounded text-ink/50 hover:text-ink hover:bg-white/50 transition-colors"
      >
        <XMarkIcon className="w-4 h-4" />
      </button>
    </div>
  )
}

export const ToastContainer: React.FC = () => {
  const toasts = useToastStore((s) => s.toasts)

  if (typeof document === 'undefined') return null

  return createPortal(
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-3 pointer-events-none">
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto">
          <ToastCard toast={t} />
        </div>
      ))}
    </div>,
    document.body
  )
}

export default ToastContainer

