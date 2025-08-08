/**
 * Preload script for secure IPC communication between renderer and main process.
 * Following Electron security best practices with context isolation.
 */

import { contextBridge, ipcRenderer, IpcRendererEvent } from 'electron'

// Define the API interface
interface ElectronAPI {
  // Python communication
  sendPythonCommand: (command: any) => Promise<boolean>
  onPythonResponse: (callback: (response: any) => void) => void
  onPythonError: (callback: (error: any) => void) => void
  onPythonDisconnected: (callback: (data: any) => void) => void
  
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
  // Python backend communication
  sendPythonCommand: (command: any) => ipcRenderer.invoke('send-python-command', command),
  
  onPythonResponse: (callback: (response: any) => void) => {
    ipcRenderer.on('python-response', (event: IpcRendererEvent, response: any) => {
      callback(response)
    })
  },
  
  onPythonError: (callback: (error: any) => void) => {
    ipcRenderer.on('python-error', (event: IpcRendererEvent, error: any) => {
      callback(error)
    })
  },
  
  onPythonDisconnected: (callback: (data: any) => void) => {
    ipcRenderer.on('python-disconnected', (event: IpcRendererEvent, data: any) => {
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