/**
 * File upload modal component with backdrop and modal layout
 */

import React from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'
import FileUpload from './FileUpload'

interface FileUploadModalProps {
  isOpen: boolean
  onFilesSelected: (files: string[]) => void
  onClose: () => void
  isProcessing?: boolean
  className?: string
}

export const FileUploadModal: React.FC<FileUploadModalProps> = ({
  isOpen,
  onFilesSelected,
  onClose,
  isProcessing = false,
  className
}) => {
  if (!isOpen) return null

  const handleFilesSelected = (files: string[]) => {
    onFilesSelected(files)
    onClose()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape' && !isProcessing) {
      onClose()
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/30 backdrop-blur-sm transition-opacity"
        onClick={!isProcessing ? onClose : undefined}
      />
      
      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div 
          className={clsx(
            'glass-morph rounded-xl border border-white/20 p-6 w-full max-w-2xl',
            'bg-white/90 backdrop-blur-xl shadow-xl',
            'animate-slide-up',
            className
          )}
          onKeyDown={handleKeyDown}
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-macos-gray-900">
              选择文件或文件夹
            </h3>
            {!isProcessing && (
              <button
                onClick={onClose}
                className="p-1 hover:bg-macos-gray-100/50 rounded-lg transition-colors"
              >
                <XMarkIcon className="w-5 h-5 text-macos-gray-400" />
              </button>
            )}
          </div>

          {/* File Upload Content */}
          <FileUpload 
            onFilesSelected={handleFilesSelected}
            isProcessing={isProcessing}
          />

          {/* Actions */}
          {!isProcessing && (
            <div className="flex justify-end mt-6">
              <button
                onClick={onClose}
                className={clsx(
                  'glass-button px-4 py-2 rounded-lg text-sm font-medium',
                  'text-macos-gray-700 hover:text-macos-gray-900'
                )}
              >
                取消
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default FileUploadModal
