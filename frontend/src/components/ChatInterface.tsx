/**
 * ChatInterface component for document Q&A.
 * Following Apple Liquid Glass design with smooth scrolling and animations.
 */

import React, { useState, useRef, useEffect } from 'react'
import { 
  PaperAirplaneIcon, 
  DocumentTextIcon, 
  SparklesIcon,
  ExclamationCircleIcon
} from '@heroicons/react/24/outline'
import clsx from 'clsx'

interface Message {
  id: string
  type: 'user' | 'assistant' | 'error'
  content: string
  sources?: Array<{
    source: string
    content_preview: string
    score: number
    start_index: number
  }>
  timestamp: Date
}

interface ChatInterfaceProps {
  onSendMessage: (message: string) => Promise<any>
  isLoading?: boolean
  hasDocuments?: boolean
  className?: string
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  onSendMessage,
  isLoading = false,
  hasDocuments = false,
  className
}) => {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!inputValue.trim() || isLoading || !hasDocuments) return

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue.trim(),
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInputValue('')

    try {
      const response = await onSendMessage(inputValue.trim())
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: response.status === 'error' ? 'error' : 'assistant',
        content: response.answer || response.message || '未收到回复',
        sources: response.sources || [],
        timestamp: new Date()
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        type: 'error',
        content: `处理您的问题时出现错误: ${error instanceof Error ? error.message : '未知错误'}`,
        timestamp: new Date()
      }

      setMessages(prev => [...prev, errorMessage])
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e as any)
    }
  }

  const formatTimestamp = (timestamp: Date) => {
    return timestamp.toLocaleTimeString('zh-CN', { 
      hour: '2-digit', 
      minute: '2-digit' 
    })
  }

  const renderMessage = (message: Message) => {
    const isUser = message.type === 'user'
    const isError = message.type === 'error'

    return (
      <div
        key={message.id}
        className={clsx(
          'flex w-full animate-slide-up',
          isUser ? 'justify-end' : 'justify-start'
        )}
      >
        <div
          className={clsx(
            'max-w-[80%] rounded-xl p-4 space-y-3',
            isUser 
              ? 'glass-morph ml-12' 
              : isError
              ? 'bg-red-50/80 border border-red-200 mr-12'
              : 'glass-morph-dark mr-12'
          )}
        >
          <div className="flex items-start space-x-3">
            {!isUser && (
              <div className={clsx(
                'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
                isError ? 'bg-red-100' : 'bg-macos-blue/20'
              )}>
                {isError ? (
                  <ExclamationCircleIcon className="w-5 h-5 text-red-500" />
                ) : (
                  <SparklesIcon className="w-5 h-5 text-macos-blue" />
                )}
              </div>
            )}
            
            <div className="flex-1 space-y-2">
              <div className={clsx(
                'text-sm leading-relaxed whitespace-pre-wrap',
                isUser 
                  ? 'text-macos-gray-900' 
                  : isError
                  ? 'text-red-700'
                  : 'text-white'
              )}>
                {message.content}
              </div>
              
              <div className={clsx(
                'text-xs opacity-70',
                isUser 
                  ? 'text-macos-gray-500' 
                  : isError
                  ? 'text-red-500'
                  : 'text-white/70'
              )}>
                {formatTimestamp(message.timestamp)}
              </div>
            </div>
          </div>

          {/* Sources */}
          {message.sources && message.sources.length > 0 && (
            <div className="mt-3 pt-3 border-t border-white/20">
              <div className="text-xs font-medium text-white/80 mb-2 flex items-center gap-1">
                <DocumentTextIcon className="w-3 h-3" />
                参考来源
              </div>
              <div className="space-y-2">
                {message.sources.slice(0, 3).map((source, index) => (
                  <div
                    key={index}
                    className="text-xs p-2 rounded bg-white/10 backdrop-blur-sm"
                  >
                    <div className="font-medium text-white/90 mb-1">
                      {source.source}
                    </div>
                    <div className="text-white/70 text-[11px] line-clamp-2">
                      {source.content_preview}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  if (!hasDocuments) {
    return (
      <div className={clsx('glass-morph rounded-xl p-8 text-center', className)}>
        <DocumentTextIcon className="w-12 h-12 mx-auto text-macos-gray-400 mb-4" />
        <h3 className="text-lg font-medium text-macos-gray-900 mb-2">
          还没有文档可以查询
        </h3>
        <p className="text-sm text-macos-gray-600">
          请先上传文件或抓取网站内容，然后就可以开始提问了
        </p>
      </div>
    )
  }

  return (
    <div className={clsx('flex flex-col h-full', className)}>
      {/* Messages Container */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
        {messages.length === 0 ? (
          <div className="glass-morph rounded-xl p-8 text-center animate-fade-in">
            <SparklesIcon className="w-12 h-12 mx-auto text-macos-blue mb-4" />
            <h3 className="text-lg font-medium text-macos-gray-900 mb-2">
              开始提问吧！
            </h3>
            <p className="text-sm text-macos-gray-600 mb-4">
              我可以帮您从已处理的文档中查找信息
            </p>
            <div className="text-xs text-macos-gray-500 space-y-1">
              <p>• 尝试问一些具体的问题</p>
              <p>• 我会引用相关的文档来源</p>
              <p>• 使用自然语言，就像和朋友聊天一样</p>
            </div>
          </div>
        ) : (
          messages.map(renderMessage)
        )}
        
        {isLoading && (
          <div className="flex justify-start animate-fade-in">
            <div className="glass-morph-dark rounded-xl p-4 mr-12">
              <div className="flex items-center space-x-3">
                <div className="w-8 h-8 rounded-full bg-macos-blue/20 flex items-center justify-center">
                  <SparklesIcon className="w-5 h-5 text-macos-blue animate-pulse" />
                </div>
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-white/60 rounded-full animate-bounce" />
                  <div className="w-2 h-2 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                  <div className="w-2 h-2 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                </div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input Form */}
      <div className="p-4 border-t border-white/20">
        <form onSubmit={handleSubmit} className="relative">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入您的问题..."
            disabled={isLoading}
            rows={1}
            className={clsx(
              'w-full p-4 pr-12 rounded-xl resize-none',
              'glass-morph text-macos-gray-900 placeholder-macos-gray-500',
              'focus:outline-none focus:ring-2 focus:ring-macos-blue',
              'transition-all duration-200',
              isLoading && 'opacity-50 cursor-not-allowed'
            )}
            style={{ minHeight: '52px', maxHeight: '120px' }}
          />
          
          <button
            type="submit"
            disabled={!inputValue.trim() || isLoading}
            className={clsx(
              'absolute right-2 bottom-2 p-2 rounded-lg',
              'glass-button text-macos-blue hover:text-blue-600',
              'disabled:text-macos-gray-400 disabled:cursor-not-allowed',
              'transition-all duration-200 transform hover:scale-105'
            )}
          >
            <PaperAirplaneIcon className="w-5 h-5" />
          </button>
        </form>
        
        <p className="text-xs text-macos-gray-500 mt-2 text-center">
          按 Enter 发送，Shift + Enter 换行
        </p>
      </div>
    </div>
  )
}

export default ChatInterface