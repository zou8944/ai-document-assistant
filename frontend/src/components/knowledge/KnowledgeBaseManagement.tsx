/**
 * Knowledge base management page - two-column layout
 * Left: accordion sidebar (overview + expandable groups with docs) | Right: README / DocReader | Top: search + import
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  DocumentIcon,
  FolderIcon,
  GlobeAltIcon,
  ArrowDownTrayIcon,
  TrashIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ChevronLeftIcon,
  MagnifyingGlassIcon,
  PlayIcon,
  ArrowPathIcon,
  StopIcon,
  EllipsisVerticalIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import { Document as APIDocument, Task as APITask, TaskLog as APITaskLog, useAPIClient, extractData, SSEEvent } from '../../services/apiClient'
import { UrlInputDialog } from '../InputDialog'
import FileUploadModal from '../FileUploadModal'
import ReadmePanel from './ReadmePanel'
import DocReader from './DocReader'
import {
  parseCategories,
  findCategoryForPath,
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

const getTaskBgClass = (task: APITask, isSelected: boolean): string => {
  if (isSelected) {
    if (task.status === 'processing') return 'bg-yellow-100/60 border-yellow-300'
    if (task.status === 'success') return 'bg-green-100/60 border-green-300'
    if (task.status === 'failed') return 'bg-red-100/60 border-red-300'
    if (task.status === 'stopped') return 'bg-blue-100/60 border-blue-300'
    return 'bg-gray-100/60 border-gray-300'
  }
  if (task.status === 'processing') return 'bg-yellow-50/40 border-yellow-200/60 hover:bg-yellow-50/60'
  if (task.status === 'success') return 'bg-green-50/40 border-green-200/60 hover:bg-green-50/60'
  if (task.status === 'failed') return 'bg-red-50/40 border-red-200/60 hover:bg-red-50/60'
  if (task.status === 'stopped') return 'bg-blue-50/40 border-blue-200/60 hover:bg-blue-50/60'
  return 'bg-gray-50/40 border-gray-200/60 hover:bg-gray-50/60'
}

export const KnowledgeBaseManagement: React.FC<KnowledgeBaseManagementProps> = ({
  className,
}) => {
  const { getCurrentKnowledgeBase, setActiveKnowledgeBase, displayLanguage, setDisplayLanguage, deleteKnowledgeBase } = useAppStore()
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
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<MappedDoc[] | null>(null)
  const [searching, setSearching] = useState(false)

  // Sidebar state
  const [sidebarWidth, setSidebarWidth] = useState(260)
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [isDragging, setIsDragging] = useState(false)
  const sidebarRef = useRef<HTMLDivElement>(null)

  // Import & Task state
  const [importCollapsed, setImportCollapsed] = useState(true)
  const [showUrlDialog, setShowUrlDialog] = useState(false)
  const [showFileUpload, setShowFileUpload] = useState(false)
  const [tasks, setTasks] = useState<APITask[]>([])
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [taskLogs, setTaskLogs] = useState<string[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const logTextAreaRef = useRef<HTMLTextAreaElement>(null)
  const [logsExpanded, setLogsExpanded] = useState(false)
  const [showActionsMenu, setShowActionsMenu] = useState(false)
  const [clearModalOpen, setClearModalOpen] = useState(false)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [confirmName, setConfirmName] = useState('')
  const [stoppingTaskIds, setStoppingTaskIds] = useState<Set<string>>(new Set())
  const actionsMenuRef = useRef<HTMLDivElement>(null)

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

  // Find selected document
  const selectedDoc = useMemo(
    () => (selectedDocId ? documents.find(d => d.id === selectedDocId) || null : null),
    [selectedDocId, documents]
  )

  // Find which category the selected doc belongs to
  const selectedDocCategory = useMemo(() => {
    if (!selectedDoc?.source_path) return null
    return findCategoryForPath(categories, selectedDoc.source_path)
  }, [selectedDoc, categories])

  // Preview URL for selected doc
  const previewUrl = useMemo(() => {
    if (!selectedDoc || !currentKb) return ''
    return apiClient.getDocumentPreviewUrl(currentKb.id, selectedDoc.id)
  }, [selectedDoc, currentKb, apiClient])

  // Group -> docs mapping
  const groupDocsMap = useMemo(() => {
    const map = new Map<string, MappedDoc[]>()
    map.set('all', documents)
    for (const cat of categories) {
      const paths = new Set(cat.pages.map(p => p.path))
      const docs = documents.filter(d => d.source_path && paths.has(d.source_path))
      map.set(cat.category, docs)
    }
    return map
  }, [documents, categories])

  // Search results grouped by category
  const searchGroupedDocs = useMemo(() => {
    if (!searchResults) return null
    const map = new Map<string, MappedDoc[]>()
    map.set('all', searchResults)
    for (const cat of categories) {
      const paths = new Set(cat.pages.map(p => p.path))
      const docs = searchResults.filter(d => d.source_path && paths.has(d.source_path))
      if (docs.length > 0) {
        map.set(cat.category, docs)
      }
    }
    return map
  }, [searchResults, categories])

  // Visible groups (when searching, only show groups with results)
  const visibleCategories = useMemo(() => {
    if (!searchResults) return categories
    return categories.filter(cat => {
      const docs = searchGroupedDocs?.get(cat.category)
      return docs && docs.length > 0
    })
  }, [searchResults, categories, searchGroupedDocs])

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
        const cat = findCategoryForPath(categories, path)
        if (cat) {
          setExpandedGroups(prev => new Set(prev).add(cat))
        }
      }
    },
    [documents, categories]
  )

  // Doc click from list
  const handleDocClick = useCallback((doc: MappedDoc) => {
    setSelectedDocId(doc.id)
  }, [])

  // Overview click
  const handleOverviewClick = useCallback(() => {
    setSelectedDocId(null)
  }, [])

  // Toggle group expand/collapse
  const toggleGroup = useCallback((group: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      if (next.has(group)) {
        next.delete(group)
      } else {
        next.add(group)
      }
      return next
    })
  }, [])

  // Drag to resize sidebar
  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setIsDragging(true)
    const startX = e.clientX
    const startWidth = sidebarWidth

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = Math.max(200, Math.min(500, startWidth + e.clientX - startX))
      setSidebarWidth(newWidth)
    }

    const handleMouseUp = () => {
      setIsDragging(false)
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [sidebarWidth])

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
      setSelectedTaskId(taskData.task_id)
      setTaskLogs([])
      setIsStreaming(true)
      apiClient.cancelRequests()
      streamTaskProgress(taskData.task_id)
      loadTasks()
    } catch (error) {
      console.error('导入失败:', error)
      alert('导入失败: ' + (error as Error).message)
    }
  }

  const handleFilesSelected = async (filePaths: string[]) => {
    if (!currentKb || filePaths.length === 0) return
    setShowFileUpload(false)
    try {
      const response = await apiClient.ingestFiles(currentKb.id, { files: filePaths })
      const taskData = extractData(response)
      setSelectedTaskId(taskData.task_id)
      setTaskLogs([])
      setIsStreaming(true)
      apiClient.cancelRequests()
      streamTaskProgress(taskData.task_id)
      loadTasks()
    } catch (error) {
      console.error('文件导入失败:', error)
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
      setTasks(prev => prev.map(t => t.task_id === taskId ? { ...t, status: 'stopped' as const } : t))
      if (selectedTaskId === taskId) {
        setIsStreaming(false)
      }
      setStoppingTaskIds(prev => new Set(prev).add(taskId))
      setTimeout(() => {
        setStoppingTaskIds(prev => {
          const next = new Set(prev)
          next.delete(taskId)
          return next
        })
      }, 5000)
    } catch (error) {
      console.error('停止任务失败:', error)
      alert('停止任务失败: ' + (error as Error).message)
    }
  }

  const handleRestartTask = async (taskId: string) => {
    try {
      await apiClient.restartTask(taskId)
      setTasks(prev => prev.map(t => t.task_id === taskId ? { ...t, status: 'pending' as const } : t))
      setSelectedTaskId(taskId)
      setTaskLogs([])
      setIsStreaming(true)
      apiClient.cancelRequests()
      streamTaskProgress(taskId)
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

  // Collection actions
  const handleClearCollection = () => {
    setShowActionsMenu(false)
    setConfirmName('')
    setClearModalOpen(true)
  }

  const handleConfirmClear = async () => {
    if (!currentKb) return
    if (confirmName !== currentKb.name) {
      alert('输入的名称与知识库名称不匹配')
      return
    }
    try {
      await apiClient.clearCollection(currentKb.id)
      setClearModalOpen(false)
      setConfirmName('')
      loadDocuments()
      loadReadme()
      loadTasks()
    } catch (error) {
      console.error('清空知识库失败:', error)
      alert('清空知识库失败: ' + (error as Error).message)
    }
  }

  const handleDeleteCollection = () => {
    setShowActionsMenu(false)
    setConfirmName('')
    setDeleteModalOpen(true)
  }

  const handleConfirmDelete = async () => {
    if (!currentKb) return
    if (confirmName !== currentKb.name) {
      alert('输入的名称与知识库名称不匹配')
      return
    }
    try {
      await apiClient.deleteCollection(currentKb.id)
      setDeleteModalOpen(false)
      setConfirmName('')
      deleteKnowledgeBase(currentKb.id)
      setActiveKnowledgeBase(null)
    } catch (error) {
      console.error('删除知识库失败:', error)
      alert('删除知识库失败: ' + (error as Error).message)
    }
  }

  // Close actions menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (actionsMenuRef.current && !actionsMenuRef.current.contains(event.target as Node)) {
        setShowActionsMenu(false)
      }
    }
    if (showActionsMenu) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showActionsMenu])

  const handleSelectTask = async (taskId: string) => {
    if (selectedTaskId === taskId) return
    setSelectedTaskId(taskId)
    setTaskLogs([])
    apiClient.cancelRequests()

    const task = tasks.find(t => t.task_id === taskId)
    if (task?.status === 'processing') {
      setIsStreaming(true)
      streamTaskProgress(taskId)
    } else {
      setIsStreaming(false)
      try {
        const response = await apiClient.getTaskLogs(taskId)
        const data = extractData(response)
        setTaskLogs(data.logs.map((log: APITaskLog) => {
          const timestamp = new Date(log.timestamp).toLocaleTimeString()
          return `[${timestamp}] ${log.message}`
        }))
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
            setIsStreaming(false)
            loadDocuments()
            loadReadme()
            loadTasks()
            break
          case 'error':
            setTaskLogs(prev => [...prev, event.data?.message || '未知错误'])
            setIsStreaming(false)
            loadTasks()
            break
        }
      },
      (error: Error) => {
        console.error('Task streaming error:', error)
        setTaskLogs(prev => [...prev, error.message || '未知错误'])
        setIsStreaming(false)
        loadTasks()
      }
    )
  }

  // Auto-refresh task list when panel is open
  useEffect(() => {
    if (!currentKb || importCollapsed) return
    const interval = setInterval(() => {
      loadTasks()
    }, 3000)
    return () => clearInterval(interval)
  }, [currentKb?.id, importCollapsed, loadTasks])

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

  // Right panel view
  const showReader = selectedDoc !== null
  const showReadme = selectedDocId === null && readmeContent !== null

  // Get display name for category
  const getDisplayCategory = useCallback((enName: string) => {
    if (!isBilingual || displayLanguage === 'source') return enName
    return categoryNameMap.get(enName) || enName
  }, [isBilingual, displayLanguage, categoryNameMap])

  // Render a document item in sidebar
  const renderDocItem = (doc: MappedDoc) => (
    <div
      key={doc.id}
      className={clsx(
        'flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors group',
        selectedDocId === doc.id
          ? 'bg-blue-50/80 border-l-2 border-blue-500'
          : 'hover:bg-white/60 border-l-2 border-transparent'
      )}
      onClick={() => handleDocClick(doc)}
    >
      <div className="flex-shrink-0">
        {doc.url ? (
          <GlobeAltIcon className="w-4 h-4 text-blue-500" />
        ) : (
          <DocumentIcon className="w-4 h-4 text-gray-400" />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className={clsx(
          'text-sm truncate',
          selectedDocId === doc.id ? 'font-medium text-blue-700' : 'text-gray-800'
        )}>
          {doc.name}
          {isBilingual && doc.nameTranslated && (
            <span className="text-gray-500 font-normal"> ({doc.nameTranslated})</span>
          )}
        </div>
        {doc.url && (
          <div className="text-xs text-gray-400 truncate">{doc.url}</div>
        )}
      </div>
      <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          onClick={e => { e.stopPropagation(); handleDownload(doc) }}
          className="p-1 hover:bg-gray-100 rounded"
          title="下载"
        >
          <ArrowDownTrayIcon className="w-3.5 h-3.5 text-gray-400 hover:text-blue-500" />
        </button>
        <button
          onClick={e => { e.stopPropagation(); handleDelete(doc) }}
          className="p-1 hover:bg-gray-100 rounded"
          title="删除"
        >
          <TrashIcon className="w-3.5 h-3.5 text-gray-400 hover:text-red-500" />
        </button>
      </div>
    </div>
  )

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
      <div className="relative z-50 flex-shrink-0 px-6 py-4 bg-gradient-to-r from-white/90 to-white/70 backdrop-blur-sm border-b border-gray-200/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setActiveKnowledgeBase(null)}
              className="p-2 hover:bg-gray-100/50 rounded-lg transition-colors"
            >
              <ChevronLeftIcon className="w-5 h-5 text-gray-600" />
            </button>
            <div>
              <h1 className="text-xl font-bold text-gray-900">{currentKb.name}</h1>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setImportCollapsed(!importCollapsed); if (importCollapsed) loadTasks() }}
              className={clsx(
                'flex items-center gap-1 text-sm px-3 py-1.5 rounded-lg transition-colors',
                !importCollapsed
                  ? 'text-blue-700 bg-blue-50'
                  : 'text-blue-600 hover:text-blue-700 hover:bg-blue-50'
              )}
            >
              {importCollapsed ? <ChevronRightIcon className="w-4 h-4" /> : <ChevronDownIcon className="w-4 h-4" />}
              导入与任务
              {tasks.filter(t => t.status === 'processing').length > 0 && (
                <span className="ml-1 w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
              )}
            </button>
            <div className="relative z-50" ref={actionsMenuRef}>
              <button
                onClick={() => setShowActionsMenu(!showActionsMenu)}
                className="p-2 hover:bg-gray-100/50 rounded-lg transition-colors text-gray-500"
                title="更多操作"
              >
                <EllipsisVerticalIcon className="w-5 h-5" />
              </button>
              {showActionsMenu && (
                <div className="absolute right-0 mt-1 w-40 bg-white rounded-lg shadow-lg border border-gray-200/50 py-1 z-50">
                  <button
                    onClick={handleClearCollection}
                    className="w-full flex items-center gap-2 px-4 py-2 text-sm text-yellow-700 hover:bg-yellow-50 transition-colors"
                  >
                    <XCircleIcon className="w-4 h-4" />
                    清空知识库
                  </button>
                  <button
                    onClick={handleDeleteCollection}
                    className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <TrashIcon className="w-4 h-4" />
                    删除知识库
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Import & Task Panel */}
        {!importCollapsed && (
          <div className="mt-4 pt-4 border-t border-gray-200/50">
            {/* Import Buttons */}
            <div className="flex gap-4 mb-4">
              <button
                onClick={() => setShowUrlDialog(true)}
                disabled={isStreaming}
                className="flex-1 flex items-center justify-center gap-2 p-3 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50"
              >
                <GlobeAltIcon className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-700">网页 URL</span>
              </button>
              <button
                onClick={() => setShowFileUpload(true)}
                disabled={isStreaming}
                className="flex-1 flex items-center justify-center gap-2 p-3 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50"
              >
                <DocumentIcon className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-700">本地文件</span>
              </button>
            </div>

            {/* Task List */}
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
                  <div
                    key={task.task_id}
                    onClick={() => handleSelectTask(task.task_id)}
                    className={clsx(
                      'flex items-center justify-between p-2 rounded-lg border cursor-pointer transition-colors',
                      getTaskBgClass(task, selectedTaskId === task.task_id),
                    )}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={clsx(
                          'w-2 h-2 rounded-full flex-shrink-0',
                          task.status === 'processing' && 'bg-yellow-500 animate-pulse',
                          task.status === 'success' && 'bg-green-500',
                          task.status === 'failed' && 'bg-red-500',
                          task.status === 'stopped' && 'bg-blue-500',
                          task.status === 'pending' && 'bg-gray-400',
                        )} />
                        <span className="text-sm font-medium text-gray-800 truncate">
                          {task.title || (task.task_type === 'ingest_urls' ? '网页抓取' : '文件上传')}
                        </span>
                        {task.status === 'processing' && task.progress !== undefined && (
                          <span className="text-xs text-blue-600 ml-1">
                            {typeof task.progress === 'number' ? task.progress : (task.progress as any)?.percentage ?? 0}%
                          </span>
                        )}
                        {stoppingTaskIds.has(task.task_id) && (
                          <span className="text-xs text-amber-600 ml-1 animate-pulse">
                            正在停止，当前操作完成后将停止
                          </span>
                        )}
                      </div>
                      <div className="grid grid-cols-10 gap-2 text-xs text-gray-500 mt-1">
                        <span className="col-span-1 truncate" title={`创建: ${new Date(task.created_at).toLocaleString()}`}>
                          创建: {new Date(task.created_at).toLocaleString()}
                        </span>
                        <span className="col-span-1 truncate" title={task.started_at ? '已运行' : ''}>
                          {task.started_at
                            ? `运行: ${task.completed_at
                                ? `${Math.round((new Date(task.completed_at).getTime() - new Date(task.started_at).getTime()) / 1000)}秒`
                                : `${Math.round((Date.now() - new Date(task.started_at).getTime()) / 1000)}秒`}`
                            : ''}
                        </span>
                        <span className="col-span-4 truncate" title={task.urls?.join(', ') || ''}>
                          {task.urls?.length
                            ? `URL: ${task.urls[0]}${task.urls.length > 1 ? ` 等${task.urls.length}个` : ''}`
                            : ''}
                        </span>
                        <span className="col-span-4 truncate" title={task.recursive_prefix || ''}>
                          {task.recursive_prefix ? `前缀: ${task.recursive_prefix}` : ''}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0 ml-2"
                      onClick={e => e.stopPropagation()}
                    >
                      {task.status === 'processing' && (
                        <button
                          onClick={() => handleStopTask(task.task_id)}
                          className="p-1.5 text-red-600 hover:bg-red-50 rounded-md transition-colors"
                          title="停止（当前操作完成后停止）"
                        >
                          <StopIcon className="w-4 h-4" />
                        </button>
                      )}
                      {(task.status === 'success' || task.status === 'failed' || task.status === 'stopped') && !tasks.some(t => t.status === 'processing') && (
                        <button
                          onClick={() => handleRestartTask(task.task_id)}
                          className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                          title={task.status === 'success' ? '重新运行' : '重跑'}
                        >
                          {task.status === 'success' ? <ArrowPathIcon className="w-4 h-4" /> : <PlayIcon className="w-4 h-4" />}
                        </button>
                      )}
                      {(task.status === 'success' || task.status === 'failed' || task.status === 'stopped') && (
                        <button
                          onClick={() => handleCleanupTask(task.task_id)}
                          className="p-1.5 text-red-600 hover:bg-red-50 rounded-md transition-colors"
                          title="清理"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Unified Log Area */}
            {selectedTaskId && (
              <div className={clsx('mt-3 flex flex-col', logsExpanded && 'h-[50vh]')}>
                <div className="flex items-center justify-between mb-2 flex-shrink-0">
                  <span className="text-xs text-gray-500">
                    {(() => {
                      const t = tasks.find(task => task.task_id === selectedTaskId)
                      return t ? (t.title || (t.task_type === 'ingest_urls' ? '网页抓取' : '文件上传')) : '任务'
                    })()} 日志
                    {taskLogs.length > 0 && (
                      <span className="ml-1 text-gray-400">({taskLogs.length} 条)</span>
                    )}
                    {isStreaming && (
                      <span className="ml-1 text-blue-600">(实时)</span>
                    )}
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setLogsExpanded(v => !v)}
                      className="text-xs text-blue-600 hover:text-blue-700 px-2 py-0.5 rounded hover:bg-blue-50 transition-colors"
                    >
                      {logsExpanded ? '收起' : '展开'}
                    </button>
                    <button
                      onClick={() => { setSelectedTaskId(null); setTaskLogs([]); setIsStreaming(false); setLogsExpanded(false); apiClient.cancelRequests() }}
                      className="text-xs text-gray-400 hover:text-gray-600 px-2 py-0.5 rounded hover:bg-gray-100 transition-colors"
                    >
                      关闭
                    </button>
                  </div>
                </div>
                <textarea
                  ref={logTextAreaRef}
                  className={clsx(
                    'w-full p-2 text-xs font-mono bg-gray-50 border border-gray-200 rounded-md resize-none',
                    logsExpanded ? 'flex-1 min-h-0' : 'h-24'
                  )}
                  value={taskLogs.join('\n')}
                  readOnly
                />
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
              if (e.target.value.trim()) {
                setSelectedDocId(null)
              }
            }}
            className="w-full pl-9 pr-4 py-2 text-sm bg-white/80 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
          />
          {searching && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400">搜索中...</div>
          )}
        </div>
      </div>

      {/* Main Content: Two-column layout */}
      <div className={clsx('flex-1 flex overflow-hidden', isDragging && 'select-none')}>
        {/* Left: Accordion Sidebar */}
        <div
          ref={sidebarRef}
          className="flex-shrink-0 border-r border-gray-200/50 bg-white/50 backdrop-blur-sm flex flex-col overflow-hidden"
          style={{ width: sidebarWidth }}
        >
          {/* Sidebar header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200/30 flex-shrink-0">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">文档</span>
          </div>

          {/* Sidebar content */}
          <div className="flex-1 overflow-y-auto py-1">
            {loadingDocuments && documents.length === 0 && (
              <div className="flex items-center justify-center py-8 text-gray-500">
                <div className="text-sm">加载中...</div>
              </div>
            )}

            {/* Overview */}
            <button
              onClick={handleOverviewClick}
              className={clsx(
                'w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors',
                selectedDocId === null && !searchQuery
                  ? 'bg-blue-50/80 text-blue-600 font-medium'
                  : 'text-gray-700 hover:bg-gray-50/80'
              )}
            >
              <span className="flex items-center gap-2">
                <FolderIcon className="w-4 h-4 flex-shrink-0" />
                概览
              </span>
              <span className={clsx(
                'text-xs px-1.5 py-0.5 rounded-full',
                selectedDocId === null && !searchQuery ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-500'
              )}>
                {readmeDocCount}
              </span>
            </button>

            {/* All Documents */}
            <div>
              <button
                onClick={() => toggleGroup('all')}
                className={clsx(
                  'w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors',
                  selectedDocId !== null && !selectedDocCategory
                    ? 'text-gray-700 hover:bg-gray-50/80'
                    : 'text-gray-700 hover:bg-gray-50/80'
                )}
              >
                <span className="flex items-center gap-2">
                  {expandedGroups.has('all') ? (
                    <ChevronDownIcon className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                  ) : (
                    <ChevronRightIcon className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                  )}
                  <span>所有文档</span>
                </span>
                <span className="text-xs px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-500">
                  {searchResults !== null
                    ? (searchGroupedDocs?.get('all')?.length ?? 0)
                    : documents.length}
                </span>
              </button>
              {expandedGroups.has('all') && (
                <div className="pb-1">
                  {(() => {
                    const docs = searchResults !== null
                      ? (searchGroupedDocs?.get('all') ?? [])
                      : (groupDocsMap.get('all') ?? [])
                    if (docs.length === 0) {
                      return (
                        <div className="px-8 py-2 text-xs text-gray-400">
                          暂无文档
                        </div>
                      )
                    }
                    return docs.map(renderDocItem)
                  })()}
                </div>
              )}
            </div>

            {/* Category Groups */}
            {visibleCategories.map(cat => {
              const isExpanded = expandedGroups.has(cat.category)
              const isHighlighted = selectedDocCategory === cat.category
              const docs = searchResults !== null
                ? (searchGroupedDocs?.get(cat.category) ?? [])
                : (groupDocsMap.get(cat.category) ?? [])
              return (
                <div key={cat.category}>
                  <button
                    onClick={() => toggleGroup(cat.category)}
                    className={clsx(
                      'w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors',
                      isHighlighted && !searchQuery
                        ? 'bg-blue-50/30 text-blue-600'
                        : 'text-gray-700 hover:bg-gray-50/80'
                    )}
                  >
                    <span className="flex items-center gap-2 min-w-0">
                      {isExpanded ? (
                        <ChevronDownIcon className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                      ) : (
                        <ChevronRightIcon className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                      )}
                      <span className="truncate">{getDisplayCategory(cat.category)}</span>
                    </span>
                    <span className={clsx(
                      'text-xs px-1.5 py-0.5 rounded-full flex-shrink-0 ml-2',
                      isHighlighted && !searchQuery ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-500'
                    )}>
                      {docs.length}
                    </span>
                  </button>
                  {isExpanded && (
                    <div className="pb-1">
                      {docs.length === 0 ? (
                        <div className="px-8 py-2 text-xs text-gray-400">
                          暂无文档
                        </div>
                      ) : (
                        docs.map(renderDocItem)
                      )}
                    </div>
                  )}
                </div>
              )
            })}

            {/* Search empty state */}
            {searchResults !== null && visibleCategories.length === 0 && (
              <div className="flex flex-col items-center justify-center py-8 text-gray-400 px-4">
                <DocumentIcon className="w-8 h-8 mb-2 opacity-50" />
                <p className="text-sm text-center">未找到匹配的文档</p>
              </div>
            )}
          </div>

          {/* Language toggle for bilingual collections */}
          {isBilingual && (
            <div className="px-4 py-3 border-t border-gray-200/50 flex-shrink-0">
              <button
                onClick={() => setDisplayLanguage(displayLanguage === 'source' ? 'zh' : 'source')}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-gray-600 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <span>{displayLanguage === 'source' ? 'English' : '中文'}</span>
                <svg className="w-3 h-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
                </svg>
                <span>{displayLanguage === 'source' ? '中文' : 'English'}</span>
              </button>
            </div>
          )}
        </div>

        {/* Drag handle */}
        <div
          className="w-1 flex-shrink-0 hover:bg-blue-400/50 active:bg-blue-500/60 transition-colors"
          style={{ cursor: isDragging ? 'col-resize' : 'col-resize' }}
          onMouseDown={handleDragStart}
          title="拖动调整宽度"
        />

        {/* Right: Detail Panel */}
        <div className="flex-1 flex flex-col overflow-hidden bg-gray-50/30">
          {showReader && selectedDoc ? (
            <DocReader
              doc={{ id: selectedDoc.id, name: selectedDoc.name, nameTranslated: selectedDoc.nameTranslated, url: selectedDoc.url }}
              previewUrl={previewUrl}
            />
          ) : showReadme && readmeContent ? (
            <ReadmePanel
              readmeContent={readmeContent}
              readmeContentZh={readmeContentZh}
              displayLanguage={displayLanguage}
              isBilingual={isBilingual}
              onDocClick={handleReadmeDocClick}
            />
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-400">
              <DocumentIcon className="w-12 h-12 mb-3 opacity-50" />
              <p className="text-sm">
                {searchQuery
                  ? '搜索中或从左侧选择一篇文档'
                  : readmeContent
                    ? '概览页面加载中...'
                    : '从左侧选择一篇文档查看详情'
                }
              </p>
            </div>
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
        isProcessing={isStreaming}
      />

      {/* Clear Collection Confirm Modal */}
      {clearModalOpen && currentKb && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          onClick={() => { setClearModalOpen(false); setConfirmName('') }}
        >
          <div
            className="w-full max-w-md bg-white rounded-xl shadow-2xl flex flex-col mx-4 overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">清空知识库</h3>
            </div>
            <div className="px-6 py-4 space-y-4">
              <p className="text-sm text-gray-600">
                此操作将删除知识库
                <span className="font-semibold text-gray-900">&nbsp;"{currentKb.name}"&nbsp;</span>
                中的所有文档、向量和任务数据，但保留知识库本身。
                此操作<span className="text-red-600 font-semibold">无法撤销</span>。
              </p>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  请输入知识库名称以确认：
                </label>
                <input
                  type="text"
                  value={confirmName}
                  onChange={e => setConfirmName(e.target.value)}
                  placeholder={currentKb.name}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent transition-all text-sm"
                  autoFocus
                />
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => { setClearModalOpen(false); setConfirmName('') }}
                className="px-4 py-2 text-sm text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleConfirmClear}
                disabled={confirmName !== currentKb.name}
                className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                确认清空
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Collection Confirm Modal */}
      {deleteModalOpen && currentKb && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          onClick={() => { setDeleteModalOpen(false); setConfirmName('') }}
        >
          <div
            className="w-full max-w-md bg-white rounded-xl shadow-2xl flex flex-col mx-4 overflow-hidden"
            onClick={e => e.stopPropagation()}
          >
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">删除知识库</h3>
            </div>
            <div className="px-6 py-4 space-y-4">
              <p className="text-sm text-gray-600">
                此操作将
                <span className="text-red-600 font-semibold">永久删除</span>
                知识库
                <span className="font-semibold text-gray-900">&nbsp;"{currentKb.name}"&nbsp;</span>
                及其所有文档、向量和任务数据。
                此操作<span className="text-red-600 font-semibold">无法撤销</span>。
              </p>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  请输入知识库名称以确认：
                </label>
                <input
                  type="text"
                  value={confirmName}
                  onChange={e => setConfirmName(e.target.value)}
                  placeholder={currentKb.name}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent transition-all text-sm"
                  autoFocus
                />
              </div>
            </div>
            <div className="px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
              <button
                onClick={() => { setDeleteModalOpen(false); setConfirmName('') }}
                className="px-4 py-2 text-sm text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleConfirmDelete}
                disabled={confirmName !== currentKb.name}
                className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default KnowledgeBaseManagement
