/**
 * Modal for selecting knowledge bases to add to chat
 */

import React, { useState } from 'react'
import { XMarkIcon, BookOpenIcon } from '@heroicons/react/24/outline'
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
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity backdrop-blur-sm"
          onClick={handleClose}
        />

        {/* Modal positioning helper */}
        <span className="hidden sm:inline-block sm:h-screen sm:align-middle" aria-hidden="true">
          &#8203;
        </span>

        {/* Modal panel */}
        <div className="relative inline-block transform rounded-lg bg-white px-4 pt-5 pb-4 text-left align-bottom shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6 sm:align-middle">
          <div className="absolute top-0 right-0 pt-4 pr-4">
            <button
              type="button"
              onClick={handleClose}
              className="rounded-lg bg-white text-gray-400 hover:text-ink/50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              <span className="sr-only">关闭</span>
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>

          <div className="sm:flex sm:items-start">
            <div className="mt-3 text-center sm:mt-0 sm:text-left w-full">
              <h3 className="text-lg font-medium leading-6 text-ink mb-4">
                管理对话知识库
              </h3>

              <div className="max-h-64 overflow-y-auto">
                {loading ? (
                  <div className="text-center text-ink/50 py-8">
                    <p>加载中...</p>
                  </div>
                ) : availableKnowledgeBases.length === 0 ? (
                  <div className="text-center text-ink/50 py-8">
                    <BookOpenIcon className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>暂无知识库</p>
                    <p className="text-sm mt-1">
                      请先创建知识库
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {availableKnowledgeBases.map((kb) => (
                      <label
                        key={kb.id}
                        className={`flex items-start space-x-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors ${
                          selectedIds.includes(kb.id) ? 'bg-blue-50 ring-1 ring-blue-200' : ''
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(kb.id)}
                          onChange={() => handleToggleSelection(kb.id)}
                          className="mt-0.5 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center space-x-2">
                            <BookOpenIcon className="w-4 h-4 text-blue-500 flex-shrink-0" />
                            <span className="font-medium text-ink">{kb.name}</span>
                          </div>
                          {kb.description && (
                            <p className="text-sm text-ink/50 mt-1">{kb.description}</p>
                          )}
                          <div className="flex items-center space-x-4 mt-1 text-xs text-gray-400">
                            <span>{kb.documentCount} 个文档</span>
                            <span>
                              {new Date(kb.createdAt).toLocaleDateString('zh-CN')}
                            </span>
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                )}
              </div>

              {!loading && availableKnowledgeBases.length > 0 && (
                <div className="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse space-y-3 sm:space-y-0 sm:space-x-3 sm:space-x-reverse">
                  <button
                    type="button"
                    onClick={handleConfirm}
                    className="w-full inline-flex justify-center rounded-lg border border-transparent bg-accent-hover px-4 py-2 text-base font-medium text-white shadow-sm hover:bg-accent-active focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 sm:ml-3 sm:w-auto sm:text-sm"
                  >
                    确认 ({selectedIds.length} 个已选择)
                  </button>
                  <button
                    type="button"
                    onClick={handleClose}
                    className="mt-3 w-full inline-flex justify-center rounded-lg border border-gray-300 bg-white px-4 py-2 text-base font-medium text-ink/80 shadow-sm hover:text-ink/50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 sm:mt-0 sm:w-auto sm:text-sm"
                  >
                    取消
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default KnowledgeBaseSelector