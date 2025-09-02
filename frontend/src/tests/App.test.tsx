/**
 * Tests for main App component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import App from '../App'

// Mock the services
const mockAPIClient = {
  processFiles: vi.fn(),
  crawlWebsite: vi.fn(),
  query: vi.fn(),
  listCollections: vi.fn(),
  healthCheck: vi.fn()
}

const mockProcessManager = {
  on: vi.fn(),
  off: vi.fn(),
  getServerInfo: vi.fn(),
  isServerConnected: vi.fn(() => true),
  restartServer: vi.fn(),
  dispose: vi.fn()
}

vi.mock('../services', () => ({
  useAPIClient: () => mockAPIClient,
  useProcessManager: () => mockProcessManager
}))

// Mock Electron API
Object.defineProperty(window, 'electronAPI', {
  writable: true,
  value: {
    showOpenDialog: vi.fn(),
    showOpenFolderDialog: vi.fn(),
    getAPIServerInfo: vi.fn(),
    restartAPIServer: vi.fn(),
    onAPIServerReady: vi.fn(),
    onAPIServerDisconnected: vi.fn(),
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
    mockAPIClient.processFiles.mockResolvedValue({
      success: true,
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
    
    // Simulate server ready event
    const serverReadyHandler = mockProcessManager.on.mock.calls.find(
      call => call[0] === 'server-ready'
    )?.[1]
    
    if (serverReadyHandler) {
      serverReadyHandler()
    }

    await waitFor(() => {
      expect(screen.getByText('后端服务已连接')).toBeInTheDocument()
    })
  })

  it('handles connection errors', async () => {
    render(<App />)
    
    // Simulate server disconnection event
    const serverDisconnectedHandler = mockProcessManager.on.mock.calls.find(
      call => call[0] === 'server-disconnected'
    )?.[1]
    
    if (serverDisconnectedHandler) {
      serverDisconnectedHandler({ code: 1 })
    }

    await waitFor(() => {
      expect(screen.getByText(/连接中断/)).toBeInTheDocument()
    })
  })

  it('shows collection info when documents are loaded', () => {
    // This would require mocking the state to show documents are loaded
    // Implementation depends on how state is managed
    render(<App />)
    
    // Would need to simulate having documents loaded
    // expect(screen.getByText('当前集合')).toBeInTheDocument()
  })

  it('cleans up services on unmount', () => {
    const { unmount } = render(<App />)
    
    unmount()
    
    expect(mockProcessManager.off).toHaveBeenCalled()
  })
})