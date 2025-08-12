/**
 * Preload script for secure IPC communication between renderer and main process.
 * Following Electron security best practices with context isolation.
 */

import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron'

// Type definitions for API server
interface APIServerInfo {
  port: number
  pid: number
  baseURL: string
}

// Define the API interface
interface ElectronAPI {
  // API server communication
  getAPIServerInfo: () => Promise<APIServerInfo | null>
  restartAPIServer: () => Promise<APIServerInfo | null>
  onAPIServerReady: (callback: (info: APIServerInfo) => void) => void
  onAPIServerDisconnected: (callback: (data: any) => void) => void
  
  // File system
  showOpenDialog: (options?: any) => Promise<any>
  showOpenFolderDialog: () => Promise<any>
  
  // Window controls
  minimizeWindow: () => Promise<void>
  maximizeWindow: () => Promise<void>
  closeWindow: () => Promise<void>
  
  // App info
  getAppVersion: () => Promise<string>
  getPlatform: () => Promise<string>
  
  // External
  openExternal: (url: string) => Promise<void>
  
  // Utility
  removeAllListeners: (channel: string) => void
}

// Exposed protected methods in the render process
const electronAPI: ElectronAPI = {
  // API server communication
  getAPIServerInfo: () => ipcRenderer.invoke('get-api-server-info'),
  restartAPIServer: () => ipcRenderer.invoke('restart-api-server'),
  
  onAPIServerReady: (callback: (info: APIServerInfo) => void) => {
    ipcRenderer.on('api-server-ready', (event: IpcRendererEvent, info: APIServerInfo) => {
      callback(info)
    })
  },
  
  onAPIServerDisconnected: (callback: (data: any) => void) => {
    ipcRenderer.on('api-server-disconnected', (event: IpcRendererEvent, data: any) => {
      callback(data)
    })
  },

  // File system dialogs
  showOpenDialog: (options?: any) => ipcRenderer.invoke('show-open-dialog', options),
  showOpenFolderDialog: () => ipcRenderer.invoke('show-open-folder-dialog'),
  
  // Window controls
  minimizeWindow: () => ipcRenderer.invoke('minimize-window'),
  maximizeWindow: () => ipcRenderer.invoke('maximize-window'),
  closeWindow: () => ipcRenderer.invoke('close-window'),
  
  // App information
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  getPlatform: () => ipcRenderer.invoke('get-platform'),
  
  // External links
  openExternal: (url: string) => ipcRenderer.invoke('open-external', url),
  
  // Utility
  removeAllListeners: (channel: string) => ipcRenderer.removeAllListeners(channel),
}

// Expose the API to the renderer process
contextBridge.exposeInMainWorld('electronAPI', electronAPI)

// Type declaration for global access in renderer
declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}