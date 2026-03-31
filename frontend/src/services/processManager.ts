/**
 * Process Manager for API server connection management.
 * Web version - manages HTTP connection to backend API.
 */

// Type definitions
export interface APIServerInfo {
  baseURL: string
  isConnected: boolean
}

export interface ProcessManagerEvents {
  'server-ready': [APIServerInfo]
  'server-disconnected': [{ code: number }]
  'connection-status-changed': [boolean]
  [key: string]: any[]
}

// Browser-compatible EventEmitter for process events
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

export class ProcessManager extends EventEmitter<ProcessManagerEvents> {
  private currentServerInfo: APIServerInfo
  private isConnected: boolean = false
  private healthCheckInterval?: number

  constructor() {
    super()
    // Get API URL from environment variables
    const apiUrl = import.meta.env.VITE_API_URL || '/api'
    this.currentServerInfo = {
      baseURL: apiUrl,
      isConnected: false
    }
    this.initialize()
  }

  private async initialize() {
    // Check server health
    await this.checkServerHealth()

    // Start periodic health checks
    this.startHealthChecks()
  }

  private async checkServerHealth(): Promise<boolean> {
    try {
      const response = await fetch(`${this.currentServerInfo.baseURL}/api/v1/health`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (response.ok) {
        if (!this.isConnected) {
          this.isConnected = true
          this.currentServerInfo.isConnected = true
          this.emit('server-ready', this.currentServerInfo)
          this.emit('connection-status-changed', true)
          console.log('API server is connected')
        }
        return true
      } else {
        if (this.isConnected) {
          this.isConnected = false
          this.currentServerInfo.isConnected = false
          this.emit('server-disconnected', { code: response.status })
          this.emit('connection-status-changed', false)
          console.warn('API server connection lost')
        }
        return false
      }
    } catch (error) {
      if (this.isConnected) {
        this.isConnected = false
        this.currentServerInfo.isConnected = false
        this.emit('server-disconnected', { code: 0 })
        this.emit('connection-status-changed', false)
        console.warn('API server connection failed:', error)
      }
      return false
    }
  }

  private startHealthChecks() {
    // Check every 30 seconds
    this.healthCheckInterval = window.setInterval(() => {
      this.checkServerHealth()
    }, 30000)
  }

  /**
   * Get current API server information
   */
  getServerInfo(): APIServerInfo {
    return this.currentServerInfo
  }

  /**
   * Get connection status
   */
  isServerConnected(): boolean {
    return this.isConnected
  }

  /**
   * Manually trigger server health check
   */
  async restartServer(): Promise<APIServerInfo> {
    console.log('Checking API server health...')
    await this.checkServerHealth()
    return this.currentServerInfo
  }

  /**
   * Wait for server to be ready
   */
  waitForServer(timeoutMs: number = 30000): Promise<APIServerInfo> {
    if (this.isConnected) {
      return Promise.resolve(this.currentServerInfo)
    }

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.off('server-ready', onReady)
        reject(new Error(`Server not ready within ${timeoutMs}ms`))
      }, timeoutMs)

      const onReady = (info: APIServerInfo) => {
        clearTimeout(timeout)
        this.off('server-ready', onReady)
        resolve(info)
      }

      this.on('server-ready', onReady)

      // Trigger immediate health check
      this.checkServerHealth()
    })
  }

  /**
   * Clean up resources
   */
  dispose() {
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval)
    }
    this.removeAllListeners()
  }
}

// Singleton instance
let processManagerInstance: ProcessManager | null = null

export const getProcessManager = (): ProcessManager => {
  if (!processManagerInstance) {
    processManagerInstance = new ProcessManager()
  }
  return processManagerInstance
}

export const disposeProcessManager = () => {
  if (processManagerInstance) {
    processManagerInstance.dispose()
    processManagerInstance = null
  }
}

// React hook for using the process manager
export const useProcessManager = () => {
  return getProcessManager()
}