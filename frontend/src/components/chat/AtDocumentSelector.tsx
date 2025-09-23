/**
 * @文档选择器 - 在输入框下方展开的文档选择组件
 */

import React, { useState, useEffect, useRef } from 'react'
import { DocumentIcon } from '@heroicons/react/24/outline'
import { useAPIClient, extractData, Document } from '../../services/apiClient'
import { useAppStore } from '../../store/appStore'

interface AtDocumentSelectorProps {
  isVisible: boolean
  onDocumentSelect: (document: Document) => void
  onClose: () => void
  searchTerm: string
  position: { top: number; left: number }
}

export const AtDocumentSelector: React.FC<AtDocumentSelectorProps> = ({
  isVisible,
  onDocumentSelect,
  onClose,
  searchTerm: initialSearchTerm,
  position
}) => {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [searchTerm, setSearchTerm] = useState('')
  const selectorRef = useRef<HTMLDivElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const { getCurrentChat } = useAppStore()
  const apiClient = useAPIClient()

  const currentChat = getCurrentChat()

  // 加载文档
  useEffect(() => {
    if (isVisible && currentChat) {
      loadDocuments()
      setSearchTerm(initialSearchTerm)
      setSelectedIndex(0) // 每次打开都从第一个开始
    }
  }, [isVisible, currentChat, initialSearchTerm])

  // 自动聚焦到搜索框
  useEffect(() => {
    if (isVisible && searchInputRef.current) {
      setTimeout(() => {
        searchInputRef.current?.focus()
        searchInputRef.current?.select()
      }, 100)
    }
  }, [isVisible])

  // 键盘导航
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!isVisible || filteredDocuments.length === 0) return

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setSelectedIndex(prev => Math.min(prev + 1, filteredDocuments.length - 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setSelectedIndex(prev => Math.max(prev - 1, 0))
        break
      case 'Enter':
        e.preventDefault()
        if (filteredDocuments[selectedIndex]) {
          onDocumentSelect(filteredDocuments[selectedIndex])
        }
        break
      case 'Escape':
        e.preventDefault()
        onClose()
        break
    }
  }

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

  const filteredDocuments = documents.filter(doc =>
    doc.name.toLowerCase().includes(searchTerm.toLowerCase())
  )

  // 重置选中索引当搜索词改变时
  useEffect(() => {
    setSelectedIndex(0)
  }, [searchTerm])

  // 滚动到选中的项目
  useEffect(() => {
    if (listRef.current && selectedIndex >= 0 && filteredDocuments.length > 0) {
      // 需要等待DOM更新后再滚动
      setTimeout(() => {
        const documentItems = listRef.current?.querySelectorAll('[data-document-item]')
        const selectedElement = documentItems?.[selectedIndex] as HTMLElement
        if (selectedElement) {
          selectedElement.scrollIntoView({
            behavior: 'smooth',
            block: 'nearest'
          })
        }
      }, 0)
    }
  }, [selectedIndex, filteredDocuments.length])

  if (!isVisible) return null

  return (
    <div
      ref={selectorRef}
      className="absolute z-50 left-0 w-2/3 bg-white rounded-lg shadow-lg border border-gray-200 max-h-64 overflow-hidden"
      style={{
        top: position.top
      }}
      onKeyDown={handleKeyDown}
    >
      {/* 搜索框 */}
      <div className="p-3 border-b border-gray-200">
        <input
          ref={searchInputRef}
          type="text"
          placeholder="搜索文档..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full px-3 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      {/* 文档列表 */}
      <div ref={listRef} className="max-h-48 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center text-gray-500">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500 mx-auto mb-2"></div>
            <p className="text-sm">加载中...</p>
          </div>
        ) : filteredDocuments.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <DocumentIcon className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">{searchTerm ? `未找到包含 "${searchTerm}" 的文档` : '暂无可用文档'}</p>
          </div>
        ) : (
          <div className="py-1">
            {filteredDocuments.map((doc, index) => (
              <button
                key={doc.id}
                data-document-item
                onClick={() => onDocumentSelect(doc)}
                className={`w-full px-3 py-2 text-left flex items-center space-x-2 transition-colors ${
                  index === selectedIndex
                    ? 'bg-blue-100 text-blue-900'
                    : 'hover:bg-gray-50 text-gray-900'
                }`}
              >
                <DocumentIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{doc.name}</div>
                  <div className="text-xs text-gray-500 truncate">{doc.uri}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 提示信息 */}
      {filteredDocuments.length > 0 && (
        <div className="px-3 py-2 bg-gray-50 border-t border-gray-200">
          <div className="text-xs text-gray-500">
            使用 ↑↓ 导航，Enter 选择，Esc 取消
          </div>
        </div>
      )}
    </div>
  )
}

export default AtDocumentSelector