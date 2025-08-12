/**
 * Services module exports.
 * Centralized export point for all service modules.
 */

// API Client
export {
  DocumentAssistantAPI,
  getAPIClient,
  setAPIBaseURL,
  disposeAPIClient,
  useAPIClient,
  type ProcessFilesRequest,
  type ProcessFilesResponse,
  type CrawlWebsiteRequest,
  type CrawlWebsiteResponse,
  type QueryRequest,
  type QueryResponse,
  type SourceInfo,
  type CollectionInfo,
  type ListCollectionsResponse,
  type DeleteCollectionRequest,
  type DeleteCollectionResponse,
  type HealthResponse,
  type AnyStreamChunk,
  type ProgressChunk,
  type ContentChunk,
  type SourcesChunk,
  type ErrorChunk,
  type DoneChunk,
} from './apiClient'

// Process Manager
export {
  ProcessManager,
  getProcessManager,
  disposeProcessManager,
  useProcessManager,
  type APIServerInfo,
  type ProcessManagerEvents,
} from './processManager'

// Health Monitor
export {
  HealthMonitor,
  getHealthMonitor,
  disposeHealthMonitor,
  useHealthMonitor,
  type HealthStatus,
  type HealthMonitorConfig,
} from './healthMonitor'

// Convenience function to initialize all services
export const initializeServices = () => {
  const processManager = getProcessManager()
  const healthMonitor = getHealthMonitor()
  
  // Start health monitoring when process manager is ready
  processManager.on('server-ready', () => {
    healthMonitor.start()
  })
  
  return {
    processManager,
    healthMonitor,
    apiClient: getAPIClient(),
  }
}

// Cleanup function for all services
export const disposeAllServices = () => {
  disposeHealthMonitor()
  disposeProcessManager()
  disposeAPIClient()
}