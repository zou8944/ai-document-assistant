/**
 * Knowledge base management page - three-column layout
 * Left: category sidebar | Right: README / DocList / DocReader | Top: search + import
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  ArrowLeftIcon,
  DocumentIcon,
  GlobeAltIcon,
  ArrowDownTrayIcon,
  TrashIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  MagnifyingGlassIcon,
  PlayIcon,
  StopIcon,
  ClipboardDocumentListIcon,
  XMarkIcon,
  ClockIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import { Document as APIDocument, Task as APITask, TaskLog as APITaskLog, useAPIClient, extractData, SSEEvent } from '../../services/apiClient'
import { ImportStatus } from '../../types/app'
import { UrlInputDialog } from '../InputDialog'
import FileUploadModal from '../FileUploadModal'
import SidebarNav from './SidebarNav'
import ReadmePanel from './ReadmePanel'
import DocReader from './DocReader'
import {
  parseCategories,
  findCategoryForPath,
  getPagesForCategory,
} from '../../utils/categoryParser'

interface KnowledgeBaseManagementProps {
  className?: string
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const mapAPIDocument = (doc: APIDocument) => ({
  id: doc.id,
  name: doc.name,
  nameTranslated: doc.name_translated,
  url: doc.uri,
  source_path: doc.source_path,
  createdAt: doc.created_at,
  size: doc.size_bytes ? formatFileSize(doc.size_bytes) : '-',
  status: doc.status,
})

type MappedDoc = ReturnType<typeof mapAPIDocument>

export const KnowledgeBaseManagement: React.FC<KnowledgeBaseManagementProps> = ({
  className,
}) => {
  const { getCurrentKnowledgeBase, setActiveKnowledgeBase, displayLanguage, setDisplayLanguage } = useAppStore()
  const apiClient = useAPIClient()
  const currentKb = getCurrentKnowledgeBase()

  // Data state
  const [documents, setDocuments] = useState<MappedDoc[]>([])
  const [loadingDocuments, setLoadingDocuments] = useState(true)
  const [readmeContent, setReadmeContent] = useState<string | null>(null)
  const [categoriesJson, setCategoriesJson] = useState<string | null>(null)
  const [readmeContentZh, setReadmeContentZh] = useState<string | null>(null)
  const [categoriesJsonZh, setCategoriesJsonZh] = useState<string | null>(null)
  const [sourceLanguage, setSourceLanguage] = useState<string | null>(null)

  // Navigation state
  const [activeTab, setActiveTab] = useState<'overview' | 'all' | string>('overview')
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<MappedDoc[] | null>(null)
  const [searching, setSearching] = useState(false)

  // Import state
  const [importCollapsed, setImportCollapsed] = useState(true)
  const [showUrlDialog, setShowUrlDialog] = useState(false)
  const [showFileUpload, setShowFileUpload] = useState(false)
  const [importStatus, setImportStatus] = useState<ImportStatus>({ isActive: false, progress: 0, message: '' })
  const [taskStatus, setTaskStatus] = useState<string>()
  const [taskLogs, setTaskLogs] = useState<string[]>([])
  const logTextAreaRef = useRef<HTMLTextAreaElement>(null)

  // Task management state
  const [tasks, setTasks] = useState<APITask[]>([])
  const [showTaskPanel, setShowTaskPanel] = useState(false)
  const [taskLogsModal, setTaskLogsModal] = useState<APITaskLog[]>([])
  const [showLogModal, setShowLogModal] = useState(false)
  const [logModalTaskId, setLogModalTaskId] = useState<string | null>(null)
  const [logModalStreaming, setLogModalStreaming] = useState(false)
  const logModalRef = useRef<HTMLDivElement>(null)

  // Whether this collection supports bilingual display
  const isBilingual = sourceLanguage === 'en' && !!categoriesJsonZh

  // Parse categories (English for internal logic)
  const categories = useMemo(() => parseCategories(categoriesJson), [categoriesJson])

  // Parse Chinese categories for display
  const categoriesZh = useMemo(() => parseCategories(categoriesJsonZh), [categoriesJsonZh])

  // Build category name mapping: en -> zh
  const categoryNameMap = useMemo(() => {
    const map = new Map<string, string>()
    if (!isBilingual) return map
    for (const enCat of categories) {
      const zhCat = categoriesZh.find(c => c.pages.length > 0 && enCat.pages.some(ep => c.pages.some(zp => zp.path === ep.path)))
      if (zhCat) {
        map.set(enCat.category, zhCat.category)
      }
    }
    return map
  }, [categories, categoriesZh, isBilingual])

  // README doc count
  const readmeDocCount = useMemo(() => {
    return categories.reduce((sum, cat) => sum + cat.pages.length, 0)
  }, [categories])

  // Determine which docs to show in list
  const displayedDocs = useMemo(() => {
    if (searchResults !== null) return searchResults
    if (activeTab === 'all') return documents
    if (activeTab !== 'overview') {
      const catPages = getPagesForCategory(categories, activeTab)
      const paths = new Set(catPages.map(p => p.path))
      return documents.filter(d => d.source_path && paths.has(d.source_path))
    }
    return []
  }, [searchResults, activeTab, categories, documents])

  // Find selected document
  const selectedDoc = useMemo(
    () => (selectedDocId ? documents.find(d => d.id === selectedDocId) || null : null),
    [selectedDocId, documents]
  )

  // Find which category the selected doc belongs to (for sidebar highlight)
  const highlightedCategory = useMemo(() => {
    if (!selectedDoc?.source_path) return null
    return findCategoryForPath(categories, selectedDoc.source_path)
  }, [selectedDoc, categories])

  // Preview URL for selected doc
  const previewUrl = useMemo(() => {
    if (!selectedDoc || !currentKb) return ''
    return apiClient.getDocumentPreviewUrl(currentKb.id, selectedDoc.id)
  }, [selectedDoc, currentKb, apiClient])

  // Load data
  const loadDocuments = useCallback(async () => {
    if (!currentKb) return
    try {
      setLoadingDocuments(true)
      const allDocs: APIDocument[] = []
      let page = 1
      let total = 0
      do {
        const response = await apiClient.listDocuments(currentKb.id, page, 200)
        const data = extractData(response)
        allDocs.push(...data.documents)
        total = data.total
        page += 1
      } while (allDocs.length < total)
      setDocuments(allDocs.map(mapAPIDocument))
    } catch (error) {
      console.error('加载文档列表失败:', error)
    } finally {
      setLoadingDocuments(false)
    }
  }, [currentKb?.id])

  const loadReadme = useCallback(async () => {
    if (!currentKb) return
    try {
      const response = await apiClient.getReadme(currentKb.id)
      const data = extractData(response)
      setReadmeContent(data.readme_content)
      setCategoriesJson(data.categories_json)
      setReadmeContentZh(data.readme_content_zh)
      setCategoriesJsonZh(data.categories_json_zh)
      setSourceLanguage(data.source_language)
    } catch {
      // No readme available - fallback
      setReadmeContent(null)
      setCategoriesJson(null)
      setReadmeContentZh(null)
      setCategoriesJsonZh(null)
      setSourceLanguage(null)
    }
  }, [currentKb?.id])

  // Search handler
  const handleSearch = useCallback(async (query: string) => {
    if (!currentKb) return
    if (!query.trim()) {
      setSearchResults(null)
      setActiveTab('overview')
      return
    }
    try {
      setSearching(true)
      const response = await apiClient.listDocuments(currentKb.id, 1, 50, query)
      const data = extractData(response)
      setSearchResults(data.documents.map(mapAPIDocument))
    } catch (error) {
      console.error('搜索失败:', error)
    } finally {
      setSearching(false)
    }
  }, [currentKb?.id])

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      handleSearch(searchQuery)
    }, 400)
    return () => clearTimeout(timer)
  }, [searchQuery, handleSearch])

  // Doc click from README - find by path
  const handleReadmeDocClick = useCallback(
    (path: string) => {
      const doc = documents.find(d => d.source_path === path)
      if (doc) {
        setSelectedDocId(doc.id)
      }
    },
    [documents]
  )

  // Doc click from list
  const handleDocClick = useCallback((doc: MappedDoc) => {
    setSelectedDocId(doc.id)
  }, [])

  // Back from reader
  const handleBackFromReader = useCallback(() => {
    setSelectedDocId(null)
  }, [])

  // Tab select from sidebar
  const handleTabSelect = useCallback((tab: 'overview' | 'all' | string) => {
    setActiveTab(tab)
    setSelectedDocId(null)
    setSearchQuery('')
    setSearchResults(null)
  }, [])

  // Import handlers
  const handleUrlDialogConfirm = async (config: {
    urls: string[]
    recursivePrefix: string
  }) => {
    setShowUrlDialog(false)
    if (!currentKb || config.urls.length === 0) return
    try {
      const response = await apiClient.ingestUrls(currentKb.id, {
        urls: config.urls,
        recursive_prefix: config.recursivePrefix,
      })
      const taskData = extractData(response)
      setImportStatus({ isActive: true, progress: 0, message: '' })
      setTaskStatus('processing')
      setTaskLogs([])
      streamTaskProgress(taskData.task_id)
    } catch (error) {
      console.error('导入失败:', error)
      setImportStatus({ isActive: false, progress: 0, message: '' })
      alert('导入失败: ' + (error as Error).message)
    }
  }

  const handleFilesSelected = async (filePaths: string[]) => {
    if (!currentKb || filePaths.length === 0) return
    setShowFileUpload(false)
    try {
      const response = await apiClient.ingestFiles(currentKb.id, { files: filePaths })
      const taskData = extractData(response)
      setTaskStatus('processing')
      setTaskLogs([])
      setImportStatus({ isActive: true, progress: 0, message: '' })
      streamTaskProgress(taskData.task_id)
    } catch (error) {
      console.error('文件导入失败:', error)
      setImportStatus({ isActive: false, progress: 0, message: '' })
      alert('文件导入失败: ' + (error as Error).message)
    }
  }

  const handleDownload = async (doc: MappedDoc) => {
    if (!currentKb) return
    try {
      const { blob, filename } = await apiClient.downloadDocument(currentKb.id, doc.id)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (error) {
      console.error('下载失败:', error)
      alert('下载失败: ' + (error as Error).message)
    }
  }

  const handleDelete = async (doc: MappedDoc) => {
    if (!currentKb) return
    if (confirm(`确定要删除 "${doc.name}" 吗？`)) {
      try {
        await apiClient.deleteDocument(currentKb.id, doc.id)
        if (selectedDocId === doc.id) setSelectedDocId(null)
        loadDocuments()
      } catch (error) {
        console.error('删除失败:', error)
        alert('删除失败: ' + (error as Error).message)
      }
    }
  }

  // Task management
  const loadTasks = useCallback(async () => {
    if (!currentKb) return
    try {
      const response = await apiClient.listTasksByCollection(currentKb.id)
      const data = extractData(response)
      setTasks(data.tasks)
    } catch (error) {
      console.error('加载任务列表失败:', error)
    }
  }, [currentKb?.id])

  const handleStopTask = async (taskId: string) => {
    try {
      await apiClient.stopTask(taskId)
      loadTasks()
    } catch (error) {
      console.error('停止任务失败:', error)
      alert('停止任务失败: ' + (error as Error).message)
    }
  }

  const handleRestartTask = async (taskId: string) => {
    try {
      await apiClient.restartTask(taskId)
      loadTasks()
    } catch (error) {
      console.error('重跑任务失败:', error)
      alert('重跑任务失败: ' + (error as Error).message)
    }
  }

  const handleCleanupTask = async (taskId: string) => {
    if (!confirm('确定要清理该任务吗？这会删除该任务产生的所有文档和日志。')) return
    try {
      await apiClient.cleanupTask(taskId)
      loadTasks()
      loadDocuments()
      loadReadme()
    } catch (error) {
      console.error('清理任务失败:', error)
      alert('清理任务失败: ' + (error as Error).message)
    }
  }

  const handleViewLogs = async (taskId: string) => {
    setLogModalTaskId(taskId)
    setShowLogModal(true)
    setTaskLogsModal([])

    const task = tasks.find(t => t.task_id === taskId)
    if (task?.status === 'processing') {
      setLogModalStreaming(true)
      await apiClient.streamTaskProgress(
        taskId,
        (event: SSEEvent) => {
          if (event.event === 'log' && event.data) {
            const logData = event.data
            const timestamp = logData.timestamp
              ? new Date(logData.timestamp).toLocaleTimeString()
              : new Date().toLocaleTimeString()
            setTaskLogsModal(prev => [...prev, {
              id: Date.now(),
              task_id: taskId,
              level: logData.level || 'info',
              message: `[${timestamp}] ${logData.message}`,
              details: logData.details || {},
              timestamp: logData.timestamp || new Date().toISOString(),
            }])
            setTimeout(() => {
              if (logModalRef.current) {
                logModalRef.current.scrollTop = logModalRef.current.scrollHeight
              }
            }, 0)
          } else if (event.event === 'done' || event.event === 'error') {
            setLogModalStreaming(false)
            loadTasks()
          }
        },
        (error: Error) => {
          console.error('日志流错误:', error)
          setLogModalStreaming(false)
        }
      )
    } else {
      setLogModalStreaming(false)
      try {
        const response = await apiClient.getTaskLogs(taskId, 200)
        const data = extractData(response)
        setTaskLogsModal(data.logs.map((log: APITaskLog) => ({
          ...log,
          message: `[${new Date(log.timestamp).toLocaleTimeString()}] ${log.message}`,
        })))
      } catch (error) {
        console.error('获取日志失败:', error)
      }
    }
  }

  // SSE task streaming
  const streamTaskProgress = async (taskId: string) => {
    await apiClient.streamTaskProgress(
      taskId,
      (event: SSEEvent) => {
        switch (event.event) {
          case 'progress':
            if (event.data) {
              const progressData = event.data
              let progress = progressData.percentage || 0
              let message = ''
              if (progressData.stats) {
                const stats = typeof progressData.stats === 'string' ? JSON.parse(progressData.stats) : progressData.stats
                if (stats.urls_crawled && stats.urls_crawl_total) {
                  message += '已爬取网页: ' + stats.urls_crawled + '/' + stats.urls_crawl_total
                }
                if (stats.files_processed && stats.files_total) {
                  message += '已处理文件: ' + stats.files_processed + '/' + stats.files_total
                }
              }
              setImportStatus(prev => ({ ...prev, progress, message }))
            }
            break
          case 'log':
            if (event.data) {
              const logData = event.data
              const timestamp = logData.timestamp ? new Date(logData.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString()
              setTaskLogs(prev => [...prev, `[${timestamp}] ${logData.message}`])
              setTimeout(() => {
                if (logTextAreaRef.current) logTextAreaRef.current.scrollTop = logTextAreaRef.current.scrollHeight
              }, 0)
            }
            break
          case 'done':
            setTaskStatus('completed')
            setImportStatus(prev => ({ ...prev, progress: 100 }))
            loadDocuments()
            loadReadme()
            break
          case 'error':
            setTaskLogs(prev => [...prev, event.data?.message || '未知错误'])
            setTaskStatus('failed')
            setImportStatus(prev => ({ ...prev, progress: 100 }))
            break
        }
      },
      (error: Error) => {
        console.error('Task streaming error:', error)
        setTaskLogs(prev => [...prev, error.message || '未知错误'])
        setImportStatus(prev => ({ ...prev, progress: 100 }))
      }
    )
  }

  // Load on mount
  useEffect(() => {
    if (!currentKb) return
    const loadData = async () => {
      await loadDocuments()
      await loadReadme()
    }
    loadData()
  }, [currentKb?.id])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      apiClient.cancelRequests()
    }
  }, [])

  // Determine right panel view
  const showReader = selectedDoc !== null
  const showDocList = !showReader && (activeTab !== 'overview' || searchQuery.trim() !== '')
  const showReadme = !showReader && !showDocList && activeTab === 'overview' && readmeContent !== null
  const showFallbackList = !showReader && !showDocList && !showReadme

  if (!currentKb) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-gray-500">
          <DocumentIcon className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p>找不到知识库</p>
          <div className="mt-4">
            <button
              onClick={() => setActiveKnowledgeBase(null)}
              className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors"
            >
              返回列表
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={clsx('h-full flex flex-col overflow-hidden', className)}>
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 bg-gradient-to-r from-white/90 to-white/70 backdrop-blur-sm border-b border-gray-200/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setActiveKnowledgeBase(null)}
              className="p-2 hover:bg-gray-100/50 rounded-lg transition-colors"
            >
              <ArrowLeftIcon className="w-5 h-5 text-gray-600" />
            </button>
            <div>
              <h1 className="text-xl font-bold text-gray-900">{currentKb.name}</h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setShowTaskPanel(!showTaskPanel); if (!showTaskPanel) loadTasks() }}
              className={clsx(
                "flex items-center gap-1 text-sm px-3 py-1.5 rounded-lg transition-colors",
                showTaskPanel
                  ? "text-purple-700 bg-purple-50"
                  : "text-purple-600 hover:text-purple-700 hover:bg-purple-50"
              )}
            >
              <ClipboardDocumentListIcon className="w-4 h-4" />
              任务管理
              {tasks.filter(t => t.status === 'processing').length > 0 && (
                <span className="ml-1 w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              )}
            </button>
            <button
              onClick={() => setImportCollapsed(!importCollapsed)}
              className="flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors"
            >
              {importCollapsed ? <ChevronRightIcon className="w-4 h-4" /> : <ChevronDownIcon className="w-4 h-4" />}
              导入文档
            </button>
          </div>
        </div>

        {/* Task Panel */}
        {showTaskPanel && (
          <div className="mt-4 pt-4 border-t border-gray-200/50">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-700">任务列表</h3>
              <button
                onClick={loadTasks}
                className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded border border-gray-300"
              >
                刷新
              </button>
            </div>
            {tasks.length === 0 ? (
              <p className="text-sm text-gray-400 py-4 text-center">暂无任务</p>
            ) : (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {tasks.map(task => (
                  <div key={task.task_id} className="flex items-center justify-between p-2 bg-white/60 rounded-lg border border-gray-200/50">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className={clsx(
                        "w-2 h-2 rounded-full flex-shrink-0",
                        task.status === 'processing' && "bg-blue-500 animate-pulse",
                        task.status === 'success' && "bg-green-500",
                        task.status === 'failed' && "bg-red-500",
                        task.status === 'stopped' && "bg-yellow-500",
                        task.status === 'pending' && "bg-gray-400",
                      )} />
                      <div className="min-w-0">
                        <p className="text-sm text-gray-800 truncate">
                          {task.task_type === 'ingest_urls' ? '网页抓取' : '文件上传'}
                        </p>
                        <p className="text-xs text-gray-400">
                          {new Date(task.created_at).toLocaleString()}
                          {task.progress !== undefined && task.status === 'processing' && ` · ${task.progress}%`}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {task.status === 'processing' && (
                        <button
                          onClick={() => handleStopTask(task.task_id)}
                          className="p-1.5 text-red-600 hover:bg-red-50 rounded-md transition-colors"
                          title="停止"
                        >
                          <StopIcon className="w-4 h-4" />
                        </button>
                      )}
                      {(task.status === 'success' || task.status === 'failed' || task.status === 'stopped') && (
                        <>
                          <button
                            onClick={() => handleRestartTask(task.task_id)}
                            className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                            title="重跑"
                          >
                            <PlayIcon className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleCleanupTask(task.task_id)}
                            className="p-1.5 text-red-600 hover:bg-red-50 rounded-md transition-colors"
                            title="清理"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        </>
                      )}
                      <button
                        onClick={() => handleViewLogs(task.task_id)}
                        className="p-1.5 text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
                        title="查看日志"
                      >
                        <ClockIcon className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Collapsible Import Area */}
        {!importCollapsed && (
          <div className="mt-4 pt-4 border-t border-gray-200/50">
            <div className="flex gap-4 mb-4">
              <button
                onClick={() => setShowUrlDialog(true)}
                disabled={importStatus.isActive}
                className="flex-1 flex items-center justify-center gap-2 p-3 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50"
              >
                <GlobeAltIcon className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-700">网页 URL</span>
              </button>
              <button
                onClick={() => setShowFileUpload(true)}
                disabled={importStatus.isActive}
                className="flex-1 flex items-center justify-center gap-2 p-3 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50"
              >
                <DocumentIcon className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-700">本地文件</span>
              </button>
            </div>

            {/* Task Progress */}
            {importStatus.isActive && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {taskStatus === 'processing' && (
                      <>
                        <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                        <span className="text-sm text-blue-600">处理中 {importStatus.progress}%</span>
                      </>
                    )}
                    {taskStatus === 'completed' && (
                      <>
                        <div className="w-2 h-2 bg-green-500 rounded-full" />
                        <span className="text-sm text-green-600">已完成</span>
                      </>
                    )}
                    {taskStatus === 'failed' && (
                      <>
                        <div className="w-2 h-2 bg-red-500 rounded-full" />
                        <span className="text-sm text-red-600">失败</span>
                      </>
                    )}
                  </div>
                  <button
                    onClick={() => { setTaskStatus(''); setTaskLogs([]); setImportStatus({ isActive: false, progress: 0, message: '' }) }}
                    className="text-xs text-gray-500 hover:text-gray-700 px-2 py-1 rounded border border-gray-300"
                  >
                    清除
                  </button>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-1.5">
                  <div className="bg-blue-500 h-1.5 rounded-full transition-all" style={{ width: `${importStatus.progress}%` }} />
                </div>
                {taskLogs.length > 0 && (
                  <textarea
                    ref={logTextAreaRef}
                    className="w-full h-16 p-2 text-xs font-mono bg-gray-50 border border-gray-200 rounded-md resize-none"
                    value={taskLogs.join('\n')}
                    readOnly
                  />
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Search Bar */}
      <div className="flex-shrink-0 px-6 py-3 border-b border-gray-200/50 bg-white/60 backdrop-blur-sm">
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="搜索文档..."
            value={searchQuery}
            onChange={e => {
              setSearchQuery(e.target.value)
              setSelectedDocId(null)
              if (e.target.value.trim()) setActiveTab('all')
            }}
            className="w-full pl-9 pr-4 py-2 text-sm bg-white/80 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
          />
          {searching && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400">搜索中...</div>
          )}
        </div>
      </div>

      {/* Main Content: Sidebar + Right Panel */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Sidebar */}
        <SidebarNav
          categories={categories}
          activeTab={activeTab}
          onTabSelect={handleTabSelect}
          highlightedCategory={highlightedCategory}
          totalDocs={documents.length}
          readmeDocCount={readmeDocCount}
          displayLanguage={displayLanguage}
          isBilingual={isBilingual}
          categoryNameMap={categoryNameMap}
          onLanguageToggle={() => setDisplayLanguage(displayLanguage === 'source' ? 'zh' : 'source')}
        />

        {/* Right Content Area */}
        <div className="flex-1 flex flex-col overflow-hidden bg-gray-50/30">
          {showReader && selectedDoc && (
            <DocReader
              doc={{ id: selectedDoc.id, name: selectedDoc.name, nameTranslated: selectedDoc.nameTranslated, url: selectedDoc.url }}
              previewUrl={previewUrl}
              onBack={handleBackFromReader}
            />
          )}

          {showReadme && readmeContent && (
            <ReadmePanel
              readmeContent={readmeContent}
              readmeContentZh={readmeContentZh}
              displayLanguage={displayLanguage}
              isBilingual={isBilingual}
              onDocClick={handleReadmeDocClick}
            />
          )}

          {(showDocList || showFallbackList) && (
            <DocListPanel
              docs={displayedDocs}
              loading={loadingDocuments}
              activeTab={activeTab}
              hasSearch={searchQuery.trim() !== ''}
              isBilingual={isBilingual}
              displayLanguage={displayLanguage}
              categoryNameMap={categoryNameMap}
              onDocClick={handleDocClick}
              onDownload={handleDownload}
              onDelete={handleDelete}
            />
          )}
        </div>
      </div>

      {/* Modals */}
      <UrlInputDialog
        isOpen={showUrlDialog}
        onConfirm={handleUrlDialogConfirm}
        onCancel={() => setShowUrlDialog(false)}
      />
      <FileUploadModal
        isOpen={showFileUpload}
        onFilesSelected={handleFilesSelected}
        onClose={() => setShowFileUpload(false)}
        isProcessing={importStatus.isActive}
      />

      {/* Log Modal */}
      {showLogModal && logModalTaskId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          onClick={() => setShowLogModal(false)}
        >
          <div
            className="w-full max-w-2xl max-h-[80vh] bg-white rounded-xl shadow-2xl flex flex-col mx-4"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200"
            >
              <h3 className="text-sm font-semibold text-gray-800"
              >
                任务日志
                {logModalStreaming && (
                  <span className="ml-2 text-xs text-blue-600"
                  >
                    (实时)
                    <span className="inline-block w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse ml-1" />
                  </span>
                )}
              </h3>
              <button
                onClick={() => setShowLogModal(false)}
                className="p-1 hover:bg-gray-100 rounded-md transition-colors"
              >
                <XMarkIcon className="w-5 h-5 text-gray-500" />
              </button>
            </div>
            <div
              ref={logModalRef}
              className="flex-1 overflow-y-auto p-4 space-y-1 min-h-[300px] max-h-[60vh]"
            >
              {taskLogsModal.length === 0 ? (
                <p className="text-sm text-gray-400 text-center py-8"
                >暂无日志</p>
              ) : (
                taskLogsModal.map((log, idx) => (
                  <div
                    key={`${log.id}-${idx}`}
                    className={clsx(
                      "text-xs font-mono py-0.5 px-1 rounded",
                      log.level === 'error' && "text-red-700 bg-red-50",
                      log.level === 'warning' && "text-yellow-700 bg-yellow-50",
                      log.level === 'debug' && "text-gray-500",
                      (log.level === 'info' || !log.level) && "text-gray-700"
                    )}
                  >
                    {log.message}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Document list panel - shown when filtering by category or search
 */
const DocListPanel: React.FC<{
  docs: MappedDoc[]
  loading: boolean
  activeTab: 'overview' | 'all' | string
  hasSearch: boolean
  isBilingual: boolean
  displayLanguage: 'source' | 'zh'
  categoryNameMap: Map<string, string>
  onDocClick: (doc: MappedDoc) => void
  onDownload: (doc: MappedDoc) => void
  onDelete: (doc: MappedDoc) => void
}> = ({ docs, loading, activeTab, hasSearch, isBilingual, displayLanguage, categoryNameMap, onDocClick, onDownload, onDelete }) => {
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-gray-500">加载中...</div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            {hasSearch ? '搜索结果' : activeTab === 'all' ? '全部文档' : (isBilingual && displayLanguage === 'zh' ? (categoryNameMap.get(activeTab) || activeTab) : activeTab)}
          </h2>
          <span className="text-sm text-gray-500">{docs.length} 个文档</span>
        </div>

        {docs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-gray-500">
            <DocumentIcon className="w-12 h-12 mb-2 opacity-50" />
            <p>{hasSearch ? '未找到匹配的文档' : '暂无文档'}</p>
          </div>
        ) : (
          <div className="space-y-1">
            {docs.map(doc => (
              <div
                key={doc.id}
                className="flex items-center gap-3 px-4 py-3 rounded-lg hover:bg-white hover:shadow-sm cursor-pointer transition-all group"
                onClick={() => onDocClick(doc)}
              >
                <div className="flex-shrink-0">
                  {doc.url ? (
                    <GlobeAltIcon className="w-4 h-4 text-blue-500" />
                  ) : (
                    <DocumentIcon className="w-4 h-4 text-gray-400" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900 truncate">
                    {doc.name}
                    {isBilingual && doc.nameTranslated && (
                      <span className="text-gray-500 font-normal"> ({doc.nameTranslated})</span>
                    )}
                  </div>
                  {doc.url && (
                    <div className="text-xs text-gray-400 truncate mt-0.5">{doc.url}</div>
                  )}
                </div>
                <span className={clsx(
                  'text-xs px-2 py-0.5 rounded-full flex-shrink-0',
                  doc.status === 'indexed' ? 'bg-green-100 text-green-700' :
                  doc.status === 'processing' ? 'bg-yellow-100 text-yellow-700' :
                  doc.status === 'pending' ? 'bg-gray-100 text-gray-600' :
                  'bg-red-100 text-red-700'
                )}>
                  {doc.status === 'indexed' ? '已索引' : doc.status === 'processing' ? '处理中' : doc.status === 'pending' ? '等待中' : '失败'}
                </span>
                <span className="text-xs text-gray-400 flex-shrink-0 w-16 text-right">{doc.size}</span>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                  <button
                    onClick={e => { e.stopPropagation(); onDownload(doc) }}
                    className="p-1 hover:bg-gray-100 rounded"
                    title="下载"
                  >
                    <ArrowDownTrayIcon className="w-3.5 h-3.5 text-gray-400 hover:text-blue-500" />
                  </button>
                  <button
                    onClick={e => { e.stopPropagation(); onDelete(doc) }}
                    className="p-1 hover:bg-gray-100 rounded"
                    title="删除"
                  >
                    <TrashIcon className="w-3.5 h-3.5 text-gray-400 hover:text-red-500" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default KnowledgeBaseManagement
