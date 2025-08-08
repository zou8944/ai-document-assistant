/**
 * Main App component for AI Document Assistant.
 * Following Apple Liquid Glass design with state management and navigation.
 */

import React, { useState, useEffect } from 'react'
import { 
  DocumentArrowUpIcon, 
  GlobeAltIcon, 
  ChatBubbleLeftRightIcon,
  Cog6ToothIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline'
import clsx from 'clsx'

// Components
import { 
  FileUpload, 
  URLInput, 
  ChatInterface, 
  StatusIndicator,
  type StatusType 
} from './components'

// Services
import { 
  usePythonBridge, 
  type ProcessFilesResponse, 
  type CrawlUrlResponse,
  type QueryResponse,
  type ProgressResponse
} from './services/pythonBridge'

type TabType = 'upload' | 'crawl' | 'chat'

interface AppState {
  activeTab: TabType
  hasDocuments: boolean
  currentCollection: string
  processing: {
    status: StatusType
    message: string
    progress?: {
      current: number
      total: number
      label: string
    }
    details: string[]
  }
}

export const App: React.FC = () => {
  const [state, setState] = useState<AppState>({
    activeTab: 'upload',
    hasDocuments: false,
    currentCollection: 'documents',
    processing: {
      status: 'idle',
      message: '',
      details: []
    }
  })

  const pythonBridge = usePythonBridge()

  // Setup Python bridge event listeners
  useEffect(() => {
    const handleProgress = (progress: ProgressResponse) => {
      setState(prev => ({
        ...prev,
        processing: {
          status: 'progress',
          message: progress.message,
          progress: {
            current: progress.progress,
            total: progress.total,
            label: progress.command === 'process_files' ? '处理文件' : 
                   progress.command === 'crawl_url' ? '抓取网页' : '处理中'
          },
          details: []
        }
      }))
    }

    const handleError = (error: Error) => {
      setState(prev => ({
        ...prev,
        processing: {
          status: 'error',
          message: `连接错误: ${error.message}`,
          details: ['请检查Python后端是否正常运行'],
        }
      }))
    }

    const handleDisconnected = ({ code }: { code: number }) => {
      setState(prev => ({
        ...prev,
        processing: {
          status: 'error',
          message: `后端连接断开 (代码: ${code})`,
          details: ['请重启应用程序'],
        }
      }))
    }

    pythonBridge.on('progress', handleProgress)
    pythonBridge.on('error', handleError)
    pythonBridge.on('disconnected', handleDisconnected)

    return () => {
      pythonBridge.off('progress', handleProgress)
      pythonBridge.off('error', handleError)
      pythonBridge.off('disconnected', handleDisconnected)
    }
  }, [pythonBridge])

  const updateProcessingStatus = (
    status: StatusType, 
    message: string, 
    details: string[] = []
  ) => {
    setState(prev => ({
      ...prev,
      processing: { status, message, details }
    }))
  }

  const handleFilesSelected = async (filePaths: string[]) => {
    try {
      updateProcessingStatus('processing', '正在处理文件...', [
        '读取文件内容',
        '分析文档结构',
        '生成向量嵌入',
        '存储到向量数据库'
      ])

      const response: ProcessFilesResponse = await pythonBridge.processFiles(
        filePaths, 
        state.currentCollection
      )

      if (response.status === 'success') {
        updateProcessingStatus('success', '文件处理完成！', [
          `已处理 ${response.processed_files} 个文件`,
          `生成 ${response.total_chunks} 个文档块`,
          `索引 ${response.indexed_count} 个向量`
        ])

        setState(prev => ({
          ...prev,
          hasDocuments: true,
          activeTab: 'chat'
        }))

        // Auto-dismiss success message
        setTimeout(() => {
          updateProcessingStatus('idle', '')
        }, 5000)
      } else {
        updateProcessingStatus('error', '文件处理失败', [response.message || '未知错误'])
      }
    } catch (error) {
      updateProcessingStatus('error', '处理文件时发生错误', [
        error instanceof Error ? error.message : '未知错误'
      ])
    }
  }

  const handleUrlSubmit = async (url: string) => {
    try {
      updateProcessingStatus('processing', '正在抓取网站...', [
        '连接到目标网站',
        '分析页面结构', 
        '抓取相关内容',
        '处理和索引内容'
      ])

      const response: CrawlUrlResponse = await pythonBridge.crawlUrl(
        url,
        'website'
      )

      if (response.status === 'success') {
        updateProcessingStatus('success', '网站抓取完成！', [
          `成功抓取 ${response.crawled_pages} 个页面`,
          `生成 ${response.total_chunks} 个文档块`,
          `索引 ${response.indexed_count} 个向量`
        ])

        setState(prev => ({
          ...prev,
          hasDocuments: true,
          currentCollection: 'website',
          activeTab: 'chat'
        }))

        // Auto-dismiss success message
        setTimeout(() => {
          updateProcessingStatus('idle', '')
        }, 5000)
      } else {
        updateProcessingStatus('error', '网站抓取失败', [response.message || '未知错误'])
      }
    } catch (error) {
      updateProcessingStatus('error', '抓取网站时发生错误', [
        error instanceof Error ? error.message : '未知错误'
      ])
    }
  }

  const handleSendMessage = async (message: string): Promise<QueryResponse> => {
    return pythonBridge.query(message, state.currentCollection)
  }

  const handleDismissStatus = () => {
    updateProcessingStatus('idle', '')
  }

  const tabs = [
    {
      id: 'upload' as const,
      name: '上传文件',
      icon: DocumentArrowUpIcon,
      description: '处理本地文档'
    },
    {
      id: 'crawl' as const,
      name: '抓取网站',
      icon: GlobeAltIcon,
      description: '抓取网页内容'
    },
    {
      id: 'chat' as const,
      name: '智能问答',
      icon: ChatBubbleLeftRightIcon,
      description: '与文档对话',
      disabled: !state.hasDocuments
    }
  ]

  const renderTabContent = () => {
    const isProcessing = state.processing.status === 'processing' || state.processing.status === 'progress'

    switch (state.activeTab) {
      case 'upload':
        return (
          <FileUpload
            onFilesSelected={handleFilesSelected}
            isProcessing={isProcessing}
            className="h-full"
          />
        )
      
      case 'crawl':
        return (
          <URLInput
            onUrlSubmit={handleUrlSubmit}
            isProcessing={isProcessing}
            className="h-full"
          />
        )
      
      case 'chat':
        return (
          <ChatInterface
            onSendMessage={handleSendMessage}
            isLoading={isProcessing}
            hasDocuments={state.hasDocuments}
            className="h-full"
          />
        )
      
      default:
        return null
    }
  }

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Title Bar */}
      <div className="flex-shrink-0 h-12 bg-gradient-to-r from-white/80 to-white/60 backdrop-blur-xl border-b border-white/20">
        <div className="flex items-center justify-between h-full px-6">
          <div className="flex items-center space-x-3">
            <div className="w-6 h-6 bg-gradient-to-r from-macos-blue to-purple-500 rounded-full" />
            <h1 className="text-lg font-semibold text-macos-gray-900 font-sf-pro">
              AI 文档助手
            </h1>
          </div>
          
          <div className="flex items-center space-x-2">
            <button className="p-1.5 hover:bg-white/20 rounded-full transition-colors">
              <Cog6ToothIcon className="w-4 h-4 text-macos-gray-600" />
            </button>
            <button className="p-1.5 hover:bg-white/20 rounded-full transition-colors">
              <InformationCircleIcon className="w-4 h-4 text-macos-gray-600" />
            </button>
          </div>
        </div>
      </div>

      {/* Status Indicator */}
      {state.processing.status !== 'idle' && (
        <div className="flex-shrink-0 p-4">
          <StatusIndicator
            status={state.processing.status}
            message={state.processing.message}
            progress={state.processing.progress}
            details={state.processing.details}
            onDismiss={handleDismissStatus}
          />
        </div>
      )}

      <div className="flex-1 flex min-h-0">
        {/* Sidebar */}
        <div className="flex-shrink-0 w-64 macos-window border-r border-white/20 p-4">
          <nav className="space-y-2">
            {tabs.map((tab) => {
              const Icon = tab.icon
              const isActive = state.activeTab === tab.id
              const isDisabled = tab.disabled

              return (
                <button
                  key={tab.id}
                  onClick={() => !isDisabled && setState(prev => ({ ...prev, activeTab: tab.id }))}
                  disabled={isDisabled}
                  className={clsx(
                    'w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-left transition-all duration-200',
                    isActive
                      ? 'bg-macos-blue text-white macos-shadow'
                      : isDisabled
                      ? 'text-macos-gray-400 cursor-not-allowed'
                      : 'text-macos-gray-700 hover:bg-white/40 hover:scale-105',
                    'glass-button'
                  )}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  <div className="flex-1">
                    <div className="font-medium">{tab.name}</div>
                    <div className={clsx(
                      'text-xs',
                      isActive ? 'text-white/80' : 'text-macos-gray-500'
                    )}>
                      {tab.description}
                    </div>
                  </div>
                </button>
              )
            })}
          </nav>

          {/* Collection Info */}
          {state.hasDocuments && (
            <div className="mt-8 glass-morph rounded-xl p-3">
              <h3 className="text-xs font-medium text-macos-gray-500 uppercase tracking-wide mb-2">
                当前集合
              </h3>
              <div className="text-sm font-medium text-macos-gray-900">
                {state.currentCollection === 'website' ? '网站内容' : '文档文件'}
              </div>
              <div className="text-xs text-macos-gray-600 mt-1">
                点击"智能问答"开始提问
              </div>
            </div>
          )}
        </div>

        {/* Main Content */}
        <div className="flex-1 min-w-0">
          <div className="h-full p-6">
            {renderTabContent()}
          </div>
        </div>
      </div>
    </div>
  )
}

export default App