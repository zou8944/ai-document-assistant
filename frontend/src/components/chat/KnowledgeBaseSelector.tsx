/**
 * Modal for selecting knowledge bases to add to chat
 */

import React, { useState } from 'react'
import { XMarkIcon, BookOpenIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAPIClient, extractData, Collection } from '../../services/apiClient'

interface KnowledgeBaseSelectorProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (kbIds: string[]) => void
  selectedIds?: string[]
}

export const KnowledgeBaseSelector: React.FC<KnowledgeBaseSelectorProps> = ({
  isOpen,
  onClose,
  onSelect,
  selectedIds: initialSelectedIds = []
}) => {
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(false)
  const apiClient = useAPIClient()

  // Reset selection and fetch latest collections from backend when modal opens.
  // We intentionally do NOT read from the persisted Zustand store here, because
  // the store keeps stale knowledge bases (collections deleted on the backend
  // remain in localStorage). The backend `collections` table is the source of
  // truth for what is currently available.
  React.useEffect(() => {
    if (!isOpen) return
    setSelectedIds([...initialSelectedIds])
    // initialSelectedIds is intentionally excluded from the dep array below to
    // avoid re-fetching when the parent re-renders with a new array reference.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen])

  React.useEffect(() => {
    if (!isOpen) return
    let cancelled = false
    const load = async () => {
      try {
        setLoading(true)
        const response = await apiClient.listCollections()
        const data = extractData(response)
        if (!cancelled) {
          setCollections(data.collections)
        }
      } catch (error) {
        console.error('加载知识库失败:', error)
        if (!cancelled) {
          setCollections([])
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [isOpen, apiClient])

  // Map backend collections to the shape the modal renders
  const availableKnowledgeBases = collections.map((collection) => ({
    id: collection.id,
    name: collection.name,
    description: collection.description || '',
    documentCount: collection.document_count,
    createdAt: collection.created_at,
  }))

  const handleToggleSelection = (kbId: string) => {
    setSelectedIds(prev => 
      prev.includes(kbId)
        ? prev.filter(id => id !== kbId)
        : [...prev, kbId]
    )
  }

  const handleConfirm = () => {
    onSelect(selectedIds)
    onClose()
  }

  const handleClose = () => {
    setSelectedIds([])
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-end justify-center px-4 pt-4 pb-20 text-center sm:block sm:p-0">
        {/* Backdrop — glass */}
        <div
          className="fixed inset-0 modal-backdrop animate-modal-backdrop"
          onClick={handleClose}
          aria-hidden="true"
        />

        {/* Modal panel */}
        <div className="relative inline-block modal-panel w-full max-w-lg mx-4 my-8 text-left overflow-hidden animate-modal-panel">
          <div className="px-6 pt-6 pb-2">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="section-label mb-1">Library</p>
                <h3 className="font-display text-2xl text-ink">
                  管理对话文库
                </h3>
                <p className="text-sm text-muted mt-1.5">
                  勾选要在当前对话中引用的文库
                </p>
              </div>
              <button
                type="button"
                onClick={handleClose}
                className="btn-ghost flex-shrink-0 -mt-1"
                aria-label="关闭"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            </div>
          </div>

          <div className="px-6 pt-4 pb-2 max-h-80 overflow-y-auto">
            {loading ? (
              <div className="text-center text-muted py-12">
                <div className="inline-block w-1.5 h-1.5 rounded-full bg-accent animate-breathe" />
                <p className="text-sm mt-3">加载中…</p>
              </div>
            ) : availableKnowledgeBases.length === 0 ? (
              <div className="text-center text-muted py-12">
                <div className="w-12 h-12 mx-auto mb-3 rounded-full accent-tile flex items-center justify-center">
                  <BookOpenIcon className="w-5 h-5 text-accent" />
                </div>
                <p className="font-display italic text-ink-soft">暂无文库</p>
                <p className="text-xs mt-1">请先在文库概览页创建一个</p>
              </div>
            ) : (
              <div className="space-y-1.5">
                {availableKnowledgeBases.map((kb) => {
                  const isSelected = selectedIds.includes(kb.id)
                  return (
                    <label
                      key={kb.id}
                      className={clsx(
                        'flex items-start gap-3 p-3 rounded-lg-editorial cursor-pointer transition-all',
                        isSelected
                          ? 'accent-tile shadow-sm'
                          : 'hover:bg-paper-warm/60 border border-transparent hover:border-paper-edge/60'
                      )}
                    >
                      <div className="flex-shrink-0 mt-0.5">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleToggleSelection(kb.id)}
                          className="sr-only"
                        />
                        <div className={clsx(
                          'w-4 h-4 rounded border-2 flex items-center justify-center transition-all',
                          isSelected
                            ? 'bg-accent border-accent'
                            : 'border-paper-edge bg-white'
                        )}>
                          {isSelected && (
                            <svg viewBox="0 0 12 12" className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" strokeWidth="2.5">
                              <polyline points="2,6.5 5,9 10,3" />
                            </svg>
                          )}
                        </div>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <BookOpenIcon className={clsx(
                            'w-3.5 h-3.5 flex-shrink-0',
                            isSelected ? 'text-accent' : 'text-muted'
                          )} />
                          <span className={clsx(
                            'font-display text-[17px] truncate',
                            isSelected ? 'text-accent-deep font-medium' : 'text-ink'
                          )}>{kb.name}</span>
                        </div>
                        {kb.description && (
                          <p className={clsx(
                            'text-sm mt-0.5 line-clamp-1',
                            isSelected ? 'text-accent-deep/80' : 'text-ink-soft'
                          )}>{kb.description}</p>
                        )}
                        <div className={clsx(
                          'flex items-center gap-3 mt-1 text-[11px] tracking-wide',
                          isSelected ? 'text-accent-deep/70' : 'text-muted'
                        )}>
                          <span className="tabular-nums">{kb.documentCount} 文档</span>
                          <span>·</span>
                          <span>{new Date(kb.createdAt).toLocaleDateString('zh-CN')}</span>
                        </div>
                      </div>
                    </label>
                  )
                })}
              </div>
            )}
          </div>

          {!loading && availableKnowledgeBases.length > 0 && (
            <div className="px-6 py-4 mt-2 border-t border-paper-edge/60 flex items-center justify-between gap-3">
              <span className="text-xs text-muted">
                已选 <span className="text-accent font-medium tabular-nums">{selectedIds.length}</span> / {availableKnowledgeBases.length}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleClose}
                  className="btn-ghost"
                >
                  取消
                </button>
                <button
                  type="button"
                  onClick={handleConfirm}
                  className="btn-primary"
                >
                  确认
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default KnowledgeBaseSelector