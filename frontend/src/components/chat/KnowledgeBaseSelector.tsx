/**
 * Modal for selecting knowledge bases to add to chat — built on unified <Modal>.
 */

import React, { useState } from 'react'
import { BookOpenIcon } from '@heroicons/react/24/outline'
import { useAPIClient, extractData, Collection } from '../../services/apiClient'
import Modal from '../common/Modal'
import { toast } from '../../hooks/useToast'

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
  selectedIds: initialSelectedIds = [],
}) => {
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [collections, setCollections] = useState<Collection[]>([])
  const [loading, setLoading] = useState(false)
  const apiClient = useAPIClient()

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
          toast.error('加载知识库失败: ' + (error as Error).message)
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

  return (
    <Modal
      open={isOpen}
      onClose={handleClose}
      title="管理对话知识库"
      size="md"
      footer={
        !loading && availableKnowledgeBases.length > 0 ? (
          <>
            <button
              type="button"
              onClick={handleClose}
              className="px-4 py-2 text-sm text-ink/80 hover:text-ink rounded-lg transition-colors"
            >
              取消
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              className="px-4 py-2 text-sm font-medium text-white bg-accent hover:bg-accent-hover rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2"
            >
              确认 ({selectedIds.length} 个已选择)
            </button>
          </>
        ) : null
      }
    >
      <div className="max-h-64 overflow-y-auto -mx-2 px-2">
        {loading ? (
          <div className="text-center text-ink/50 py-8">
            <p>加载中...</p>
          </div>
        ) : availableKnowledgeBases.length === 0 ? (
          <div className="text-center text-ink/50 py-8">
            <BookOpenIcon className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>暂无知识库</p>
            <p className="text-sm mt-1">请先创建知识库</p>
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
                    <BookOpenIcon className="w-4 h-4 text-accent flex-shrink-0" />
                    <span className="font-medium text-ink">{kb.name}</span>
                  </div>
                  {kb.description && (
                    <p className="text-sm text-ink/50 mt-1">{kb.description}</p>
                  )}
                  <div className="flex items-center space-x-4 mt-1 text-xs text-ink/50">
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
    </Modal>
  )
}

export default KnowledgeBaseSelector
