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
import DocChatSidebar from '../chat/DocChatSidebar'
import Modal from '../common/Modal'
import { toast } from '../../hooks/useToast'
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
  return 'bg-gray-50/40 border-white/40 hover:bg-gray-50/60'
}

export const KnowledgeBaseManagement: React.FC<KnowledgeBaseManagementProps> = ({
  className,
}) => {
  const {
    getCurrentKnowledgeBase,
    setActiveKnowledgeBase,
    displayLanguage,
    setDisplayLanguage,
    deleteKnowledgeBase,
    addChatSession,
    docChatSidebarOpen,
    setDocChatSidebarOpen,
    docChatSidebarWidth,
    setDocChatSidebarWidth,
  } = useAppStore()
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
  const [docListSidebarWidth, setDocListSidebarWidth] = useState(260)
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const sidebarRef = useRef<HTMLDivElement>(null)

  // Bound chat state
  const [boundChatId, setBoundChatId] = useState<string | null>(null)
  const initializedCollectionsRef = useRef<Set<string>>(new Set())

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
  const [logOffset, setLogOffset] = useState(0)
  const [loadingMoreLogs, setLoadingMoreLogs] = useState(false)
  const LOGS_PAGE_SIZE = 100
  const [showActionsMenu, setShowActionsMenu] = useState(false)
  const [clearModalOpen, setClearModalOpen] = useState(false)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [confirmName, setConfirmName] = useState('')
  const [stoppingTaskIds, setStoppingTaskIds] = useState<Set<string>>(new Set())
  const actionsMenuRef = useRef<HTMLDivElement>(null)

  // Recategorize modal state
  const [recategorizeModalOpen, setRecategorizeModalOpen] = useState(false)
  const [recategorizeMode, setRecategorizeMode] = useState('ai')

  // Delete task modal state
  const [deleteTaskModalOpen, setDeleteTaskModalOpen] = useState(false)
  const [taskToDeleteId, setTaskToDeleteId] = useState<string | null>(null)
  const [cleanupDocsChecked, setCleanupDocsChecked] = useState(false)

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
    const docByPath = new Map<string, MappedDoc>()
    for (const d of documents) {
      if (d.source_path) docByPath.set(d.source_path, d)
    }

    const map = new Map<string, MappedDoc[]>()

    // Per-category groups: preserve cat.pages order
    for (const cat of categories) {
      const docs: MappedDoc[] = []
      for (const p of cat.pages) {
        const d = docByPath.get(p.path)
        if (d) docs.push(d)
      }
      map.set(cat.category, docs)
    }

    // 'all' view: uncategorized (lex sorted) first, then grouped in order
    const coveredPaths = new Set(categories.flatMap(c => c.pages.map(p => p.path)))
    const uncategorized = documents
      .filter(d => !d.source_path || !coveredPaths.has(d.source_path))
      .sort((a, b) => (a.source_path ?? a.name).localeCompare(b.source_path ?? b.name))
    const groupedFlat = categories.flatMap(cat => map.get(cat.category) ?? [])
    map.set('all', [...uncategorized, ...groupedFlat])

    return map
  }, [documents, categories])

  // Search results grouped by category
  const searchGroupedDocs = useMemo(() => {
    if (!searchResults) return null
    const docByPath = new Map<string, MappedDoc>()
    for (const d of searchResults) {
      if (d.source_path) docByPath.set(d.source_path, d)
    }

    const map = new Map<string, MappedDoc[]>()

    for (const cat of categories) {
      const docs: MappedDoc[] = []
      for (const p of cat.pages) {
        const d = docByPath.get(p.path)
        if (d) docs.push(d)
      }
      if (docs.length > 0) {
        map.set(cat.category, docs)
      }
    }

    // 'all' search view: same ordering logic
    const coveredPaths = new Set(categories.flatMap(c => c.pages.map(p => p.path)))
    const uncategorized = searchResults
      .filter(d => !d.source_path || !coveredPaths.has(d.source_path))
      .sort((a, b) => (a.source_path ?? a.name).localeCompare(b.source_path ?? b.name))
    const groupedFlat = categories.flatMap(cat => map.get(cat.category) ?? [])
    map.set('all', [...uncategorized, ...groupedFlat])

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

  // Drag to resize left sidebar
  const handleLeftDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startWidth = docListSidebarWidth

    // Disable pointer events on iframes during drag so mouse events
    // are not captured by iframe content (fixes stuck drag when
    // releasing mouse over HTML preview).
    const iframes = document.querySelectorAll('iframe')
    iframes.forEach((iframe) => { iframe.style.pointerEvents = 'none' })

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = Math.max(200, Math.min(500, startWidth + e.clientX - startX))
      setDocListSidebarWidth(newWidth)
    }

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      // Restore pointer events
      iframes.forEach((iframe) => { iframe.style.pointerEvents = '' })
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [docListSidebarWidth])

  // Drag to resize right chat sidebar (handled by DocChatSidebar component)

  // Import handlers
  const handleUrlDialogConfirm = async (config: {
    urls: string[]
    recursivePrefixes: string[]
    categorizeMode: string
    generateReadme: boolean
  }) => {
    setShowUrlDialog(false)
    if (!currentKb || config.urls.length === 0) return
    try {
      const response = await apiClient.ingestUrls(currentKb.id, {
        url_configs: [{
          seed_urls: config.urls,
          recursive_prefixes: config.recursivePrefixes,
        }],
        categorize_mode: config.categorizeMode,
        generate_readme: config.generateReadme,
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
      toast.error('导入失败: ' + (error as Error).message)
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
      toast.error('文件导入失败: ' + (error as Error).message)
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
      toast.error('下载失败: ' + (error as Error).message)
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
        toast.error('删除失败: ' + (error as Error).message)
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
      toast.error('停止任务失败: ' + (error as Error).message)
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
      toast.error('重跑任务失败: ' + (error as Error).message)
    }
  }

  const handleDeleteTask = (taskId: string) => {
    setTaskToDeleteId(taskId)
    setCleanupDocsChecked(false)
    setDeleteTaskModalOpen(true)
  }

  const handleConfirmDeleteTask = async () => {
    if (!taskToDeleteId) return
    try {
      await apiClient.deleteTask(taskToDeleteId, cleanupDocsChecked)
      setTasks(prev => prev.filter(t => t.task_id !== taskToDeleteId))
      if (selectedTaskId === taskToDeleteId) {
        setSelectedTaskId(null)
        setTaskLogs([])
        setIsStreaming(false)
      }
      setDeleteTaskModalOpen(false)
      setTaskToDeleteId(null)
      setCleanupDocsChecked(false)
    } catch (error) {
      console.error('删除任务失败:', error)
      toast.error('删除任务失败: ' + (error as Error).message)
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
      toast.error('输入的名称与知识库名称不匹配')
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
      toast.error('清空知识库失败: ' + (error as Error).message)
    }
  }

  const handleDeleteCollection = () => {
    setShowActionsMenu(false)
    setConfirmName('')
    setDeleteModalOpen(true)
  }

  const handleRecategorize = () => {
    setShowActionsMenu(false)
    setRecategorizeMode(currentKb?.categorizeMode || 'ai')
    setRecategorizeModalOpen(true)
  }

  const handleConfirmRecategorize = async () => {
    if (!currentKb) return
    setRecategorizeModalOpen(false)
    try {
      const response = await apiClient.recategorizeCollection(currentKb.id, {
        categorize_mode: recategorizeMode,
      })
      const taskData = extractData(response)
      setSelectedTaskId(taskData.task_id)
      setTaskLogs([])
      setIsStreaming(true)
      apiClient.cancelRequests()
      streamTaskProgress(taskData.task_id)
      loadTasks()
    } catch (error) {
      console.error('重新分类失败:', error)
      toast.error('重新分类失败: ' + (error as Error).message)
    }
  }

  const handleRegenerateReadme = async () => {
    setShowActionsMenu(false)
    if (!currentKb) return
    try {
      const response = await apiClient.regenerateReadme(currentKb.id)
      const taskData = extractData(response)
      setSelectedTaskId(taskData.task_id)
      setTaskLogs([])
      setIsStreaming(true)
      apiClient.cancelRequests()
      streamTaskProgress(taskData.task_id)
      loadTasks()
    } catch (error) {
      console.error('重新生成 README 失败:', error)
      toast.error('重新生成 README 失败: ' + (error as Error).message)
    }
  }

  const handleConfirmDelete = async () => {
    if (!currentKb) return
    if (confirmName !== currentKb.name) {
      toast.error('输入的名称与知识库名称不匹配')
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
      toast.error('删除知识库失败: ' + (error as Error).message)
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
    setLogOffset(0)
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
        // Only load latest logs
        const offset = Math.max(0, data.total - LOGS_PAGE_SIZE)
        setLogOffset(offset)
        const logsResponse = await apiClient.getTaskLogs(taskId, LOGS_PAGE_SIZE, offset)
        const logsData = extractData(logsResponse)
        setTaskLogs(logsData.logs.map((log: APITaskLog) => {
          const timestamp = new Date(log.timestamp).toLocaleTimeString()
          return `[${timestamp}] ${log.message}`
        }))
        // Scroll to bottom after loading
        setTimeout(() => {
          if (logTextAreaRef.current) logTextAreaRef.current.scrollTop = logTextAreaRef.current.scrollHeight
        }, 0)
      } catch (error) {
        console.error('获取日志失败:', error)
      }
    }
  }

  const loadOlderLogs = async () => {
    if (!selectedTaskId || logOffset <= 0 || loadingMoreLogs) return
    setLoadingMoreLogs(true)
    try {
      const newOffset = Math.max(0, logOffset - LOGS_PAGE_SIZE)
      const logsResponse = await apiClient.getTaskLogs(selectedTaskId, logOffset - newOffset, newOffset)
      const logsData = extractData(logsResponse)
      const olderLogs = logsData.logs.map((log: APITaskLog) => {
        const timestamp = new Date(log.timestamp).toLocaleTimeString()
        return `[${timestamp}] ${log.message}`
      })
      setTaskLogs(prev => [...olderLogs, ...prev])
      setLogOffset(newOffset)
    } catch (error) {
      console.error('加载更多日志失败:', error)
    } finally {
      setLoadingMoreLogs(false)
    }
  }

  const handleLogScroll = (e: React.UIEvent<HTMLTextAreaElement>) => {
    const target = e.target as HTMLTextAreaElement
    if (target.scrollTop === 0 && logOffset > 0 && !loadingMoreLogs) {
      loadOlderLogs()
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

  // Initialize or find bound chat for current collection
  useEffect(() => {
    if (!currentKb) {
      setBoundChatId(null)
      return
    }

    if (initializedCollectionsRef.current.has(currentKb.id)) return
    initializedCollectionsRef.current.add(currentKb.id)

    const initBoundChat = async () => {
      try {
        // Try to find on backend
        const response = await apiClient.listChats()
        const data = extractData(response)
        const boundChat = data.chats.find(
          (chat: any) => chat.bound_collection_id === currentKb.id
        )

        if (boundChat) {
          // Add to store if not present
          const newSession = {
            id: boundChat.chat_id,
            name: boundChat.name,
            knowledgeBaseIds: boundChat.collection_ids,
            createdAt: boundChat.created_at,
            lastMessageAt: boundChat.last_message_at || boundChat.created_at,
            messageCount: boundChat.message_count || 0,
            boundCollectionId: boundChat.bound_collection_id,
          }
          addChatSession(newSession)
          setBoundChatId(boundChat.chat_id)
        } else {
          // Create new bound chat
          const createResponse = await apiClient.createChat({
            name: currentKb.name,
            collection_ids: [currentKb.id],
            bound_collection_id: currentKb.id,
          })
          const newChat = extractData(createResponse)
          const newSession = {
            id: newChat.chat_id,
            name: newChat.name,
            knowledgeBaseIds: newChat.collection_ids,
            createdAt: newChat.created_at,
            lastMessageAt: newChat.last_message_at || newChat.created_at,
            messageCount: newChat.message_count || 0,
            boundCollectionId: newChat.bound_collection_id,
          }
          addChatSession(newSession)
          setBoundChatId(newChat.chat_id)
        }
      } catch (error) {
        console.error('初始化绑定聊天失败:', error)
      }
    }

    initBoundChat()
  }, [currentKb?.id, addChatSession, apiClient])

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
          selectedDocId === doc.id ? 'font-medium text-blue-700' : 'text-ink/90'
        )}>
          {isBilingual && displayLanguage === 'zh' && doc.nameTranslated
            ? doc.nameTranslated
            : doc.name}
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
        <div className="text-center text-ink/50">
          <DocumentIcon className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p>找不到知识库</p>
          <div className="mt-4">
            <button
              onClick={() => setActiveKnowledgeBase(null)}
              className="bg-accent hover:bg-accent-hover text-white px-4 py-2 rounded-lg transition-colors"
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
      <div className="relative z-50 flex-shrink-0 px-6 py-4 bg-gradient-to-r from-white/90 to-white/70 backdrop-blur-sm border-b border-white/40">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setActiveKnowledgeBase(null)}
              className="p-2 hover:bg-gray-100/50 rounded-lg transition-colors"
            >
              <ChevronLeftIcon className="w-5 h-5 text-ink/65" />
            </button>
            <h1 className="text-xl font-bold text-ink">{currentKb.name}</h1>
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
                <span className="ml-1 w-2 h-2 bg-accent rounded-full animate-pulse" />
              )}
            </button>
            <div className="relative z-50" ref={actionsMenuRef}>
              <button
                onClick={() => setShowActionsMenu(!showActionsMenu)}
                className="p-2 hover:bg-gray-100/50 rounded-lg transition-colors text-ink/50"
                title="更多操作"
              >
                <EllipsisVerticalIcon className="w-5 h-5" />
              </button>
              {showActionsMenu && (
                <div className="absolute right-0 mt-1 w-44 bg-white rounded-lg shadow-lg border border-white/40 py-1 z-50">
                  <button
                    onClick={handleRecategorize}
                    className="w-full flex items-center gap-2 px-4 py-2 text-sm text-ink/80 hover:bg-gray-50 transition-colors"
                  >
                    <ArrowPathIcon className="w-4 h-4" />
                    重新分类
                  </button>
                  <button
                    onClick={handleRegenerateReadme}
                    className="w-full flex items-center gap-2 px-4 py-2 text-sm text-ink/80 hover:bg-gray-50 transition-colors"
                  >
                    <DocumentIcon className="w-4 h-4" />
                    重新生成 README
                  </button>
                  <div className="border-t border-gray-100 my-1" />
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
          <div className="mt-4 pt-4 border-t border-white/40">
            {/* Import Buttons */}
            <div className="flex gap-4 mb-4">
              <button
                onClick={() => setShowUrlDialog(true)}
                disabled={isStreaming}
                className="flex-1 flex items-center justify-center gap-2 p-3 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50"
              >
                <GlobeAltIcon className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-ink/80">网页 URL</span>
              </button>
              <button
                onClick={() => setShowFileUpload(true)}
                disabled={isStreaming}
                className="flex-1 flex items-center justify-center gap-2 p-3 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50"
              >
                <DocumentIcon className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-ink/80">本地文件</span>
              </button>
            </div>

            {/* Task List */}
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-ink/80">任务列表</h3>
              <button
                onClick={loadTasks}
                className="text-xs text-ink/50 hover:text-ink/80 px-2 py-1 rounded border border-gray-300"
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
                          task.status === 'stopped' && 'bg-accent',
                          task.status === 'pending' && 'bg-gray-400',
                        )} />
                        <span className="text-sm font-medium text-ink/90 truncate">
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
                      <div className="grid grid-cols-10 gap-2 text-xs text-ink/50 mt-1">
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
                        <span className="col-span-4 truncate" title={task.recursive_prefixes?.join(', ') || task.recursive_prefix || ''}>
                          {task.recursive_prefixes?.length
                            ? `前缀: ${task.recursive_prefixes.join(', ')}`
                            : task.recursive_prefix
                              ? `前缀: ${task.recursive_prefix}`
                              : ''}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0 ml-2"
                      onClick={e => e.stopPropagation()}
                    >
                      {task.status === 'processing' && (
                        <button
                          onClick={() => handleStopTask(task.task_id)}
                          className="p-1.5 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="停止（当前操作完成后停止）"
                        >
                          <StopIcon className="w-4 h-4" />
                        </button>
                      )}
                      {(task.status === 'success' || task.status === 'failed' || task.status === 'stopped') && !tasks.some(t => t.status === 'processing') && (
                        <button
                          onClick={() => handleRestartTask(task.task_id)}
                          className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                          title={task.status === 'success' ? '重新运行' : '重跑'}
                        >
                          {task.status === 'success' ? <ArrowPathIcon className="w-4 h-4" /> : <PlayIcon className="w-4 h-4" />}
                        </button>
                      )}
                      {(task.status === 'success' || task.status === 'failed' || task.status === 'stopped') && (
                        <button
                          onClick={() => handleDeleteTask(task.task_id)}
                          className="p-1.5 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="删除任务"
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
                  <span className="text-xs text-ink/50">
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
                      className="text-xs text-gray-400 hover:text-ink/65 px-2 py-0.5 rounded hover:bg-gray-100 transition-colors"
                    >
                      关闭
                    </button>
                  </div>
                </div>
                <textarea
                  ref={logTextAreaRef}
                  className={clsx(
                    'w-full p-2 text-xs font-mono bg-gray-50 border border-gray-200 rounded-lg resize-none',
                    logsExpanded ? 'flex-1 min-h-0' : 'h-24'
                  )}
                  value={taskLogs.join('\n')}
                  readOnly
                  onScroll={handleLogScroll}
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Search Bar */}
      <div className="flex-shrink-0 px-6 py-3 border-b border-white/40 bg-white/60 backdrop-blur-sm">
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

      {/* Main Content: Two or three-column layout */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left: Accordion Sidebar */}
        <div
          ref={sidebarRef}
          className="flex-shrink-0 border-r border-white/40 bg-white/50 backdrop-blur-sm flex flex-col overflow-hidden"
          style={{ width: docListSidebarWidth }}
        >
          {/* Sidebar header */}
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200/30 flex-shrink-0">
            <span className="text-xs font-semibold text-ink/50 uppercase tracking-wider">文档</span>
          </div>

          {/* Sidebar content */}
          <div className="flex-1 overflow-y-auto py-1">
            {loadingDocuments && documents.length === 0 && (
              <div className="flex items-center justify-center py-8 text-ink/50">
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
                  : 'text-ink/80 hover:bg-gray-50/80'
              )}
            >
              <span className="flex items-center gap-2">
                <FolderIcon className="w-4 h-4 flex-shrink-0" />
                概览
              </span>
              <span className={clsx(
                'text-xs px-1.5 py-0.5 rounded-full',
                selectedDocId === null && !searchQuery ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-ink/50'
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
                    ? 'text-ink/80 hover:bg-gray-50/80'
                    : 'text-ink/80 hover:bg-gray-50/80'
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
                <span className="text-xs px-1.5 py-0.5 rounded-full bg-gray-100 text-ink/50">
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
                        : 'text-ink/80 hover:bg-gray-50/80'
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
                      isHighlighted && !searchQuery ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-ink/50'
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
            <div className="px-4 py-3 border-t border-white/40 flex-shrink-0">
              <button
                onClick={() => setDisplayLanguage(displayLanguage === 'source' ? 'zh' : 'source')}
                className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-ink/65 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
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

        {/* Left drag handle */}
        <div
          className="w-1 flex-shrink-0 hover:bg-blue-400/50 active:bg-accent/60 transition-colors cursor-col-resize"
          onMouseDown={handleLeftDragStart}
          title="拖动调整宽度"
        />

        {/* Middle: Detail Panel */}
        <div className="flex-1 flex flex-col overflow-hidden bg-gray-50/30">
          {showReader && selectedDoc ? (
            <DocReader
              key={selectedDoc.id}
              doc={{ id: selectedDoc.id, name: selectedDoc.name, nameTranslated: selectedDoc.nameTranslated, url: selectedDoc.url }}
              previewUrl={previewUrl}
              collectionId={currentKb.id}
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

        {/* Right: Doc Chat Sidebar */}
        <DocChatSidebar
          documentId={selectedDocId}
          chatId={boundChatId}
          isOpen={docChatSidebarOpen}
          onToggle={() => setDocChatSidebarOpen(!docChatSidebarOpen)}
          width={docChatSidebarWidth}
          onResize={setDocChatSidebarWidth}
        />
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

      {/* Recategorize Modal */}
      <Modal
        open={recategorizeModalOpen && !!currentKb}
        onClose={() => setRecategorizeModalOpen(false)}
        title="重新分类文档"
        size="sm"
        footer={
          <>
            <button
              type="button"
              onClick={() => setRecategorizeModalOpen(false)}
              className="px-4 py-2 text-sm text-ink/80 hover:text-ink rounded-lg transition-colors"
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleConfirmRecategorize}
              className="px-4 py-2 text-sm font-medium text-white bg-accent hover:bg-accent-hover rounded-lg transition-colors"
            >
              确认重新分类
            </button>
          </>
        }
      >
        {currentKb && (
          <div className="space-y-4">
            <p className="text-sm text-ink/65">
              选择分类方式后，系统将重新对知识库
              <span className="font-semibold text-ink">&nbsp;"{currentKb.name}"&nbsp;</span>
              中的所有文档进行分类。
            </p>
            <div>
              <label className="block text-sm font-medium text-ink/80 mb-2">
                分类方式
              </label>
              <div className="flex gap-3">
                <label className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors">
                  <input
                    type="radio"
                    name="recategorizeMode"
                    value="ai"
                    checked={recategorizeMode === 'ai'}
                    onChange={(e) => setRecategorizeMode(e.target.value)}
                    className="w-4 h-4 text-accent"
                  />
                  <span className="text-sm text-ink/80">AI 智能分类</span>
                </label>
                <label className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50 transition-colors">
                  <input
                    type="radio"
                    name="recategorizeMode"
                    value="path_prefix"
                    checked={recategorizeMode === 'path_prefix'}
                    onChange={(e) => setRecategorizeMode(e.target.value)}
                    className="w-4 h-4 text-accent"
                  />
                  <span className="text-sm text-ink/80">按路径前缀分类</span>
                </label>
              </div>
            </div>
          </div>
        )}
      </Modal>

      {/* Clear Collection Confirm Modal */}
      <Modal
        open={clearModalOpen && !!currentKb}
        onClose={() => { setClearModalOpen(false); setConfirmName('') }}
        title="清空知识库"
        size="sm"
        footer={
          <>
            <button
              type="button"
              onClick={() => { setClearModalOpen(false); setConfirmName('') }}
              className="px-4 py-2 text-sm text-ink/80 hover:text-ink rounded-lg transition-colors"
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleConfirmClear}
              disabled={confirmName !== currentKb?.name}
              className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              确认清空
            </button>
          </>
        }
      >
        {currentKb && (
          <div className="space-y-4">
            <p className="text-sm text-ink/65">
              此操作将删除知识库
              <span className="font-semibold text-ink">&nbsp;"{currentKb.name}"&nbsp;</span>
              中的所有文档、向量和任务数据，但保留知识库本身。
              此操作<span className="text-red-600 font-semibold">无法撤销</span>。
            </p>
            <div>
              <label className="block text-sm font-medium text-ink/80 mb-1">
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
        )}
      </Modal>

      {/* Delete Collection Confirm Modal */}
      <Modal
        open={deleteModalOpen && !!currentKb}
        onClose={() => { setDeleteModalOpen(false); setConfirmName('') }}
        title="删除知识库"
        size="sm"
        footer={
          <>
            <button
              type="button"
              onClick={() => { setDeleteModalOpen(false); setConfirmName('') }}
              className="px-4 py-2 text-sm text-ink/80 hover:text-ink rounded-lg transition-colors"
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleConfirmDelete}
              disabled={confirmName !== currentKb?.name}
              className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              确认删除
            </button>
          </>
        }
      >
        {currentKb && (
          <div className="space-y-4">
            <p className="text-sm text-ink/65">
              此操作将
              <span className="text-red-600 font-semibold">永久删除</span>
              知识库
              <span className="font-semibold text-ink">&nbsp;"{currentKb.name}"&nbsp;</span>
              及其所有文档、向量和任务数据。
              此操作<span className="text-red-600 font-semibold">无法撤销</span>。
            </p>
            <div>
              <label className="block text-sm font-medium text-ink/80 mb-1">
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
        )}
      </Modal>

      {/* Delete Task Confirm Modal */}
      <Modal
        open={deleteTaskModalOpen && !!taskToDeleteId}
        onClose={() => { setDeleteTaskModalOpen(false); setTaskToDeleteId(null); setCleanupDocsChecked(false) }}
        title="删除任务"
        size="sm"
        footer={
          <>
            <button
              type="button"
              onClick={() => { setDeleteTaskModalOpen(false); setTaskToDeleteId(null); setCleanupDocsChecked(false) }}
              className="px-4 py-2 text-sm text-ink/80 hover:text-ink rounded-lg transition-colors"
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleConfirmDeleteTask}
              className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
            >
              确认删除
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-sm text-ink/65">
            确定要删除该任务吗？任务记录及其日志将被
            <span className="text-red-600 font-semibold">永久删除</span>。
          </p>
          <label className="flex items-start space-x-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors">
            <input
              type="checkbox"
              checked={cleanupDocsChecked}
              onChange={e => setCleanupDocsChecked(e.target.checked)}
              className="mt-0.5 h-4 w-4 text-red-600 focus:ring-red-500 border-gray-300 rounded"
            />
            <div className="flex-1">
              <span className="text-sm text-ink/80">同时清理该任务下载的文档、向量和缓存</span>
            </div>
          </label>
        </div>
      </Modal>
    </div>
  )
}

export default KnowledgeBaseManagement
