/**
 * Document chat panel - chat interface for the doc sidebar
 */

import React, { useState, useRef, useEffect } from 'react'
import {
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
import { useChat, StageTiming } from '../../hooks/useChat'
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
    <div className="mt-2 pt-1.5 border-t border-gray-200/50 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-gray-400">
      <div className="flex items-center space-x-0.5">
        <ClockIcon className="w-2.5 h-2.5" />
        <span>总计 {(timings.total_ms / 1000).toFixed(1)}s</span>
      </div>
      {items.map((item) => (
        <div key={item.label} className="flex items-center space-x-0.5" title={`${item.label}: ${item.ms}ms`}>
          <item.Icon className="w-2.5 h-2.5" />
          <span>{item.label} {(item.ms / 1000).toFixed(1)}s</span>
        </div>
      ))}
    </div>
  )
}

interface DocChatPanelProps {
  chatId: string | null
  documentId: string | null
}

export const DocChatPanel: React.FC<DocChatPanelProps> = ({ chatId, documentId }) => {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const {
    messages,
    isLoading,
    isStreaming,
    streamingContent,
    processingStatus,
    sendMessage,
    stopGeneration,
  } = useChat(chatId)

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, streamingContent, isLoading])

  const handleSend = async () => {
    if (!input.trim() || isLoading || !chatId) return
    const content = input.trim()
    setInput('')
    await sendMessage(content, documentId ? [documentId] : undefined)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !isLoading && !isStreaming) {
      e.preventDefault()
      handleSend()
    }
  }

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const hasNoDocument = !documentId

  return (
    <div className="h-full flex flex-col">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
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
                'flex max-w-[90%] space-x-2',
                msg.type === 'user' ? 'flex-row-reverse space-x-reverse' : 'flex-row'
              )}
            >
              {/* Avatar */}
              <div className={clsx(
                'flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center',
                msg.type === 'user'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-200 text-gray-600'
              )}>
                {msg.type === 'user' ? (
                  <UserIcon className="w-3 h-3" />
                ) : (
                  <CpuChipIcon className="w-3 h-3" />
                )}
              </div>

              {/* Message Content */}
              <div className="flex-1 min-w-0">
                <div
                  className={clsx(
                    'px-3 py-2 rounded-xl text-xs',
                    msg.type === 'user'
                      ? 'bg-blue-500 text-white'
                      : 'bg-white/80 backdrop-blur-sm border border-gray-200/50 text-gray-900'
                  )}
                >
                  <MarkdownContent content={msg.content} isUser={msg.type === 'user'} />
                  <SourceReferences sources={msg.sources || []} />
                  {msg.type === 'assistant' && msg.timings && (
                    <TimingDisplay timings={msg.timings} />
                  )}
                </div>
                <div className={clsx(
                  'mt-0.5 text-[10px] text-gray-500',
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
            <div className="flex max-w-[90%] space-x-2">
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-gray-200 text-gray-600 flex items-center justify-center">
                <CpuChipIcon className="w-3 h-3" />
              </div>
              <div className="flex-1 min-w-0">
                {processingStatus && (
                  <div className="mb-1 flex items-center space-x-1 text-[10px] text-gray-500">
                    <div className="w-2.5 h-2.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    <span>{processingStatus}</span>
                  </div>
                )}
                <div className="px-3 py-2 rounded-xl bg-white/80 backdrop-blur-sm border border-gray-200/50 text-gray-900 text-xs">
                  {streamingContent ? (
                    <>
                      <MarkdownContent content={streamingContent} />
                      <div className="mt-2 w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse" />
                    </>
                  ) : (
                    <div className="flex space-x-1">
                      <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" />
                      <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                      <div className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="flex-shrink-0 p-3 border-t border-gray-200/50 bg-white/50 backdrop-blur-sm">
        {hasNoDocument ? (
          <div className="text-center py-2">
            <p className="text-xs text-gray-500">当前没有选中文档</p>
            <p className="text-[10px] text-gray-400 mt-0.5">请先选择一篇文档以开始对话</p>
          </div>
        ) : (
          <div className="flex space-x-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入您的问题..."
              disabled={isLoading || isStreaming}
              rows={1}
              className="flex-1 resize-none rounded-lg border border-gray-300 bg-white/80 backdrop-blur-sm px-3 py-2 text-xs focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ minHeight: '32px', maxHeight: '120px' }}
            />
            {isLoading || isStreaming ? (
              <button
                onClick={stopGeneration}
                className="flex-shrink-0 bg-red-500 hover:bg-red-600 text-white p-2 rounded-lg transition-colors"
                title="停止生成"
              >
                <StopIcon className="w-4 h-4" />
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="flex-shrink-0 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-300 text-white p-2 rounded-lg transition-colors disabled:cursor-not-allowed"
              >
                <PaperAirplaneIcon className="w-4 h-4" />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default DocChatPanel
