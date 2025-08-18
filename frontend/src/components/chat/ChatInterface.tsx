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
import { useAPIClient, extractData, ChatMessage as APIChatMessage, SSEEvent } from '../../services/apiClient'
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

// Map API message to UI message
const mapAPIMessageToUIMessage = (msg: APIChatMessage): Message => {
  let sources: Array<{ name: string, url?: string }> = []
  if (msg.sources) {
    try {
      const parsedSources = JSON.parse(msg.sources)
      sources = parsedSources.map((s: any) => ({
        name: s.document_name || s.name,
        url: s.url
      }))
    } catch (e) {
      console.error('Failed to parse sources:', e)
    }
  }
  
  return {
    id: msg.id,
    type: msg.role,
    content: msg.content,
    timestamp: msg.created_at,
    sources
  }
}

interface ChatInterfaceProps {
  className?: string
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ className }) => {
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [showKnowledgeBaseSelector, setShowKnowledgeBaseSelector] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const apiClient = useAPIClient()
  
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

  // Load chat messages from API
  useEffect(() => {
    if (currentChat) {
      loadChatMessages()
    }
  }, [currentChat])
  
  const loadChatMessages = async () => {
    if (!currentChat) return
    
    try {
      const response = await apiClient.getChatMessages(currentChat.id)
      const data = extractData(response)
      const uiMessages = data.messages.map(mapAPIMessageToUIMessage)
      setMessages(uiMessages)
      
      // If no messages, add a welcome message
      if (uiMessages.length === 0) {
        setMessages([{
          id: 'welcome',
          type: 'assistant',
          content: '您好！我可以帮您解答关于已加载知识库的问题。请问有什么需要了解的吗？',
          timestamp: new Date().toISOString()
        }])
      }
    } catch (error) {
      console.error('加载聊天消息失败:', error)
    }
  }

  const handleSendMessage = async () => {
    if (!message.trim() || isLoading || !currentChat) return

    const userMessageContent = message.trim()
    setMessage('')
    setIsLoading(true)
    setIsStreaming(true)
    setStreamingContent('')

    try {
      // Send message via streaming API
      await apiClient.sendMessageStream(
        currentChat.id,
        { message: userMessageContent, include_sources: true },
        handleStreamEvent,
        handleStreamError
      )
    } catch (error) {
      console.error('发送消息失败:', error)
      setIsLoading(false)
      setIsStreaming(false)
      alert('发送消息失败: ' + (error as Error).message)
    }
  }
  
  const handleStreamEvent = (event: SSEEvent) => {
    console.log('Stream event:', event)
    
    switch (event.event) {
      case 'metadata':
        // Add user message to UI immediately
        const userMessage: Message = {
          id: `user_${Date.now()}`,
          type: 'user',
          content: event.data.user_message,
          timestamp: new Date().toISOString()
        }
        setMessages(prev => [...prev, userMessage])
        break
        
      case 'user_message':
        // User message saved to backend
        break
        
      case 'status':
        // Update loading status if needed
        break
        
      case 'sources':
        // Sources found - could show in UI if needed
        break
        
      case 'content':
        // Streaming content
        setStreamingContent(prev => prev + event.data.content)
        break
        
      case 'done':
        // Response complete
        setIsLoading(false)
        setIsStreaming(false)
        
        // Add complete AI message
        const aiMessage: Message = {
          id: event.data.message_id || `ai_${Date.now()}`,
          type: 'assistant',
          content: streamingContent,
          timestamp: new Date().toISOString()
        }
        setMessages(prev => [...prev, aiMessage])
        setStreamingContent('')
        
        // Update chat session
        if (currentChat) {
          updateChatSession(currentChat.id, {
            messageCount: messages.length + 2,
            lastMessageAt: new Date().toISOString()
          })
        }
        break
        
      case 'error':
        console.error('Stream error:', event.data)
        setIsLoading(false)
        setIsStreaming(false)
        setStreamingContent('')
        alert('生成回复失败: ' + event.data.message)
        break
        
      default:
        if (event.event === 'data') {
          // Handle generic data events
          console.log('Data event:', event.data)
        }
        break
    }
  }
  
  const handleStreamError = (error: Error) => {
    console.error('流式响应错误:', error)
    setIsLoading(false)
    setIsStreaming(false)
    setStreamingContent('')
    alert('生成回复失败: ' + error.message)
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !isLoading && !isStreaming) {
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

        {/* Streaming content */}
        {isStreaming && streamingContent && (
          <div className="flex justify-start">
            <div className="flex max-w-3xl space-x-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 text-gray-600 flex items-center justify-center">
                <CpuChipIcon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="px-4 py-3 rounded-2xl bg-white/80 backdrop-blur-sm border border-gray-200/50 text-gray-900">
                  <p className="whitespace-pre-wrap">{streamingContent}</p>
                  <div className="mt-2 w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Loading indicator */}
        {isLoading && !streamingContent && (
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
              disabled={isLoading || isStreaming}
              rows={1}
              className="w-full resize-none rounded-lg border border-gray-300 bg-white/80 backdrop-blur-sm px-4 py-3 pr-12 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
          </div>
          <button
            onClick={handleSendMessage}
            disabled={!message.trim() || isLoading || isStreaming}
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