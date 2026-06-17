/**
 * Chat interface - Hermes UI inspired design
 */

import React, { useState, useRef, useEffect, useCallback } from 'react'
import { toast } from '../../hooks/useToast'
import {
  FolderPlusIcon,
  PaperAirplaneIcon,
  StopIcon,
  CpuChipIcon,
  ClipboardIcon,
  ArrowPathIcon,
  CheckIcon,
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
import DotsLoader from '../common/DotsLoader'

/**
 * Derive a stable, name-driven avatar (initials + gradient).
 * - CJK names → first 1–2 characters
 * - Latin names → uppercase initials (1–2 chars)
 * - Color is hashed from the name so the same KB always shows the same avatar.
 */
const getKbAvatar = (name: string | undefined): { initials: string; gradient: string; textColor: string } | null => {
  if (!name) return null
  const trimmed = name.trim()
  if (!trimmed) return null

  let initials: string
  if (/[㐀-鿿]/.test(trimmed)) {
    // CJK: take up to first 2 characters for a chunkier look in a tiny circle
    initials = trimmed.slice(0, 2)
  } else {
    const words = trimmed.split(/[\s_-]+/).filter(Boolean)
    if (words.length >= 2) {
      initials = (words[0][0] + words[1][0]).toUpperCase()
    } else {
      initials = trimmed.replace(/[^A-Za-z0-9]/g, '').slice(0, 2).toUpperCase() || trimmed.slice(0, 2).toUpperCase()
    }
  }

  // djb2-style hash → hue in [0, 360)
  let hash = 5381
  for (let i = 0; i < trimmed.length; i++) {
    hash = ((hash << 5) + hash + trimmed.charCodeAt(i)) & 0xffffffff
  }
  const hue = Math.abs(hash) % 360
  const hue2 = (hue + 28) % 360
  const gradient = `linear-gradient(135deg, hsl(${hue} 72% 82%) 0%, hsl(${hue2} 68% 68%) 100%)`
  const textColor = `hsl(${hue} 45% 22%)`
  return { initials, gradient, textColor }
}

const BotAvatar: React.FC<{ className?: string; title?: string; seed: ReturnType<typeof getKbAvatar> }> = ({ className, title, seed }) => {
  if (!seed) {
    return (
      <div className={clsx('w-7 h-7 rounded-full bg-accent/10 text-accent flex items-center justify-center', className)}>
        <CpuChipIcon className="w-3.5 h-3.5" />
      </div>
    )
  }
  return (
    <div
      className={clsx('w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-semibold tracking-wide select-none', className)}
      style={{
        background: seed.gradient,
        color: seed.textColor,
        boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.55), 0 1px 2px rgba(15,23,42,0.08)',
      }}
      title={title}
      aria-label={title}
    >
      <span
        aria-hidden
        className="absolute inset-0 rounded-full pointer-events-none"
        style={{ boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.35)' }}
      />
      <span className="relative">{seed.initials}</span>
    </div>
  )
}

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
  const [selectedDocumentNames, setSelectedDocumentNames] = useState<string[]>([])
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)
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

    const docIds = selectedDocumentIds.length > 0 ? [...selectedDocumentIds] : undefined
    const docNames = selectedDocumentNames.length > 0 ? [...selectedDocumentNames] : undefined

    setMessage('')
    setSelectedDocumentIds([])
    setSelectedDocumentNames([])

    // Always scroll to bottom when user sends a new message
    wasNearBottomRef.current = true
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }

    await sendMessage(userMessageContent, docIds, docNames)
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
      toast.error('更新知识库失败: ' + (error as Error).message)
    }
  }

  const handleUpdateSelectedDocuments = (documentIds: string[]) => {
    setSelectedDocumentIds(documentIds)
  }

  const handleCopyMessage = async (messageId: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedMessageId(messageId)
      setTimeout(() => setCopiedMessageId(null), 2000)
    } catch (error) {
      toast.error('复制失败: ' + (error as Error).message)
    }
  }

  // TODO: wire to regenerate API — find the last user message before this AI message
  // and re-send it. The backend needs a regenerate endpoint or we re-use sendMessage
  // with the previous user query. No regenerate function currently exists in
  // services/apiClient.ts or store/appStore.ts.
  const handleRegenerateMessage = (_messageId: string) => {
    // intentionally a no-op until the regenerate flow is wired
  }

  const handleRichTextChange = (value: string, mentions: DocumentMention[], mentionedDocIds: string[]) => {
    setMessage(value)

    // Always merge: RichTextInput removes @[name](doc:id) from text after
    // selection, so subsequent keystrokes produce empty mentionedDocIds.
    // We must preserve previously-selected documents across those calls.
    const allSelectedIds = [...new Set([...selectedDocumentIds, ...mentionedDocIds])]
    setSelectedDocumentIds(allSelectedIds)

    // Build name lookup: seed with existing names, then overlay new mentions
    const nameMap = new Map<string, string>()
    selectedDocumentIds.forEach((id, i) => {
      if (selectedDocumentNames[i]) nameMap.set(id, selectedDocumentNames[i])
    })
    mentions.forEach(m => nameMap.set(m.id, m.name))

    const allNames = allSelectedIds.map(id => nameMap.get(id) || id)
    setSelectedDocumentNames(allNames)
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
          <CpuChipIcon className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p>请选择一个聊天会话</p>
        </div>
      </div>
    )
  }

  const kbNames = getKnowledgeBaseNames()
  const isBoundChat = currentChat.boundCollectionId != null

  // Bot avatar is driven by the chat's first knowledge base (falls back to chip icon).
  const primaryKbId = currentChat.knowledgeBaseIds[0]
  const primaryKb = primaryKbId ? knowledgeBases.find(k => k.id === primaryKbId) : undefined
  const botAvatar = getKbAvatar(primaryKb?.name)

  return (
    <div className={clsx('h-full flex flex-col', className)}>
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-3 border-b border-white/40 bg-white/30 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-2 text-sm text-muted">
            <span>知识库:</span>
            {kbNames.length > 0 ? (
              <span className="text-ink font-medium">
                {kbNames.join(' + ')}
              </span>
            ) : (
              <span>暂无</span>
            )}
          </div>

          {!isBoundChat && (
            <button
              onClick={() => setShowKnowledgeBaseSelector(true)}
              className="flex items-center space-x-1 text-sm text-muted hover:text-accent transition-colors"
            >
              <FolderPlusIcon className="w-4 h-4" />
              <span>添加知识库</span>
            </button>
          )}
        </div>
      </div>

      {/* Messages Area */}
      <div ref={scrollContainerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto">
          {/* Loading older messages indicator */}
          {isLoadingOlder && (
            <div className="px-6 py-3 flex justify-center">
              <DotsLoader />
            </div>
          )}
          {messages.map((msg) => (
            <div key={msg.id} className={clsx(
              'px-6 py-3.5',
              msg.type === 'user' ? 'animate-message-user' : 'animate-message-ai'
            )}>
              {msg.type === 'user' ? (
                /* User message - right aligned card */
                <div className="flex justify-end">
                  <div className="max-w-3xl">
                    <div className="brand-surface rounded-2xl px-5 py-3">
                      <MarkdownContent content={msg.content} isUser />
                    </div>
                    {msg.documentNames && msg.documentNames.length > 0 && (
                      <div className="mt-1 flex items-center gap-1 text-xs text-neutral-400 justify-end">
                        <span>📄</span>
                        <span>基于：{msg.documentNames.join('、')}</span>
                      </div>
                    )}
                    <div className="mt-1.5 text-meta-xs text-muted text-right">
                      {formatTime(msg.timestamp)}
                    </div>
                  </div>
                </div>
              ) : (
                /* AI message - left aligned with bubble */
                <div className="flex space-x-4 group">
                  <div className="flex-shrink-0 relative">
                    <BotAvatar seed={botAvatar} title={primaryKb?.name} />
                  </div>
                  <div className="flex-1 min-w-0">
                    {msg.agentState && (
                      <AgentTrace state={msg.agentState} />
                    )}
                    <div className="bg-white/80 backdrop-blur-sm rounded-2xl px-5 py-3 border border-warm-line/40">
                      <div className="text-base leading-[1.7] text-ink">
                        <MarkdownContent content={msg.content} />
                      </div>
                      <SourceReferences sources={msg.sources || []} />
                    </div>
                    <div className="mt-1.5 flex items-center justify-between">
                      <div className="text-meta-xs text-muted">
                        {formatTime(msg.timestamp)}
                      </div>
                      <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                        <button
                          onClick={() => handleCopyMessage(msg.id, msg.content)}
                          className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] p-2 rounded-lg text-muted hover:text-ink hover:bg-white/60 transition-colors focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                          aria-label="复制消息"
                        >
                          {copiedMessageId === msg.id ? (
                            <CheckIcon className="w-4 h-4 text-apple-green" />
                          ) : (
                            <ClipboardIcon className="w-4 h-4" />
                          )}
                        </button>
                        <button
                          onClick={() => handleRegenerateMessage(msg.id)}
                          className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] p-2 rounded-lg text-muted hover:text-ink hover:bg-white/60 transition-colors focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                          aria-label="重新生成"
                        >
                          <ArrowPathIcon className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Streaming content */}
          {isStreaming && (
            <div className="px-6 py-3.5">
              <div className="flex space-x-4">
                <div className="flex-shrink-0 relative">
                  <BotAvatar seed={botAvatar} title={primaryKb?.name} />
                </div>
                <div className="flex-1 min-w-0">
                  {processingStatus && (
                    <div className="mb-2 flex items-center space-x-2 text-xs text-muted">
                      <div className="w-3 h-3 border-2 border-accent border-t-transparent rounded-full animate-spin" />
                      <span>{processingStatus}</span>
                    </div>
                  )}
                  {streamingAgentState && (
                    <AgentTrace state={streamingAgentState} />
                  )}
                  <div className="bg-white/80 backdrop-blur-sm rounded-2xl px-5 py-3 border border-warm-line/40">
                    <div className="text-base leading-[1.7] text-ink">
                      {streamingContent ? (
                        <>
                          <MarkdownContent content={streamingContent} />
                          <div className="inline-block w-2 h-4 bg-accent ml-0.5 animate-pulse align-middle" />
                        </>
                      ) : (
                        <DotsLoader className="py-2" />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Loading indicator */}
          {isLoading && !isStreaming && (
            <div className="px-6 py-3.5">
              <div className="flex space-x-4">
                <div className="flex-shrink-0 relative">
                  <BotAvatar seed={botAvatar} title={primaryKb?.name} />
                </div>
                <div className="flex-1 min-w-0">
                  <DotsLoader className="py-2" />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="relative flex-shrink-0 bg-white/30 backdrop-blur-sm">
        {/* 顶部色差过渡层：消息区背景与输入区背景的渐变衔接 */}
        <div
          aria-hidden
          className="pointer-events-none absolute -top-6 left-0 right-0 h-6 bg-gradient-to-b from-transparent to-white/30"
        />
        <div className="max-w-6xl mx-auto px-6 py-4">
          {/* Document picker */}
          <DocumentPicker
            selectedDocumentIds={selectedDocumentIds}
            onDocumentSelect={handleUpdateSelectedDocuments}
          />

          {/* @ document hint */}
          {selectedDocumentIds.length > 0 && (
            <div className="flex items-center gap-1 text-xs text-neutral-400 mb-1.5 ml-1">
              <span>📌</span>
              <span>AI 将基于选中的文档回答</span>
            </div>
          )}

          {/* Input box */}
          <div className="flex space-x-3 bg-white/70 backdrop-blur-xl rounded-2xl border border-white/40 px-4 py-3 shadow-[0_2px_10px_rgba(0,0,0,0.06)] transition-all duration-200 focus-within:border-blue-300/60 focus-within:shadow-[0_2px_20px_rgba(0,122,255,0.12)] focus-within:bg-white/85">
            <div className="flex-1 relative">
              <RichTextInput
                value={message}
                onChange={handleRichTextChange}
                onKeyDown={(e) => {
                  // IME composition: CJK users press Enter to confirm a candidate.
                  // Without this guard the half-typed word is sent prematurely.
                  if (e.nativeEvent.isComposing) return
                  if (e.key === 'Enter' && !e.shiftKey && !isLoading && !isStreaming) {
                    e.preventDefault()
                    handleSendMessage()
                  }
                }}
                placeholder="输入您的问题，使用 @ 来引用特定文档..."
                disabled={isLoading || isStreaming}
                className="w-full resize-none rounded-xl border-0 bg-transparent px-0 py-0 pr-4 focus:ring-0 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>
            {isLoading || isStreaming ? (
              <button
                onClick={stopGeneration}
                className="flex-shrink-0 bg-ink text-white p-3 rounded-xl transition-colors active:scale-95 transition-transform duration-75 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                aria-label="停止生成"
              >
                <StopIcon className="w-5 h-5" />
              </button>
            ) : (
              <button
                onClick={handleSendMessage}
                disabled={!getRealUserInput(message).trim()}
                className="flex-shrink-0 bg-accent hover:bg-accent-hover disabled:bg-warm-border text-white p-3 rounded-xl transition-colors disabled:cursor-not-allowed active:scale-95 transition-transform duration-75 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                aria-label="发送消息"
              >
                <PaperAirplaneIcon className="w-5 h-5" />
              </button>
            )}
          </div>
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
