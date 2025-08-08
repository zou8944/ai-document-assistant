/**
 * Test setup configuration
 */

import '@testing-library/jest-dom'
import { beforeAll, afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// Mock Electron API globally
Object.defineProperty(window, 'electronAPI', {
  writable: true,
  value: {
    sendPythonCommand: vi.fn(),
    onPythonResponse: vi.fn(),
    onPythonError: vi.fn(),
    onPythonDisconnected: vi.fn(),
    showOpenDialog: vi.fn(),
    showOpenFolderDialog: vi.fn(),
    minimizeWindow: vi.fn(),
    maximizeWindow: vi.fn(),
    closeWindow: vi.fn(),
    getAppVersion: vi.fn(() => Promise.resolve('1.0.0')),
    getPlatform: vi.fn(() => Promise.resolve('darwin')),
    openExternal: vi.fn(),
    removeAllListeners: vi.fn()
  }
})

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}))

// Mock IntersectionObserver
global.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}))

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock File and FileReader for drag-and-drop tests
global.File = class File {
  constructor(public bits: any[], public name: string, public options?: any) {}
  size = 1024
  type = 'text/plain'
}

global.FileReader = class FileReader {
  result = ''
  error = null
  readAsText = vi.fn()
  readAsDataURL = vi.fn()
  onload = vi.fn()
  onerror = vi.fn()
} as any

// Clean up after each test
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

beforeAll(() => {
  // Setup any global test configuration
})