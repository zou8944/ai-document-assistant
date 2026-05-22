/**
 * Source references - minimal style
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
    <div className="mt-4 pt-3 border-t border-warm-border">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center space-x-1 text-[11px] text-muted hover:text-ink transition-colors"
      >
        <span>参考来源 ({sources.length})</span>
        {isExpanded ? (
          <ChevronUpIcon className="w-3 h-3" />
        ) : (
          <ChevronDownIcon className="w-3 h-3" />
        )}
      </button>

      <div className={`overflow-hidden transition-all duration-300 ${
        isExpanded ? 'max-h-[600px] opacity-100 mt-2' : 'max-h-0 opacity-0'
      }`}>
        <div className="space-y-2 max-h-[600px] overflow-y-auto">
          {sources.map((source, index) => (
            <div
              key={`${source.document_id}-${source.chunk_index}`}
              className="text-xs rounded-md p-2.5 bg-white border border-warm-border hover:shadow-sm hover:border-gray-300 transition-all duration-150"
              style={{ transitionDelay: `${index * 30}ms` }}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-ink truncate">{source.document_name}</div>
                  {source.document_uri && (
                    <div className="text-[11px] text-accent truncate mt-0.5">
                      {source.document_uri}
                    </div>
                  )}
                </div>
                {source.relevance_score && (
                  <span className="text-[10px] bg-[#FAFAF8] text-muted px-2 py-0.5 rounded-full ml-2 flex-shrink-0 border border-warm-border">
                    {(source.relevance_score * 100).toFixed(0)}%
                  </span>
                )}
              </div>
              {source.content_preview && (
                <div className="text-[11px] text-muted leading-relaxed line-clamp-3">
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
