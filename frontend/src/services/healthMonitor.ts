/**
 * Health Monitor for API server connection monitoring and automatic recovery.
 */

import { getAPIClient, setAPIBaseURL } from './apiClient'
import { getProcessManager, type APIServerInfo } from './processManager'

export interface HealthStatus {
  isHealthy: boolean
  lastChecked: Date
  latency?: number
  error?: string
}

export interface HealthMonitorConfig {
  checkInterval: number // ms
  timeoutMs: number // ms
  maxRetries: number
  retryDelay: number // ms
}

const DEFAULT_CONFIG: HealthMonitorConfig = {
  checkInterval: 30000, // 30 seconds
  timeoutMs: 5000, // 5 seconds
  maxRetries: 3,
  retryDelay: 2000, // 2 seconds
}

export class HealthMonitor {
  private config: HealthMonitorConfig
  private intervalId: NodeJS.Timeout | null = null
  private currentStatus: HealthStatus = {
    isHealthy: false,
    lastChecked: new Date()
  }
  private retryCount: number = 0
  private listeners: Array<(status: HealthStatus) => void> = []

  constructor(config: Partial<HealthMonitorConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config }
    this.setupProcessManagerListeners()
  }

  private setupProcessManagerListeners() {
    const processManager = getProcessManager()
    
    // Update API client when server info changes
    processManager.on('server-ready', (info: APIServerInfo) => {
      console.log('Health monitor: Server ready, updating API base URL')
      setAPIBaseURL(info.baseURL)
      this.resetRetryCount()
      this.performHealthCheck() // Immediate check
    })

    processManager.on('server-disconnected', () => {
      console.log('Health monitor: Server disconnected')
      this.updateStatus({
        isHealthy: false,
        lastChecked: new Date(),
        error: 'Server disconnected'
      })
    })
  }

  /**
   * Start monitoring API server health
   */
  start(): void {
    if (this.intervalId) {
      console.warn('Health monitor already running')
      return
    }

    console.log('Starting health monitor...')
    
    // Perform immediate health check
    this.performHealthCheck()
    
    // Schedule periodic checks
    this.intervalId = setInterval(() => {
      this.performHealthCheck()
    }, this.config.checkInterval)
  }

  /**
   * Stop monitoring
   */
  stop(): void {
    if (this.intervalId) {
      clearInterval(this.intervalId)
      this.intervalId = null
      console.log('Health monitor stopped')
    }
  }

  /**
   * Perform a health check
   */
  async performHealthCheck(): Promise<HealthStatus> {
    const startTime = Date.now()
    
    try {
      const apiClient = getAPIClient()
      const response = await Promise.race([
        apiClient.healthCheck(),
        new Promise<never>((_, reject) => 
          setTimeout(() => reject(new Error('Health check timeout')), this.config.timeoutMs)
        )
      ])

      const latency = Date.now() - startTime
      
      if (response.status === 'healthy') {
        this.resetRetryCount()
        this.updateStatus({
          isHealthy: true,
          lastChecked: new Date(),
          latency
        })
      } else {
        throw new Error(`Server unhealthy: ${response.status}`)
      }

    } catch (error) {
      console.error('Health check failed:', error)
      
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      this.updateStatus({
        isHealthy: false,
        lastChecked: new Date(),
        error: errorMessage
      })

      // Attempt recovery if max retries not reached
      if (this.retryCount < this.config.maxRetries) {
        this.retryCount++
        console.log(`Attempting recovery (${this.retryCount}/${this.config.maxRetries})...`)
        
        setTimeout(() => {
          this.attemptRecovery()
        }, this.config.retryDelay)
      } else {
        console.error('Max retry attempts reached, giving up recovery')
      }
    }

    return this.currentStatus
  }

  /**
   * Attempt to recover connection
   */
  private async attemptRecovery(): Promise<void> {
    try {
      const processManager = getProcessManager()
      
      // Try restarting the API server
      console.log('Attempting to restart API server...')
      await processManager.restartServer()
      
      // Wait a bit for server to fully start
      await new Promise(resolve => setTimeout(resolve, 3000))
      
      // Perform health check
      await this.performHealthCheck()
      
    } catch (error) {
      console.error('Recovery attempt failed:', error)
    }
  }

  /**
   * Get current health status
   */
  getStatus(): HealthStatus {
    return { ...this.currentStatus }
  }

  /**
   * Subscribe to health status changes
   */
  onStatusChange(callback: (status: HealthStatus) => void): () => void {
    this.listeners.push(callback)
    
    // Return unsubscribe function
    return () => {
      const index = this.listeners.indexOf(callback)
      if (index !== -1) {
        this.listeners.splice(index, 1)
      }
    }
  }

  /**
   * Force a health check (useful for manual testing)
   */
  async forceCheck(): Promise<HealthStatus> {
    return this.performHealthCheck()
  }

  private updateStatus(status: HealthStatus): void {
    this.currentStatus = status
    
    // Notify all listeners
    this.listeners.forEach(listener => {
      try {
        listener(status)
      } catch (error) {
        console.error('Health monitor listener error:', error)
      }
    })
  }

  private resetRetryCount(): void {
    this.retryCount = 0
  }

  /**
   * Clean up resources
   */
  dispose(): void {
    this.stop()
    this.listeners = []
  }
}

// Singleton instance
let healthMonitorInstance: HealthMonitor | null = null

export const getHealthMonitor = (config?: Partial<HealthMonitorConfig>): HealthMonitor => {
  if (!healthMonitorInstance) {
    healthMonitorInstance = new HealthMonitor(config)
  }
  return healthMonitorInstance
}

export const disposeHealthMonitor = (): void => {
  if (healthMonitorInstance) {
    healthMonitorInstance.dispose()
    healthMonitorInstance = null
  }
}

// React hook for using the health monitor
export const useHealthMonitor = (config?: Partial<HealthMonitorConfig>) => {
  return getHealthMonitor(config)
}