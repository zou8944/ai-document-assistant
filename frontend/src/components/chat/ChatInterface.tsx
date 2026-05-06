/**
 * Chat interface with breadcrumb and knowledge base management
 */

import React, { useState, useRef, useEffect } from 'react'
import {
  PlusIcon,
  PaperAirplaneIcon,
  StopIcon,
  UserIcon,
  CpuChipIcon,
  ClockIcon,
  MagnifyingGlassIcon,
  BookOpenIcon,
  PuzzlePieceIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import {
  useAPIClient,
  extractData,
  UpdateChatRequest,
} from '../../services/apiClient'
import { useChat, StageTiming } from '../../hooks/useChat'
import KnowledgeBaseSelector from './KnowledgeBaseSelector'
import DocumentPicker from './DocumentPicker'
import RichTextInput from './RichTextInput'
import MarkdownContent from './MarkdownContent'
import SourceReferences from './SourceReferences'

const TimingDisplay: React.FC<{ timings: StageTiming }> = ({ timings }) => {
  const items = [
    { label: '意图分析', ms: timings.intent_analysis_ms, Icon: SparklesIcon },
    { label: '文档检索', ms: timings.document_retrieval_ms, Icon: MagnifyingGlassIcon },
    { label: '整理上下文', ms: timings.context_assembly_ms, Icon: PuzzlePieceIcon },
    { label: '生成回答', ms: timings.generation_ms, Icon: BookOpenIcon },
  ]

  return (
    <div className="mt-2 pt-2 border-t border-gray-200/50 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-gray-400">
      <div className="flex items-center space-x-0.5">
        <ClockIcon className="w-3 h-3" />
        <span>总计 {(timings.total_ms / 1000).toFixed(1)}s</span>
      </div>
      {items.map((item) => (
        <div key={item.label} className="flex items-center space-x-0.5" title={`${item.label}: ${item.ms}ms`}>
          <item.Icon className="w-3 h-3" />
          <span>{item.label} {(item.ms / 1000).toFixed(1)}s</span>
        </div>
      ))}
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
  const messagesEndRef = useRef<HTMLDivElement>(null)
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
    processingStatus,
    sendMessage,
    stopGeneration,
  } = useChat(currentChat?.id || null)

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, streamingContent, isLoading])

  const handleSendMessage = async () => {
    if (!message.trim() || isLoading || !currentChat) return

    const userMessageContent = getRealUserInput(message).trim()
    if (!userMessageContent) return
    setMessage('')

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
      <div className="flex items-center justify-center h-full text-gray-500">
        <div className="text-center">
          <CpuChipIcon className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p>请选择一个聊天会话</p>
        </div>
      </div>
    )
  }

  const kbNames = getKnowledgeBaseNames()
  const isBoundChat = currentChat.boundCollectionId != null

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

          {!isBoundChat && (
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setShowKnowledgeBaseSelector(true)}
                className="flex items-center space-x-1 text-sm text-blue-500 hover:text-blue-600 transition-colors"
              >
                <PlusIcon className="w-4 h-4" />
                <span>管理知识库</span>
              </button>
            </div>
          )}
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
                  {msg.type === 'assistant' && msg.timings && (
                    <TimingDisplay timings={msg.timings} />
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
        {isStreaming && (
          <div className="flex justify-start">
            <div className="flex max-w-3xl space-x-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 text-gray-600 flex items-center justify-center">
                <CpuChipIcon className="w-4 h-4" />
              </div>
              <div className="flex-1 min-w-0">
                {processingStatus && (
                  <div className="mb-1.5 flex items-center space-x-1.5 text-xs text-gray-500">
                    <div className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    <span>{processingStatus}</span>
                  </div>
                )}
                <div className="px-4 py-3 rounded-2xl bg-white/80 backdrop-blur-sm border border-gray-200/50 text-gray-900 text-sm">
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
        <div className="space-y-2">
          {/* Document picker */}
          <DocumentPicker
            selectedDocumentIds={selectedDocumentIds}
            onDocumentSelect={handleUpdateSelectedDocuments}
          />

          {/* Input box and send button */}
          <div className="flex space-x-3">
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
                placeholder="输入您的问题，使用 @ 来引用特定文档..."
                disabled={isLoading || isStreaming}
                className="w-full resize-none rounded-lg border border-gray-300 bg-white/80 backdrop-blur-sm px-4 py-3 pr-12 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>
            {isLoading || isStreaming ? (
              <button
                onClick={stopGeneration}
                className="flex-shrink-0 bg-red-500 hover:bg-red-600 text-white p-3 rounded-lg transition-colors"
                title="停止生成"
              >
                <StopIcon className="w-5 h-5" />
              </button>
            ) : (
              <button
                onClick={handleSendMessage}
                disabled={!getRealUserInput(message).trim()}
                className="flex-shrink-0 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white p-3 rounded-lg transition-colors disabled:cursor-not-allowed"
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
