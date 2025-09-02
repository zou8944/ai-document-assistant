/**
 * Process Manager for Python API server lifecycle management.
 * Handles communication with Electron main process for server control.
 */

// Type definitions
export interface APIServerInfo {
  port: number
  pid: number
  baseURL: string
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
  private currentServerInfo: APIServerInfo | null = null
  private isConnected: boolean = false

  constructor() {
    super()
    this.setupEventListeners()
    this.initialize()
  }

  private setupEventListeners() {
    // Listen for server ready events
    window.electronAPI.onAPIServerReady((info: APIServerInfo) => {
      console.log('API server ready:', info)
      this.currentServerInfo = info
      this.isConnected = true
      this.emit('server-ready', info)
      this.emit('connection-status-changed', true)
    })

    // Listen for server disconnection events
    window.electronAPI.onAPIServerDisconnected((data: { code: number }) => {
      console.log('API server disconnected:', data)
      this.currentServerInfo = null
      this.isConnected = false
      this.emit('server-disconnected', data)
      this.emit('connection-status-changed', false)
    })
  }

  private async initialize() {
    // Check if server is already running
    try {
      const serverInfo = await window.electronAPI.getAPIServerInfo()
      if (serverInfo) {
        this.currentServerInfo = serverInfo
        this.isConnected = true
        this.emit('server-ready', serverInfo)
        this.emit('connection-status-changed', true)
      }
    } catch (error) {
      console.error('Failed to get initial server info:', error)
    }
  }

  /**
   * Get current API server information
   */
  getServerInfo(): APIServerInfo | null {
    return this.currentServerInfo
  }

  /**
   * Get connection status
   */
  isServerConnected(): boolean {
    return this.isConnected
  }

  /**
   * Restart the API server
   */
  async restartServer(): Promise<APIServerInfo | null> {
    try {
      console.log('Restarting API server...')
      const serverInfo = await window.electronAPI.restartAPIServer()
      
      if (serverInfo) {
        this.currentServerInfo = serverInfo
        this.isConnected = true
        this.emit('server-ready', serverInfo)
        this.emit('connection-status-changed', true)
      }
      
      return serverInfo
    } catch (error) {
      console.error('Failed to restart API server:', error)
      this.isConnected = false
      this.emit('connection-status-changed', false)
      throw error
    }
  }

  /**
   * Wait for server to be ready
   */
  waitForServer(timeoutMs: number = 30000): Promise<APIServerInfo> {
    if (this.isConnected && this.currentServerInfo) {
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
    })
  }

  /**
   * Clean up resources
   */
  dispose() {
    this.removeAllListeners()
    
    // Remove Electron API listeners
    window.electronAPI.removeAllListeners('api-server-ready')
    window.electronAPI.removeAllListeners('api-server-disconnected')
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