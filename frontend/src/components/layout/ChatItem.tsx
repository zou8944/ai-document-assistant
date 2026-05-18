/**
 * Chat item component with rename, drag, and delete functionality
 */

import React, { useState, useRef, useEffect } from 'react'
import { ChatBubbleLeftRightIcon, EllipsisVerticalIcon, PencilIcon, TrashIcon } from '@heroicons/react/24/outline'
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
  onDragEnd: () => void
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
  onDragEnd,
  isDragging,
  dragOverIndex
}) => {
  const [isEditing, setIsEditing] = useState(false)
  const [editName, setEditName] = useState(chat.name)
  const [showMenu, setShowMenu] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isEditing])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (showMenu && menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowMenu(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showMenu])

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

  const handleMenuToggle = (e: React.MouseEvent) => {
    e.stopPropagation()
    setShowMenu((prev) => !prev)
  }

  const handleRenameClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setShowMenu(false)
    setIsEditing(true)
    setEditName(chat.name)
  }

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    setShowMenu(false)
    onDelete(chat.id)
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
    <div className={clsx('relative', showMenu && 'z-50')}>
      <div
        draggable={!isEditing}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onDragEnd={onDragEnd}
        onClick={() => !isEditing && onSelect(chat.id)}
        className={clsx(
          'group w-full flex items-center space-x-3 p-3 rounded-lg text-left transition-all duration-200 cursor-pointer select-none',
          !showMenu && 'hover:scale-[1.02] active:scale-[0.98]',
          isActive
            ? 'brand-surface shadow-md shadow-[#007AFF]/20'
            : 'text-[#1c1c1e] hover:bg-white/50',
          isDragging && 'opacity-50',
          dragOverIndex === index && 'border-t-2 border-[#007AFF]'
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
              className={clsx(
                'w-full rounded px-1.5 py-0.5 outline-none font-medium text-current placeholder-current/60',
                isActive
                  ? 'bg-white/20 ring-1 ring-white/50 focus:ring-white'
                  : 'bg-black/5 ring-1 ring-black/15 focus:ring-[#007AFF]'
              )}
              placeholder="输入聊天名称..."
            />
          ) : (
            <div className="font-medium truncate">{chat.name}</div>
          )}
          <div className={clsx(
            'text-xs truncate',
            isActive ? 'text-white/80' : 'text-[#8E8E93]'
          )}>
            {chat.messageCount > 0
              ? `${chat.messageCount} 条消息`
              : '暂无消息'
            }
          </div>
        </div>

        {/* More button - visible on hover */}
        {!isEditing && (
          <div className="relative" ref={menuRef}>
            <button
              onClick={handleMenuToggle}
              className={clsx(
                'p-1 rounded-md transition-all duration-200 opacity-0 group-hover:opacity-100',
                isActive ? 'hover:bg-white/20' : 'hover:bg-gray-200/50',
                showMenu && 'opacity-100'
              )}
            >
              <EllipsisVerticalIcon className="w-4 h-4" />
            </button>

            {/* Dropdown menu */}
            {showMenu && (
              <div className="absolute right-0 top-full mt-1 z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-[140px]">
                <button
                  onClick={handleRenameClick}
                  className="w-full px-3 py-2 text-left text-sm text-[#1c1c1e] hover:bg-gray-100 flex items-center space-x-2"
                >
                  <PencilIcon className="w-4 h-4" />
                  <span>修改对话名称</span>
                </button>
                <button
                  onClick={handleDeleteClick}
                  className="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center space-x-2"
                >
                  <TrashIcon className="w-4 h-4" />
                  <span>删除对话</span>
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default ChatItem