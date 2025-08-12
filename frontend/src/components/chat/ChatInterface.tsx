/**
 * Chat interface with breadcrumb and knowledge base management
 */

import React, { useState, useRef, useEffect } from 'react'
import {
  PlusIcon,
  PaperAirplaneIcon,
  UserIcon,
  CpuChipIcon
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import KnowledgeBaseSelector from './KnowledgeBaseSelector'

interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: string
  sources?: Array<{
    name: string
    url?: string
  }>
}

interface ChatInterfaceProps {
  className?: string
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ className }) => {
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [showKnowledgeBaseSelector, setShowKnowledgeBaseSelector] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  const {
    getCurrentChat,
    knowledgeBases,
    updateChatSession
  } = useAppStore()

  const currentChat = getCurrentChat()

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Mock initial messages
  useEffect(() => {
    if (currentChat && messages.length === 0) {
      setMessages([
        {
          id: '1',
          type: 'assistant',
          content: '您好！我可以帮您解答关于已加载知识库的问题。请问有什么需要了解的吗？',
          timestamp: new Date().toISOString()
        }
      ])
    }
  }, [currentChat])

  const handleSendMessage = async () => {
    if (!message.trim() || isLoading) return

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      type: 'user',
      content: message.trim(),
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setMessage('')
    setIsLoading(true)

    // Mock AI response
    setTimeout(() => {
      const aiMessage: Message = {
        id: `msg_${Date.now()}_ai`,
        type: 'assistant',
        content: '这是一个模拟的回复。在实际应用中，这里会调用后端API来获取基于知识库的回答。',
        timestamp: new Date().toISOString(),
        sources: [
          { name: '用户手册.pdf' },
          { name: 'API文档', url: 'https://example.com/api' }
        ]
      }
      setMessages(prev => [...prev, aiMessage])
      setIsLoading(false)

      // Update chat session
      if (currentChat) {
        updateChatSession(currentChat.id, {
          messageCount: messages.length + 2,
          lastMessageAt: new Date().toISOString()
        })
      }
    }, 1500)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleAddKnowledgeBase = (kbIds: string[]) => {
    if (currentChat) {
      const updatedKbIds = [...new Set([...currentChat.knowledgeBaseIds, ...kbIds])]
      updateChatSession(currentChat.id, {
        knowledgeBaseIds: updatedKbIds
      })
    }
  }

  const getKnowledgeBaseNames = () => {
    if (!currentChat) return []
    return currentChat.knowledgeBaseIds
      .map(id => knowledgeBases.find(kb => kb.id === id)?.name)
      .filter(Boolean) as string[]
  }

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  if (!currentChat) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        <div className="text-center">
          <CpuChipIcon className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p>请选择一个聊天会话</p>
        </div>
      </div>
    )
  }

  const kbNames = getKnowledgeBaseNames()

  return (
    <div className={clsx('h-full flex flex-col', className)}>
      {/* Breadcrumb Header */}
      <div className="flex-shrink-0 p-4 bg-gradient-to-r from-white/90 to-white/70 backdrop-blur-sm border-b border-gray-200/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 text-sm">
            <span className="text-gray-500">📚</span>
            {kbNames.length > 0 ? (
              <span className="text-gray-900 font-medium">
                {kbNames.join(' > ')}
              </span>
            ) : (
              <span className="text-gray-500">暂无知识库</span>
            )}
          </div>
          
          <button
            onClick={() => setShowKnowledgeBaseSelector(true)}
            className="flex items-center space-x-1 text-sm text-blue-500 hover:text-blue-600 transition-colors"
          >
            <PlusIcon className="w-4 h-4" />
            <span>添加知识库</span>
          </button>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={clsx(
              'flex',
              msg.type === 'user' ? 'justify-end' : 'justify-start'
            )}
          >
            <div
              className={clsx(
                'flex max-w-3xl space-x-3',
                msg.type === 'user' ? 'flex-row-reverse space-x-reverse' : 'flex-row'
              )}
            >
              {/* Avatar */}
              <div className={clsx(
                'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
                msg.type === 'user' 
                  ? 'bg-blue-500 text-white' 
                  : 'bg-gray-200 text-gray-600'
              )}>
                {msg.type === 'user' ? (
                  <UserIcon className="w-4 h-4" />
                ) : (
                  <CpuChipIcon className="w-4 h-4" />
                )}
              </div>

              {/* Message Content */}
              <div className="flex-1 min-w-0">
                <div
                  className={clsx(
                    'px-4 py-3 rounded-2xl text-sm',
                    msg.type === 'user'
                      ? 'bg-blue-500 text-white'
                      : 'bg-white/80 backdrop-blur-sm border border-gray-200/50 text-gray-900'
                  )}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                  
                  {/* Sources */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-300/50">
                      <p className="text-xs opacity-75 mb-2">参考来源:</p>
                      <div className="space-y-1">
                        {msg.sources.map((source, index) => (
                          <div key={index} className="text-xs">
                            {source.url ? (
                              <a
                                href={source.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-200 hover:text-blue-100 underline"
                              >
                                {source.name}
                              </a>
                            ) : (
                              <span className="opacity-75">{source.name}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                
                <div className={clsx(
                  'mt-1 text-xs text-gray-500',
                  msg.type === 'user' ? 'text-right' : 'text-left'
                )}>
                  {formatTime(msg.timestamp)}
                </div>
              </div>
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="flex max-w-3xl space-x-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 text-gray-600 flex items-center justify-center">
                <CpuChipIcon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="px-4 py-3 rounded-2xl bg-white/80 backdrop-blur-sm border border-gray-200/50">
                  <div className="flex space-x-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="flex-shrink-0 p-4 border-t border-gray-200/50 bg-white/50 backdrop-blur-sm">
        <div className="flex space-x-3">
          <div className="flex-1 relative">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="输入您的问题..."
              disabled={isLoading}
              rows={1}
              className="w-full resize-none rounded-lg border border-gray-300 bg-white/80 backdrop-blur-sm px-4 py-3 pr-12 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
          </div>
          <button
            onClick={handleSendMessage}
            disabled={!message.trim() || isLoading}
            className="flex-shrink-0 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white p-3 rounded-lg transition-colors disabled:cursor-not-allowed"
          >
            <PaperAirplaneIcon className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Knowledge Base Selector Modal */}
      <KnowledgeBaseSelector
        isOpen={showKnowledgeBaseSelector}
        onClose={() => setShowKnowledgeBaseSelector(false)}
        onSelect={handleAddKnowledgeBase}
        excludeIds={currentChat.knowledgeBaseIds}
      />
    </div>
  )
}

export default ChatInterface