/**
 * Modal for selecting specific documents to use in chat context —
 * built on unified <Modal>.
 */

import React, { useState, useEffect } from 'react'
import { DocumentIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { useAPIClient, extractData, Document } from '../../services/apiClient'
import { useAppStore } from '../../store/appStore'
import Modal from '../common/Modal'
import { toast } from '../../hooks/useToast'

interface DocumentSelectorProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (documentIds: string[]) => void
  selectedDocumentIds?: string[]
}

export const DocumentSelector: React.FC<DocumentSelectorProps> = ({
  isOpen,
  onClose,
  onSelect,
  selectedDocumentIds: initialSelectedIds = [],
}) => {
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const { getCurrentChat } = useAppStore()
  const apiClient = useAPIClient()

  const currentChat = getCurrentChat()

  useEffect(() => {
    if (isOpen) {
      setSelectedIds([...initialSelectedIds])
      loadDocuments()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, initialSelectedIds])

  const loadDocuments = async () => {
    if (!currentChat) return

    setLoading(true)
    try {
      const allDocuments: Document[] = []

      for (const collectionId of currentChat.knowledgeBaseIds) {
        const response = await apiClient.listDocuments(collectionId, 1, 100)
        const data = extractData(response)
        allDocuments.push(...data.documents)
      }

      setDocuments(allDocuments)
    } catch (error) {
      console.error('Failed to load documents:', error)
      toast.error('加载文档失败: ' + (error as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const handleToggleSelection = (docId: string) => {
    setSelectedIds(prev =>
      prev.includes(docId)
        ? prev.filter(id => id !== docId)
        : [...prev, docId]
    )
  }

  const handleConfirm = () => {
    onSelect(selectedIds)
    onClose()
  }

  const handleClose = () => {
    setSelectedIds([])
    setSearchTerm('')
    onClose()
  }

  const filteredDocuments = documents.filter(doc =>
    doc.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    doc.uri.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <Modal
      open={isOpen}
      onClose={handleClose}
      title="选择特定文档"
      size="lg"
      footer={
        filteredDocuments.length > 0 ? (
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
      {/* Search bar */}
      <div className="relative mb-4">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <MagnifyingGlassIcon className="h-5 w-5 text-ink/50" />
        </div>
        <input
          type="text"
          placeholder="搜索文档..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg leading-5 bg-white placeholder-ink/50 focus:outline-none focus:placeholder-ink/40 focus:ring-1 focus:ring-accent focus:border-accent sm:text-sm"
        />
      </div>

      <div className="max-h-96 overflow-y-auto -mx-2 px-2">
        {loading ? (
          <div className="text-center text-ink/50 py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent mx-auto mb-2"></div>
            <p>加载文档中...</p>
          </div>
        ) : filteredDocuments.length === 0 ? (
          <div className="text-center text-ink/50 py-8">
            <DocumentIcon className="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p>{searchTerm ? '未找到匹配的文档' : '暂无文档'}</p>
            {!searchTerm && (
              <p className="text-sm mt-1">请先向知识库添加文档</p>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredDocuments.map((doc) => (
              <label
                key={doc.id}
                className={`flex items-start space-x-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors ${
                  selectedIds.includes(doc.id) ? 'bg-blue-50 ring-1 ring-blue-200' : ''
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedIds.includes(doc.id)}
                  onChange={() => handleToggleSelection(doc.id)}
                  className="mt-0.5 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2">
                    <DocumentIcon className="w-4 h-4 text-green-500 flex-shrink-0" />
                    <span className="font-medium text-ink truncate">{doc.name}</span>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${
                      doc.status === 'indexed' ? 'bg-green-100 text-green-800' :
                      doc.status === 'processing' ? 'bg-yellow-100 text-yellow-800' :
                      doc.status === 'failed' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-ink/90'
                    }`}>
                      {doc.status === 'indexed' ? '已索引' :
                       doc.status === 'processing' ? '处理中' :
                       doc.status === 'failed' ? '失败' : '待处理'}
                    </span>
                  </div>
                  <p className="text-sm text-ink/50 mt-1 truncate">{doc.uri}</p>
                  <div className="flex items-center space-x-4 mt-1 text-xs text-ink/50">
                    <span>{(doc.size_bytes / 1024).toFixed(1)} KB</span>
                    <span>
                      {new Date(doc.created_at).toLocaleDateString('zh-CN')}
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

export default DocumentSelector
