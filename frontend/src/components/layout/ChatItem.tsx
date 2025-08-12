/**
 * Chat item component with rename, drag, and delete functionality
 */

import React, { useState, useRef, useEffect } from 'react'
import { ChatBubbleLeftRightIcon, XMarkIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { ChatSession } from '../../types/app'

interface ChatItemProps {
  chat: ChatSession
  isActive: boolean
  index: number
  onSelect: (chatId: string) => void
  onRename: (chatId: string, newName: string) => void
  onDelete: (chatId: string) => void
  onDragStart: (index: number) => void
  onDragOver: (index: number) => void
  onDrop: () => void
  isDragging: boolean
  dragOverIndex: number | null
}

export const ChatItem: React.FC<ChatItemProps> = ({
  chat,
  isActive,
  index,
  onSelect,
  onRename,
  onDelete,
  onDragStart,
  onDragOver,
  onDrop,
  isDragging,
  dragOverIndex
}) => {
  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState(chat.name)
  const [showContextMenu, setShowContextMenu] = useState(false)
  const [contextMenuPos, setContextMenuPos] = useState({ x: 0, y: 0 })
  const inputRef = useRef<HTMLInputElement>(null)
  const itemRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isEditing])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (showContextMenu && itemRef.current && !itemRef.current.contains(event.target as Node)) {
        setShowContextMenu(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showContextMenu])

  const handleDoubleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsEditing(true)
    setEditName(chat.name)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSaveName()
    } else if (e.key === 'Escape') {
      setIsEditing(false)
      setEditName(chat.name)
    }
  }

  const handleSaveName = () => {
    const trimmedName = editName.trim()
    if (trimmedName && trimmedName !== chat.name) {
      onRename(chat.id, trimmedName)
    }
    setIsEditing(false)
  }

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setContextMenuPos({ x: e.clientX, y: e.clientY })
    setShowContextMenu(true)
  }

  const handleDeleteClick = () => {
    onDelete(chat.id)
    setShowContextMenu(false)
  }

  const handleDragStart = (e: React.DragEvent) => {
    e.dataTransfer.effectAllowed = 'move'
    onDragStart(index)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    onDragOver(index)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    onDrop()
  }

  return (
    <div ref={itemRef} className="relative">
      <div
        draggable={!isEditing}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onDoubleClick={handleDoubleClick}
        onContextMenu={handleContextMenu}
        onClick={() => !isEditing && onSelect(chat.id)}
        className={clsx(
          'w-full flex items-center space-x-3 p-3 rounded-lg text-left transition-all duration-200 cursor-pointer select-none',
          'hover:scale-[1.02] active:scale-[0.98]',
          isActive
            ? 'bg-blue-500 text-white shadow-lg'
            : 'text-gray-700 hover:bg-gray-100/50',
          isDragging && 'opacity-50',
          dragOverIndex === index && 'border-t-2 border-blue-500'
        )}
      >
        <ChatBubbleLeftRightIcon className="w-4 h-4 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          {isEditing ? (
            <input
              ref={inputRef}
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onBlur={handleSaveName}
              onKeyDown={handleKeyDown}
              className="w-full bg-transparent border-none outline-none font-medium text-current placeholder-current/50"
              placeholder="输入聊天名称..."
            />
          ) : (
            <div className="font-medium truncate">{chat.name}</div>
          )}
          <div className={clsx(
            'text-xs truncate',
            isActive ? 'text-white/80' : 'text-gray-500'
          )}>
            {chat.messageCount > 0 
              ? `${chat.messageCount} 条消息`
              : '暂无消息'
            }
          </div>
        </div>
      </div>

      {/* Context Menu */}
      {showContextMenu && (
        <div
          className="fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-[120px]"
          style={{
            left: contextMenuPos.x,
            top: contextMenuPos.y,
          }}
        >
          <button
            onClick={handleDeleteClick}
            className="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center space-x-2"
          >
            <XMarkIcon className="w-4 h-4" />
            <span>删除聊天</span>
          </button>
        </div>
      )}
    </div>
  )
}

export default ChatItem