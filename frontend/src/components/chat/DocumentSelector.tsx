/**
 * Modal for selecting specific documents to use in chat context
 */

import React, { useState, useEffect } from 'react'
import { XMarkIcon, DocumentIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'
import { useAPIClient, extractData, Document } from '../../services/apiClient'
import { useAppStore } from '../../store/appStore'

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
  selectedDocumentIds: initialSelectedIds = []
}) => {
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const { getCurrentChat, knowledgeBases } = useAppStore()
  const apiClient = useAPIClient()

  const currentChat = getCurrentChat()

  // Reset selection when modal opens
  useEffect(() => {
    if (isOpen) {
      setSelectedIds([...initialSelectedIds])
      loadDocuments()
    }
  }, [isOpen, initialSelectedIds])

  const loadDocuments = async () => {
    if (!currentChat) return

    setLoading(true)
    try {
      const allDocuments: Document[] = []

      // Load documents from all collections associated with this chat
      for (const collectionId of currentChat.knowledgeBaseIds) {
        const response = await apiClient.listDocuments(collectionId, 1, 100)
        const data = extractData(response)
        allDocuments.push(...data.documents)
      }

      setDocuments(allDocuments)
    } catch (error) {
      console.error('Failed to load documents:', error)
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

  const getCollectionName = (doc: Document) => {
    // Find which collection this document belongs to
    // This is a simplified approach - in practice you might want to track this explicitly
    return currentChat?.knowledgeBaseIds
      .map(id => knowledgeBases.find(kb => kb.id === id)?.name)
      .find(Boolean) || '未知知识库'
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
        <div className="relative inline-block transform rounded-lg bg-white px-4 pt-5 pb-4 text-left align-bottom shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-2xl sm:p-6 sm:align-middle">
          <div className="absolute top-0 right-0 pt-4 pr-4">
            <button
              type="button"
              onClick={handleClose}
              className="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              <span className="sr-only">关闭</span>
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>

          <div className="sm:flex sm:items-start">
            <div className="mt-3 text-center sm:mt-0 sm:text-left w-full">
              <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
                选择特定文档
              </h3>

              {/* Search bar */}
              <div className="relative mb-4">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
                </div>
                <input
                  type="text"
                  placeholder="搜索文档..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                />
              </div>

              <div className="max-h-96 overflow-y-auto">
                {loading ? (
                  <div className="text-center text-gray-500 py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-2"></div>
                    <p>加载文档中...</p>
                  </div>
                ) : filteredDocuments.length === 0 ? (
                  <div className="text-center text-gray-500 py-8">
                    <DocumentIcon className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>{searchTerm ? '未找到匹配的文档' : '暂无文档'}</p>
                    {!searchTerm && (
                      <p className="text-sm mt-1">
                        请先向知识库添加文档
                      </p>
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
                            <span className="font-medium text-gray-900 truncate">{doc.name}</span>
                            <span className={`px-2 py-0.5 text-xs rounded-full ${
                              doc.status === 'indexed' ? 'bg-green-100 text-green-800' :
                              doc.status === 'processing' ? 'bg-yellow-100 text-yellow-800' :
                              doc.status === 'failed' ? 'bg-red-100 text-red-800' :
                              'bg-gray-100 text-gray-800'
                            }`}>
                              {doc.status === 'indexed' ? '已索引' :
                               doc.status === 'processing' ? '处理中' :
                               doc.status === 'failed' ? '失败' : '待处理'}
                            </span>
                          </div>
                          <p className="text-sm text-gray-500 mt-1 truncate">{doc.uri}</p>
                          <div className="flex items-center space-x-4 mt-1 text-xs text-gray-400">
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

              {filteredDocuments.length > 0 && (
                <div className="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse space-y-3 sm:space-y-0 sm:space-x-3 sm:space-x-reverse">
                  <button
                    type="button"
                    onClick={handleConfirm}
                    className="w-full inline-flex justify-center rounded-md border border-transparent bg-blue-600 px-4 py-2 text-base font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 sm:ml-3 sm:w-auto sm:text-sm"
                  >
                    确认 ({selectedIds.length} 个已选择)
                  </button>
                  <button
                    type="button"
                    onClick={handleClose}
                    className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-base font-medium text-gray-700 shadow-sm hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 sm:mt-0 sm:w-auto sm:text-sm"
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

export default DocumentSelector