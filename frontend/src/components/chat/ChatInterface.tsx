/**
 * Chat interface with breadcrumb and knowledge base management
 */

import React, { useState, useRef, useEffect } from 'react'
import {
  PlusIcon,
  PaperAirplaneIcon,
  UserIcon,
  CpuChipIcon,
  ChevronDownIcon,
  ChevronUpIcon
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { useAppStore } from '../../store/appStore'
import { 
  useAPIClient, 
  extractData, 
  ChatMessage as APIChatMessage, 
  SourceReference,
  SSEEvent,
  UpdateChatRequest
} from '../../services/apiClient'
import KnowledgeBaseSelector from './KnowledgeBaseSelector'

// Markdown content component with custom styling
const MarkdownContent: React.FC<{ content: string; isUser?: boolean }> = ({ content, isUser = false }) => {
  if (isUser) {
    // User messages don't need markdown rendering
    return <p className="whitespace-pre-wrap">{content}</p>
  }

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkBreaks]}
      components={{
        // Custom styling for different markdown elements
        h1: ({ children }) => <h1 className="text-lg font-bold mb-2 text-gray-900">{children}</h1>,
        h2: ({ children }) => <h2 className="text-base font-semibold mb-2 text-gray-900">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-semibold mb-1 text-gray-900">{children}</h3>,
        p: ({ children }) => <p className="mb-2 last:mb-0 text-gray-900 leading-relaxed">{children}</p>,
        ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1 text-gray-900">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1 text-gray-900">{children}</ol>,
        li: ({ children }) => <li className="text-gray-900">{children}</li>,
        blockquote: ({ children }) => (
          <blockquote className="border-l-4 border-gray-300 pl-4 py-2 mb-2 bg-gray-50 text-gray-700 italic">
            {children}
          </blockquote>
        ),
        code: ({ inline, className, children, ...props }) => {
          if (inline) {
            return (
              <code
                className="bg-gray-100 text-gray-800 px-1 py-0.5 rounded text-xs font-mono"
                {...props}
              >
                {children}
              </code>
            )
          }
          return (
            <div className="my-2">
              <pre className="bg-gray-900 text-gray-100 p-3 rounded-lg overflow-x-auto text-xs">
                <code className={className} {...props}>
                  {children}
                </code>
              </pre>
            </div>
          )
        },
        table: ({ children }) => (
          <div className="overflow-x-auto mb-2">
            <table className="min-w-full border border-gray-300 text-xs">
              {children}
            </table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-gray-50">{children}</thead>,
        tbody: ({ children }) => <tbody>{children}</tbody>,
        tr: ({ children }) => <tr className="border-b border-gray-200">{children}</tr>,
        th: ({ children }) => (
          <th className="border border-gray-300 px-2 py-1 text-left font-semibold text-gray-900">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="border border-gray-300 px-2 py-1 text-gray-900">
            {children}
          </td>
        ),
        strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
        em: ({ children }) => <em className="italic text-gray-900">{children}</em>,
        a: ({ href, children }) => (
          <a
            href={href}
            className="text-blue-600 hover:text-blue-800 underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            {children}
          </a>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: string
  sources?: SourceReference[]
}

// Component for collapsible source references
const SourceReferences: React.FC<{ sources: SourceReference[] }> = ({ sources }) => {
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
          {sources.map((source, index) => (
            <div key={index} className="text-xs bg-gray-50/50 rounded p-2 border border-gray-200/30">
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

// Map API message to UI message
const mapAPIMessageToUIMessage = (msg: APIChatMessage): Message => {
  return {
    id: msg.message_id,
    type: msg.role,
    content: msg.content,
    timestamp: msg.created_at,
    sources: msg.sources || []
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
  const [currentStreamingSources, setCurrentStreamingSources] = useState<SourceReference[]>([])  
  const [currentStreamingMessageId, setCurrentStreamingMessageId] = useState<string | null>(null)
  const [isInitialLoad, setIsInitialLoad] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const apiClient = useAPIClient()
  
  const {
    getCurrentChat,
    knowledgeBases,
    updateChatSession
  } = useAppStore()

  const currentChat = getCurrentChat()

  // Scroll to bottom when new messages arrive, streaming content updates, or loading state changes
  useEffect(() => {
    if (messagesEndRef.current) {
      if (isInitialLoad) {
        // On initial load, scroll immediately without animation
        messagesEndRef.current.scrollIntoView({ behavior: 'instant' })
        setIsInitialLoad(false)
      } else {
        // For new messages, streaming content, or loading changes, use smooth scroll
        messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
      }
    }
  }, [messages, streamingContent, isLoading, isStreaming, isInitialLoad])

  // Load chat messages from API
  useEffect(() => {
    if (currentChat) {
      setIsInitialLoad(true) // Reset initial load flag when switching chats
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
    setCurrentStreamingSources([])
    setCurrentStreamingMessageId(null)

    try {
      await apiClient.sendMessageStream(
        currentChat.id,
        { message: userMessageContent, include_sources: true },
        (event) => handleStreamEvent(event, userMessageContent),
        handleStreamError
      )
    } catch (error) {
      console.error('发送消息失败:', error)
      setIsLoading(false)
      setIsStreaming(false)
      alert('发送消息失败: ' + (error as Error).message)
    }
  }
  
  const handleStreamEvent = (event: SSEEvent, userMessageContent?: string) => {
    console.log('Stream event:', event)
    
    switch (event.event) {
      case 'metadata':
        // Add user message to UI immediately
        const userMessage: Message = {
          id: `user_${Date.now()}`,
          type: 'user',
          content: event.data?.user_message || userMessageContent || '用户消息',
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
        // Store sources for final message
        if (event.data && Array.isArray(event.data)) {
          setCurrentStreamingSources(event.data)
        }
        break
        
      case 'content':
        // Streaming content
        if (event.data && event.data.content) {
          setStreamingContent(prev => prev + event.data.content)
        }
        break
        
      case 'done':
        // Response complete - use the accumulated streaming content
        setIsLoading(false)
        setIsStreaming(false)
        
        // Use a functional update to get the latest streaming content
        setStreamingContent(currentContent => {
          const finalContent = event.data?.content || currentContent
          const finalSources = event.data?.sources || currentStreamingSources
          
          // Only add the AI message if we have content
          if (finalContent) {
            const aiMessage: Message = {
              id: event.data?.message_id || currentStreamingMessageId || `ai_${Date.now()}`,
              type: 'assistant',
              content: finalContent,
              timestamp: new Date().toISOString(),
              sources: finalSources
            }
            setMessages(prev => [...prev, aiMessage])
          }
          
          return '' // Reset streaming content
        })
        
        // Reset other streaming state
        setCurrentStreamingSources([])
        setCurrentStreamingMessageId(null)
        
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
        setCurrentStreamingSources([])
        setCurrentStreamingMessageId(null)
        alert('生成回复失败: ' + (event.data?.message || '未知错误'))
        break
        
      default:
        // Handle generic data events from basic streaming
        if (event.event === 'data' && event.data) {
          // This might be the basic streaming format
          if (event.data.content) {
            setStreamingContent(prev => prev + event.data.content)
          }
          if (event.data.message_id && !currentStreamingMessageId) {
            setCurrentStreamingMessageId(event.data.message_id)
          }
          if (event.data.sources) {
            setCurrentStreamingSources(event.data.sources)
          }
        }
        break
    }
  }
  
  const handleStreamError = (error: Error) => {
    console.error('流式响应错误:', error)
    setIsLoading(false)
    setIsStreaming(false)
    setStreamingContent('')
    setCurrentStreamingSources([])
    setCurrentStreamingMessageId(null)
    alert('生成回复失败: ' + error.message)
  }


  const handleUpdateKnowledgeBases = async (selectedKbIds: string[]) => {
    if (!currentChat) return
    
    try {
      // Update the chat with new knowledge base collection IDs via API
      const updateRequest: UpdateChatRequest = {
        collection_ids: selectedKbIds
      }
      
      const response = await apiClient.updateChat(currentChat.id, updateRequest)
      const updatedChat = extractData(response)
      
      // Update local state with the response from API
      updateChatSession(currentChat.id, {
        knowledgeBaseIds: updatedChat.collection_ids
      })
      
      console.log('Knowledge bases updated successfully:', selectedKbIds)
    } catch (error) {
      console.error('Failed to update knowledge bases:', error)
      alert('更新知识库失败: ' + (error as Error).message)
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
            <span className="text-gray-500">当前知识库: </span>
            {kbNames.length > 0 ? (
              <span className="text-gray-900 font-medium">
                {kbNames.join(' + ')}
              </span>
            ) : (
              <span className="text-gray-500">暂无知识库</span>
            )}
          </div>
          
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setShowKnowledgeBaseSelector(true)}
              className="flex items-center space-x-1 text-sm text-blue-500 hover:text-blue-600 transition-colors"
            >
              <PlusIcon className="w-4 h-4" />
              <span>管理知识库</span>
            </button>
          </div>
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
                  <MarkdownContent content={msg.content} isUser={msg.type === 'user'} />
                  
                  {/* Sources */}
                  <SourceReferences sources={msg.sources || []} />
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
        {isStreaming && (
          <div className="flex justify-start">
            <div className="flex max-w-3xl space-x-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 text-gray-600 flex items-center justify-center">
                <CpuChipIcon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="px-4 py-3 rounded-2xl bg-white/80 backdrop-blur-sm border border-gray-200/50 text-gray-900">
                  {streamingContent ? (
                    <>
                      <MarkdownContent content={streamingContent} />
                      <div className="mt-2 w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                    </>
                  ) : (
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Loading indicator - only show when not streaming */}
        {isLoading && !isStreaming && (
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
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !isLoading && !isStreaming) {
                  e.preventDefault()
                  handleSendMessage()
                }
              }}
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
        onSelect={handleUpdateKnowledgeBases}
        selectedIds={currentChat.knowledgeBaseIds}
      />
    </div>
  )
}

export default ChatInterface