/**
 * Tests for PythonBridge service
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { PythonBridge } from '../../services/pythonBridge'

// Mock Electron API
const mockElectronAPI = {
  onPythonResponse: vi.fn(),
  onPythonError: vi.fn(),
  onPythonDisconnected: vi.fn(),
  sendPythonCommand: vi.fn(),
  removeAllListeners: vi.fn()
}

Object.defineProperty(window, 'electronAPI', {
  writable: true,
  value: mockElectronAPI
})

describe('PythonBridge', () => {
  let bridge: PythonBridge

  beforeEach(() => {
    vi.clearAllMocks()
    bridge = new PythonBridge()
  })

  afterEach(() => {
    bridge.dispose()
  })

  it('initializes with event listeners', () => {
    expect(mockElectronAPI.onPythonResponse).toHaveBeenCalled()
    expect(mockElectronAPI.onPythonError).toHaveBeenCalled()
    expect(mockElectronAPI.onPythonDisconnected).toHaveBeenCalled()
  })

  it('reports connected status initially', () => {
    expect(bridge.getConnectionStatus()).toBe(true)
  })

  it('processes files successfully', async () => {
    const mockResponse = {
      status: 'success',
      command: 'process_files',
      processed_files: 2,
      total_chunks: 10,
      indexed_count: 10
    }

    // Mock successful command sending
    mockElectronAPI.sendPythonCommand.mockResolvedValue(true)

    // Start the command
    const processPromise = bridge.processFiles(['/path/file1.txt', '/path/file2.txt'])

    // Simulate Python response
    const responseCallback = mockElectronAPI.onPythonResponse.mock.calls[0][0]
    responseCallback(mockResponse)

    const result = await processPromise
    expect(result.status).toBe('success')
    expect(result.processed_files).toBe(2)
  })

  it('handles crawl URL successfully', async () => {
    const mockResponse = {
      status: 'success',
      command: 'crawl_url',
      crawled_pages: 5,
      total_chunks: 20,
      indexed_count: 20
    }

    mockElectronAPI.sendPythonCommand.mockResolvedValue(true)

    const crawlPromise = bridge.crawlUrl('https://example.com')

    // Simulate Python response
    const responseCallback = mockElectronAPI.onPythonResponse.mock.calls[0][0]
    responseCallback(mockResponse)

    const result = await crawlPromise
    expect(result.status).toBe('success')
    expect(result.crawled_pages).toBe(5)
  })

  it('handles query successfully', async () => {
    const mockResponse = {
      status: 'success',
      command: 'query',
      answer: 'This is the answer',
      sources: [
        {
          source: 'document.txt',
          content_preview: 'Preview of content...',
          score: 0.9,
          start_index: 0
        }
      ],
      confidence: 0.9
    }

    mockElectronAPI.sendPythonCommand.mockResolvedValue(true)

    const queryPromise = bridge.query('What is the answer?')

    // Simulate Python response
    const responseCallback = mockElectronAPI.onPythonResponse.mock.calls[0][0]
    responseCallback(mockResponse)

    const result = await queryPromise
    expect(result.status).toBe('success')
    expect(result.answer).toBe('This is the answer')
    expect(result.sources).toHaveLength(1)
  })

  it('handles progress events', () => {
    const progressSpy = vi.fn()
    bridge.on('progress', progressSpy)

    const progressResponse = {
      status: 'progress',
      command: 'process_files',
      progress: 3,
      total: 10,
      message: 'Processing file 3 of 10'
    }

    // Simulate progress event
    const responseCallback = mockElectronAPI.onPythonResponse.mock.calls[0][0]
    responseCallback(progressResponse)

    expect(progressSpy).toHaveBeenCalledWith(progressResponse)
  })

  it('handles Python errors', () => {
    const errorSpy = vi.fn()
    bridge.on('error', errorSpy)

    const error = { message: 'Python backend error' }

    // Simulate error event
    const errorCallback = mockElectronAPI.onPythonError.mock.calls[0][0]
    errorCallback(error)

    expect(errorSpy).toHaveBeenCalled()
    expect(bridge.getConnectionStatus()).toBe(false)
  })

  it('handles disconnection', () => {
    const disconnectedSpy = vi.fn()
    bridge.on('disconnected', disconnectedSpy)

    const disconnectData = { code: 1 }

    // Simulate disconnection event
    const disconnectedCallback = mockElectronAPI.onPythonDisconnected.mock.calls[0][0]
    disconnectedCallback(disconnectData)

    expect(disconnectedSpy).toHaveBeenCalledWith(disconnectData)
    expect(bridge.getConnectionStatus()).toBe(false)
  })

  it('handles command timeouts', async () => {
    mockElectronAPI.sendPythonCommand.mockResolvedValue(true)

    // Don't simulate a response to trigger timeout
    await expect(
      bridge.processFiles(['/path/file.txt'])
    ).rejects.toThrow('timed out')
  })

  it('handles command errors', async () => {
    const errorResponse = {
      status: 'error',
      command: 'process_files',
      message: 'File not found'
    }

    mockElectronAPI.sendPythonCommand.mockResolvedValue(true)

    const processPromise = bridge.processFiles(['/invalid/path.txt'])

    // Simulate error response
    const responseCallback = mockElectronAPI.onPythonResponse.mock.calls[0][0]
    responseCallback(errorResponse)

    await expect(processPromise).rejects.toThrow('File not found')
  })

  it('rejects pending commands on disconnection', async () => {
    mockElectronAPI.sendPythonCommand.mockResolvedValue(true)

    const processPromise = bridge.processFiles(['/path/file.txt'])

    // Simulate disconnection
    const disconnectedCallback = mockElectronAPI.onPythonDisconnected.mock.calls[0][0]
    disconnectedCallback({ code: 1 })

    await expect(processPromise).rejects.toThrow('disconnected')
  })

  it('cleans up resources on dispose', () => {
    bridge.dispose()

    expect(mockElectronAPI.removeAllListeners).toHaveBeenCalledWith('python-response')
    expect(mockElectronAPI.removeAllListeners).toHaveBeenCalledWith('python-error')
    expect(mockElectronAPI.removeAllListeners).toHaveBeenCalledWith('python-disconnected')
  })
})