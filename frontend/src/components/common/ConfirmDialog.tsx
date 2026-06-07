/**
 * ConfirmDialog — prebuilt confirmation modal on top of <Modal>.
 *
 * Used in place of native `window.confirm(...)` (which is non-macOS in look
 * and blocking) for destructive actions such as "delete chat" or
 * "clear knowledge base".
 */

import React from 'react'
import clsx from 'clsx'
import Modal, { type ModalSize } from './Modal'

export interface ConfirmDialogProps {
  open: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  destructive?: boolean
  size?: ModalSize
  /** Disable the confirm button while an async operation is in flight. */
  loading?: boolean
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = '确认',
  cancelLabel = '取消',
  destructive = false,
  size = 'sm',
  loading = false,
}) => {
  const handleConfirm = () => {
    if (loading) return
    onConfirm()
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size={size}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="px-4 py-2 text-sm text-ink/80 hover:text-ink rounded-lg transition-colors disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={loading}
            className={clsx(
              'px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-offset-2',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              destructive
                ? 'bg-red-600 hover:bg-red-700 focus:ring-red-500'
                : 'bg-accent hover:bg-accent-hover focus:ring-accent'
            )}
          >
            {loading ? '处理中...' : confirmLabel}
          </button>
        </>
      }
    >
      <p className="text-sm text-ink/80 leading-relaxed whitespace-pre-line">{message}</p>
    </Modal>
  )
}

export default ConfirmDialog
