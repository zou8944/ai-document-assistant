/**
 * Collapsible source references component
 */

import React, { useState } from 'react'
import { ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline'
import { SourceReference } from '../../services/apiClient'

interface SourceReferencesProps {
  sources: SourceReference[]
}

export const SourceReferences: React.FC<SourceReferencesProps> = ({ sources }) => {
  const [isExpanded, setIsExpanded] = useState(false)

  if (!sources || sources.length === 0) return null

  return (
    <div className="mt-3 pt-3 border-t border-gray-300/50">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center justify-between w-full text-left text-xs opacity-75 mb-2 hover:opacity-100 transition-opacity"
      >
        <span>参考来源 ({sources.length})</span>
        {isExpanded ? (
          <ChevronUpIcon className="w-3 h-3" />
        ) : (
          <ChevronDownIcon className="w-3 h-3" />
        )}
      </button>

      <div className={`overflow-hidden transition-all duration-300 ${
        isExpanded ? 'max-h-[600px] opacity-100' : 'max-h-0 opacity-0'
      }`}>
        <div className="space-y-2 mt-2 max-h-[600px] overflow-y-auto">
          {sources.map((source) => (
            <div key={`${source.document_id}-${source.chunk_index}`} className="text-xs bg-gray-50/50 rounded p-2 border border-gray-200/30">
              <div className="flex items-center justify-between mb-1">
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-gray-700 truncate">{source.document_name}</div>
                  {source.document_uri && (
                    <div className="text-xs text-blue-600 truncate mt-0.5">
                      {source.document_uri}
                    </div>
                  )}
                </div>
                {source.relevance_score && (
                  <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full ml-2 flex-shrink-0">
                    {(source.relevance_score * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              {source.content_preview && (
                <div className="text-xs text-gray-600 leading-relaxed line-clamp-3">
                  {source.content_preview.substring(0, 200)}...
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default SourceReferences
