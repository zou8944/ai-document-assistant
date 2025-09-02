/**
 * REST API client for AI Document Assistant backend.
 * Updated to match the actual FastAPI backend endpoints.
 */

// Collection types
export interface Collection {
  id: string
  name: string
  description?: string
  document_count: number
  vector_count: number
  created_at: string
  updated_at: string
}

export interface CreateCollectionRequest {
  id: string
  name: string
  description?: string
}

export interface UpdateCollectionRequest {
  name?: string
  description?: string
}

// Document types
export interface Document {
  id: string
  name: string
  file_path?: string
  url?: string
  content_type: string
  file_size?: number
  status: 'pending' | 'processing' | 'indexed' | 'failed'
  created_at: string
  updated_at: string
  error_message?: string
}

export interface DocumentListResponse {
  documents: Document[]
  total: number
  page: number
  page_size: number
}

// Ingestion types
export interface IngestFilesRequest {
  files: string[]
}

export interface IngestUrlsRequest {
  urls: string[]
  max_depth?: number
  override?: boolean
}

// Task types
export interface Task {
  task_id: string
  task_type: string
  collection_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress?: number
  result?: any
  error_message?: string
  created_at: string
  updated_at: string
}

// Chat types
export interface Chat {
  chat_id: string
  name: string
  collection_ids: string[]
  created_at: string
  updated_at: string
}

export interface CreateChatRequest {
  name: string
  collection_ids: string[]
}

export interface ChatMessage {
  message_id: string
  chat_id: string
  role: 'user' | 'assistant'
  content: string
  sources: Array<SourceReference>
  created_at: string
}

export interface SourceReference {
  document_name: string
  document_id: string
  chunk_index: number
  content_preview: string
  relevance_score: number
}

export interface ChatMessageRequest {
  message: string
  stream?: boolean
  include_sources?: boolean
}

export interface SourceInfo {
  document_name: string
  url?: string
  content_preview: string
  relevance_score: number
}

// Enhanced Chat Types
export interface EnhancedChatResponse {
  message_id: string
  chat_id: string
  content: string
  sources: SourceReference[]
  metadata: Record<string, any>
  confidence: number
  intent_analysis?: IntentAnalysis
  retrieval_strategy: string
  cache_hit: boolean
  retrieval_time_ms?: number
  generation_time_ms?: number
  total_time_ms?: number
  collections_searched: string[]
  documents_retrieved: number
  sources_count: number
}

export interface IntentAnalysis {
  intent: string
  confidence: string
  confidence_score: number
  keyword_scores: Record<string, number>
  description: string
  analysis_method: string
}

export interface EnhancedChatRequest {
  message: string
  include_sources?: boolean
  enable_intent_analysis?: boolean
  enable_cache?: boolean
  enable_summary_overview?: boolean
  retrieval_strategy?: 'auto' | 'semantic' | 'hybrid'
}

// Health check
export interface HealthResponse {
  status: string
  version?: string
  timestamp: string
}

// Settings
export interface Settings {
  openai_api_key?: string
  openai_model_name: string
  embedding_model_name: string
  chunk_size: number
  chunk_overlap: number
  top_k: number
  temperature: number
}

// Streaming types for SSE
export interface SSEEvent {
  event: string
  data: any
}

// Unified API response wrapper (matches backend ApiResponse model)
export interface APIResponse<T = any> {
  code: 'Success' | 'InvalidRequest' | 'NotFound' | 'Unauthorized' | 'Forbidden' | 'Conflict' | 'ValidationError' | 'InternalError' | 'ServiceUnavailable' | 'DatabaseError' | 'ExternalServiceError'
  message: string
  data: T | null
}

// API Client class
export class DocumentAssistantAPI {
  private baseURL: string
  private abortController?: AbortController

  constructor(baseURL: string) {
    this.baseURL = baseURL.endsWith('/') ? baseURL.slice(0, -1) : baseURL
  }

  /**
   * Set a new base URL (useful when API server restarts with new port)
   */
  setBaseURL(baseURL: string) {
    this.baseURL = baseURL.endsWith('/') ? baseURL.slice(0, -1) : baseURL
  }

  /**
   * Cancel any ongoing requests
   */
  cancelRequests() {
    if (this.abortController) {
      this.abortController.abort()
    }
  }

  /**
   * Generic request method with error handling
   */
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    this.abortController = new AbortController()
    
    const url = `${this.baseURL}${endpoint}`
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      signal: this.abortController.signal,
      ...options,
    }

    try {
      const response = await fetch(url, config)

      if (!response.ok) {
        const errorText = await response.text()
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`
        
        try {
          const errorJson = JSON.parse(errorText)
          errorMessage = errorJson.detail || errorMessage
        } catch {
          // Use the raw text if it's not JSON
          if (errorText) {
            errorMessage = errorText
          }
        }
        
        throw new Error(errorMessage)
      }

      return await response.json()
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('Request was cancelled')
      }
      throw error
    }
  }

  /**
   * Health check endpoint
   */
  async healthCheck(): Promise<APIResponse<HealthResponse>> {
    return this.request<APIResponse<HealthResponse>>('/api/v1/health')
  }

  // Collection Management
  /**
   * Create a new collection
   */
  async createCollection(request: CreateCollectionRequest): Promise<APIResponse<Collection>> {
    return this.request<APIResponse<Collection>>('/api/v1/collections', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  /**
   * List all collections
   */
  async listCollections(search?: string): Promise<APIResponse<{ collections: Collection[], total: number }>> {
    const url = search ? `/api/v1/collections?search=${encodeURIComponent(search)}` : '/api/v1/collections'
    return this.request<APIResponse<{ collections: Collection[], total: number }>>(url)
  }

  /**
   * Get a specific collection
   */
  async getCollection(collectionId: string): Promise<APIResponse<Collection>> {
    return this.request<APIResponse<Collection>>(`/api/v1/collections/${encodeURIComponent(collectionId)}`)
  }

  /**
   * Update a collection
   */
  async updateCollection(collectionId: string, request: UpdateCollectionRequest): Promise<APIResponse<Collection>> {
    return this.request<APIResponse<Collection>>(`/api/v1/collections/${encodeURIComponent(collectionId)}`, {
      method: 'PATCH',
      body: JSON.stringify(request),
    })
  }

  /**
   * Delete a collection
   */
  async deleteCollection(collectionId: string): Promise<APIResponse<{}>> {
    return this.request<APIResponse<{}>>(`/api/v1/collections/${encodeURIComponent(collectionId)}`, {
      method: 'DELETE',
    })
  }

  // Document Management
  /**
   * List documents in a collection
   */
  async listDocuments(
    collectionId: string,
    page: number = 1,
    pageSize: number = 50,
    search?: string,
    status?: string
  ): Promise<APIResponse<DocumentListResponse>> {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    })
    if (search) params.append('search', search)
    if (status) params.append('status', status)
    
    return this.request<APIResponse<DocumentListResponse>>(
      `/api/v1/collections/${encodeURIComponent(collectionId)}/documents?${params}`
    )
  }

  /**
   * Get a specific document
   */
  async getDocument(collectionId: string, documentId: string): Promise<APIResponse<Document>> {
    return this.request<APIResponse<Document>>(
      `/api/v1/collections/${encodeURIComponent(collectionId)}/documents/${encodeURIComponent(documentId)}`
    )
  }

  /**
   * Delete a document
   */
  async deleteDocument(collectionId: string, documentId: string): Promise<APIResponse<{ document_id: string, deleted: boolean }>> {
    return this.request<APIResponse<{ document_id: string, deleted: boolean }>>(
      `/api/v1/collections/${encodeURIComponent(collectionId)}/documents/${encodeURIComponent(documentId)}`,
      { method: 'DELETE' }
    )
  }

  // Ingestion
  /**
   * Ingest files into a collection
   */
  async ingestFiles(collectionId: string, request: IngestFilesRequest): Promise<APIResponse<{ task_id: string, status: string }>> {
    return this.request<APIResponse<{ task_id: string, status: string }>>(
      `/api/v1/collections/${encodeURIComponent(collectionId)}/ingest/folder`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      }
    )
  }

  /**
   * Ingest URLs into a collection
   */
  async ingestUrls(collectionId: string, request: IngestUrlsRequest): Promise<APIResponse<{ task_id: string, status: string }>> {
    return this.request<APIResponse<{ task_id: string, status: string }>>(
      `/api/v1/collections/${encodeURIComponent(collectionId)}/ingest/urls`,
      {
        method: 'POST',
        body: JSON.stringify(request),
      }
    )
  }

  // Task Management
  /**
   * Get task status
   */
  async getTask(taskId: string): Promise<APIResponse<Task>> {
    return this.request<APIResponse<Task>>(`/api/v1/tasks/${encodeURIComponent(taskId)}`)
  }

  /**
   * List tasks
   */
  async listTasks(status?: string, taskType?: string): Promise<APIResponse<{ tasks: Task[], total: number }>> {
    const params = new URLSearchParams()
    if (status) params.append('status', status)
    if (taskType) params.append('task_type', taskType)
    
    const url = params.toString() ? `/api/v1/tasks?${params}` : '/api/v1/tasks'
    return this.request<APIResponse<{ tasks: Task[], total: number }>>(url)
  }

  // Chat Management
  /**
   * Create a new chat
   */
  async createChat(request: CreateChatRequest): Promise<APIResponse<Chat>> {
    return this.request<APIResponse<Chat>>('/api/v1/chats', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  /**
   * List chats
   */
  async listChats(offset: number = 0, limit: number = 50): Promise<APIResponse<{ chats: Chat[], offset: number, limit: number, total: number }>> {
    return this.request<APIResponse<{ chats: Chat[], offset: number, limit: number, total: number }>>(
      `/api/v1/chats?offset=${offset}&limit=${limit}`
    )
  }

  /**
   * Get a specific chat
   */
  async getChat(chatId: string): Promise<APIResponse<Chat>> {
    return this.request<APIResponse<Chat>>(`/api/v1/chats/${encodeURIComponent(chatId)}`)
  }

  /**
   * Delete a chat
   */
  async deleteChat(chatId: string): Promise<APIResponse<{ chat_id: string, deleted: boolean }>> {
    return this.request<APIResponse<{ chat_id: string, deleted: boolean }>>(`/api/v1/chats/${encodeURIComponent(chatId)}`, {
      method: 'DELETE',
    })
  }

  /**
   * Get chat messages
   */
  async getChatMessages(
    chatId: string,
    offset: number = 0,
    limit: number = 50
  ): Promise<APIResponse<{ messages: ChatMessage[], offset: number, limit: number, total: number }>> {
    return this.request<APIResponse<{ messages: ChatMessage[], offset: number, limit: number, total: number }>>(
      `/api/v1/chats/${encodeURIComponent(chatId)}/messages?offset=${offset}&limit=${limit}`
    )
  }

  /**
   * Send a message to chat (synchronous)
   */
  async sendMessage(chatId: string, request: ChatMessageRequest): Promise<APIResponse<ChatMessage>> {
    return this.request<APIResponse<ChatMessage>>(`/api/v1/chats/${encodeURIComponent(chatId)}/chat`, {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  /**
   * Send a message to chat (streaming)
   */
  async sendMessageStream(
    chatId: string,
    request: ChatMessageRequest,
    onEvent: (event: SSEEvent) => void,
    onError?: (error: Error) => void
  ): Promise<void> {
    this.abortController = new AbortController()
    
    try {
      const response = await fetch(`${this.baseURL}/api/v1/chats/${encodeURIComponent(chatId)}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(request),
        signal: this.abortController.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('Response body is not readable')
      }

      try {
        let buffer = ''
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          
          // Keep the last incomplete line in the buffer
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6).trim()
              if (data && data !== '[DONE]') {
                try {
                  const parsed = JSON.parse(data)
                  onEvent({ event: 'data', data: parsed })
                } catch (e) {
                  console.error('Failed to parse SSE data:', e, 'Data:', data)
                }
              }
            } else if (line.startsWith('event: ')) {
              const eventType = line.slice(7).trim()
              onEvent({ event: eventType, data: null })
            }
          }
        }
      } finally {
        reader.releaseLock()
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        return // Request was cancelled, don't treat as error
      }
      
      const err = error instanceof Error ? error : new Error('Unknown error')
      if (onError) {
        onError(err)
      } else {
        throw err
      }
    }
  }

  // Enhanced Chat Methods
  /**
   * Send enhanced message with advanced features (synchronous)
   */
  async sendEnhancedMessage(
    chatId: string, 
    request: EnhancedChatRequest
  ): Promise<APIResponse<EnhancedChatResponse>> {
    const params = new URLSearchParams()
    if (request.enable_intent_analysis !== undefined) {
      params.append('enable_intent_analysis', request.enable_intent_analysis.toString())
    }
    if (request.enable_cache !== undefined) {
      params.append('enable_cache', request.enable_cache.toString())
    }
    if (request.enable_summary_overview !== undefined) {
      params.append('enable_summary_overview', request.enable_summary_overview.toString())
    }
    if (request.retrieval_strategy) {
      params.append('retrieval_strategy', request.retrieval_strategy)
    }

    const url = `/api/v1/chats/${encodeURIComponent(chatId)}/chat/enhanced?${params}`
    return this.request<APIResponse<EnhancedChatResponse>>(url, {
      method: 'POST',
      body: JSON.stringify({
        message: request.message,
        include_sources: request.include_sources
      }),
    })
  }

  /**
   * Send enhanced message with streaming response
   */
  async sendEnhancedMessageStream(
    chatId: string,
    request: EnhancedChatRequest,
    onEvent: (event: SSEEvent) => void,
    onError?: (error: Error) => void
  ): Promise<void> {
    this.abortController = new AbortController()

    const params = new URLSearchParams()
    if (request.enable_intent_analysis !== undefined) {
      params.append('enable_intent_analysis', request.enable_intent_analysis.toString())
    }
    if (request.enable_cache !== undefined) {
      params.append('enable_cache', request.enable_cache.toString())
    }
    if (request.enable_summary_overview !== undefined) {
      params.append('enable_summary_overview', request.enable_summary_overview.toString())
    }
    if (request.retrieval_strategy) {
      params.append('retrieval_strategy', request.retrieval_strategy)
    }

    try {
      const response = await fetch(`${this.baseURL}/api/v1/chats/${encodeURIComponent(chatId)}/chat/enhanced/stream?${params}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify({
          message: request.message,
          include_sources: request.include_sources
        }),
        signal: this.abortController.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('Response body is not readable')
      }

      try {
        let buffer = ''
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6).trim()
              if (data && data !== '[DONE]') {
                try {
                  const parsed = JSON.parse(data)
                  onEvent({ event: 'data', data: parsed })
                } catch (e) {
                  console.error('Failed to parse enhanced SSE data:', e, 'Data:', data)
                }
              }
            } else if (line.startsWith('event: ')) {
              const eventType = line.slice(7).trim()
              onEvent({ event: eventType, data: null })
            }
          }
        }
      } finally {
        reader.releaseLock()
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        return
      }
      
      const err = error instanceof Error ? error : new Error('Unknown error')
      if (onError) {
        onError(err)
      } else {
        throw err
      }
    }
  }

  /**
   * Analyze message intent
   */
  async analyzeMessageIntent(
    chatId: string, 
    message: string
  ): Promise<APIResponse<IntentAnalysis>> {
    return this.request<APIResponse<IntentAnalysis>>(
      `/api/v1/chats/${encodeURIComponent(chatId)}/intent-analysis?message=${encodeURIComponent(message)}`
    )
  }

  /**
   * Get cache statistics for a chat
   */
  async getCacheStats(chatId: string): Promise<APIResponse<any>> {
    return this.request<APIResponse<any>>(`/api/v1/chats/${encodeURIComponent(chatId)}/cache-stats`)
  }

  /**
   * Clear cache for a chat
   */
  async clearCache(
    chatId: string, 
    cacheType?: 'query_results' | 'intent' | 'embeddings'
  ): Promise<APIResponse<{ cleared_count: number, cache_type: string }>> {
    const url = cacheType 
      ? `/api/v1/chats/${encodeURIComponent(chatId)}/cache?cache_type=${encodeURIComponent(cacheType)}`
      : `/api/v1/chats/${encodeURIComponent(chatId)}/cache`
    return this.request<APIResponse<{ cleared_count: number, cache_type: string }>>(url, {
      method: 'DELETE'
    })
  }

  // Settings
  /**
   * Get settings
   */
  async getSettings(): Promise<APIResponse<Settings>> {
    return this.request<APIResponse<Settings>>('/api/v1/settings')
  }

  /**
   * Update settings
   */
  async updateSettings(settings: Partial<Settings>): Promise<APIResponse<Settings>> {
    return this.request<APIResponse<Settings>>('/api/v1/settings', {
      method: 'PUT',
      body: JSON.stringify(settings),
    })
  }
}

// Singleton instance management
let apiClientInstance: DocumentAssistantAPI | null = null

export const getAPIClient = (): DocumentAssistantAPI => {
  if (!apiClientInstance) {
    // Default URL - will be updated when API server starts
    apiClientInstance = new DocumentAssistantAPI('http://127.0.0.1:8000')
  }
  return apiClientInstance
}

export const setAPIBaseURL = (baseURL: string) => {
  if (apiClientInstance) {
    apiClientInstance.setBaseURL(baseURL)
  } else {
    apiClientInstance = new DocumentAssistantAPI(baseURL)
  }
}

export const disposeAPIClient = () => {
  if (apiClientInstance) {
    apiClientInstance.cancelRequests()
    apiClientInstance = null
  }
}

// React hook for using the API client
export const useAPIClient = () => {
  return getAPIClient()
}

// Helper function to extract data from API response
export const extractData = <T>(response: APIResponse<T>): T => {
  if (response.code !== 'Success') {
    throw new Error(response.message || 'API request failed')
  }
  if (response.data === null) {
    throw new Error('Response data is null')
  }
  return response.data as T
}