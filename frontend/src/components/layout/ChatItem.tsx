/**
 * Chat item component with rename, drag, and delete functionality
 */

import React, { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { ChatBubbleLeftRightIcon, EllipsisVerticalIcon, PencilIcon, TrashIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { ChatSession } from '../../types/app'

interface ChatItemProps {
  chat: ChatSession
  isActive: boolean
  isExiting: boolean
  index: number
  registerRef: (id: string, el: HTMLDivElement | null) => void
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
  isExiting,
  index,
  registerRef,
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
  const [menuPos, setMenuPos] = useState<{ top: number; right: number } | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select()
    }
  }, [isEditing])

  useEffect(() => {
    if (!showMenu) return
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node
      const insideButton = buttonRef.current?.contains(target)
      const insideDropdown = dropdownRef.current?.contains(target)
      if (!insideButton && !insideDropdown) {
        setShowMenu(false)
      }
    }
    // 滚动时关闭菜单，避免 fixed 定位的菜单与按钮脱离
    const handleScroll = () => setShowMenu(false)
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('scroll', handleScroll, true)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('scroll', handleScroll, true)
    }
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
    if (!showMenu && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect()
      setMenuPos({
        top: rect.bottom + 4,
        right: window.innerWidth - rect.right,
      })
    }
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
    <div
      className={clsx(
        'grid transition-[grid-template-rows,opacity,padding-bottom] duration-300 ease-out',
        isExiting ? 'grid-rows-[0fr] opacity-0 pb-0' : 'grid-rows-[1fr] opacity-100 pb-1'
      )}
    >
      <div className="overflow-hidden">
        <div
          ref={(el) => registerRef(chat.id, el)}
          className="relative"
        >
          <div
            draggable={!isEditing}
            onDragStart={handleDragStart}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onDragEnd={onDragEnd}
            onClick={() => !isEditing && onSelect(chat.id)}
            className={clsx(
              'group w-full flex items-center space-x-3 p-3 rounded-lg text-left transition-colors duration-200 cursor-pointer select-none relative z-10',
              !showMenu && !isActive && 'hover:scale-[1.02] active:scale-[0.98]',
              isActive
                ? 'text-white'
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
              <>
                <button
                  ref={buttonRef}
                  onClick={handleMenuToggle}
                  className={clsx(
                    'p-1 rounded-lg transition-all duration-200 opacity-0 group-hover:opacity-100',
                    isActive ? 'hover:bg-white/20' : 'hover:bg-gray-200/50',
                    showMenu && 'opacity-100'
                  )}
                >
                  <EllipsisVerticalIcon className="w-4 h-4" />
                </button>

                {/* Dropdown menu rendered via portal to escape overflow:hidden of the grid wrapper */}
                {showMenu && menuPos && createPortal(
                  <div
                    ref={dropdownRef}
                    className="fixed z-[1000] bg-white border border-gray-200 rounded-lg shadow-lg py-1 min-w-[140px]"
                    style={{ top: menuPos.top, right: menuPos.right }}
                  >
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
                  </div>,
                  document.body
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ChatItem