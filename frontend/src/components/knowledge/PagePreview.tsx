/**
 * Page preview modal - displays crawled HTML pages in an iframe
 */

import React from 'react'
import { XMarkIcon, ArrowTopRightOnSquareIcon } from '@heroicons/react/24/outline'

interface PagePreviewProps {
  isOpen: boolean
  onClose: () => void
  previewUrl: string | null
  pageTitle: string
  sourceUrl: string
}

export const PagePreview: React.FC<PagePreviewProps> = ({
  isOpen,
  onClose,
  previewUrl,
  pageTitle,
  sourceUrl,
}) => {
  if (!isOpen || !previewUrl) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-[90vw] h-[85vh] bg-white rounded-xl shadow-2xl flex flex-col overflow-hidden animate-slide-up">
        {/* Header */}
        <div className="flex-shrink-0 flex items-center justify-between px-5 py-3 bg-gradient-to-r from-white/95 to-white/80 backdrop-blur-sm border-b border-gray-200/50">
          <div className="flex-1 min-w-0 mr-4">
            <h3 className="text-base font-semibold text-gray-900 truncate">
              {pageTitle || '页面预览'}
            </h3>
            {sourceUrl && (
              <a
                href={sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-500 hover:text-blue-600 truncate flex items-center gap-1 mt-0.5"
              >
                <ArrowTopRightOnSquareIcon className="w-3 h-3 flex-shrink-0" />
                {sourceUrl}
              </a>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-gray-100/50 rounded-lg transition-colors flex-shrink-0"
          >
            <XMarkIcon className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Iframe */}
        <div className="flex-1 bg-white">
          <iframe
            src={previewUrl}
            className="w-full h-full border-0"
            title={pageTitle || '页面预览'}
            sandbox="allow-same-origin"
          />
        </div>
      </div>
    </div>
  )
}

export default PagePreview
