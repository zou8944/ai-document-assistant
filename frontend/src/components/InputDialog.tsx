/**
 * Input dialog component to replace browser prompt
 */

import React, { useState } from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'

interface InputDialogProps {
  isOpen: boolean
  title: string
  placeholder?: string
  defaultValue?: string
  onConfirm: (value: string) => void
  onCancel: () => void
  className?: string
}

export const InputDialog: React.FC<InputDialogProps> = ({
  isOpen,
  title,
  placeholder,
  defaultValue = '',
  onConfirm,
  onCancel,
  className
}) => {
  const [value, setValue] = useState(defaultValue)

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (value.trim()) {
      onConfirm(value.trim())
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onCancel()
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/30 backdrop-blur-sm transition-opacity"
        onClick={onCancel}
      />
      
      {/* Dialog */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div 
          className={clsx(
            'glass-morph rounded-xl border border-white/20 p-6 w-full max-w-md',
            'bg-white/90 backdrop-blur-xl shadow-xl',
            'animate-slide-up',
            className
          )}
          onKeyDown={handleKeyDown}
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-macos-gray-900">
              {title}
            </h3>
            <button
              onClick={onCancel}
              className="p-1 hover:bg-macos-gray-100/50 rounded-lg transition-colors"
            >
              <XMarkIcon className="w-5 h-5 text-macos-gray-400" />
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit}>
            <input
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder={placeholder}
              className={clsx(
                'w-full px-4 py-3 border border-macos-gray-300 rounded-xl',
                'focus:ring-2 focus:ring-macos-blue focus:border-macos-blue',
                'bg-white/70 backdrop-blur-sm text-macos-gray-900 placeholder-macos-gray-500',
                'transition-all duration-200'
              )}
              autoFocus
            />
            
            {/* Actions */}
            <div className="flex justify-end space-x-3 mt-6">
              <button
                type="button"
                onClick={onCancel}
                className={clsx(
                  'glass-button px-4 py-2 rounded-lg text-sm font-medium',
                  'text-macos-gray-700 hover:text-macos-gray-900',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                取消
              </button>
              <button
                type="submit"
                disabled={!value.trim()}
                className={clsx(
                  'px-4 py-2 text-sm font-medium text-white rounded-lg',
                  'bg-macos-blue hover:bg-blue-600',
                  'disabled:bg-macos-gray-300 disabled:cursor-not-allowed',
                  'transition-colors duration-200',
                  'focus:outline-none focus:ring-2 focus:ring-macos-blue focus:ring-offset-2'
                )}
              >
                确认
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

export default InputDialog
