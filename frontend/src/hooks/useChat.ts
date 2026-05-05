/**
 * Custom hook for chat message loading and SSE streaming
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import {
  useAPIClient,
  extractData,
  ChatMessage as APIChatMessage,
  SourceReference,
  SSEEvent,
} from '../services/apiClient'

export interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: string
  sources?: SourceReference[]
}

const mapAPIMessageToUIMessage = (msg: APIChatMessage): Message => {
  return {
    id: msg.message_id,
    type: msg.role,
    content: msg.content,
    timestamp: msg.created_at,
    sources: msg.sources || []
  }
}

export interface UseChatReturn {
  messages: Message[]
  isLoading: boolean
  isStreaming: boolean
  streamingContent: string
  processingStatus: string | null
  sendMessage: (content: string, documentIds?: string[]) => Promise<void>
  loadMessages: () => Promise<void>
}

export const useChat = (chatId: string | null): UseChatReturn => {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [processingStatus, setProcessingStatus] = useState<string | null>(null)
  const apiClient = useAPIClient()
  const streamingSourcesRef = useRef<SourceReference[]>([])
  const streamingMessageIdRef = useRef<string | null>(null)
  const streamingContentRef = useRef('')

  // Load chat messages from API
  const loadMessages = useCallback(async () => {
    if (!chatId) {
      setMessages([])
      return
    }

    try {
      const response = await apiClient.getChatMessages(chatId)
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
  }, [chatId, apiClient])

  // Auto-load messages when chatId changes
  useEffect(() => {
    if (chatId) {
      loadMessages()
    } else {
      setMessages([])
    }
  }, [chatId, loadMessages])

  // Cleanup: cancel ongoing SSE requests when chatId changes or unmounts
  useEffect(() => {
    return () => {
      apiClient.cancelRequests()
    }
  }, [chatId, apiClient])

  const handleStreamEvent = useCallback((event: SSEEvent) => {
    switch (event.event) {
      case 'metadata':
        break

      case 'user_message':
        break

      case 'status': {
        if (event.data) {
          if (event.data.message) {
            setProcessingStatus(event.data.message)
          } else if (event.data.status) {
            const statusMap: Record<string, string> = {
              retrieving_documents: '检索相关文档...',
              generating_response: '生成回答...',
            }
            setProcessingStatus(statusMap[event.data.status] || event.data.status)
          }
        }
        break
      }

      case 'intent':
        if (event.data) {
          console.log('Query intent:', event.data)
        }
        break

      case 'sources': {
        let sources: SourceReference[] = []
        if (Array.isArray(event.data)) {
          sources = event.data
        } else if (event.data?.documents) {
          sources = event.data.documents.map((d: any) => ({
            document_id: d.document_id || '',
            document_name: d.document_name || '',
            document_uri: d.document_uri || '',
            chunk_index: d.chunk_index || 0,
            content_preview: '',
            relevance_score: d.relevance_score || 0,
          }))
        } else if (event.data?.sources) {
          sources = event.data.sources
        }
        streamingSourcesRef.current = sources
        break
      }

      case 'content':
        if (event.data) {
          const content = event.data.delta || event.data.content
          if (content) {
            streamingContentRef.current += content
            setStreamingContent((prev) => prev + content)
            setProcessingStatus(null)
          }
        }
        break

      case 'done':
        setIsLoading(false)
        setIsStreaming(false)
        setProcessingStatus(null)

        {
          const finalContent = event.data?.content || streamingContentRef.current
          const finalSources = event.data?.sources || streamingSourcesRef.current

          if (finalContent) {
            const aiMessage: Message = {
              id: event.data?.message_id || streamingMessageIdRef.current || `ai_${Date.now()}`,
              type: 'assistant',
              content: finalContent,
              timestamp: new Date().toISOString(),
              sources: finalSources,
            }
            setMessages((prev) => [...prev, aiMessage])
          }
        }

        setStreamingContent('')
        streamingContentRef.current = ''
        streamingSourcesRef.current = []
        streamingMessageIdRef.current = null
        break

      case 'error':
        console.error('Stream error:', event.data)
        setIsLoading(false)
        setIsStreaming(false)
        setStreamingContent('')
        streamingContentRef.current = ''
        streamingSourcesRef.current = []
        streamingMessageIdRef.current = null
        setProcessingStatus(null)
        alert(
          '生成回复失败: ' + (event.data?.message || event.data?.detail || '未知错误')
        )
        break

      default:
        if (event.event === 'data' && event.data) {
          if (event.data.content) {
            streamingContentRef.current += event.data.content
            setStreamingContent((prev) => prev + event.data.content)
          }
          if (event.data.delta) {
            streamingContentRef.current += event.data.delta
            setStreamingContent((prev) => prev + event.data.delta)
          }
          if (event.data.message_id) {
            streamingMessageIdRef.current = event.data.message_id
          }
          if (event.data.sources) {
            streamingSourcesRef.current = event.data.sources
          }
        }
        break
    }
  }, [])

  const handleStreamError = useCallback((error: Error) => {
    console.error('流式响应错误:', error)
    setIsLoading(false)
    setIsStreaming(false)
    setStreamingContent('')
    streamingContentRef.current = ''
    streamingSourcesRef.current = []
    streamingMessageIdRef.current = null
    setProcessingStatus(null)
    alert('生成回复失败: ' + error.message)
  }, [])

  const sendMessage = useCallback(async (content: string, documentIds?: string[]) => {
    if (!content.trim() || isLoading || !chatId) return

    const userMessageContent = content.trim()
    if (!userMessageContent) return

    // Add user message to UI immediately
    const userMessage: Message = {
      id: `user_${Date.now()}`,
      type: 'user',
      content: userMessageContent,
      timestamp: new Date().toISOString()
    }
    setMessages(prev => [...prev, userMessage])

    setIsLoading(true)
    setIsStreaming(true)
    setStreamingContent('')
    streamingContentRef.current = ''
    streamingSourcesRef.current = []
    streamingMessageIdRef.current = null
    setProcessingStatus(null)

    try {
      await apiClient.sendMessageStream(
        chatId,
        {
          message: userMessageContent,
          include_sources: true,
          document_ids: documentIds && documentIds.length > 0 ? documentIds : undefined
        },
        handleStreamEvent,
        handleStreamError
      )
    } catch (error) {
      console.error('发送消息失败:', error)
      setIsLoading(false)
      setIsStreaming(false)
      alert('发送消息失败: ' + (error as Error).message)
    }
  }, [chatId, isLoading, apiClient, handleStreamEvent, handleStreamError])

  return {
    messages,
    isLoading,
    isStreaming,
    streamingContent,
    processingStatus,
    sendMessage,
    loadMessages
  }
}

export default useChat
