/**
 * REST API client for AI Document Assistant backend.
 * Replaces the python-shell based communication with standard HTTP requests.
 */

// Type definitions for API requests and responses
export interface ProcessFilesRequest {
  file_paths: string[]
  collection_name: string
}

export interface ProcessFilesResponse {
  success: boolean
  collection_name: string
  processed_files: number
  total_files: number
  total_chunks: number
  indexed_count: number
  message?: string
}

export interface CrawlWebsiteRequest {
  url: string
  collection_name: string
  max_pages?: number
}

export interface CrawlWebsiteResponse {
  success: boolean
  collection_name: string
  crawled_pages: number
  failed_pages: number
  total_chunks: number
  indexed_count: number
  stats?: any
  message?: string
}

export interface QueryRequest {
  question: string
  collection_name: string
  include_sources?: boolean
}

export interface SourceInfo {
  source: string
  content_preview: string
  score: number
  start_index: number
}

export interface QueryResponse {
  answer: string
  sources: SourceInfo[]
  confidence: number
  collection_name: string
  question: string
}

export interface CollectionInfo {
  name: string
  vector_size: number
  document_count: number
  source_type: string
}

export interface ListCollectionsResponse {
  collections: CollectionInfo[]
}

export interface DeleteCollectionRequest {
  collection_name: string
}

export interface DeleteCollectionResponse {
  success: boolean
  collection_name: string
  message?: string
}

export interface HealthResponse {
  status: string
  version: string
  embeddings_available: boolean
  chroma_available: boolean
}

// Streaming chunk types
export interface StreamChunk {
  type: string
}

export interface ProgressChunk extends StreamChunk {
  type: 'progress'
  message: string
  current?: number
  total?: number
}

export interface ContentChunk extends StreamChunk {
  type: 'content'
  content: string
}

export interface SourcesChunk extends StreamChunk {
  type: 'sources'
  sources: SourceInfo[]
}

export interface ErrorChunk extends StreamChunk {
  type: 'error'
  error: string
}

export interface DoneChunk extends StreamChunk {
  type: 'done'
  confidence?: number
}

export type AnyStreamChunk = ProgressChunk | ContentChunk | SourcesChunk | ErrorChunk | DoneChunk

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
  async healthCheck(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/api/health')
  }

  /**
   * Process files and index them
   */
  async processFiles(request: ProcessFilesRequest): Promise<ProcessFilesResponse> {
    return this.request<ProcessFilesResponse>('/api/files/process', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  /**
   * Crawl website and index content
   */
  async crawlWebsite(request: CrawlWebsiteRequest): Promise<CrawlWebsiteResponse> {
    return this.request<CrawlWebsiteResponse>('/api/crawler/crawl', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  /**
   * Synchronous document query
   */
  async query(request: QueryRequest): Promise<QueryResponse> {
    return this.request<QueryResponse>('/api/query', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  /**
   * Streaming document query with real-time response
   */
  async queryStream(
    request: QueryRequest,
    onChunk: (chunk: AnyStreamChunk) => void,
    onError?: (error: Error) => void
  ): Promise<void> {
    this.abortController = new AbortController()
    
    try {
      const response = await fetch(`${this.baseURL}/api/query/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
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
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value, { stream: true })
          const lines = chunk.split('\\n')

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6).trim()
              if (data) {
                try {
                  const parsed = JSON.parse(data) as AnyStreamChunk
                  onChunk(parsed)
                } catch (e) {
                  console.error('Failed to parse SSE data:', e, 'Data:', data)
                }
              }
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

  /**
   * List all available collections
   */
  async listCollections(): Promise<ListCollectionsResponse> {
    return this.request<ListCollectionsResponse>('/api/collections')
  }

  /**
   * Get information about a specific collection
   */
  async getCollectionInfo(collectionName: string): Promise<CollectionInfo> {
    return this.request<CollectionInfo>(`/api/collections/${encodeURIComponent(collectionName)}`)
  }

  /**
   * Delete a collection
   */
  async deleteCollection(request: DeleteCollectionRequest): Promise<DeleteCollectionResponse> {
    return this.request<DeleteCollectionResponse>('/api/collections', {
      method: 'DELETE',
      body: JSON.stringify(request),
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