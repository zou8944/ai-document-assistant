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
import { AgentMessageState } from '../types/agent'

export interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: string
  sources?: SourceReference[]
  agentState?: AgentMessageState
}

const mapAPIMessageToUIMessage = (msg: APIChatMessage): Message => {
  const agentState = msg.metadata?.ui_state as AgentMessageState | undefined
  return {
    id: msg.message_id,
    type: msg.role,
    content: msg.content,
    timestamp: msg.created_at,
    sources: msg.sources || [],
    agentState,
  }
}

export interface UseChatReturn {
  messages: Message[]
  isLoading: boolean
  isStreaming: boolean
  streamingContent: string
  streamingAgentState: AgentMessageState | null
  processingStatus: string | null
  sendMessage: (content: string, documentIds?: string[]) => Promise<void>
  stopGeneration: () => void
  loadMessages: () => Promise<void>
}

export const useChat = (chatId: string | null): UseChatReturn => {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [streamingAgentState, setStreamingAgentState] = useState<AgentMessageState | null>(null)
  const [processingStatus, setProcessingStatus] = useState<string | null>(null)
  const apiClient = useAPIClient()
  const streamingSourcesRef = useRef<SourceReference[]>([])
  const streamingMessageIdRef = useRef<string | null>(null)
  const streamingContentRef = useRef('')
  const streamingAgentStateRef = useRef<AgentMessageState | null>(null)

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
          const agentState = streamingAgentStateRef.current

          if (finalContent || agentState) {
            const finalAgentState = agentState
              ? {
                  ...agentState,
                  status: 'done' as const,
                  timings: event.data?.agent_timings
                    ? (event.data.agent_timings as AgentMessageState['timings'])
                    : agentState.timings,
                }
              : undefined
            const aiMessage: Message = {
              id: event.data?.message_id || streamingMessageIdRef.current || `ai_${Date.now()}`,
              type: 'assistant',
              content: finalContent || agentState?.finalText || '',
              timestamp: new Date().toISOString(),
              sources: finalSources,
              agentState: finalAgentState,
            }
            setMessages((prev) => [...prev, aiMessage])
          }
        }

        setStreamingContent('')
        setStreamingAgentState(null)
        streamingContentRef.current = ''
        streamingSourcesRef.current = []
        streamingMessageIdRef.current = null
        streamingAgentStateRef.current = null
        break

      case 'error':
        console.error('Stream error:', event.data)
        setIsLoading(false)
        setIsStreaming(false)

        {
          const agentState = streamingAgentStateRef.current
          if (agentState) {
            const aiMessage: Message = {
              id: streamingMessageIdRef.current || `ai_${Date.now()}`,
              type: 'assistant',
              content: agentState.finalText || streamingContentRef.current || '',
              timestamp: new Date().toISOString(),
              sources: streamingSourcesRef.current,
              agentState: { ...agentState, status: 'error' as const },
            }
            setMessages((prev) => [...prev, aiMessage])
          }
        }

        setStreamingContent('')
        setStreamingAgentState(null)
        streamingContentRef.current = ''
        streamingSourcesRef.current = []
        streamingMessageIdRef.current = null
        streamingAgentStateRef.current = null
        setProcessingStatus(null)
        alert(
          '生成回复失败: ' + (event.data?.message || event.data?.detail || '未知错误')
        )
        break

      // Agent mode events
      case 'agent_start': {
        const newState: AgentMessageState = {
          steps: [],
          finalText: '',
          iterations: 0,
          status: 'running',
        }
        streamingAgentStateRef.current = newState
        setStreamingAgentState(newState)
        if (event.data?.message_id) {
          streamingMessageIdRef.current = event.data.message_id
        }
        break
      }

      case 'iteration_start': {
        const state = streamingAgentStateRef.current
        if (!state) break
        const iteration = event.data?.iteration ?? state.iterations + 1
        const newState: AgentMessageState = {
          ...state,
          iterations: iteration,
          steps: [...state.steps, { kind: 'thinking', iteration, text: '' }],
        }
        streamingAgentStateRef.current = newState
        setStreamingAgentState(newState)
        break
      }

      case 'agent_thinking': {
        const state = streamingAgentStateRef.current
        if (!state) break
        const iteration = event.data?.iteration ?? state.iterations
        const delta = event.data?.delta || ''
        const stepIndex = (() => {
          for (let i = state.steps.length - 1; i >= 0; i--) {
            const s = state.steps[i]
            if (s.kind === 'thinking' && s.iteration === iteration && !s.hidden) {
              return i
            }
          }
          return -1
        })()
        if (stepIndex >= 0) {
          const updatedSteps = [...state.steps]
          updatedSteps[stepIndex] = {
            ...updatedSteps[stepIndex],
            text: (updatedSteps[stepIndex].text || '') + delta,
          }
          const newState = { ...state, steps: updatedSteps }
          streamingAgentStateRef.current = newState
          setStreamingAgentState(newState)
        } else if (iteration === -1) {
          // Forced final answer thinking (e.g. max_iterations or loop_detected)
          const newState: AgentMessageState = {
            ...state,
            steps: [...state.steps, { kind: 'thinking', iteration: -1, text: delta }],
          }
          streamingAgentStateRef.current = newState
          setStreamingAgentState(newState)
        }
        break
      }

      case 'thinking_done': {
        const state = streamingAgentStateRef.current
        if (!state) break
        const iteration = event.data?.iteration ?? state.iterations
        const ms = event.data?.ms
        const updatedSteps = [...state.steps]
        for (let i = updatedSteps.length - 1; i >= 0; i--) {
          const s = updatedSteps[i]
          if (s.kind === 'thinking' && s.iteration === iteration && !s.hidden) {
            updatedSteps[i] = { ...s, thinkingMs: ms }
            break
          }
        }
        const newState = { ...state, steps: updatedSteps }
        streamingAgentStateRef.current = newState
        setStreamingAgentState(newState)
        break
      }

      case 'tool_call': {
        const state = streamingAgentStateRef.current
        if (!state) break
        const newState: AgentMessageState = {
          ...state,
          steps: [
            ...state.steps,
            {
              kind: 'tool',
              iteration: state.iterations,
              toolId: event.data?.id || '',
              toolName: event.data?.name || '',
              toolInput: event.data?.input || {},
              toolStatus: 'running',
            },
          ],
        }
        streamingAgentStateRef.current = newState
        setStreamingAgentState(newState)
        break
      }

      case 'tool_result': {
        const state = streamingAgentStateRef.current
        if (!state) break
        const toolId = event.data?.id || ''
        let stepIndex = -1
        for (let i = state.steps.length - 1; i >= 0; i--) {
          const s = state.steps[i]
          if (s.kind === 'tool' && s.toolId === toolId) {
            stepIndex = i
            break
          }
        }
        if (stepIndex >= 0) {
          const updatedSteps = [...state.steps]
          updatedSteps[stepIndex] = {
            ...updatedSteps[stepIndex],
            toolStatus: event.data?.is_error ? 'error' : 'done',
            toolPreview: event.data?.preview || '',
            toolMs: event.data?.ms,
          }
          const newState = { ...state, steps: updatedSteps }
          streamingAgentStateRef.current = newState
          setStreamingAgentState(newState)
        }
        break
      }

      case 'compact_triggered': {
        const state = streamingAgentStateRef.current
        if (!state) break
        const newState: AgentMessageState = {
          ...state,
          steps: [
            ...state.steps,
            {
              kind: 'compact',
              iteration: state.iterations,
              beforeTokens: event.data?.before_tokens,
              afterTokens: event.data?.after_tokens,
            },
          ],
        }
        streamingAgentStateRef.current = newState
        setStreamingAgentState(newState)
        break
      }

      case 'final_text_promote': {
        const state = streamingAgentStateRef.current
        if (!state) break
        const iteration = event.data?.iteration ?? state.iterations
        const stepIndex = (() => {
          for (let i = state.steps.length - 1; i >= 0; i--) {
            const s = state.steps[i]
            if (s.kind === 'thinking' && s.iteration === iteration && !s.hidden) {
              return i
            }
          }
          return -1
        })()
        if (stepIndex >= 0) {
          const promotedText = state.steps[stepIndex].text || ''
          const newFinalText = state.finalText
            ? state.finalText + '\n\n' + promotedText
            : promotedText
          const newState: AgentMessageState = {
            ...state,
            finalText: newFinalText,
          }
          streamingAgentStateRef.current = newState
          setStreamingAgentState(newState)
          // Update streaming content so bubble shows final text
          streamingContentRef.current = newFinalText
          setStreamingContent(newFinalText)
        }
        break
      }

      case 'agent_halted': {
        const state = streamingAgentStateRef.current
        if (!state) break
        const reason = event.data?.reason as string | undefined
        if (reason === 'loop_warning') {
          // Warning only; agent continues running
          break
        }
        const newState = {
          ...state,
          status: 'done' as const,
          halted: true,
        }
        streamingAgentStateRef.current = newState
        setStreamingAgentState(newState)
        break
      }

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
    setStreamingAgentState(null)
    streamingContentRef.current = ''
    streamingSourcesRef.current = []
    streamingMessageIdRef.current = null
    streamingAgentStateRef.current = null
    setProcessingStatus(null)
    alert('生成回复失败: ' + error.message)
  }, [])

  const stopGeneration = useCallback(() => {
    apiClient.cancelRequests()

    const partialContent = streamingContentRef.current
    const partialSources = streamingSourcesRef.current
    const partialMessageId = streamingMessageIdRef.current
    const agentState = streamingAgentStateRef.current

    if (partialContent || agentState) {
      const aiMessage: Message = {
        id: partialMessageId || `ai_${Date.now()}`,
        type: 'assistant',
        content: partialContent || agentState?.finalText || '',
        timestamp: new Date().toISOString(),
        sources: partialSources,
        agentState: agentState
          ? { ...agentState, status: 'cancelled' as const }
          : undefined,
      }
      setMessages((prev) => [...prev, aiMessage])
    }

    setIsLoading(false)
    setIsStreaming(false)
    setStreamingContent('')
    setStreamingAgentState(null)
    setProcessingStatus(null)
    streamingContentRef.current = ''
    streamingSourcesRef.current = []
    streamingMessageIdRef.current = null
    streamingAgentStateRef.current = null
  }, [apiClient])

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
    setStreamingAgentState(null)
    streamingContentRef.current = ''
    streamingSourcesRef.current = []
    streamingMessageIdRef.current = null
    streamingAgentStateRef.current = null
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
    streamingAgentState,
    processingStatus,
    sendMessage,
    stopGeneration,
    loadMessages
  }
}

export default useChat
