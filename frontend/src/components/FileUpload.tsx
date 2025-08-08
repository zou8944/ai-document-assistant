/**
 * FileUpload component with drag-and-drop support.
 * Following Apple Liquid Glass design with native macOS feel.
 */

import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { DocumentArrowUpIcon, FolderOpenIcon, XMarkIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'

interface FileUploadProps {
  onFilesSelected: (files: string[]) => void
  isProcessing?: boolean
  className?: string
}

export const FileUpload: React.FC<FileUploadProps> = ({
  onFilesSelected,
  isProcessing = false,
  className
}) => {
  const [selectedFiles, setSelectedFiles] = useState<string[]>([])

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (isProcessing) return

    const filePaths = acceptedFiles.map(file => (file as any).path || file.name)
    setSelectedFiles(prev => [...prev, ...filePaths])
    onFilesSelected(filePaths)
  }, [onFilesSelected, isProcessing])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled: isProcessing,
    multiple: true,
    accept: {
      'application/pdf': ['.pdf'],
      'text/plain': ['.txt'],
      'text/markdown': ['.md', '.markdown'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'application/msword': ['.doc'],
    }
  })

  const handleBrowseFiles = async () => {
    if (isProcessing) return

    try {
      const result = await window.electronAPI.showOpenDialog({
        properties: ['openFile', 'multiSelections'],
        filters: [
          { name: 'Documents', extensions: ['pdf', 'txt', 'md', 'docx', 'doc'] },
          { name: 'All Files', extensions: ['*'] }
        ]
      })

      if (!result.canceled && result.filePaths) {
        setSelectedFiles(prev => [...prev, ...result.filePaths])
        onFilesSelected(result.filePaths)
      }
    } catch (error) {
      console.error('Error opening file dialog:', error)
    }
  }

  const handleBrowseFolder = async () => {
    if (isProcessing) return

    try {
      const result = await window.electronAPI.showOpenFolderDialog()

      if (!result.canceled && result.filePaths && result.filePaths[0]) {
        const folderPath = result.filePaths[0]
        setSelectedFiles(prev => [...prev, folderPath])
        onFilesSelected([folderPath])
      }
    } catch (error) {
      console.error('Error opening folder dialog:', error)
    }
  }

  const removeFile = (index: number) => {
    if (isProcessing) return
    
    setSelectedFiles(prev => prev.filter((_, i) => i !== index))
  }

  const clearAll = () => {
    if (isProcessing) return
    
    setSelectedFiles([])
  }

  return (
    <div className={clsx('space-y-4', className)}>
      {/* Drop Zone */}
      <div
        {...getRootProps()}
        className={clsx(
          'glass-morph rounded-xl p-8 text-center transition-all duration-200 cursor-pointer',
          'border-2 border-dashed',
          isDragActive 
            ? 'border-macos-blue bg-blue-50/50 scale-105' 
            : 'border-macos-gray-300 hover:border-macos-blue hover:bg-macos-gray-50/50',
          isProcessing && 'opacity-50 cursor-not-allowed',
          'animate-fade-in'
        )}
      >
        <input {...getInputProps()} />
        
        <div className="space-y-4">
          <DocumentArrowUpIcon className="w-12 h-12 mx-auto text-macos-gray-500" />
          
          <div>
            <p className="text-lg font-medium text-macos-gray-900 mb-2">
              {isDragActive ? '释放文件以添加' : '拖拽文件到此处'}
            </p>
            <p className="text-sm text-macos-gray-600">
              支持 PDF, TXT, Markdown, Word 文档
            </p>
          </div>

          <div className="flex gap-3 justify-center">
            <button
              type="button"
              onClick={handleBrowseFiles}
              disabled={isProcessing}
              className={clsx(
                'glass-button px-4 py-2 rounded-lg text-sm font-medium',
                'text-macos-gray-700 hover:text-macos-blue',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              选择文件
            </button>
            
            <button
              type="button"
              onClick={handleBrowseFolder}
              disabled={isProcessing}
              className={clsx(
                'glass-button px-4 py-2 rounded-lg text-sm font-medium',
                'text-macos-gray-700 hover:text-macos-blue',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                'flex items-center gap-2'
              )}
            >
              <FolderOpenIcon className="w-4 h-4" />
              选择文件夹
            </button>
          </div>
        </div>
      </div>

      {/* Selected Files List */}
      {selectedFiles.length > 0 && (
        <div className="glass-morph rounded-xl p-4 animate-slide-up">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-macos-gray-900">
              已选择 {selectedFiles.length} 个项目
            </h3>
            {!isProcessing && (
              <button
                onClick={clearAll}
                className="text-xs text-macos-gray-500 hover:text-red-500 transition-colors"
              >
                清除全部
              </button>
            )}
          </div>

          <div className="space-y-2 max-h-32 overflow-y-auto">
            {selectedFiles.map((file, index) => (
              <div
                key={index}
                className={clsx(
                  'flex items-center justify-between p-2 rounded-lg',
                  'bg-white/30 backdrop-blur-sm border border-white/20'
                )}
              >
                <span className="text-sm text-macos-gray-700 truncate flex-1 mr-2">
                  {file.split('/').pop() || file}
                </span>
                
                {!isProcessing && (
                  <button
                    onClick={() => removeFile(index)}
                    className="p-1 hover:bg-red-100 rounded transition-colors"
                  >
                    <XMarkIcon className="w-4 h-4 text-macos-gray-400 hover:text-red-500" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default FileUpload