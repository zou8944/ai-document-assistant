/**
 * Python Bridge Service for communication with the backend.
 * Following 2024 best practices for async request/response handling with error recovery.
 */

// Browser-compatible EventEmitter implementation
class EventEmitter<T extends Record<string, any[]> = Record<string, any[]>> {
  private listeners: Map<keyof T, Function[]> = new Map()

  on<K extends keyof T>(event: K, listener: (...args: T[K]) => void): this {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, [])
    }
    this.listeners.get(event)!.push(listener)
    return this
  }

  off<K extends keyof T>(event: K, listener: (...args: T[K]) => void): this {
    const eventListeners = this.listeners.get(event)
    if (eventListeners) {
      const index = eventListeners.indexOf(listener)
      if (index !== -1) {
        eventListeners.splice(index, 1)
      }
      // Clean up empty listener array
      if (eventListeners.length === 0) {
        this.listeners.delete(event)
      }
    }
    return this
  }

  emit<K extends keyof T>(event: K, ...args: T[K]): boolean {
    const eventListeners = this.listeners.get(event)
    if (!eventListeners) return false
    
    eventListeners.forEach(listener => {
      try {
        listener(...args)
      } catch (error) {
        console.error('EventEmitter listener error:', error)
      }
    })
    return true
  }

  removeAllListeners(event?: keyof T): this {
    if (event) {
      this.listeners.delete(event)
    } else {
      this.listeners.clear()
    }
    return this
  }
}

// Type definitions for Python communication
export interface PythonCommand {
  command: string
  [key: string]: any
}

export interface PythonResponse {
  status: 'success' | 'error' | 'progress'
  command?: string
  message?: string
  [key: string]: any
}

export interface ProcessFilesCommand extends PythonCommand {
  command: 'process_files'
  file_paths: string[]
  collection_name: string
}

export interface CrawlUrlCommand extends PythonCommand {
  command: 'crawl_url'
  url: string
  collection_name: string
}

export interface QueryCommand extends PythonCommand {
  command: 'query'
  question: string
  collection_name: string
}

export interface ListCollectionsCommand extends PythonCommand {
  command: 'list_collections'
}

// Response types
export interface ProcessFilesResponse {
  status: 'success' | 'error'
  collection_name?: string
  processed_files?: number
  total_files?: number
  total_chunks?: number
  indexed_count?: number
  message?: string
}

export interface CrawlUrlResponse {
  status: 'success' | 'error'
  collection_name?: string
  crawled_pages?: number
  failed_pages?: number
  total_chunks?: number
  indexed_count?: number
  stats?: any
  message?: string
}

export interface QueryResponse {
  status: 'success' | 'error'
  answer?: string
  sources?: Array<{
    source: string
    content_preview: string
    score: number
    start_index: number
  }>
  confidence?: number
  question?: string
  collection_name?: string
  message?: string
}

export interface ProgressResponse {
  status: 'progress'
  command: string
  progress: number
  total: number
  message: string
}

// Event types
export type PythonBridgeEvents = {
  'response': [PythonResponse]
  'progress': [ProgressResponse]
  'error': [Error]
  'connected': []
  'disconnected': [{ code: number }]
}

export class PythonBridge extends EventEmitter<PythonBridgeEvents> {
  private isConnected: boolean = false
  private pendingCommands: Map<string, {
    resolve: (value: any) => void
    reject: (error: Error) => void
    timeout: NodeJS.Timeout
  }> = new Map()

  constructor() {
    super()
    this.setupEventListeners()
    this.checkConnection()
  }

  private setupEventListeners() {
    // Handle responses from Python backend
    window.electronAPI.onPythonResponse((response: PythonResponse) => {
      console.log('Python response received:', response)

      if (response.status === 'progress') {
        this.emit('progress', response as ProgressResponse)
      } else {
        // Handle command responses
        const commandId = response.command
        if (commandId && this.pendingCommands.has(commandId)) {
          const pending = this.pendingCommands.get(commandId)!
          clearTimeout(pending.timeout)
          this.pendingCommands.delete(commandId)
          
          if (response.status === 'error') {
            pending.reject(new Error(response.message || 'Unknown error'))
          } else {
            pending.resolve(response)
          }
        }
        
        this.emit('response', response)
      }
    })

    // Handle Python errors
    window.electronAPI.onPythonError((error: any) => {
      console.error('Python error:', error)
      this.isConnected = false
      this.emit('error', new Error(error.message || 'Python backend error'))
      
      // Reject all pending commands
      this.rejectAllPending(new Error('Python backend disconnected'))
    })

    // Handle disconnection
    window.electronAPI.onPythonDisconnected((data: { code: number }) => {
      console.log('Python backend disconnected with code:', data.code)
      this.isConnected = false
      this.emit('disconnected', data)
      
      // Reject all pending commands
      this.rejectAllPending(new Error('Python backend disconnected'))
    })
  }

  private checkConnection() {
    // Assume connected initially; will be updated by events
    this.isConnected = true
    this.emit('connected')
  }

  private rejectAllPending(error: Error) {
    for (const [commandId, pending] of this.pendingCommands.entries()) {
      clearTimeout(pending.timeout)
      pending.reject(error)
    }
    this.pendingCommands.clear()
  }

  private async sendCommand<T = PythonResponse>(
    command: PythonCommand, 
    timeoutMs: number = 60000
  ): Promise<T> {
    if (!this.isConnected) {
      throw new Error('Python backend is not connected')
    }

    return new Promise<T>((resolve, reject) => {
      const commandId = command.command + '_' + Date.now()
      
      // Set up timeout
      const timeout = setTimeout(() => {
        this.pendingCommands.delete(commandId)
        reject(new Error(`Command '${command.command}' timed out after ${timeoutMs}ms`))
      }, timeoutMs)

      // Store pending command
      this.pendingCommands.set(command.command, {
        resolve: resolve as (value: any) => void,
        reject,
        timeout
      })

      // Send command to main process
      window.electronAPI.sendPythonCommand(command)
        .catch((error) => {
          clearTimeout(timeout)
          this.pendingCommands.delete(command.command)
          reject(new Error(`Failed to send command: ${error.message}`))
        })
    })
  }

  // Public API methods

  /**
   * Process local files and index them for searching
   */
  async processFiles(
    filePaths: string[], 
    collectionName: string = 'documents'
  ): Promise<ProcessFilesResponse> {
    const command: ProcessFilesCommand = {
      command: 'process_files',
      file_paths: filePaths,
      collection_name: collectionName
    }

    return this.sendCommand<ProcessFilesResponse>(command, 120000) // 2 minute timeout
  }

  /**
   * Crawl a website and index the content
   */
  async crawlUrl(
    url: string, 
    collectionName: string = 'website'
  ): Promise<CrawlUrlResponse> {
    const command: CrawlUrlCommand = {
      command: 'crawl_url',
      url,
      collection_name: collectionName
    }

    return this.sendCommand<CrawlUrlResponse>(command, 300000) // 5 minute timeout
  }

  /**
   * Query documents using natural language
   */
  async query(
    question: string, 
    collectionName: string = 'documents'
  ): Promise<QueryResponse> {
    const command: QueryCommand = {
      command: 'query',
      question,
      collection_name: collectionName
    }

    return this.sendCommand<QueryResponse>(command, 30000) // 30 second timeout
  }

  /**
   * List available collections
   */
  async listCollections(): Promise<{ collections: any[] }> {
    const command: ListCollectionsCommand = {
      command: 'list_collections'
    }

    return this.sendCommand(command, 10000) // 10 second timeout
  }

  /**
   * Get connection status
   */
  getConnectionStatus(): boolean {
    return this.isConnected
  }

  /**
   * Clean up resources
   */
  dispose() {
    this.removeAllListeners()
    this.rejectAllPending(new Error('PythonBridge disposed'))
    
    // Remove Electron API listeners
    window.electronAPI.removeAllListeners('python-response')
    window.electronAPI.removeAllListeners('python-error')
    window.electronAPI.removeAllListeners('python-disconnected')
  }
}

// Singleton instance
let pythonBridgeInstance: PythonBridge | null = null

export const getPythonBridge = (): PythonBridge => {
  if (!pythonBridgeInstance) {
    pythonBridgeInstance = new PythonBridge()
  }
  return pythonBridgeInstance
}

export const disposePythonBridge = () => {
  if (pythonBridgeInstance) {
    pythonBridgeInstance.dispose()
    pythonBridgeInstance = null
  }
}

// Convenience hooks for React components
export const usePythonBridge = () => {
  return getPythonBridge()
}