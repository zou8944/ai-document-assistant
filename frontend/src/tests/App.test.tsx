/**
 * Tests for main App component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import App from '../App'

// Mock the python bridge service
const mockPythonBridge = {
  on: vi.fn(),
  off: vi.fn(), 
  processFiles: vi.fn(),
  crawlUrl: vi.fn(),
  query: vi.fn(),
  listCollections: vi.fn(),
  getConnectionStatus: vi.fn(() => true),
  dispose: vi.fn()
}

vi.mock('../services/pythonBridge', () => ({
  usePythonBridge: () => mockPythonBridge,
  getPythonBridge: () => mockPythonBridge,
  disposePythonBridge: vi.fn()
}))

// Mock Electron API
Object.defineProperty(window, 'electronAPI', {
  writable: true,
  value: {
    showOpenDialog: vi.fn(),
    showOpenFolderDialog: vi.fn(),
    sendPythonCommand: vi.fn(),
    onPythonResponse: vi.fn(),
    onPythonError: vi.fn(),
    onPythonDisconnected: vi.fn(),
    removeAllListeners: vi.fn()
  }
})

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders main application', () => {
    render(<App />)
    
    expect(screen.getByText('AI 文档助手')).toBeInTheDocument()
    expect(screen.getByText('上传文件')).toBeInTheDocument()
    expect(screen.getByText('抓取网站')).toBeInTheDocument()
    expect(screen.getByText('智能问答')).toBeInTheDocument()
  })

  it('starts with upload tab active', () => {
    render(<App />)
    
    const uploadTab = screen.getByText('上传文件').closest('button')
    expect(uploadTab).toHaveClass('bg-macos-blue')
  })

  it('chat tab is initially disabled when no documents', () => {
    render(<App />)
    
    const chatTab = screen.getByText('智能问答').closest('button')
    expect(chatTab).toBeDisabled()
  })

  it('can switch between tabs', () => {
    render(<App />)
    
    const crawlTab = screen.getByText('抓取网站').closest('button')
    fireEvent.click(crawlTab!)
    
    expect(crawlTab).toHaveClass('bg-macos-blue')
  })

  it('shows file upload component on upload tab', () => {
    render(<App />)
    
    expect(screen.getByText('拖拽文件到此处')).toBeInTheDocument()
  })

  it('shows URL input component on crawl tab', () => {
    render(<App />)
    
    const crawlTab = screen.getByText('抓取网站').closest('button')
    fireEvent.click(crawlTab!)
    
    expect(screen.getByText('抓取网站内容')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('https://example.com')).toBeInTheDocument()
  })

  it('enables chat tab after successful file processing', async () => {
    mockPythonBridge.processFiles.mockResolvedValue({
      status: 'success',
      processed_files: 1,
      total_chunks: 5,
      indexed_count: 5
    })

    render(<App />)
    
    // Simulate file processing
    const fileUploadComponent = screen.getByText('拖拽文件到此处')
    expect(fileUploadComponent).toBeInTheDocument()
    
    // Wait for processing to complete (would need to trigger file selection)
    // This is a simplified test - in reality would need to mock file selection
  })

  it('shows processing status during operations', async () => {
    render(<App />)
    
    // Simulate progress event
    const progressHandler = mockPythonBridge.on.mock.calls.find(
      call => call[0] === 'progress'
    )?.[1]
    
    if (progressHandler) {
      progressHandler({
        status: 'progress',
        command: 'process_files',
        progress: 2,
        total: 5,
        message: '正在处理文件...'
      })
    }

    await waitFor(() => {
      expect(screen.getByText('正在处理文件...')).toBeInTheDocument()
    })
  })

  it('handles connection errors', async () => {
    render(<App />)
    
    // Simulate error event  
    const errorHandler = mockPythonBridge.on.mock.calls.find(
      call => call[0] === 'error'
    )?.[1]
    
    if (errorHandler) {
      errorHandler(new Error('Connection failed'))
    }

    await waitFor(() => {
      expect(screen.getByText(/连接错误/)).toBeInTheDocument()
    })
  })

  it('shows collection info when documents are loaded', () => {
    // This would require mocking the state to show documents are loaded
    // Implementation depends on how state is managed
    render(<App />)
    
    // Would need to simulate having documents loaded
    // expect(screen.getByText('当前集合')).toBeInTheDocument()
  })

  it('cleans up python bridge on unmount', () => {
    const { unmount } = render(<App />)
    
    unmount()
    
    expect(mockPythonBridge.off).toHaveBeenCalled()
  })
})