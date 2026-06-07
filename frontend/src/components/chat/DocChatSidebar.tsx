/**
 * Document chat sidebar - collapsible sidebar with resize handle
 */

import React, { useCallback } from 'react'
import {
  ChatBubbleLeftRightIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import DocChatPanel from './DocChatPanel'

interface DocChatSidebarProps {
  documentId: string | null
  chatId: string | null
  isOpen: boolean
  onToggle: () => void
  width: number
  onResize: (width: number) => void
}

export const DocChatSidebar: React.FC<DocChatSidebarProps> = ({
  documentId: _documentId,
  chatId,
  isOpen,
  onToggle,
  width,
  onResize,
}) => {
  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startWidth = width

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = Math.max(240, Math.min(600, startWidth - (e.clientX - startX)))
      onResize(newWidth)
    }

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [width, onResize])

  return (
    <>
      {/* Floating toggle button when collapsed */}
      {!isOpen && (
        <button
          onClick={onToggle}
          aria-label="打开聊天"
          className="absolute bottom-6 right-6 z-40 w-12 h-12 bg-accent hover:bg-accent-hover text-white rounded-full shadow-lg flex items-center justify-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
          title="打开聊天"
        >
          <ChatBubbleLeftRightIcon className="w-6 h-6" />
        </button>
      )}

      {/* Sidebar */}
      {isOpen && (
        <>
          {/* Resize handle */}
          <div
            className="w-1 flex-shrink-0 hover:bg-blue-400/50 active:bg-accent/60 transition-colors cursor-col-resize"
            onMouseDown={handleDragStart}
            title="拖动调整宽度"
          />

          {/* Chat panel container */}
          <div
            className={clsx(
              'flex-shrink-0 border-l border-white/40 bg-white/60 backdrop-blur-sm flex flex-col overflow-hidden'
            )}
            style={{ width }}
          >
            {/* Header */}
            <div className="flex-shrink-0 flex items-center justify-between px-3 py-2 border-b border-white/40 bg-white/40">
              <div className="flex items-center gap-2">
                <ChatBubbleLeftRightIcon className="w-4 h-4 text-blue-500" />
                <span className="text-sm font-medium text-ink/80">文档问答</span>
              </div>
              <button
                onClick={onToggle}
                aria-label="关闭侧边栏"
                className="p-2 inline-flex items-center justify-center min-h-[44px] min-w-[44px] hover:bg-gray-100 rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                title="收起"
              >
                <ChevronRightIcon className="w-4 h-4 text-ink/50" />
              </button>
            </div>

            {/* Chat content */}
            <div className="flex-1 overflow-hidden">
              <DocChatPanel
                chatId={chatId}
                documentId={_documentId}
              />
            </div>
          </div>
        </>
      )}
    </>
  )
}

export default DocChatSidebar
