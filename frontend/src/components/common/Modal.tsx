/**
 * Unified Modal — Apple Liquid Glass style.
 *
 * Single source of truth for all dialog/modal surfaces. Replaces the 3
 * previously coexisting styles (Tailwind-UI bottom-sheet, partial-glass,
 * inline centered) so every dialog shares the same backdrop, panel, and
 * focus/escape behavior.
 *
 * - Backdrop: `bg-black/40 backdrop-blur-sm` (semi-transparent dark)
 * - Panel: `.glass-morph` rounded-2xl, white/20 border, scaleIn animation
 * - Escape key + backdrop click both close (when dismissible)
 * - First focusable element receives autoFocus
 */

import React, { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { XMarkIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'

export type ModalSize = 'sm' | 'md' | 'lg'

export interface ModalProps {
  open: boolean
  onClose: () => void
  title?: string
  description?: string
  children?: React.ReactNode
  footer?: React.ReactNode
  /** When false, Escape and backdrop click are disabled. Defaults to true. */
  dismissible?: boolean
  size?: ModalSize
  className?: string
  /** Optional aria-label when no title is set. */
  ariaLabel?: string
}

const sizeClass: Record<ModalSize, string> = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
}

export const Modal: React.FC<ModalProps> = ({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  dismissible = true,
  size = 'md',
  className,
  ariaLabel,
}) => {
  const panelRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!open || !dismissible) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onClose()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, dismissible, onClose])

  useEffect(() => {
    if (!open) return
    // Auto-focus the first focusable element inside the panel
    const panel = panelRef.current
    if (!panel) return
    const focusable = panel.querySelector<HTMLElement>(
      'input, textarea, select, button, [tabindex]:not([tabindex="-1"])'
    )
    if (focusable) {
      // Defer to next frame so the modal is fully painted
      const id = requestAnimationFrame(() => focusable.focus())
      return () => cancelAnimationFrame(id)
    }
  }, [open])

  if (!open) return null
  if (typeof document === 'undefined') return null

  const handleBackdropClick = () => {
    if (dismissible) onClose()
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm animate-fade-in"
      onClick={handleBackdropClick}
      onKeyDown={(e) => {
        if (!dismissible) return
        if (e.key === 'Escape') {
          e.stopPropagation()
          onClose()
        }
      }}
      role="presentation"
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel ?? title}
        onClick={(e) => e.stopPropagation()}
        className={clsx(
          'glass-morph rounded-2xl border border-white/20 w-full',
          'bg-white/90 backdrop-blur-xl shadow-xl',
          'animate-scale-in max-h-[90vh] flex flex-col overflow-hidden',
          sizeClass[size],
          className
        )}
      >
        {(title || dismissible) && (
          <div className="flex items-start justify-between px-6 py-4 border-b border-white/40">
            <div className="flex-1 min-w-0 pr-4">
              {title && (
                <h2 className="text-lg font-semibold text-ink truncate">{title}</h2>
              )}
              {description && (
                <p className="text-sm text-ink/65 mt-1">{description}</p>
              )}
            </div>
            {dismissible && (
              <button
                type="button"
                onClick={onClose}
                aria-label="关闭"
                className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] p-2 rounded-lg text-ink/50 hover:bg-white/50 hover:text-ink transition-colors flex-shrink-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            )}
          </div>
        )}

        <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4">{children}</div>

        {footer && (
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-white/40">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body
  )
}

export default Modal
