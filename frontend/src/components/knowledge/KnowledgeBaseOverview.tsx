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
      alert('重启任务失败: ' + (error as Error).message)
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

  // Load collections on component mount and when search query changes
  useEffect(() => {
    loadCollections()
    loadActiveTasks()
  }, [])
  
  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      loadCollections()
    }, 500)

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
      alert('触发重新索引失败: ' + (error as Error).message)
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
      alert('创建聊天失败: ' + (error as Error).message)
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
      alert('编辑失败: ' + (err as Error).message)
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
      <div className="flex-shrink-0 px-8 py-7 border-b border-paper-edge/60 surface-glass">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-end justify-between mb-6 gap-6">
            <div>
              <p className="section-label mb-1.5">Library</p>
              <h1 className="editorial-display text-4xl md:text-5xl text-ink">
                文库概览
              </h1>
              <p className="mt-2 text-ink-soft text-sm max-w-md">
                管理你的文档集合 — 把文件、网页、知识沉淀为可对话的档案。
              </p>
            </div>

            <button
              onClick={() => setIsAddModalOpen(true)}
              className="btn-primary flex-shrink-0"
            >
              <PlusIcon className="w-4 h-4" />
              <span>新建文库</span>
            </button>
          </div>

          {/* Search Bar */}
          <div className="relative max-w-xl">
            <MagnifyingGlassIcon className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted pointer-events-none" />
            <input
              type="text"
              placeholder="按名称或描述搜索文库…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field pl-10"
            />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-6xl mx-auto">
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 reveal-stagger">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="library-card p-5 space-y-3">
                <div className="flex items-center space-x-2">
                  <div className="w-5 h-5 rounded shimmer" />
                  <div className="h-4 rounded shimmer w-3/5" />
                </div>
                <div className="space-y-2">
                  <div className="h-3 rounded shimmer w-full" />
                  <div className="h-3 rounded shimmer w-4/5" />
                </div>
                <div className="pt-3 mt-1 border-t border-paper-edge/40 flex gap-3">
                  <div className="h-3 rounded shimmer w-16" />
                  <div className="h-3 rounded shimmer w-12" />
                </div>
              </div>
            ))}
          </div>
        ) : filteredCollections.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-72 text-muted">
            {searchQuery ? (
              <>
                <MagnifyingGlassIcon className="w-12 h-12 mb-4 opacity-50" />
                <h3 className="font-display text-xl italic text-ink-soft mb-1.5">未找到匹配</h3>
                <p className="text-sm">尝试不同的关键词</p>
              </>
            ) : (
              <>
                <div className="w-16 h-16 mb-5 rounded-full accent-tile flex items-center justify-center">
                  <BookOpenIcon className="w-7 h-7 text-accent" />
                </div>
                <h3 className="font-display text-2xl italic text-ink mb-2">尚无文库</h3>
                <p className="text-sm mb-5">创建第一个文库，开始与文档对话</p>
                <button
                  onClick={() => setIsAddModalOpen(true)}
                  className="btn-primary"
                >
                  <PlusIcon className="w-4 h-4" />
                  <span>创建文库</span>
                </button>
              </>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 reveal-stagger">
            {filteredCollections.map((collection) => (
              <div key={collection.id} className="library-card group p-5 flex flex-col">
                {/* Header */}
                <div className="flex items-start justify-between gap-2 mb-2.5">
                  <div className="flex items-start gap-2.5 min-w-0 flex-1">
                    <div className="w-9 h-9 flex-shrink-0 rounded-md accent-tile flex items-center justify-center">
                      <BookOpenIcon className="w-4 h-4 text-accent" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="font-display text-[20px] font-medium leading-tight text-ink truncate">
                        {collection.name}
                      </h3>
                      <p className="section-label mt-0.5 text-muted-soft">collection</p>
                    </div>
                  </div>
                  <div className="flex items-center flex-shrink-0">
                    <div className="relative" ref={menuOpenId === collection.id ? menuRef : undefined}>
                      <button
                        onClick={(e) => handleToggleMenu(e, collection.id)}
                        className="p-1.5 rounded-md text-muted hover:text-ink hover:bg-paper-warm/60 transition-colors opacity-0 group-hover:opacity-100 focus:opacity-100"
                        title="更多操作"
                      >
                        <EllipsisVerticalIcon className="w-4 h-4" />
                      </button>
                      {menuOpenId === collection.id && (
                        <div className="absolute right-0 mt-1 w-32 modal-panel py-1 z-50 overflow-hidden">
                          <button
                            onClick={() => handleStartEdit(collection)}
                            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-ink hover:bg-paper-warm transition-colors"
                          >
                            <PencilIcon className="w-3.5 h-3.5 text-muted" />
                            编辑
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Description */}
                <p className="text-sm text-ink-soft line-clamp-2 mb-4 leading-relaxed min-h-[2.5rem]">
                  {collection.description || <span className="italic text-muted-soft">未添加描述</span>}
                </p>

                {/* Metadata row */}
                <div className="mt-auto pt-3 border-t border-paper-edge/40 flex items-center justify-between gap-3 text-xs text-muted">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="flex items-center gap-1.5 flex-shrink-0">
                      <DocumentIcon className="w-3 h-3" />
                      <span className="font-medium text-ink-soft tabular-nums">{collection.document_count}</span>
                      <span>文档</span>
                    </span>
                    <span className="flex items-center gap-1.5 min-w-0">
                      <CalendarIcon className="w-3 h-3 flex-shrink-0" />
                      <span className="truncate">{formatDate(collection.created_at)}</span>
                    </span>
                  </div>
                  {(() => {
                    const tasks = getCollectionTasks(collection.id)
                    if (tasks.length === 0) {
                      return (
                        <span className="flex items-center gap-1.5 text-sage flex-shrink-0">
                          <span className="w-1.5 h-1.5 rounded-full bg-sage" />
                          <span>就绪</span>
                        </span>
                      )
                    }
                    return (
                      <div className="flex items-center gap-2 flex-shrink-0">
                        {tasks.map(task => {
                          const progress = typeof task.progress === 'number' ? task.progress : 0
                          const color = task.status === 'failed' ? '#C73E1D' : task.status === 'pending' ? '#8E8E93' : '#007AFF'
                          return (
                            <div key={task.task_id} className="flex items-center gap-1" title={task.title || (task.task_type === 'ingest_urls' ? '网页抓取' : '文件上传')}>
                              <CircularProgress progress={progress} size={14} color={color} />
                              <span className="text-[10px] tabular-nums">{progress}%</span>
                            </div>
                          )
                        })}
                      </div>
                    )
                  })()}
                </div>

                {/* Actions — primary chat, secondary management */}
                <div className="mt-4 flex items-center gap-2">
                  <button
                    onClick={() => handleChatClick(collection.id)}
                    className="btn-primary flex-1 !py-2"
                  >
                    <ChatBubbleLeftRightIcon className="w-3.5 h-3.5" />
                    <span>开始对话</span>
                  </button>
                  <button
                    onClick={() => handleManageClick(collection.id)}
                    className="btn-secondary !p-2.5"
                    title="管理文档"
                  >
                    <CogIcon className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => handleReindex(collection.id)}
                    disabled={!collection.needs_reindex || reindexingId === collection.id}
                    className={clsx(
                      'btn-secondary !p-2.5',
                      !collection.needs_reindex && '!opacity-40 !cursor-not-allowed hover:!bg-white/70 hover:!transform-none',
                      reindexingId === collection.id && '!opacity-60'
                    )}
                    title={collection.needs_reindex ? '向量化参数已变更，点击重新索引' : '当前索引参数已是最新'}
                  >
                    <ArrowPathIcon className={clsx('w-3.5 h-3.5', reindexingId === collection.id && 'animate-spin')} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        </div>
      </div>

      {/* Add Knowledge Base Modal */}
      <AddKnowledgeBaseModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSuccess={loadCollections}
      />

      {/* Edit Collection Modal */}
      {editingCollection && (
        <div className="fixed inset-0 z-50 flex items-center justify-center modal-backdrop animate-modal-backdrop" onClick={handleCancelEdit}>
          <div className="modal-panel w-full max-w-md mx-4 animate-modal-panel" onClick={(e) => e.stopPropagation()}>
            <div className="px-6 pt-6 pb-4">
              <p className="section-label mb-1">Collection</p>
              <h2 className="font-display text-2xl text-ink">编辑文库</h2>
              <p className="text-sm text-muted mt-1">修改文库的名称和描述</p>
            </div>
            <div className="px-6 pb-2 space-y-4">
              <div>
                <label className="block section-label mb-1.5">名称</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleConfirmEdit()
                    if (e.key === 'Escape') handleCancelEdit()
                  }}
                  autoFocus
                  className="input-field"
                  placeholder="文库名称"
                />
              </div>
              <div>
                <label className="block section-label mb-1.5">描述</label>
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={3}
                  className="input-field resize-none"
                  placeholder="文库描述（可选）"
                />
              </div>
            </div>
            <div className="px-6 py-4 mt-2 border-t border-paper-edge/60 flex justify-end gap-2">
              <button
                onClick={handleCancelEdit}
                className="btn-ghost"
              >
                取消
              </button>
              <button
                onClick={handleConfirmEdit}
                disabled={savingEdit || !editName.trim()}
                className="btn-primary"
              >
                {savingEdit ? '保存中…' : '保存'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Restart Tasks Modal */}
      {showRestartModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center modal-backdrop animate-modal-backdrop" onClick={handleDismissRestart}>
          <div className="modal-panel w-full max-w-md mx-4 animate-modal-panel" onClick={(e) => e.stopPropagation()}>
            <div className="px-6 pt-6 pb-4">
              <p className="section-label mb-1">Tasks</p>
              <h2 className="font-display text-2xl text-ink">发现未完成任务</h2>
              <p className="text-sm text-muted mt-1.5">
                有 <span className="text-accent font-medium tabular-nums">{pendingRestartTasks.length}</span> 个任务需要继续处理，是否立即重启？
              </p>
            </div>
            <div className="px-6 pb-2 max-h-60 overflow-y-auto">
              <div className="space-y-1.5">
                {pendingRestartTasks.map(task => {
                  const collection = collections.find(c => c.id === task.collection_id)
                  return (
                    <div
                      key={task.task_id}
                      className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-paper-warm/50 border border-paper-edge/60"
                    >
                      <div className={clsx(
                        'w-2 h-2 rounded-full flex-shrink-0',
                        task.status === 'processing' && 'bg-rust animate-pulse',
                        task.status === 'pending' && 'bg-muted',
                        task.status === 'failed' && 'bg-crimson'
                      )} />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-ink truncate">
                          {task.title || (task.task_type === 'ingest_urls' ? '网页抓取' : '文件上传')}
                        </div>
                        <div className="text-xs text-muted truncate italic">
                          {collection?.name || '未知文库'}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
            <div className="px-6 py-4 mt-2 border-t border-paper-edge/60 flex justify-end gap-2">
              <button
                onClick={handleDismissRestart}
                className="btn-ghost"
              >
                稍后
              </button>
              <button
                onClick={handleRestartAll}
                disabled={restarting}
                className="btn-primary"
              >
                {restarting ? '重启中…' : '重启所有'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default KnowledgeBaseOverview