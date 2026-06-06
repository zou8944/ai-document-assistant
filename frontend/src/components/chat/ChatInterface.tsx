/**
 * Chat interface - Hermes UI inspired design
 */

import React, { useState, useRef, useEffect, useCallback } from 'react'
import {
  PlusIcon,
  PaperAirplaneIcon,
  StopIcon,
  CpuChipIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import {
  useAPIClient,
  extractData,
  UpdateChatRequest,
} from '../../services/apiClient'
import { useChat } from '../../hooks/useChat'
import KnowledgeBaseSelector from './KnowledgeBaseSelector'
import DocumentPicker from './DocumentPicker'
import RichTextInput from './RichTextInput'
import MarkdownContent from './MarkdownContent'
import SourceReferences from './SourceReferences'
import AgentTrace from './AgentTrace'

interface DocumentMention {
  id: string
  name: string
  start: number
  end: number
}

interface ChatInterfaceProps {
  className?: string
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ className }) => {
  const [message, setMessage] = useState('')
  const [showKnowledgeBaseSelector, setShowKnowledgeBaseSelector] = useState(false)
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const wasNearBottomRef = useRef(true)
  const prevScrollHeightRef = useRef(0)
  const scrolledForChatRef = useRef<string | null>(null)
  const apiClient = useAPIClient()

  const {
    getCurrentChat,
    knowledgeBases,
    updateChatSession,
  } = useAppStore()

  const currentChat = getCurrentChat()

  const {
    messages,
    isLoading,
    isStreaming,
    streamingContent,
    streamingAgentState,
    processingStatus,
    sendMessage,
    stopGeneration,
    loadOlderMessages,
    hasMoreOlder,
    isLoadingOlder,
  } = useChat(currentChat?.id || null)

  // Smart auto-scroll: instant jump on chat switch, smooth only for new messages
  useEffect(() => {
    const chatId = currentChat?.id || null
    // First time seeing this chat with messages: instant jump to bottom
    if (chatId !== scrolledForChatRef.current && messages.length > 0) {
      scrolledForChatRef.current = chatId
      if (messagesEndRef.current) {
        messagesEndRef.current.scrollIntoView({ behavior: 'auto' })
      }
      wasNearBottomRef.current = true
      return
    }
    // Already scrolled for this chat: only smooth-scroll if user is near bottom
    if (wasNearBottomRef.current && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, streamingContent, streamingAgentState, isLoading, currentChat?.id])

  // Maintain scroll position when older messages are prepended
  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return
    const newScrollHeight = container.scrollHeight
    if (prevScrollHeightRef.current > 0 && newScrollHeight > prevScrollHeightRef.current) {
      container.scrollTop += newScrollHeight - prevScrollHeightRef.current
    }
    prevScrollHeightRef.current = 0
  }, [messages])

  const handleScroll = useCallback(() => {
    const container = scrollContainerRef.current
    if (!container) return

    // Track if user is near bottom (within 100px)
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    wasNearBottomRef.current = distanceFromBottom < 100

    // Load older messages when scrolled near top
    if (container.scrollTop < 80 && hasMoreOlder && !isLoadingOlder) {
      prevScrollHeightRef.current = container.scrollHeight
      loadOlderMessages()
    }
  }, [hasMoreOlder, isLoadingOlder, loadOlderMessages])

  const handleSendMessage = async () => {
    if (!message.trim() || isLoading || !currentChat) return

    const userMessageContent = getRealUserInput(message).trim()
    if (!userMessageContent) return
    setMessage('')

    // Always scroll to bottom when user sends a new message
    wasNearBottomRef.current = true
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }

    await sendMessage(
      userMessageContent,
      selectedDocumentIds.length > 0 ? selectedDocumentIds : undefined
    )
  }

  const handleUpdateKnowledgeBases = async (selectedKbIds: string[]) => {
    if (!currentChat) return

    try {
      const updateRequest: UpdateChatRequest = {
        collection_ids: selectedKbIds
      }

      const response = await apiClient.updateChat(currentChat.id, updateRequest)
      const updatedChat = extractData(response)

      updateChatSession(currentChat.id, {
        knowledgeBaseIds: updatedChat.collection_ids
      })

      console.log('Knowledge bases updated successfully:', selectedKbIds)
    } catch (error) {
      console.error('Failed to update knowledge bases:', error)
      alert('更新知识库失败: ' + (error as Error).message)
    }
  }

  const handleUpdateSelectedDocuments = (documentIds: string[]) => {
    setSelectedDocumentIds(documentIds)
  }

  const handleRichTextChange = (value: string, _mentions: DocumentMention[], mentionedDocIds: string[]) => {
    setMessage(value)

    if (mentionedDocIds.length > 0) {
      const allSelectedIds = [...new Set([...selectedDocumentIds, ...mentionedDocIds])]
      setSelectedDocumentIds(allSelectedIds)
    }
  }

  const getRealUserInput = (input: string): string => {
    return input.replace(/@\[[^\]]+\]\(doc:[^)]+\)/g, '').trim()
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
      <div className="flex items-center justify-center h-full text-muted">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full accent-tile flex items-center justify-center">
            <CpuChipIcon className="w-7 h-7 text-accent" />
          </div>
          <p className="font-display text-lg italic text-ink-soft">请选择一条对话</p>
          <p className="text-xs mt-1.5 text-muted">从左侧选一个 chat 开始，或创建新对话</p>
        </div>
      </div>
    )
  }

  const kbNames = getKnowledgeBaseNames()
  const isBoundChat = currentChat.boundCollectionId != null

  return (
    <div className={clsx('h-full flex flex-col', className)}>
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-3 border-b border-paper-edge/60 surface-glass">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <span className="section-label text-muted-soft">Reading</span>
            {kbNames.length > 0 ? (
              <span className="font-display italic text-ink-soft truncate">
                {kbNames.join(' · ')}
              </span>
            ) : (
              <span className="font-display italic text-muted">未指定文库</span>
            )}
          </div>

          {!isBoundChat && (
            <button
              onClick={() => setShowKnowledgeBaseSelector(true)}
              className="btn-ghost"
            >
              <PlusIcon className="w-3.5 h-3.5" />
              <span>管理文库</span>
            </button>
          )}
        </div>
      </div>

      {/* Messages Area */}
      <div ref={scrollContainerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto py-6">
          {/* Loading older messages indicator */}
          {isLoadingOlder && (
            <div className="px-6 py-3 flex justify-center">
              <div className="flex space-x-1.5">
                <div className="w-1.5 h-1.5 bg-muted-soft rounded-full animate-bounce" />
                <div className="w-1.5 h-1.5 bg-muted-soft rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                <div className="w-1.5 h-1.5 bg-muted-soft rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
              </div>
            </div>
          )}
          {messages.map((msg) => (
            <div key={msg.id} className={clsx(
              'px-6 py-4',
              msg.type === 'user' ? 'animate-message-user' : 'animate-message-ai'
            )}>
              {msg.type === 'user' ? (
                /* User message - right aligned bubble */
                <div className="flex justify-end">
                  <div className="max-w-2xl">
                    <div className="msg-user rounded-2xl rounded-br-md px-5 py-3 leading-relaxed text-[15px] text-white">
                      <MarkdownContent content={msg.content} isUser />
                    </div>
                    <div className="mt-1.5 text-[10px] tracking-wider text-muted-soft text-right uppercase">
                      {formatTime(msg.timestamp)}
                    </div>
                  </div>
                </div>
              ) : (
                /* AI message - left aligned with bubble + integrated agent trace */
                <div className="flex gap-3.5">
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 rounded-full accent-tile flex items-center justify-center">
                      <CpuChipIcon className="w-4 h-4 text-accent" />
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="msg-ai rounded-2xl rounded-tl-md px-5 py-3.5">
                      {msg.agentState && (
                        <AgentTrace state={msg.agentState} />
                      )}
                      <div className="text-[15px] leading-[1.7] text-ink">
                        <MarkdownContent content={msg.content} />
                      </div>
                      <SourceReferences sources={msg.sources || []} />
                    </div>
                    <div className="mt-1.5 ml-1 text-[10px] tracking-wider text-muted-soft uppercase">
                      {formatTime(msg.timestamp)}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Streaming content */}
          {isStreaming && (
            <div className="px-6 py-4">
              <div className="flex gap-3.5">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 rounded-full accent-tile flex items-center justify-center">
                    <CpuChipIcon className="w-4 h-4 text-accent" />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="msg-ai rounded-2xl rounded-tl-md px-5 py-3.5">
                    {processingStatus && (
                      <div className="mb-2.5 flex items-center gap-2 text-[11px] tracking-wider text-muted uppercase">
                        <div
                          className="w-2 h-2 rounded-full bg-accent animate-breathe"
                          style={{ boxShadow: '0 0 8px rgba(0,122,255,0.4)' }}
                        />
                        <span>{processingStatus}</span>
                      </div>
                    )}
                    {streamingAgentState && (
                      <AgentTrace state={streamingAgentState} />
                    )}
                    <div className="text-[15px] leading-[1.7] text-ink">
                      {streamingContent ? (
                        <>
                          <MarkdownContent content={streamingContent} />
                          <span
                            className="inline-block w-1.5 h-4 bg-accent ml-0.5 align-middle animate-breathe"
                            style={{ borderRadius: 1 }}
                          />
                        </>
                      ) : (
                        <div className="flex items-center gap-1.5 py-2">
                          <div className="w-1.5 h-1.5 bg-muted-soft rounded-full animate-breathe" />
                          <div className="w-1.5 h-1.5 bg-muted-soft rounded-full animate-breathe" style={{ animationDelay: '0.3s' }} />
                          <div className="w-1.5 h-1.5 bg-muted-soft rounded-full animate-breathe" style={{ animationDelay: '0.6s' }} />
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Loading indicator (between messages, no stream yet) */}
          {isLoading && !isStreaming && (
            <div className="px-6 py-4">
              <div className="flex gap-3.5">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 rounded-full accent-tile flex items-center justify-center">
                    <CpuChipIcon className="w-4 h-4 text-accent" />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="msg-ai rounded-2xl rounded-tl-md px-5 py-4">
                    <div className="flex items-center gap-1.5">
                      <div className="w-1.5 h-1.5 bg-muted-soft rounded-full animate-breathe" />
                      <div className="w-1.5 h-1.5 bg-muted-soft rounded-full animate-breathe" style={{ animationDelay: '0.3s' }} />
                      <div className="w-1.5 h-1.5 bg-muted-soft rounded-full animate-breathe" style={{ animationDelay: '0.6s' }} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="relative flex-shrink-0 surface-glass">
        {/* 顶部色差过渡层 */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-8 left-0 right-0 h-8 bg-gradient-to-b from-transparent to-paper/40"
        />
        <div className="max-w-4xl mx-auto px-6 py-4">
          {/* Document picker */}
          <DocumentPicker
            selectedDocumentIds={selectedDocumentIds}
            onDocumentSelect={handleUpdateSelectedDocuments}
          />

          {/* Input box */}
          <div className="group flex items-end gap-2.5 surface-card rounded-2xl px-4 py-3 transition-all duration-200 focus-within:border-accent/40 focus-within:bg-white/85 focus-within:shadow-lift">
            <div className="flex-1 relative">
              <RichTextInput
                value={message}
                onChange={handleRichTextChange}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey && !isLoading && !isStreaming) {
                    e.preventDefault()
                    handleSendMessage()
                  }
                }}
                placeholder="向 AI 文库提问，使用 @ 引用特定文档…"
                disabled={isLoading || isStreaming}
                className="w-full resize-none rounded-xl border-0 bg-transparent px-0 py-0.5 pr-2 text-[15px] text-ink placeholder:text-muted focus:ring-0 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>
            {isLoading || isStreaming ? (
              <button
                onClick={stopGeneration}
                className="flex-shrink-0 bg-ink hover:bg-ink-soft text-white p-2.5 rounded-xl transition-all active:scale-95 shadow-sm"
                title="停止生成"
              >
                <StopIcon className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleSendMessage}
                disabled={!getRealUserInput(message).trim()}
                className="btn-primary flex-shrink-0 p-2.5 disabled:!shadow-none disabled:!transform-none"
              >
                <PaperAirplaneIcon className="w-4 h-4" />
              </button>
            )}
          </div>
          <p className="mt-2 text-center text-[10px] tracking-wider text-muted-soft uppercase">
            Enter 发送 · Shift+Enter 换行
          </p>
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
