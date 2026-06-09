/**
 * Knowledge base overview page with search and grid layout
 */

import React, { useState, useEffect, useRef } from 'react'
import {
  PlusIcon,
  MagnifyingGlassIcon,
  BookOpenIcon,
  ChatBubbleLeftRightIcon,
  CogIcon,
  CalendarIcon,
  DocumentIcon,
  ArrowPathIcon,
  EllipsisVerticalIcon,
  PencilIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import { useAPIClient, extractData, Collection, Task } from '../../services/apiClient'
import AddKnowledgeBaseModal from './AddKnowledgeBaseModal'
import CircularProgress from './CircularProgress'
import Modal from '../common/Modal'
import { toast } from '../../hooks/useToast'

interface KnowledgeBaseOverviewProps {
  className?: string
}

export const KnowledgeBaseOverview: React.FC<KnowledgeBaseOverviewProps> = ({
  className
}) => {
  const [searchQuery, setSearchQuery] = useState('')
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(true)
  const [reindexingId, setReindexingId] = useState<string | null>(null)
  const [activeTasks, setActiveTasks] = useState<Task[]>([])
  const [showRestartModal, setShowRestartModal] = useState(false)
  const [pendingRestartTasks, setPendingRestartTasks] = useState<Task[]>([])
  const [restarting, setRestarting] = useState(false)
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null)
  const [editingCollection, setEditingCollection] = useState<Collection | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [savingEdit, setSavingEdit] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const apiClient = useAPIClient()
  const RESTART_DISMISS_KEY = 'knowledge_restart_dismissed'

  const {
    knowledgeBases,
    setActiveKnowledgeBase,
    setActiveSidebarSection,
    addChatSession,
    setActiveChat,
    addKnowledgeBase,
    updateKnowledgeBase
  } = useAppStore()

  // Filter collections based on search query
  const filteredCollections = collections.filter((collection) =>
    collection.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (collection.description && collection.description.toLowerCase().includes(searchQuery.toLowerCase()))
  )
  
  // Load collections from API
  const loadCollections = async () => {
    try {
      setLoading(true)
      const response = await apiClient.listCollections(searchQuery || undefined)
      const data = extractData(response)
      setCollections(data.collections)
      
      // Sync collections to store as knowledge bases
      data.collections.forEach(collection => {
        const kb = {
          id: collection.id,
          name: collection.name,
          description: collection.description || '',
          documentCount: collection.document_count,
          createdAt: collection.created_at,
          sourceType: 'mixed' as const
        }
        
        // Add to store if not exists, or update if exists
        const existingKb = knowledgeBases.find(k => k.id === collection.id)
        if (!existingKb) {
          addKnowledgeBase(kb)
        } else {
          // Update existing knowledge base with latest data
          updateKnowledgeBase(collection.id, {
            name: kb.name,
            description: kb.description,
            documentCount: kb.documentCount
          })
        }
      })
    } catch (error) {
      console.error('加载知识库失败:', error)
    } finally {
      setLoading(false)
    }
  }
  
  // Load active tasks (pending/processing/failed) for all collections
  const loadActiveTasks = async () => {
    try {
      const response = await apiClient.listTasks(['pending', 'processing', 'failed'])
      const data = extractData(response)
      setActiveTasks(data.tasks)

      // Only failed tasks need user intervention to restart
      const needsRestart = data.tasks.filter((t: Task) => t.status === 'failed')
      if (needsRestart.length > 0 && !sessionStorage.getItem(RESTART_DISMISS_KEY)) {
        setPendingRestartTasks(needsRestart)
        setShowRestartModal(true)
      }
    } catch (error) {
      console.error('加载任务列表失败:', error)
    }
  }

  const handleRestartAll = async () => {
    try {
      setRestarting(true)
      await apiClient.restartPendingTasks()
      setShowRestartModal(false)
      // Clear dismiss flag so future failures can still prompt
      sessionStorage.removeItem(RESTART_DISMISS_KEY)
      await loadActiveTasks()
    } catch (error) {
      console.error('重启任务失败:', error)
      toast.error('重启任务失败: ' + (error as Error).message)
    } finally {
      setRestarting(false)
    }
  }

  const handleDismissRestart = () => {
    setShowRestartModal(false)
    sessionStorage.setItem(RESTART_DISMISS_KEY, 'true')
  }

  // Group active tasks by collection_id
  const getCollectionTasks = (collectionId: string): Task[] => {
    return activeTasks
      .filter(t => t.collection_id === collectionId)
      .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
  }

  // Load active tasks on mount
  useEffect(() => {
    loadActiveTasks()
  }, [])

  // Load collections on mount (via initial searchQuery=''), and debounce on search changes
  useEffect(() => {
    const timer = setTimeout(() => {
      loadCollections()
    }, 300)

    return () => clearTimeout(timer)
  }, [searchQuery])


  const handleManageClick = (collectionId: string) => {
    // Map collection to knowledge base format for compatibility
    const collection = collections.find(c => c.id === collectionId)
    if (collection) {
      // Store collection in app store as knowledge base
      const kb = {
        id: collection.id,
        name: collection.name,
        description: collection.description || '',
        documentCount: collection.document_count,
        createdAt: collection.created_at,
        sourceType: 'mixed' as const // Default value
      }
      
      // Add to store if not exists
      const existingKb = knowledgeBases.find(k => k.id === collection.id)
      if (!existingKb) {
        addKnowledgeBase(kb)
      }
      
      setActiveKnowledgeBase(collectionId)
    }
  }

  const handleReindex = async (collectionId: string) => {
    if (reindexingId) return
    setReindexingId(collectionId)
    try {
      await apiClient.reindexCollection(collectionId)
      await loadCollections()
    } catch (error) {
      console.error('触发重新索引失败:', error)
      toast.error('触发重新索引失败: ' + (error as Error).message)
    } finally {
      setReindexingId(null)
    }
  }

  const handleChatClick = async (collectionId: string) => {
    try {
      const collection = collections.find(c => c.id === collectionId)
      if (!collection) return
      
      // Create new chat via API
      const response = await apiClient.createChat({
        name: `与${collection.name}对话`,
        collection_ids: [collectionId]
      })
      
      const chat = extractData(response)
      
      // Add to app store for UI consistency
      const newChat = {
        id: chat.chat_id,
        name: chat.name,
        knowledgeBaseIds: chat.collection_ids,
        createdAt: chat.created_at,
        lastMessageAt: chat.created_at,
        messageCount: 0
      }
      
      addChatSession(newChat)
      setActiveChat(newChat.id)
      setActiveSidebarSection('chat')
    } catch (error) {
      console.error('创建聊天失败:', error)
      toast.error('创建聊天失败: ' + (error as Error).message)
    }
  }

  // Menu and edit handlers
  const handleToggleMenu = (e: React.MouseEvent, collectionId: string) => {
    e.stopPropagation()
    setMenuOpenId(menuOpenId === collectionId ? null : collectionId)
  }

  const handleStartEdit = (collection: Collection) => {
    setMenuOpenId(null)
    setEditingCollection(collection)
    setEditName(collection.name)
    setEditDescription(collection.description || '')
  }

  const handleConfirmEdit = async () => {
    if (!editingCollection) return
    const trimmedName = editName.trim()
    if (!trimmedName) return
    setSavingEdit(true)
    try {
      await apiClient.updateCollection(editingCollection.id, {
        name: trimmedName,
        description: editDescription.trim() || undefined,
      })
      // Update local state
      setCollections(prev =>
        prev.map(c =>
          c.id === editingCollection.id
            ? { ...c, name: trimmedName, description: editDescription.trim() || undefined }
            : c
        )
      )
      // Update store
      updateKnowledgeBase(editingCollection.id, {
        name: trimmedName,
        description: editDescription.trim() || '',
      })
      setEditingCollection(null)
    } catch (err) {
      console.error('Edit failed:', err)
      toast.error('编辑失败: ' + (err as Error).message)
    } finally {
      setSavingEdit(false)
    }
  }

  const handleCancelEdit = () => {
    setEditingCollection(null)
  }

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null)
      }
    }
    if (menuOpenId) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [menuOpenId])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  }

  return (
    <div className={clsx('h-full flex flex-col', className)}>
      {/* Header */}
      <div className="flex-shrink-0 p-6 bg-gradient-to-r from-white/90 to-white/70 backdrop-blur-sm border-b border-white/40">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-ink">知识库概览</h1>
            <p className="text-ink/65 mt-1">管理您的文档和知识库</p>
          </div>
          
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center space-x-2 bg-accent hover:bg-accent-hover text-white px-4 py-2 rounded-lg transition-colors shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
          >
            <PlusIcon className="w-4 h-4" />
            <span>添加知识库</span>
          </button>
        </div>

        {/* Search Bar */}
        <div className="relative">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="搜索知识库..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-3 bg-white/80 backdrop-blur-sm border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="bg-white/80 backdrop-blur-sm rounded-xl border border-white/40 overflow-hidden">
                <div className="p-4 pb-3 space-y-3">
                  <div className="flex items-center space-x-2">
                    <div className="w-5 h-5 rounded shimmer" />
                    <div className="h-4 rounded shimmer w-3/5" />
                  </div>
                  <div className="space-y-2">
                    <div className="h-3 rounded shimmer w-full" />
                    <div className="h-3 rounded shimmer w-4/5" />
                  </div>
                  <div className="space-y-2 pt-1">
                    <div className="h-3 rounded shimmer w-2/3" />
                    <div className="h-3 rounded shimmer w-1/2" />
                    <div className="h-3 rounded shimmer w-1/3" />
                  </div>
                </div>
                <div className="border-t border-white/40 px-4 py-3 bg-gray-50/50 flex space-x-2">
                  <div className="flex-1 h-8 rounded shimmer" />
                  <div className="flex-1 h-8 rounded shimmer" />
                  <div className="flex-1 h-8 rounded shimmer" />
                </div>
              </div>
            ))}
          </div>
        ) : filteredCollections.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-ink/50">
            {searchQuery ? (
              <>
                <MagnifyingGlassIcon className="w-16 h-16 mb-4 opacity-50" />
                <h3 className="text-lg font-medium mb-2">未找到匹配的知识库</h3>
                <p className="text-center">尝试使用不同的关键词搜索</p>
              </>
            ) : (
              <>
                <BookOpenIcon className="w-16 h-16 mb-4 opacity-50" />
                <h3 className="text-lg font-medium mb-2">暂无知识库</h3>
                <p className="text-center mb-4">创建您的第一个知识库来开始使用</p>
                <button
                  onClick={() => setIsAddModalOpen(true)}
                  className="flex items-center space-x-2 bg-accent hover:bg-accent-hover text-white px-4 py-2 rounded-lg transition-colors"
                >
                  <PlusIcon className="w-4 h-4" />
                  <span>创建知识库</span>
                </button>
              </>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {filteredCollections.map((collection, index) => (
              <div
                key={collection.id}
                className="bg-white/80 backdrop-blur-sm rounded-xl border border-white/40 overflow-hidden hover:-translate-y-px hover:shadow-lg hover:border-gray-300/50 transition-all duration-200 animate-card-in"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                {/* Card Header */}
                <div className="p-4 pb-3">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center space-x-2 min-w-0">
                      <BookOpenIcon className="w-5 h-5 text-blue-500 flex-shrink-0" />
                      <h3 className="font-semibold text-ink truncate">{collection.name}</h3>
                    </div>
                    <div className="flex items-center gap-1.5 ml-2 flex-shrink-0">
                      {/* More actions menu */}
                      <div className="relative" ref={menuOpenId === collection.id ? menuRef : undefined}>
                        <button
                          id={`kebab-menu-button-${collection.id}`}
                          onClick={(e) => handleToggleMenu(e, collection.id)}
                          aria-label="知识库操作菜单"
                          aria-haspopup="menu"
                          aria-expanded={menuOpenId === collection.id}
                          aria-controls={menuOpenId === collection.id ? `kebab-menu-${collection.id}` : undefined}
                          className="p-2 inline-flex items-center justify-center min-h-[44px] min-w-[44px] hover:bg-gray-100 rounded-lg transition-colors text-gray-400 hover:text-ink/65 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                          title="更多操作"
                        >
                          <EllipsisVerticalIcon className="w-4 h-4" />
                        </button>
                        {menuOpenId === collection.id && (
                          <div
                            id={`kebab-menu-${collection.id}`}
                            role="menu"
                            aria-label="知识库操作"
                            className="absolute right-0 mt-1 w-32 bg-white rounded-lg shadow-lg border border-white/40 py-1 z-50"
                          >
                            <button
                              role="menuitem"
                              tabIndex={-1}
                              onClick={() => handleStartEdit(collection)}
                              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink/80 hover:bg-gray-50 transition-colors focus-visible:outline-none focus-visible:bg-white focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-inset"
                            >
                              <PencilIcon className="w-3.5 h-3.5" />
                              编辑
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  <p className="text-sm text-ink/65 mb-3 line-clamp-2">
                    {collection.description || '暂无描述'}
                  </p>

                  {/* Metadata */}
                  <div className="space-y-2 text-xs text-ink/50">
                    <div className="flex items-center space-x-2">
                      <CalendarIcon className="w-3 h-3" />
                      <span>创建于 {formatDate(collection.created_at)}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <DocumentIcon className="w-3 h-3" />
                      <span>{collection.document_count} 个文档</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <div className="w-3 h-3 rounded-full bg-green-400" />
                        <span>知识库</span>
                      </div>
                      {(() => {
                        const tasks = getCollectionTasks(collection.id)
                        if (tasks.length === 0) return null
                        return (
                          <div className="flex items-center gap-2">
                            {tasks.map(task => {
                              const progress = typeof task.progress === 'number' ? task.progress : 0
                              const color = task.status === 'failed' ? '#ef4444' : task.status === 'pending' ? '#9ca3af' : '#3b82f6'
                              return (
                                <div key={task.task_id} className="flex items-center gap-1" title={task.title || (task.task_type === 'ingest_urls' ? '网页抓取' : '文件上传')}>
                                  <CircularProgress progress={progress} size={16} color={color} />
                                  <span className="text-[10px] text-ink/50">{progress}%</span>
                                </div>
                              )
                            })}
                          </div>
                        )
                      })()}
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="border-t border-white/40 px-4 py-3 bg-gray-50/50 flex space-x-2">
                  <button
                    onClick={() => handleManageClick(collection.id)}
                    className="flex-1 flex items-center justify-center space-x-1 py-2 px-3 min-h-[44px] bg-white hover:bg-gray-50 border border-gray-200 rounded-lg transition-colors text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                  >
                    <CogIcon className="w-3 h-3" />
                    <span>管理</span>
                  </button>

                  <button
                    onClick={() => handleChatClick(collection.id)}
                    className="flex-1 flex items-center justify-center space-x-1 py-2 px-3 min-h-[44px] bg-accent hover:bg-accent-hover text-white rounded-lg transition-colors text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
                  >
                    <ChatBubbleLeftRightIcon className="w-3 h-3" />
                    <span>聊天</span>
                  </button>

                  <button
                    onClick={() => handleReindex(collection.id)}
                    disabled={!collection.needs_reindex || reindexingId === collection.id}
                    className={clsx(
                      'flex items-center justify-center space-x-1 py-2 px-3 min-h-[44px] border rounded-lg transition-colors text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2',
                      collection.needs_reindex && reindexingId !== collection.id
                        ? 'bg-white hover:bg-amber-50 border-amber-300 text-amber-700'
                        : 'bg-gray-100 border-gray-200 text-gray-400 cursor-not-allowed'
                    )}
                    title={collection.needs_reindex ? '向量化参数已变更，点击重新索引' : '当前索引参数已是最新'}
                  >
                    <ArrowPathIcon className={clsx('w-3 h-3', reindexingId === collection.id && 'animate-spin')} />
                    <span>{reindexingId === collection.id ? '索引中' : '重新索引'}</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Knowledge Base Modal */}
      <AddKnowledgeBaseModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSuccess={loadCollections}
      />

      {/* Edit Collection Modal */}
      <Modal
        open={!!editingCollection}
        onClose={handleCancelEdit}
        title="编辑知识库"
        description="修改知识库的名称和描述"
        size="sm"
        footer={
          <>
            <button
              type="button"
              onClick={handleCancelEdit}
              className="px-4 py-2 text-sm text-ink/65 hover:text-ink/90 transition-colors"
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleConfirmEdit}
              disabled={savingEdit || !editName.trim()}
              className="px-4 py-2 text-sm bg-accent hover:bg-accent-hover text-white rounded-lg transition-colors disabled:opacity-50"
            >
              {savingEdit ? '保存中...' : '保存'}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1">名称</label>
            <input
              type="text"
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleConfirmEdit()
                if (e.key === 'Escape') handleCancelEdit()
              }}
              autoFocus
              className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-accent focus:border-transparent outline-none"
              placeholder="知识库名称"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1">描述</label>
            <textarea
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-accent focus:border-transparent outline-none resize-none"
              placeholder="知识库描述（可选）"
            />
          </div>
        </div>
      </Modal>

      {/* Restart Tasks Modal */}
      <Modal
        open={showRestartModal}
        onClose={handleDismissRestart}
        title="发现未完成任务"
        description={`有 ${pendingRestartTasks.length} 个任务需要继续处理，是否立即重启？`}
        size="sm"
        footer={
          <>
            <button
              type="button"
              onClick={handleDismissRestart}
              className="px-4 py-2 text-sm text-ink/65 hover:text-ink/90 transition-colors"
            >
              稍后
            </button>
            <button
              type="button"
              onClick={handleRestartAll}
              disabled={restarting}
              className="px-4 py-2 text-sm bg-accent hover:bg-accent-hover text-white rounded-lg transition-colors disabled:opacity-50"
            >
              {restarting ? '重启中...' : '重启所有'}
            </button>
          </>
        }
      >
        <div className="max-h-60 overflow-y-auto -mx-2 px-2">
          <div className="space-y-2">
            {pendingRestartTasks.map(task => {
              const collection = collections.find(c => c.id === task.collection_id)
              return (
                <div
                  key={task.task_id}
                  className="flex items-center gap-3 p-2 rounded-lg bg-gray-50 border border-gray-100"
                >
                  <div className={clsx(
                    'w-2.5 h-2.5 rounded-full flex-shrink-0',
                    task.status === 'processing' && 'bg-yellow-500 animate-pulse',
                    task.status === 'pending' && 'bg-gray-400',
                    task.status === 'failed' && 'bg-red-500'
                  )} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-ink/90 truncate">
                      {task.title || (task.task_type === 'ingest_urls' ? '网页抓取' : '文件上传')}
                    </div>
                    <div className="text-xs text-ink/50 truncate">
                      {collection?.name || '未知知识库'}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default KnowledgeBaseOverview