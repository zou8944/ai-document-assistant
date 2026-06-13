/**
 * Main sidebar component with three sections: Knowledge, Chat, Settings
 */

import React, { useCallback, useLayoutEffect, useRef, useState } from 'react'
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
import { useAPIClient, extractData, CreateChatRequest } from '../../services/apiClient'
import { useToast } from '../../hooks/useToast'
import ConfirmDialog from '../common/ConfirmDialog'

interface SidebarProps {
  className?: string
}

export const Sidebar: React.FC<SidebarProps> = ({ className }) => {
  const {
    activeSidebarSection,
    setActiveSidebarSection,
    chatSessions,
    setActiveChat,
    setActiveKnowledgeBase,
    activeChat,
    addChatSession,
    updateChatSession,
    deleteChatSession,
    reorderChatSessions,
    setChatSessions
  } = useAppStore()

  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null)
  const [exitingIds, setExitingIds] = useState<Set<string>>(() => new Set())
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
  const toast = useToast()

  // 选中指示器：跟随 activeChat 平滑滑动
  const listRef = useRef<HTMLDivElement>(null)
  const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const hasPositionedRef = useRef(false)
  const [indicatorRect, setIndicatorRect] = useState<{ top: number; height: number } | null>(null)
  const [indicatorAnimated, setIndicatorAnimated] = useState(false)
  // 指示器透明度：删除激活项时先淡出再触发列表滑动
  const [indicatorOpacity, setIndicatorOpacity] = useState(1)

  const registerItemRef = useCallback((id: string, el: HTMLDivElement | null) => {
    if (el) {
      itemRefs.current.set(id, el)
    } else {
      itemRefs.current.delete(id)
    }
  }, [])

  useLayoutEffect(() => {
    // 没有激活项时收起指示器，并重置首次定位标志
    if (!activeChat) {
      setIndicatorRect(null)
      setIndicatorAnimated(false)
      hasPositionedRef.current = false
      return
    }
    const itemEl = itemRefs.current.get(activeChat)
    const listEl = listRef.current
    if (!itemEl || !listEl) return
    const top = itemEl.offsetTop
    const height = itemEl.offsetHeight
    setIndicatorRect((prev) => {
      if (prev && prev.top === top && prev.height === height) return prev
      return { top, height }
    })
    // 首次定位不要 transition，之后才平滑过渡
    if (!hasPositionedRef.current) {
      hasPositionedRef.current = true
      // 下一帧再启用动画，避免初始定位时的瞬移有过渡
      requestAnimationFrame(() => setIndicatorAnimated(true))
    }
  }, [activeChat, chatSessions, exitingIds])

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

  const apiClient = useAPIClient()

  const handleAddChat = async () => {
    try {
      const request: CreateChatRequest = {
        name: `新对话 ${chatSessions.length + 1}`,
        collection_ids: [],
      }
      const response = await apiClient.createChat(request)
      const chat = extractData(response)

      const newChat = {
        id: chat.chat_id,
        name: chat.name,
        knowledgeBaseIds: chat.collection_ids || [],
        createdAt: chat.created_at,
        lastMessageAt: chat.last_message_at || chat.created_at,
        messageCount: chat.message_count || 0,
        boundCollectionId: chat.bound_collection_id,
      }
      addChatSession(newChat)
      setActiveChat(newChat.id)
      setActiveSidebarSection('chat')
    } catch (error) {
      console.error('创建聊天失败:', error)
      toast.error('创建聊天失败: ' + (error as Error).message)
    }
  }

  const handleChatClick = (chatId: string) => {
    const chat = chatSessions.find(c => c.id === chatId)
    if (chat?.boundCollectionId) {
      // Bound chat: switch to knowledge section
      setActiveKnowledgeBase(chat.boundCollectionId)
      setActiveSidebarSection('knowledge')
    } else {
      setActiveChat(chatId)
      setActiveSidebarSection('chat')
    }
  }

  const handleChatRename = async (chatId: string, newName: string) => {
    try {
      await apiClient.updateChat(chatId, { name: newName })
      updateChatSession(chatId, { name: newName })
    } catch (error) {
      console.error('重命名失败:', error)
      toast.error('重命名失败: ' + (error as Error).message)
    }
  }

  const handleChatDelete = (chatId: string) => {
    // Open confirm dialog; actual delete runs in performDeleteChat below
    setPendingDeleteId(chatId)
  }

  const performDeleteChat = async () => {
    const chatId = pendingDeleteId
    if (!chatId) return
    setPendingDeleteId(null)
    const isActiveBeingDeleted = activeChat === chatId
    try {
      await apiClient.deleteChat(chatId)
      // 删除激活项时，先让蓝色指示器淡出，再触发列表滑动
      if (isActiveBeingDeleted) {
        setIndicatorOpacity(0)
        await new Promise<void>((resolve) => window.setTimeout(resolve, 180))
      }
      // 标记为退场状态，触发收起动画
      setExitingIds((prev) => {
        const next = new Set(prev)
        next.add(chatId)
        return next
      })
      // 等待退场动画结束后再从 store 真正删除，下方项目滑上来填补
      window.setTimeout(() => {
        deleteChatSession(chatId)
        setExitingIds((prev) => {
          if (!prev.has(chatId)) return prev
          const next = new Set(prev)
          next.delete(chatId)
          return next
        })
        // 指示器透明度复位，供下次激活使用（此时 indicatorRect 已被卸载）
        if (isActiveBeingDeleted) {
          setIndicatorOpacity(1)
        }
      }, 300)
    } catch (error) {
      // 出错时恢复指示器
      if (isActiveBeingDeleted) {
        setIndicatorOpacity(1)
      }
      console.error('删除聊天失败:', error)
      toast.error('删除聊天失败: ' + (error as Error).message)
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

  const handleDrop = async () => {
    if (dragIndex === null || dragOverIndex === null || dragIndex === dragOverIndex) {
      return
    }
    // 1) 乐观更新本地顺序
    reorderChatSessions(dragIndex, dragOverIndex)
    // 2) 拿到新顺序提交后端
    const ids = useAppStore.getState().chatSessions.map((c) => c.id)
    try {
      await apiClient.reorderChats(ids)
    } catch (error) {
      console.error('排序保存失败:', error)
      // 失败：从后端重新拉一次，保证本地与服务端一致
      try {
        const res = await apiClient.listChats(0, 1000)
        const data = extractData(res)
        setChatSessions(data.chats.map((chat) => ({
          id: chat.chat_id,
          name: chat.name,
          knowledgeBaseIds: chat.collection_ids || [],
          createdAt: chat.created_at,
          lastMessageAt: chat.last_message_at || chat.created_at,
          messageCount: chat.message_count || 0,
          boundCollectionId: chat.bound_collection_id,
        })))
      } catch (reloadError) {
        console.error('重新拉取列表也失败:', reloadError)
      }
      toast.error('排序保存失败: ' + (error as Error).message)
    }
    // 状态清理交给 handleDragEnd，保证拖到任意位置（含原位 / 列表外 / Esc 取消）都能复位
  }

  const handleDragEnd = () => {
    setDragIndex(null)
    setDragOverIndex(null)
  }

  // Keyboard reorder: move the chat one slot up or down and persist the new order.
  // Reuses the same persistence path as drag-and-drop so server state stays in sync.
  const persistReorder = async (ids: string[]) => {
    try {
      await apiClient.reorderChats(ids)
    } catch (error) {
      console.error('排序保存失败:', error)
      toast.error('排序保存失败: ' + (error as Error).message)
    }
  }

  const handleMoveUp = (fromIndex: number) => {
    if (fromIndex <= 0) return
    reorderChatSessions(fromIndex, fromIndex - 1)
    const ids = useAppStore.getState().chatSessions
      .map((c) => c.id)
      .filter((_, i) => i !== fromIndex)
    ids.splice(fromIndex - 1, 0, useAppStore.getState().chatSessions[fromIndex].id)
    void persistReorder(ids)
  }

  const handleMoveDown = (fromIndex: number) => {
    if (fromIndex >= chatSessions.length - 1) return
    reorderChatSessions(fromIndex, fromIndex + 1)
    const ids = useAppStore.getState().chatSessions
      .map((c) => c.id)
      .filter((_, i) => i !== fromIndex)
    ids.splice(fromIndex + 1, 0, useAppStore.getState().chatSessions[fromIndex].id)
    void persistReorder(ids)
  }

  return (
    <div className={clsx('flex flex-col h-full w-full bg-white/60 backdrop-blur-xl border-r border-white/20', className)}>
      {/* Knowledge Base Section - Fixed at top */}
      <div className="flex-shrink-0 p-4 border-b border-white/40">
        <button
          onClick={() => handleSectionClick('knowledge')}
          className={clsx(
            'w-full flex items-center space-x-3 p-3 rounded-xl transition-all duration-200',
            activeSidebarSection === 'knowledge'
              ? 'brand-surface shadow-md shadow-accent/20'
              : 'text-ink hover:bg-white/50'
          )}
        >
          <BookOpenIcon className="w-5 h-5" />
          <span className="font-medium">知识库</span>
        </button>
      </div>

      {/* Chat Section - Scrollable middle area */}
      <div className="flex-1 flex flex-col min-h-0">
        <div className="flex-shrink-0 p-4 pb-2 border-b border-white/40">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-muted uppercase tracking-wide">
              聊天
            </h3>
            <button
              onClick={handleAddChat}
              aria-label="新建聊天"
              className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] p-2 rounded-lg hover:bg-white/50 text-muted hover:text-ink transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
            >
              <PlusIcon className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Scrollable chat list */}
        <div
          ref={listRef}
          className="relative flex-1 overflow-y-auto px-4 py-2"
        >
          {/* 选中指示器：跟随 activeChat 滑动 */}
          {indicatorRect && (
            <div
              aria-hidden
              className={clsx(
                'pointer-events-none absolute left-4 right-4 brand-surface rounded-lg shadow-md shadow-accent/20',
                indicatorAnimated && 'transition-[transform,height,opacity] duration-300 ease-out'
              )}
              style={{
                transform: `translateY(${indicatorRect.top}px)`,
                height: `${indicatorRect.height}px`,
                top: 0,
                opacity: indicatorOpacity,
                transitionDuration: indicatorOpacity === 0 ? '180ms' : undefined,
              }}
            />
          )}
          {chatSessions.map((chat, index) => (
            <ChatItem
              key={chat.id}
              chat={chat}
              index={index}
              isActive={activeChat === chat.id}
              isExiting={exitingIds.has(chat.id)}
              registerRef={registerItemRef}
              onSelect={handleChatClick}
              onRename={handleChatRename}
              onDelete={handleChatDelete}
              onDragStart={handleDragStart}
              onDragOver={handleDragOver}
              onDrop={handleDrop}
              onDragEnd={handleDragEnd}
              totalCount={chatSessions.length}
              onMoveUp={handleMoveUp}
              onMoveDown={handleMoveDown}
              isDragging={dragIndex === index}
              dragOverIndex={dragOverIndex}
            />
          ))}
          
          {chatSessions.length === 0 && (
            <div className="text-center text-muted text-sm py-8">
              <ChatBubbleLeftRightIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>暂无聊天记录</p>
              <p className="text-xs mt-1 opacity-75">点击上方 + 按钮创建新对话</p>
            </div>
          )}
        </div>
      </div>

      {/* Settings Section - Fixed at bottom */}
      <div className="flex-shrink-0 p-4 border-t border-white/40">
        <button
          onClick={() => handleSectionClick('settings')}
          className={clsx(
            'w-full flex items-center space-x-3 p-3 rounded-xl transition-all duration-200',
            activeSidebarSection === 'settings'
              ? 'brand-surface shadow-md shadow-accent/20'
              : 'text-ink hover:bg-white/50'
          )}
        >
          <Cog6ToothIcon className="w-5 h-5" />
          <span className="font-medium">设置</span>
        </button>
      </div>

      {/* Delete chat confirmation */}
      <ConfirmDialog
        open={pendingDeleteId !== null}
        onClose={() => setPendingDeleteId(null)}
        onConfirm={performDeleteChat}
        title="删除聊天"
        message="确定要删除这个聊天吗？这个操作无法撤销。"
        confirmLabel="删除"
        destructive
      />
    </div>
  )
}

export default Sidebar