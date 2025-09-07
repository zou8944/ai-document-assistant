/**
 * Main sidebar component with three sections: Knowledge, Chat, Settings
 */

import React, { useState } from 'react'
import { 
  BookOpenIcon,
  ChatBubbleLeftRightIcon,
  Cog6ToothIcon,
  PlusIcon
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import { SidebarSection } from '../../types/app'
import ChatItem from './ChatItem'

interface SidebarProps {
  className?: string
}

export const Sidebar: React.FC<SidebarProps> = ({ className }) => {
  const {
    activeSidebarSection,
    setActiveSidebarSection,
    chatSessions,
    setActiveChat,
    activeChat,
    addChatSession,
    updateChatSession,
    deleteChatSession,
    reorderChatSessions
  } = useAppStore()

  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)

  const handleSectionClick = (section: SidebarSection) => {
    setActiveSidebarSection(section)
    
    if (section === 'knowledge' || section === 'settings') {
      // 当切换到知识库或设置时，清除当前聊天选中状态
      setActiveChat(null)
    } else if (section === 'chat' && chatSessions.length > 0 && !activeChat) {
      // 当切换到聊天且没有选中的聊天时，选择第一个聊天
      setActiveChat(chatSessions[0].id)
    }
  }

  const handleAddChat = () => {
    const newChat = {
      id: `chat_${Date.now()}`,
      name: `新对话 ${chatSessions.length + 1}`,
      knowledgeBaseIds: [],
      createdAt: new Date().toISOString(),
      lastMessageAt: new Date().toISOString(),
      messageCount: 0
    }
    addChatSession(newChat)
    setActiveChat(newChat.id)
    setActiveSidebarSection('chat')
  }

  const handleChatClick = (chatId: string) => {
    setActiveChat(chatId)
    setActiveSidebarSection('chat')
  }

  const handleChatRename = (chatId: string, newName: string) => {
    updateChatSession(chatId, { name: newName })
  }

  const handleChatDelete = (chatId: string) => {
    if (window.confirm('确定要删除这个聊天吗？这个操作无法撤销。')) {
      deleteChatSession(chatId)
    }
  }

  const handleDragStart = (index: number) => {
    setDragIndex(index)
    setDragOverIndex(null)
  }

  const handleDragOver = (index: number) => {
    if (dragIndex !== null && dragIndex !== index) {
      setDragOverIndex(index)
    }
  }

  const handleDrop = () => {
    if (dragIndex !== null && dragOverIndex !== null && dragIndex !== dragOverIndex) {
      reorderChatSessions(dragIndex, dragOverIndex)
    }
    setDragIndex(null)
    setDragOverIndex(null)
  }

  return (
    <div className={clsx('flex flex-col h-full bg-white/80 backdrop-blur-md', className)}>
      {/* Knowledge Base Section - Fixed at top */}
      <div className="flex-shrink-0 p-4 border-b border-gray-200/50">
        <button
          onClick={() => handleSectionClick('knowledge')}
          className={clsx(
            'w-full flex items-center space-x-3 p-3 rounded-xl transition-all duration-200',
            activeSidebarSection === 'knowledge'
              ? 'bg-blue-500 text-white shadow-lg'
              : 'text-gray-700 hover:bg-gray-100/50'
          )}
        >
          <BookOpenIcon className="w-5 h-5" />
          <span className="font-medium">知识库</span>
        </button>
      </div>

      {/* Chat Section - Scrollable middle area */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex-shrink-0 p-4 pb-2 border-b border-gray-200/50">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">
              聊天
            </h3>
            <button
              onClick={handleAddChat}
              className="p-1 rounded-md hover:bg-gray-100/50 transition-colors"
              title="新建聊天"
            >
              <PlusIcon className="w-4 h-4 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Scrollable chat list */}
        <div className="flex-1 overflow-y-auto px-4 py-2 space-y-1">
          {chatSessions.map((chat, index) => (
            <ChatItem
              key={chat.id}
              chat={chat}
              index={index}
              isActive={activeChat === chat.id}
              onSelect={handleChatClick}
              onRename={handleChatRename}
              onDelete={handleChatDelete}
              onDragStart={handleDragStart}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              isDragging={dragIndex === index}
              dragOverIndex={dragOverIndex}
            />
          ))}
          
          {chatSessions.length === 0 && (
            <div className="text-center text-gray-500 text-sm py-8">
              <ChatBubbleLeftRightIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>暂无聊天记录</p>
              <p className="text-xs mt-1">点击上方 + 按钮创建新对话</p>
            </div>
          )}
        </div>
      </div>

      {/* Settings Section - Fixed at bottom */}
      <div className="flex-shrink-0 p-4 border-t border-gray-200/50">
        <button
          onClick={() => handleSectionClick('settings')}
          className={clsx(
            'w-full flex items-center space-x-3 p-3 rounded-xl transition-all duration-200',
            activeSidebarSection === 'settings'
              ? 'bg-blue-500 text-white shadow-lg'
              : 'text-gray-700 hover:bg-gray-100/50'
          )}
        >
          <Cog6ToothIcon className="w-5 h-5" />
          <span className="font-medium">设置</span>
        </button>
      </div>
    </div>
  )
}

export default Sidebar