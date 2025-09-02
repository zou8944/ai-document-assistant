/**
 * Knowledge base management page with import area and document list
 */

import React, { useState, useEffect } from 'react'
import {
  ArrowLeftIcon,
  DocumentIcon,
  GlobeAltIcon,
  FolderIcon,
  ArrowDownTrayIcon,
  TrashIcon
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import { Document as APIDocument, Task, useAPIClient, extractData } from '../../services/apiClient'
import { ImportProgress } from '../../types/app'

interface KnowledgeBaseManagementProps {
  className?: string
}

// Map API document to UI document
const mapAPIDocumentToUIDocument = (doc: APIDocument) => ({
  id: doc.id,
  name: doc.name,
  source: doc.url ? doc.url : '本地文件',
  url: doc.url,
  createdAt: doc.created_at,
  size: doc.file_size ? formatFileSize(doc.file_size) : '-',
  type: doc.url ? 'website' as const : 'file' as const,
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
  const [importProgress, setImportProgress] = useState<ImportProgress>({
    isActive: false,
    progress: 0,
    total: 0,
    message: ''
  })
  const [documents, setDocuments] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [currentTask, setCurrentTask] = useState<Task | null>(null)

  const handleBack = () => {
    setActiveKnowledgeBase(null)
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
    if (!currentKb) return
    
    try {
      // In a real implementation, you would show a file picker dialog
      // For now, we'll simulate with a prompt
      const filePath = prompt('请输入文件路径:')
      if (!filePath) return
      
      setImportProgress({
        isActive: true,
        currentFile: filePath,
        progress: 0,
        total: 100,
        message: '正在创建处理任务...'
      })
      
      // Start ingestion task
      const response = await apiClient.ingestFiles(currentKb.id, {
        files: [filePath]
      })
      
      const taskData = extractData(response)
      const task = await apiClient.getTask(taskData.task_id)
      setCurrentTask(extractData(task))
      
      // Poll task status
      pollTaskStatus(taskData.task_id)
      
    } catch (error) {
      console.error('文件导入失败:', error)
      setImportProgress({
        isActive: false,
        progress: 0,
        total: 0,
        message: ''
      })
      alert('文件导入失败: ' + (error as Error).message)
    }
  }

  const handleUrlImport = async () => {
    if (!currentKb) return
    
    try {
      const url = prompt('请输入要导入的网页URL:')
      if (!url) return
      
      setImportProgress({
        isActive: true,
        currentFile: url,
        progress: 0,
        total: 100,
        message: '正在创建爬取任务...'
      })
      
      // Start URL ingestion task
      const response = await apiClient.ingestUrls(currentKb.id, {
        urls: [url],
        max_depth: 1
      })
      
      const taskData = extractData(response)
      const task = await apiClient.getTask(taskData.task_id)
      setCurrentTask(extractData(task))
      
      // Poll task status
      pollTaskStatus(taskData.task_id)
      
    } catch (error) {
      console.error('URL导入失败:', error)
      setImportProgress({
        isActive: false,
        progress: 0,
        total: 0,
        message: ''
      })
      alert('URL导入失败: ' + (error as Error).message)
    }
  }

  const handleFolderUpload = async () => {
    if (!currentKb) return
    
    try {
      // In a real implementation, you would show a folder picker dialog
      const folderPath = prompt('请输入文件夹路径:')
      if (!folderPath) return
      
      setImportProgress({
        isActive: true,
        currentFile: folderPath,
        progress: 0,
        total: 100,
        message: '正在扫描文件夹...'
      })
      
      // For folder upload, we would need to scan the folder first
      // This is a simplified implementation
      const response = await apiClient.ingestFiles(currentKb.id, {
        files: [folderPath] // In reality, this would be a list of files
      })
      
      const taskData = extractData(response)
      const task = await apiClient.getTask(taskData.task_id)
      setCurrentTask(extractData(task))
      
      pollTaskStatus(taskData.task_id)
      
    } catch (error) {
      console.error('文件夹导入失败:', error)
      setImportProgress({
        isActive: false,
        progress: 0,
        total: 0,
        message: ''
      })
      alert('文件夹导入失败: ' + (error as Error).message)
    }
  }

  const handleDownload = async (doc: any) => {
    if (!currentKb || doc.type === 'website') return
    
    try {
      // For local files, we could implement download functionality
      // This would need to be implemented in the backend
      console.log('下载文档:', doc.name)
      alert('下载功能暂未实现')
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

  // Poll task status
  const pollTaskStatus = async (taskId: string) => {
    try {
      const response = await apiClient.getTask(taskId)
      const task = extractData(response)
      
      setImportProgress({
        isActive: task.status === 'running' || task.status === 'pending',
        progress: task.progress || 0,
        total: 100,
        message: getTaskStatusMessage(task)
      })
      
      if (task.status === 'completed') {
        setCurrentTask(null)
        loadDocuments() // Refresh documents list
        setTimeout(() => {
          setImportProgress({
            isActive: false,
            progress: 0,
            total: 0,
            message: ''
          })
        }, 1000)
      } else if (task.status === 'failed') {
        setCurrentTask(null)
        alert('任务执行失败: ' + (task.error_message || '未知错误'))
        setImportProgress({
          isActive: false,
          progress: 0,
          total: 0,
          message: ''
        })
      } else if (task.status === 'running' || task.status === 'pending') {
        // Continue polling
        setTimeout(() => pollTaskStatus(taskId), 2000)
      }
    } catch (error) {
      console.error('获取任务状态失败:', error)
      setImportProgress({
        isActive: false,
        progress: 0,
        total: 0,
        message: ''
      })
    }
  }

  const getTaskStatusMessage = (task: Task): string => {
    switch (task.status) {
      case 'pending':
        return '任务等待中...'
      case 'running':
        return task.task_type === 'ingest_files' ? '正在处理文件...' : '正在抓取网页...'
      case 'completed':
        return '处理完成！'
      case 'failed':
        return '处理失败'
      default:
        return '处理中...'
    }
  }

  // Load documents when component mounts or knowledge base changes
  useEffect(() => {
    if (currentKb) {
      loadDocuments()
    }
  }, [currentKb])

  return (
    <div className={clsx('h-full flex flex-col', className)}>
      {/* Header */}
      <div className="flex-shrink-0 p-6 bg-gradient-to-r from-white/90 to-white/70 backdrop-blur-sm border-b border-gray-200/50">
        <div className="flex items-center space-x-4 mb-4">
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

      {/* Import Area - Top 1/3 */}
      <div className="flex-shrink-0 h-1/3 p-6 border-b border-gray-200/50">
        <div className="h-full bg-white/80 backdrop-blur-sm rounded-xl border border-gray-200/50 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">文档导入区域</h2>
          
          {/* Import Options */}
          <div className="flex space-x-4 mb-6">
            <button
              onClick={handleFileUpload}
              disabled={importProgress.isActive}
              className="flex-1 flex flex-col items-center justify-center p-4 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <DocumentIcon className="w-8 h-8 text-gray-400 mb-2" />
              <span className="text-sm font-medium text-gray-700">📁 本地文件</span>
              <span className="text-xs text-gray-500 mt-1">拖拽或点击</span>
            </button>

            <button
              onClick={handleUrlImport}
              disabled={importProgress.isActive}
              className="flex-1 flex flex-col items-center justify-center p-4 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <GlobeAltIcon className="w-8 h-8 text-gray-400 mb-2" />
              <span className="text-sm font-medium text-gray-700">🌐 网页URL</span>
              <span className="text-xs text-gray-500 mt-1">输入链接地址</span>
            </button>

            <button
              onClick={handleFolderUpload}
              disabled={importProgress.isActive}
              className="flex-1 flex flex-col items-center justify-center p-4 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <FolderIcon className="w-8 h-8 text-gray-400 mb-2" />
              <span className="text-sm font-medium text-gray-700">📂 文件夹</span>
              <span className="text-xs text-gray-500 mt-1">选择整个目录</span>
            </button>
          </div>

          {/* Progress Bar */}
          {importProgress.isActive && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">
                  进度: {importProgress.progress}% 
                  {importProgress.currentFile && ` 正在处理: ${importProgress.currentFile}`}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${importProgress.progress}%` }}
                />
              </div>
              {importProgress.message && (
                <p className="text-sm text-gray-500">{importProgress.message}</p>
              )}
            </div>
          )}

          {!importProgress.isActive && (
            <div className="flex justify-end">
              <button
                onClick={loadDocuments}
                disabled={importProgress.isActive}
                className="bg-gray-500 hover:bg-gray-600 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg transition-colors mr-2 disabled:cursor-not-allowed"
              >
                刷新列表
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Document List - Bottom 2/3 */}
      <div className="flex-1 p-6 overflow-hidden">
        <div className="h-full bg-white/80 backdrop-blur-sm rounded-xl border border-gray-200/50 overflow-hidden">
          <div className="p-6 border-b border-gray-200/50">
            <h2 className="text-lg font-semibold text-gray-900">文档列表</h2>
          </div>
          
          <div className="flex-1 overflow-y-auto">
            {documents.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-gray-500">
                <DocumentIcon className="w-12 h-12 mb-2 opacity-50" />
                <p>暂无文档</p>
                <p className="text-sm">请使用上方导入区域添加文档</p>
              </div>
            ) : loading ? (
              <div className="flex items-center justify-center h-32">
                <div className="text-gray-500">加载中...</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50/50 sticky top-0">
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
                              <GlobeAltIcon className="w-4 h-4 text-blue-500 mr-2" />
                            ) : (
                              <DocumentIcon className="w-4 h-4 text-gray-400 mr-2" />
                            )}
                            <span className="text-sm font-medium text-gray-900">
                              {doc.name}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {doc.url ? (
                            <a
                              href={doc.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-500 hover:text-blue-600 underline"
                            >
                              {doc.source}
                            </a>
                          ) : (
                            doc.source
                          )}
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
                            {doc.type === 'file' && (
                              <button
                                onClick={() => handleDownload(doc)}
                                className="p-1 hover:bg-gray-100 rounded transition-colors"
                                title="下载"
                              >
                                <ArrowDownTrayIcon className="w-4 h-4 text-gray-400 hover:text-blue-500" />
                              </button>
                            )}
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
      </div>
    </div>
  )
}

export default KnowledgeBaseManagement