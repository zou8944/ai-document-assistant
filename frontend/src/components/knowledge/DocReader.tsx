/**
 * Document reader panel - shows a document in an iframe within the page
 */

import React from 'react'
import { ArrowLeftIcon, ArrowTopRightOnSquareIcon } from '@heroicons/react/24/outline'

interface DocInfo {
  id: string
  name: string
  url?: string
}

interface DocReaderProps {
  doc: DocInfo
  previewUrl: string
  onBack: () => void
}

export const DocReader: React.FC<DocReaderProps> = ({ doc, previewUrl, onBack }) => {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Top bar */}
      <div className="flex-shrink-0 flex items-center gap-3 px-4 py-3 border-b border-gray-200/50 bg-white/80 backdrop-blur-sm">
        <button
          onClick={onBack}
          className="p-1.5 hover:bg-gray-100/50 rounded-lg transition-colors flex-shrink-0"
          title="返回"
        >
          <ArrowLeftIcon className="w-4 h-4 text-gray-600" />
        </button>
        <h3 className="text-sm font-semibold text-gray-900 truncate flex-1">
          {doc.name}
        </h3>
        {doc.url && (
          <a
            href={doc.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-blue-500 hover:text-blue-600 flex-shrink-0"
          >
            <ArrowTopRightOnSquareIcon className="w-3.5 h-3.5" />
            原文
          </a>
        )}
      </div>

      {/* Iframe */}
      <div className="flex-1 bg-white">
        <iframe
          src={previewUrl}
          className="w-full h-full border-0"
          title={doc.name}
          sandbox="allow-same-origin"
        />
      </div>
    </div>
  )
}

export default DocReader
