/**
 * Chat interface - Hermes UI inspired design
 */

import React, { useState, useRef, useEffect } from 'react'
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
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-3 border-b border-warm-border">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-2 text-sm text-gray-500">
            <span>知识库:</span>
            {kbNames.length > 0 ? (
              <span className="text-gray-900 font-medium">
                {kbNames.join(' + ')}
              </span>
            ) : (
              <span>暂无</span>
            )}
          </div>

          {!isBoundChat && (
            <button
              onClick={() => setShowKnowledgeBaseSelector(true)}
              className="flex items-center space-x-1 text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              <PlusIcon className="w-4 h-4" />
              <span>管理知识库</span>
            </button>
          )}
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto">
          {messages.map((msg) => (
            <div key={msg.id} className="px-6 py-3.5 animate-message-in">
              {msg.type === 'user' ? (
                /* User message - right aligned card */
                <div className="flex justify-end">
                  <div className="max-w-3xl">
                    <div className="bg-[#F7F7F8] rounded-2xl px-5 py-3">
                      <MarkdownContent content={msg.content} isUser />
                    </div>
                    <div className="mt-1.5 text-[11px] text-muted text-right">
                      {formatTime(msg.timestamp)}
                    </div>
                  </div>
                </div>
              ) : (
                /* AI message - left aligned, no background */
                <div className="flex space-x-4">
                  <div className="flex-shrink-0">
                    <div className="w-7 h-7 rounded-full bg-accent/10 text-accent flex items-center justify-center">
                      <CpuChipIcon className="w-3.5 h-3.5" />
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    {msg.agentState && (
                      <AgentTrace state={msg.agentState} />
                    )}
                    <div className="text-base leading-[1.7] text-ink">
                      <MarkdownContent content={msg.content} />
                    </div>
                    <SourceReferences sources={msg.sources || []} />
                    <div className="mt-2 text-[11px] text-muted">
                      {formatTime(msg.timestamp)}
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
                <div className="flex-shrink-0">
                  <div className="w-7 h-7 rounded-full bg-accent/10 text-accent flex items-center justify-center">
                    <CpuChipIcon className="w-3.5 h-3.5" />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  {processingStatus && (
                    <div className="mb-2 flex items-center space-x-2 text-xs text-muted">
                      <div className="w-3 h-3 border-2 border-muted border-t-transparent rounded-full animate-spin" />
                      <span>{processingStatus}</span>
                    </div>
                  )}
                  {streamingAgentState && (
                    <AgentTrace state={streamingAgentState} />
                  )}
                  <div className="text-base leading-[1.7] text-ink">
                    {streamingContent ? (
                      <>
                        <MarkdownContent content={streamingContent} />
                        <div className="inline-block w-2 h-4 bg-muted ml-0.5 animate-pulse align-middle" />
                      </>
                    ) : (
                      <div className="flex space-x-1.5 py-2">
                        <div className="w-2 h-2 bg-warm-line rounded-full animate-bounce" />
                        <div className="w-2 h-2 bg-warm-line rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                        <div className="w-2 h-2 bg-warm-line rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Loading indicator */}
          {isLoading && !isStreaming && (
            <div className="px-6 py-3.5">
              <div className="flex space-x-4">
                <div className="flex-shrink-0">
                  <div className="w-7 h-7 rounded-full bg-accent/10 text-accent flex items-center justify-center">
                    <CpuChipIcon className="w-3.5 h-3.5" />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex space-x-1.5 py-2">
                    <div className="w-2 h-2 bg-warm-line rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-warm-line rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                    <div className="w-2 h-2 bg-warm-line rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="flex-shrink-0 border-t border-warm-border">
        <div className="max-w-6xl mx-auto px-6 py-4">
          {/* Document picker */}
          <DocumentPicker
            selectedDocumentIds={selectedDocumentIds}
            onDocumentSelect={handleUpdateSelectedDocuments}
          />

          {/* Input box */}
          <div className="flex space-x-3 bg-white/80 backdrop-blur-sm rounded-2xl border border-warm-border px-4 py-3 shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
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
                className="w-full resize-none rounded-xl border-0 bg-transparent px-0 py-0 pr-4 focus:ring-0 focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>
            {isLoading || isStreaming ? (
              <button
                onClick={stopGeneration}
                className="flex-shrink-0 bg-ink hover:bg-[#2D2A26] text-white p-3 rounded-xl transition-colors"
                title="停止生成"
              >
                <StopIcon className="w-5 h-5" />
              </button>
            ) : (
              <button
                onClick={handleSendMessage}
                disabled={!getRealUserInput(message).trim()}
                className="flex-shrink-0 bg-accent hover:bg-accent-hover disabled:bg-warm-border text-white p-3 rounded-xl transition-colors disabled:cursor-not-allowed"
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
