/**
 * 文档选择器 - 输入框上方的小型弹窗组件
 */

import React, { useState, useRef, useEffect } from 'react'
import { PlusIcon, XMarkIcon, DocumentIcon, ChevronDownIcon, ChevronUpIcon } from '@heroicons/react/24/outline'
import { useAPIClient, extractData, Document } from '../../services/apiClient'
import { useAppStore } from '../../store/appStore'

interface DocumentPickerProps {
  selectedDocumentIds: string[]
  onDocumentSelect: (documentIds: string[]) => void
}

export const DocumentPicker: React.FC<DocumentPickerProps> = ({
  selectedDocumentIds,
  onDocumentSelect
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const [isExpanded, setIsExpanded] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const { getCurrentChat } = useAppStore()
  const apiClient = useAPIClient()

  const currentChat = getCurrentChat()

  // 点击外部关闭下拉框
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // 加载文档
  const loadDocuments = async () => {
    if (!currentChat) return

    setLoading(true)
    try {
      const allDocuments: Document[] = []

      for (const collectionId of currentChat.knowledgeBaseIds) {
        const response = await apiClient.listDocuments(collectionId, 1, 100)
        const data = extractData(response)
        allDocuments.push(...data.documents.filter(doc => doc.status === 'indexed'))
      }

      setDocuments(allDocuments)
    } catch (error) {
      console.error('Failed to load documents:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleToggleDropdown = () => {
    if (!isOpen) {
      loadDocuments()
    }
    setIsOpen(!isOpen)
  }

  const handleDocumentToggle = (docId: string) => {
    const newSelectedIds = selectedDocumentIds.includes(docId)
      ? selectedDocumentIds.filter(id => id !== docId)
      : [...selectedDocumentIds, docId]

    onDocumentSelect(newSelectedIds)
  }

  const handleRemoveDocument = (docId: string) => {
    onDocumentSelect(selectedDocumentIds.filter(id => id !== docId))
  }

  const filteredDocuments = documents.filter(doc =>
    doc.name.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const selectedDocuments = documents.filter(doc => selectedDocumentIds.includes(doc.id))
  const displayedDocuments = isExpanded ? selectedDocuments : selectedDocuments.slice(0, 2)
  const hasMoreDocuments = selectedDocuments.length > 2

  return (
    <div className="relative" ref={dropdownRef}>
      {/* 文档选择器触发按钮和已选文档展示 */}
      <div className="flex items-center space-x-2 mb-2">
        <button
          onClick={handleToggleDropdown}
          className={`w-6 h-6 rounded-full border-2 border-dashed flex items-center justify-center transition-colors ${
            isOpen ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
          }`}
        >
          <PlusIcon className={`w-3 h-3 ${isOpen ? 'text-blue-500' : 'text-gray-400'}`} />
        </button>

        {/* 已选文档展示 */}
        {selectedDocuments.length > 0 && (
          <div className="flex flex-col space-y-1">
            <div className="flex items-center flex-wrap gap-1">
              {displayedDocuments.map((doc) => (
                <div
                  key={doc.id}
                  className="inline-flex items-center space-x-1 bg-blue-100 text-blue-800 px-2 py-1 rounded-full text-xs max-w-full"
                >
                  <DocumentIcon className="w-3 h-3 flex-shrink-0" />
                  <span className="truncate" title={doc.name}>{doc.name}</span>
                  <button
                    onClick={() => handleRemoveDocument(doc.id)}
                    className="text-blue-600 hover:text-blue-800 flex-shrink-0"
                  >
                    <XMarkIcon className="w-3 h-3" />
                  </button>
                </div>
              ))}
            </div>

            {hasMoreDocuments && (
              <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="inline-flex items-center space-x-1 text-xs text-gray-500 hover:text-gray-700 self-start"
              >
                <span>{isExpanded ? '收起' : `+${selectedDocuments.length - 2}个`}</span>
                {isExpanded ? (
                  <ChevronUpIcon className="w-3 h-3" />
                ) : (
                  <ChevronDownIcon className="w-3 h-3" />
                )}
              </button>
            )}
          </div>
        )}
      </div>

      {/* 文档选择下拉框 */}
      {isOpen && (
        <div className="absolute bottom-full left-0 z-10 w-2/3 bg-white rounded-lg shadow-lg border border-gray-200 max-h-64 overflow-hidden mb-2">
          {/* 搜索框 */}
          <div className="p-3 border-b border-gray-200">
            <input
              type="text"
              placeholder="搜索文档..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* 文档列表 */}
          <div className="max-h-48 overflow-y-auto">
            {loading ? (
              <div className="p-4 text-center text-gray-500">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500 mx-auto mb-2"></div>
                <p className="text-sm">加载中...</p>
              </div>
            ) : filteredDocuments.length === 0 ? (
              <div className="p-4 text-center text-gray-500">
                <DocumentIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">{searchTerm ? '未找到匹配的文档' : '暂无可用文档'}</p>
              </div>
            ) : (
              <div className="py-1">
                {filteredDocuments.map((doc) => (
                  <button
                    key={doc.id}
                    onClick={() => handleDocumentToggle(doc.id)}
                    className={`w-full px-3 py-2 text-left hover:bg-gray-50 flex items-center space-x-2 ${
                      selectedDocumentIds.includes(doc.id) ? 'bg-blue-50' : ''
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={selectedDocumentIds.includes(doc.id)}
                      onChange={() => {}}
                      className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <DocumentIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-gray-900 truncate">{doc.name}</div>
                      <div className="text-xs text-gray-500 truncate">{doc.uri}</div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default DocumentPicker