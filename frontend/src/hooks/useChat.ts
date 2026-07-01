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
import { toast } from './useToast'
import { useAppStore } from '../store/appStore'

export interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: string
  sources?: SourceReference[]
  agentState?: AgentMessageState
  documentIds?: string[]
  documentNames?: string[]
}

const mapAPIMessageToUIMessage = (msg: APIChatMessage): Message => {
  const agentState = msg.metadata?.ui_state as AgentMessageState | undefined
  const documentIds = msg.metadata?.document_ids as string[] | undefined
  const documentNames = msg.metadata?.document_names as string[] | undefined
  return {
    id: msg.message_id,
    type: msg.role,
    content: msg.content,
    timestamp: msg.created_at,
    sources: msg.sources || [],
    agentState,
    documentIds,
    documentNames,
  }
}

export interface UseChatReturn {
  messages: Message[]
  isLoading: boolean
  isStreaming: boolean
  streamingContent: string
  streamingAgentState: AgentMessageState | null
  processingStatus: string | null
  sendMessage: (content: string, documentIds?: string[], documentNames?: string[]) => Promise<void>
  regenerateMessage: (messageId: string) => Promise<void>
  stopGeneration: () => void
  loadMessages: () => Promise<void>
  loadOlderMessages: () => Promise<void>
  clearMessages: () => Promise<void>
  hasMoreOlder: boolean
  isLoadingOlder: boolean
}

const PAGE_SIZE = 20

export const useChat = (chatId: string | null): UseChatReturn => {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [streamingAgentState, setStreamingAgentState] = useState<AgentMessageState | null>(null)
  const [processingStatus, setProcessingStatus] = useState<string | null>(null)
  const [hasMoreOlder, setHasMoreOlder] = useState(false)
  const [isLoadingOlder, setIsLoadingOlder] = useState(false)
  const totalRef = useRef(0)
  const loadedRef = useRef(0)
  const apiClient = useAPIClient()
  const streamingSourcesRef = useRef<SourceReference[]>([])
  const streamingMessageIdRef = useRef<string | null>(null)
  const streamingContentRef = useRef('')
  const streamingAgentStateRef = useRef<AgentMessageState | null>(null)

  // Load chat messages from API — load the latest PAGE_SIZE messages
  const loadMessages = useCallback(async () => {
    if (!chatId) {
      setMessages([])
      totalRef.current = 0
      loadedRef.current = 0
      setHasMoreOlder(false)
      return
    }

    try {
      // First, get total count
      const countResp = await apiClient.getChatMessages(chatId, 0, 1)
      const countData = extractData(countResp)
      const total = countData.total
      totalRef.current = total

      if (total === 0) {
        setMessages([])
        loadedRef.current = 0
        setHasMoreOlder(false)
        return
      }

      // Load the last PAGE_SIZE messages
      const offset = Math.max(0, total - PAGE_SIZE)
      const response = await apiClient.getChatMessages(chatId, offset, PAGE_SIZE)
      const data = extractData(response)
      const uiMessages = data.messages.map(mapAPIMessageToUIMessage)
      setMessages(uiMessages)
      loadedRef.current = uiMessages.length
      setHasMoreOlder(offset > 0)
    } catch (error) {
      console.error('加载聊天消息失败:', error)
    }
  }, [chatId, apiClient])

  // Load older messages (prepend) — called when user scrolls to top
  const loadOlderMessages = useCallback(async () => {
    if (!chatId || isLoadingOlder || !hasMoreOlder) return

    setIsLoadingOlder(true)
    try {
      const alreadyLoaded = loadedRef.current
      const total = totalRef.current
      const remaining = total - alreadyLoaded
      const offset = Math.max(0, remaining - PAGE_SIZE)
      const limit = remaining - offset

      const response = await apiClient.getChatMessages(chatId, offset, limit)
      const data = extractData(response)
      const olderMessages = data.messages.map(mapAPIMessageToUIMessage)

      if (olderMessages.length > 0) {
        setMessages(prev => [...olderMessages, ...prev])
        loadedRef.current += olderMessages.length
        setHasMoreOlder(offset > 0)
      } else {
        setHasMoreOlder(false)
      }
    } catch (error) {
      console.error('加载更早消息失败:', error)
    } finally {
      setIsLoadingOlder(false)
    }
  }, [chatId, apiClient, isLoadingOlder, hasMoreOlder])

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
            // Sync sidebar message count: +2 for user message + AI response
            if (chatId) {
              const store = useAppStore.getState()
              const current = store.chatSessions.find(c => c.id === chatId)
              if (current) {
                store.updateChatSession(chatId, { messageCount: current.messageCount + 2 })
              }
            }
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
          // Sync sidebar message count: backend persists user + error messages
          if (chatId) {
            const store = useAppStore.getState()
            const current = store.chatSessions.find(c => c.id === chatId)
            if (current) {
              store.updateChatSession(chatId, { messageCount: current.messageCount + 2 })
            }
          }
        }

        setStreamingContent('')
        setStreamingAgentState(null)
        streamingContentRef.current = ''
        streamingSourcesRef.current = []
        streamingMessageIdRef.current = null
        streamingAgentStateRef.current = null
        setProcessingStatus(null)
        toast.error(
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

        // start_answer was called: stream directly to bubble
        if (state.answering) {
          streamingContentRef.current += delta
          setStreamingContent((prev) => prev + delta)
          const newState = { ...state, finalText: streamingContentRef.current }
          streamingAgentStateRef.current = newState
          break
        }

        // Normal thinking: update trace step
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
        // Sync chat name if chat_info tool renamed it
        if (event.data?.name === 'chat_info' && event.data?.structured?.new_name && chatId) {
          useAppStore.getState().updateChatSession(chatId, { name: event.data.structured.new_name })
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

        // Find the thinking step for this iteration
        const stepIndex = (() => {
          for (let i = state.steps.length - 1; i >= 0; i--) {
            const s = state.steps[i]
            if (s.kind === 'thinking' && s.iteration === iteration && !s.hidden) {
              return i
            }
          }
          return -1
        })()

        if (state.answering) {
          // start_answer was called: text already in bubble, just hide trace step
          const newState: AgentMessageState = {
            ...state,
            finalText: streamingContentRef.current,
            steps: stepIndex >= 0
              ? state.steps.map((s, i) => i === stepIndex ? { ...s, hidden: true } : s)
              : state.steps,
          }
          streamingAgentStateRef.current = newState
          setStreamingAgentState(newState)
        } else if (stepIndex >= 0) {
          // Fallback: no marker detected, promote thinking text to bubble
          const promotedText = state.steps[stepIndex].text || ''
          // Use only the current iteration's thinking text, not cumulative
          const newFinalText = promotedText
          const newState: AgentMessageState = {
            ...state,
            finalText: newFinalText,
            steps: state.steps.map((s, i) =>
              i === stepIndex ? { ...s, hidden: true } : s
            ),
          }
          streamingAgentStateRef.current = newState
          setStreamingAgentState(newState)
          streamingContentRef.current = newFinalText
          setStreamingContent(newFinalText)
        }
        break
      }

      case 'start_answer': {
        const state = streamingAgentStateRef.current
        if (!state) break
        const newState = { ...state, answering: true }
        streamingAgentStateRef.current = newState
        setStreamingAgentState(newState)
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
    toast.error('生成回复失败: ' + error.message)
  }, [])

  const stopGeneration = useCallback(() => {
    apiClient.cancelRequests()

    // Discard the half-generated reply entirely — user asked to stop, so the
    // partial bubble should disappear instead of being committed as a message.
    // (Backend mirrors this by deleting the empty assistant placeholder.)
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

  const sendMessage = useCallback(async (content: string, documentIds?: string[], documentNames?: string[]) => {
    if (!content.trim() || isLoading || !chatId) return

    const userMessageContent = content.trim()
    if (!userMessageContent) return

    // Add user message to UI immediately
    const userMessage: Message = {
      id: `user_${Date.now()}`,
      type: 'user',
      content: userMessageContent,
      timestamp: new Date().toISOString(),
      documentIds: documentIds && documentIds.length > 0 ? documentIds : undefined,
      documentNames: documentNames && documentNames.length > 0 ? documentNames : undefined,
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
      toast.error('发送消息失败: ' + (error as Error).message)
    }
  }, [chatId, isLoading, apiClient, handleStreamEvent, handleStreamError])

  const regenerateMessage = useCallback(async (messageId: string) => {
    if (isLoading || !chatId) return

    // Find the assistant message and the preceding user message in the UI
    const msgIndex = messages.findIndex(m => m.id === messageId)
    if (msgIndex < 0 || messages[msgIndex].type !== 'assistant') return

    // Find the preceding user message
    let userMsgIndex = -1
    for (let i = msgIndex - 1; i >= 0; i--) {
      if (messages[i].type === 'user') {
        userMsgIndex = i
        break
      }
    }
    if (userMsgIndex < 0) return

    // Remove both messages from UI
    setMessages(prev => [...prev.slice(0, userMsgIndex), ...prev.slice(msgIndex + 1)])

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
      await apiClient.regenerateMessage(
        chatId,
        messageId,
        handleStreamEvent,
        handleStreamError
      )
    } catch (error) {
      console.error('重新生成失败:', error)
      setIsLoading(false)
      setIsStreaming(false)
      toast.error('重新生成失败: ' + (error as Error).message)
    }
  }, [chatId, isLoading, messages, apiClient, handleStreamEvent, handleStreamError])

  const clearMessages = useCallback(async () => {
    if (!chatId) return
    try {
      await apiClient.clearChatMessages(chatId)
      setMessages([])
      totalRef.current = 0
      loadedRef.current = 0
      setHasMoreOlder(false)
      setIsLoadingOlder(false)
      useAppStore.getState().updateChatSession(chatId, { messageCount: 0 })
    } catch (error) {
      console.error('清空消息失败:', error)
      toast.error('清空消息失败: ' + (error as Error).message)
    }
  }, [chatId, apiClient])

  return {
    messages,
    isLoading,
    isStreaming,
    streamingContent,
    streamingAgentState,
    processingStatus,
    sendMessage,
    regenerateMessage,
    stopGeneration,
    loadMessages,
    loadOlderMessages,
    clearMessages,
    hasMoreOlder,
    isLoadingOlder,
  }
}

export default useChat
