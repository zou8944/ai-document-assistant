/**
 * Knowledge base management page with import area and document list
 */

import React, { useState, useEffect, useRef } from 'react'
import {
  ArrowLeftIcon,
  DocumentIcon,
  GlobeAltIcon,
  ArrowDownTrayIcon,
  TrashIcon,
  EyeIcon,
  MapIcon,
  ListBulletIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import { Document as APIDocument, useAPIClient, extractData, SSEEvent } from '../../services/apiClient'
import { ImportStatus } from '../../types/app'
import { UrlInputDialog } from '../InputDialog'
import FileUploadModal from '../FileUploadModal'
import SitemapView from './SitemapView'
import PagePreview from './PagePreview'

interface KnowledgeBaseManagementProps {
  className?: string
}

// Map API document to UI document
const mapAPIDocumentToUIDocument = (doc: APIDocument) => ({
  id: doc.id,
  name: doc.name,
  url: doc.uri,
  createdAt: doc.created_at,
  size: doc.size_bytes ? formatFileSize(doc.size_bytes) : '-',
  status: doc.status
})

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

export const KnowledgeBaseManagement: React.FC<KnowledgeBaseManagementProps> = ({
  className
}) => {
  const { getCurrentKnowledgeBase, setActiveKnowledgeBase } = useAppStore()
  const apiClient = useAPIClient()
  const [documents, setDocuments] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showUrlDialog, setShowUrlDialog] = useState(false)
  const [showFileUpload, setShowFileUpload] = useState(false)

  // Import task progress tracking
  const [importStatus, setImportStatus] = useState<ImportStatus>({ isActive: false, progress: 0, message: ""})
  const [taskStatus, setTaskStatus] = useState<string>()
  const [taskLogs, setTaskLogs] = useState<string[]>([])
  const logTextAreaRef = useRef<HTMLTextAreaElement>(null)

  // Tab and sitemap state
  const [activeTab, setActiveTab] = useState<'documents' | 'sitemap'>('documents')
  const [sitemapJson, setSitemapJson] = useState<string | null>(null)
  const [loadingSitemap, setLoadingSitemap] = useState(false)

  // Page preview state
  const [previewOpen, setPreviewOpen] = useState(false)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [previewTitle, setPreviewTitle] = useState('')
  const [previewSourceUrl, setPreviewSourceUrl] = useState('')

  const handleBack = () => {
    setActiveKnowledgeBase(null)
  }

  const loadSitemap = async () => {
    if (!currentKb) return
    try {
      setLoadingSitemap(true)
      const response = await apiClient.getSitemap(currentKb.id)
      const data = extractData(response)
      setSitemapJson(data.sitemap_json)
    } catch (error) {
      console.error('加载站点结构失败:', error)
    } finally {
      setLoadingSitemap(false)
    }
  }

  const openPreview = (doc: any) => {
    if (!currentKb) return
    setPreviewUrl(apiClient.getDocumentPreviewUrl(currentKb.id, doc.id))
    setPreviewTitle(doc.name)
    setPreviewSourceUrl(doc.url || '')
    setPreviewOpen(true)
  }

  const openPreviewByPath = async (path: string) => {
    if (!currentKb) return
    const doc = documents.find(d => d.url && new URL(d.url).pathname === path)
    if (doc) {
      openPreview(doc)
    }
  }

  const currentKb = getCurrentKnowledgeBase()

  // Debug logging
  console.log('KnowledgeBaseManagement - currentKb:', currentKb)
  console.log('KnowledgeBaseManagement - activeKnowledgeBase:', useAppStore.getState().activeKnowledgeBase)
  console.log('KnowledgeBaseManagement - knowledgeBases:', useAppStore.getState().knowledgeBases)

  if (!currentKb) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-gray-500">
          <DocumentIcon className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p>找不到知识库</p>
          <div className="mt-4">
            <button
              onClick={handleBack}
              className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors"
            >
              返回列表
            </button>
          </div>
        </div>
      </div>
    )
  }

  const handleFileUpload = async () => {
    setShowFileUpload(true)
  }

  const handleUrlImport = async () => {
    setShowUrlDialog(true)
  }

  const handleUrlDialogConfirm = async (config: {
    urls: string[]
    excludeUrls: string[]
    maxDepth: number
    recursivePrefix: string
  }) => {
    setShowUrlDialog(false)
    
    if (!currentKb || config.urls.length === 0) return
    
    try {
      const response = await apiClient.ingestUrls(currentKb.id, {
        urls: config.urls,
        exclude_urls: config.excludeUrls,
        max_depth: config.maxDepth,
        recursive_prefix: config.recursivePrefix
      })
      const taskData = extractData(response)
      
      // Initialize new task: clear previous state and start processing
      setImportStatus({ isActive: true, progress: 0, message: "" })
      setTaskStatus('processing')
      setTaskLogs([])
      streamTaskProgress(taskData.task_id)

      console.log("import status", importStatus.isActive)
      
    } catch (error) {
      console.error('导入失败:', error)
      setImportStatus({ isActive: false, progress: 0, message: "" })
      alert('导入失败: ' + (error as Error).message)
    }
  }

  const handleUrlDialogCancel = () => {
    setShowUrlDialog(false)
  }

  const handleFileUploadModalClose = () => {
    setShowFileUpload(false)
  }

  const handleFilesSelected = async (filePaths: string[]) => {
    if (!currentKb || filePaths.length === 0) return
    
    setShowFileUpload(false)
    
    try {
      
      const response = await apiClient.ingestFiles(currentKb.id, {
        files: filePaths
      })
      
      const taskData = extractData(response)
      // Initialize new task: clear previous state and start processing
      setTaskStatus('processing')
      setTaskLogs([])
      setImportStatus({ isActive: true, progress: 0, message: "" })
      streamTaskProgress(taskData.task_id)
      
    } catch (error) {
      console.error('文件导入失败:', error)
      setImportStatus({ isActive: false, progress: 0, message: "" })
      alert('文件导入失败: ' + (error as Error).message)
    }
  }

  const handleDownload = async (doc: any) => {
    if (!currentKb) return
    
    try {
      // Download the document from API
      const { blob, filename } = await apiClient.downloadDocument(currentKb.id, doc.id)
      
      // Create a download link
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      
      // Append to body, click and remove
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      
      // Clean up the URL object
      window.URL.revokeObjectURL(url)
      
      console.log('文档下载成功:', filename)
    } catch (error) {
      console.error('下载失败:', error)
      alert('下载失败: ' + (error as Error).message)
    }
  }

  const handleDelete = async (doc: any) => {
    if (!currentKb) return
    
    if (confirm(`确定要删除 "${doc.name}" 吗？`)) {
      try {
        await apiClient.deleteDocument(currentKb.id, doc.id)
        // Refresh documents list
        loadDocuments()
        alert('文档删除成功')
      } catch (error) {
        console.error('删除失败:', error)
        alert('删除失败: ' + (error as Error).message)
      }
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  // Load documents from API
  const loadDocuments = async () => {
    if (!currentKb) return
    
    try {
      setLoading(true)
      const response = await apiClient.listDocuments(currentKb.id)
      const data = extractData(response)
      const mappedDocs = data.documents.map(mapAPIDocumentToUIDocument)
      setDocuments(mappedDocs)
    } catch (error) {
      console.error('加载文档列表失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // Stream task progress using SSE
  const streamTaskProgress = async (taskId: string) => {
    
    await apiClient.streamTaskProgress(
      taskId,
      (event: SSEEvent) => {
        console.log('Task SSE event:', event)
        
        switch (event.event) {
          case 'metadata':
            // metadata 暂时用不到
            break
            
          case 'progress':
            // Progress updates
            if (event.data) {
              const progressData = event.data

              let progress = progressData.percentage || 0
              let message = ""

              if (progressData.stats) {
                const stats = typeof progressData.stats === 'string' ? JSON.parse(progressData.stats) : progressData.stats

                if (stats.urls_crawled && stats.urls_crawl_total) {
                  message += "已爬取网页: " + stats.urls_crawled + "/" + stats.urls_crawl_total
                }
                if (stats.files_processed && stats.files_total) {
                  message += "已处理文件: " + stats.files_processed + "/" + stats.files_total
                }
              }

              setImportStatus((prev) => ({ ...prev, progress: progress, message: message }))
            }
            break
            
          case 'log':
            // Log messages - add to log display
            if (event.data) {
              const logData = event.data
              const timestamp = logData.timestamp ? new Date(logData.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString()
              const logMessage = `[${timestamp}] ${logData.message}`
              
              setTaskLogs(prev => [...prev, logMessage])
              
              // Auto scroll to bottom after adding log
              setTimeout(() => {
                if (logTextAreaRef.current) {
                  logTextAreaRef.current.scrollTop = logTextAreaRef.current.scrollHeight
                }
              }, 0)
            }
            break
            
          case 'done':
            // Task completed successfully
            setTaskStatus('completed')
            setImportStatus(prev => ({ ...prev, progress: 100 }))
            loadDocuments() // Refresh documents list
            loadSitemap() // Refresh sitemap
            break
            
          case 'error':
            // Task failed
            setTaskLogs(prev => [...prev, event.data?.message || '未知错误'])
            setTaskStatus('failed')
            setImportStatus(prev => ({ ...prev, progress: 100 }))
            break
            
          default:
            console.log('Unknown SSE event type:', event.event)
        }
      },
      (error: Error) => {
        console.error('Task streaming error:', error)
        setTaskLogs(prev => [...prev, error.message || '未知错误'])
        setImportStatus(prev => ({ ...prev, progress: 100 }))
      }
    )
  }


  // Load documents when component mounts or knowledge base changes
  useEffect(() => {
    if (currentKb) {
      loadDocuments()
      loadSitemap()
    }
  }, [currentKb])

  // Cleanup SSE connection on unmount
  useEffect(() => {
    return () => {
      console.log('Cleaning up SSE connection on unmount')
      apiClient.cancelRequests()
    }
  }, [])

  return (
    <div className={clsx('h-full flex flex-col overflow-hidden', className)}>
      {/* Header */}
      <div className="flex-shrink-0 p-6 bg-gradient-to-r from-white/90 to-white/70 backdrop-blur-sm border-b border-gray-200/50">
        <div className="flex items-center space-x-4">
          <button
            onClick={handleBack}
            className="p-2 hover:bg-gray-100/50 rounded-lg transition-colors"
          >
            <ArrowLeftIcon className="w-5 h-5 text-gray-600" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{currentKb.name}</h1>
            <p className="text-gray-600 mt-1">知识库管理</p>
          </div>
        </div>
      </div>

      {/* Content Area with Scroll */}
      <div className="flex-1 overflow-y-auto">
        <div className="space-y-6 p-6">
          {/* Import Area */}
          <div className="bg-white/80 backdrop-blur-sm rounded-xl border border-gray-200/50 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">导入文档</h2>
            
            {/* Import Options */}
            <div className="flex space-x-4 mb-6">
              <button
                onClick={handleUrlImport}
                disabled={importStatus.isActive}
                className="flex-1 flex flex-col items-center justify-center p-4 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <GlobeAltIcon className="w-8 h-8 text-gray-400 mb-2" />
                <span className="text-sm font-medium text-gray-700">🌐 网页URL</span>
                <span className="text-xs text-gray-500 mt-1">输入链接地址</span>
              </button>

              <button
                onClick={handleFileUpload}
                disabled={importStatus.isActive}
                className="flex-1 flex flex-col items-center justify-center p-4 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <DocumentIcon className="w-8 h-8 text-gray-400 mb-2" />
                <span className="text-sm font-medium text-gray-700">📁 本地文件</span>
                <span className="text-xs text-gray-500 mt-1">拖拽或点击</span>
              </button>
            </div>

            {/* Task Progress and Status */}
            {importStatus.isActive && (
              <div className="space-y-4 border-t border-gray-200/50 pt-4">
                {/* Status and Progress */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <span className="text-sm font-medium text-gray-700">任务状态:</span>
                    <div className="flex items-center space-x-2">
                      {taskStatus === 'processing' && (
                        <>
                          <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
                          <span className="text-sm text-blue-600 font-medium">处理中</span>
                        </>
                      )}
                      {taskStatus === 'completed' && (
                        <>
                          <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                          <span className="text-sm text-green-600 font-medium">已完成</span>
                        </>
                      )}
                      {taskStatus === 'failed' && (
                        <>
                          <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                          <span className="text-sm text-red-600 font-medium">失败</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center space-x-3">
                    <span className="text-sm text-gray-600">
                      {importStatus.progress}%
                    </span>
                    <button
                      onClick={() => {
                        setTaskStatus("")
                        setTaskLogs([])
                        setImportStatus({ isActive: false, progress: 0, message: "" })
                      }}
                      className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded border border-gray-300 hover:border-gray-400 transition-colors"
                    >
                      清除
                    </button>
                  </div>
                </div>
                
                {/* Progress Bar */}
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${importStatus.progress}%` }}
                  />
                </div>
                
                {/* Task Logs */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700">任务日志:</label>
                  <textarea
                    ref={logTextAreaRef}
                    className="w-full h-20 p-3 text-xs font-mono bg-gray-50 border border-gray-200 rounded-md resize-none overflow-y-auto focus:outline-none focus:ring-1 focus:ring-blue-500"
                    value={taskLogs.join('\n')}
                    readOnly
                    placeholder="任务日志将在此处显示..."
                  />
                </div>
              </div>
            )}

            {!importStatus.isActive && !taskStatus && taskLogs.length === 0 && (
              <div className="flex justify-end">
                <button
                  onClick={loadDocuments}
                  disabled={importStatus.isActive}
                  className="bg-gray-500 hover:bg-gray-600 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg transition-colors disabled:cursor-not-allowed"
                >
                  刷新列表
                </button>
              </div>
            )}
          </div>

          {/* Tab Switcher */}
          <div className="flex space-x-1 bg-white/60 backdrop-blur-sm rounded-lg p-1 border border-gray-200/50">
            <button
              onClick={() => setActiveTab('documents')}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
                activeTab === 'documents'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-white/50'
              )}
            >
              <ListBulletIcon className="w-4 h-4" />
              文档列表
            </button>
            <button
              onClick={() => setActiveTab('sitemap')}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors',
                activeTab === 'sitemap'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-white/50'
              )}
            >
              <MapIcon className="w-4 h-4" />
              站点结构
            </button>
          </div>

          {/* Sitemap Tab */}
          {activeTab === 'sitemap' && (
            <div className="bg-white/80 backdrop-blur-sm rounded-xl border border-gray-200/50">
              <div className="p-6 border-b border-gray-200/50 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">站点结构</h2>
                <button
                  onClick={loadSitemap}
                  disabled={loadingSitemap}
                  className="bg-gray-500 hover:bg-gray-600 disabled:bg-gray-300 text-white px-3 py-1.5 rounded-lg text-sm transition-colors disabled:cursor-not-allowed"
                >
                  {loadingSitemap ? '加载中...' : '刷新'}
                </button>
              </div>
              <div className="p-4 max-h-[600px] overflow-y-auto">
                {loadingSitemap ? (
                  <div className="flex items-center justify-center py-16">
                    <div className="text-gray-500">加载中...</div>
                  </div>
                ) : (
                  <SitemapView
                    sitemapJson={sitemapJson}
                    onPageClick={openPreviewByPath}
                  />
                )}
              </div>
            </div>
          )}

          {/* Document List Tab */}
          {activeTab === 'documents' && (
          <div className="bg-white/80 backdrop-blur-sm rounded-xl border border-gray-200/50">
            <div className="p-6 border-b border-gray-200/50">
              <h2 className="text-lg font-semibold text-gray-900">文档列表</h2>
            </div>
            
            <div className="min-h-[300px]">
              {documents.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-gray-500">
                  <DocumentIcon className="w-12 h-12 mb-2 opacity-50" />
                  <p>暂无文档</p>
                  <p className="text-sm">请使用上方导入区域添加文档</p>
                </div>
              ) : loading ? (
                <div className="flex items-center justify-center py-16">
                  <div className="text-gray-500">加载中...</div>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50/50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          文档名称
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          来源
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          状态
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          创建时间
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          大小
                        </th>
                        <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                          操作
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200/50">
                      {documents.map((doc) => (
                        <tr key={doc.id} className="hover:bg-gray-50/30 transition-colors">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center">
                              {doc.type === 'website' ? (
                                <GlobeAltIcon className="w-4 h-4 text-blue-500 mr-2 flex-shrink-0" />
                              ) : (
                                <DocumentIcon className="w-4 h-4 text-gray-400 mr-2 flex-shrink-0" />
                              )}
                              <span className="text-sm font-medium text-gray-900 truncate">
                                {doc.name}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            <div className="max-w-xs">
                              <a
                                href={doc.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-500 hover:text-blue-600 underline truncate block"
                                title={doc.name}
                              >
                                {doc.url}
                              </a>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={clsx(
                              'inline-flex px-2 py-1 text-xs font-semibold rounded-full',
                              {
                                'bg-green-100 text-green-800': doc.status === 'indexed',
                                'bg-yellow-100 text-yellow-800': doc.status === 'processing' || doc.status === 'pending',
                                'bg-red-100 text-red-800': doc.status === 'failed'
                              }
                            )}>
                              {({
                                indexed: '已索引',
                                processing: '处理中',
                                pending: '等待中',
                                failed: '失败'
                              } as Record<'indexed' | 'processing' | 'pending' | 'failed', string>)[doc.status as 'indexed' | 'processing' | 'pending' | 'failed'] || doc.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {formatDate(doc.createdAt)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {doc.size}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            <div className="flex items-center justify-end space-x-2">
                              {doc.url && doc.status === 'indexed' && (
                                <button
                                  onClick={() => openPreview(doc)}
                                  className="p-1 hover:bg-gray-100 rounded transition-colors"
                                  title="预览"
                                >
                                  <EyeIcon className="w-4 h-4 text-gray-400 hover:text-green-500" />
                                </button>
                              )}
                              <button
                                onClick={() => handleDownload(doc)}
                                className="p-1 hover:bg-gray-100 rounded transition-colors"
                                title="下载"
                              >
                                <ArrowDownTrayIcon className="w-4 h-4 text-gray-400 hover:text-blue-500" />
                              </button>
                              <button
                                onClick={() => handleDelete(doc)}
                                className="p-1 hover:bg-gray-100 rounded transition-colors"
                                title="删除"
                              >
                                <TrashIcon className="w-4 h-4 text-gray-400 hover:text-red-500" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
          )}
        </div>
      </div>
      
      {/* URL Input Dialog */}
      <UrlInputDialog
        isOpen={showUrlDialog}
        onConfirm={handleUrlDialogConfirm}
        onCancel={handleUrlDialogCancel}
      />

      {/* File Upload Modal */}
      <FileUploadModal
        isOpen={showFileUpload}
        onFilesSelected={handleFilesSelected}
        onClose={handleFileUploadModalClose}
        isProcessing={importStatus.isActive}
      />

      {/* Page Preview Modal */}
      <PagePreview
        isOpen={previewOpen}
        onClose={() => setPreviewOpen(false)}
        previewUrl={previewUrl}
        pageTitle={previewTitle}
        sourceUrl={previewSourceUrl}
      />
    </div>
  )
}

export default KnowledgeBaseManagement