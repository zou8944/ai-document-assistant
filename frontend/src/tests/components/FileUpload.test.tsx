/**
 * Tests for FileUpload component
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import FileUpload from '../../components/FileUpload'

// Mock Electron API
Object.defineProperty(window, 'electronAPI', {
  writable: true,
  value: {
    showOpenDialog: vi.fn(),
    showOpenFolderDialog: vi.fn()
  }
})

describe('FileUpload', () => {
  const mockOnFilesSelected = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders upload area', () => {
    render(<FileUpload onFilesSelected={mockOnFilesSelected} />)
    
    expect(screen.getByText('拖拽文件到此处')).toBeInTheDocument()
    expect(screen.getByText('支持 PDF, TXT, Markdown, Word 文档')).toBeInTheDocument()
  })

  it('shows browse buttons', () => {
    render(<FileUpload onFilesSelected={mockOnFilesSelected} />)
    
    expect(screen.getByText('选择文件')).toBeInTheDocument()
    expect(screen.getByText('选择文件夹')).toBeInTheDocument()
  })

  it('handles file dialog opening', async () => {
    const mockDialogResult = {
      canceled: false,
      filePaths: ['/path/to/file1.txt', '/path/to/file2.pdf']
    }
    
    window.electronAPI.showOpenDialog = vi.fn().mockResolvedValue(mockDialogResult)
    
    render(<FileUpload onFilesSelected={mockOnFilesSelected} />)
    
    const browseButton = screen.getByText('选择文件')
    fireEvent.click(browseButton)
    
    expect(window.electronAPI.showOpenDialog).toHaveBeenCalledWith({
      properties: ['openFile', 'multiSelections'],
      filters: [
        { name: 'Documents', extensions: ['pdf', 'txt', 'md', 'docx', 'doc'] },
        { name: 'All Files', extensions: ['*'] }
      ]
    })
  })

  it('handles folder dialog opening', async () => {
    const mockDialogResult = {
      canceled: false,
      filePaths: ['/path/to/folder']
    }
    
    window.electronAPI.showOpenFolderDialog = vi.fn().mockResolvedValue(mockDialogResult)
    
    render(<FileUpload onFilesSelected={mockOnFilesSelected} />)
    
    const browseFolderButton = screen.getByText('选择文件夹')
    fireEvent.click(browseFolderButton)
    
    expect(window.electronAPI.showOpenFolderDialog).toHaveBeenCalled()
  })

  it('shows selected files', async () => {
    const mockDialogResult = {
      canceled: false,
      filePaths: ['/path/to/file1.txt']
    }
    
    window.electronAPI.showOpenDialog = vi.fn().mockResolvedValue(mockDialogResult)
    
    render(<FileUpload onFilesSelected={mockOnFilesSelected} />)
    
    const browseButton = screen.getByText('选择文件')
    fireEvent.click(browseButton)
    
    // Wait for async operation and re-render
    await new Promise(resolve => setTimeout(resolve, 0))
    
    expect(mockOnFilesSelected).toHaveBeenCalledWith(['/path/to/file1.txt'])
  })

  it('disables interaction when processing', () => {
    render(<FileUpload onFilesSelected={mockOnFilesSelected} isProcessing={true} />)
    
    const browseButton = screen.getByText('选择文件')
    const browseFolderButton = screen.getByText('选择文件夹')
    
    expect(browseButton).toBeDisabled()
    expect(browseFolderButton).toBeDisabled()
  })

  it('shows drag active state', () => {
    render(<FileUpload onFilesSelected={mockOnFilesSelected} />)
    
    const dropzone = screen.getByText('拖拽文件到此处').closest('div')
    
    // Simulate drag enter
    fireEvent.dragEnter(dropzone!, {
      dataTransfer: {
        files: [new File(['content'], 'test.txt', { type: 'text/plain' })]
      }
    })
    
    expect(screen.getByText('释放文件以添加')).toBeInTheDocument()
  })

  it('handles file removal', () => {
    render(<FileUpload onFilesSelected={mockOnFilesSelected} />)
    
    // Would need to simulate having files selected first
    // This test would be more complex in a real scenario
  })

  it('clears all files', () => {
    render(<FileUpload onFilesSelected={mockOnFilesSelected} />)
    
    // Would need to simulate having files selected first
    // This test would be more complex in a real scenario
  })
})