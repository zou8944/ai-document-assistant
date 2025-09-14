/**
 * Knowledge base overview page with search and grid layout
 */

import React, { useState, useEffect } from 'react'
import {
  PlusIcon,
  MagnifyingGlassIcon,
  BookOpenIcon,
  ChatBubbleLeftRightIcon,
  CogIcon,
  CalendarIcon,
  DocumentIcon,
  TrashIcon
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import { useAPIClient, extractData, Collection } from '../../services/apiClient'
import AddKnowledgeBaseModal from './AddKnowledgeBaseModal'

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
  const apiClient = useAPIClient()
  
  const {
    knowledgeBases,
    setActiveKnowledgeBase,
    setActiveSidebarSection,
    addChatSession,
    setActiveChat,
    addKnowledgeBase,
    updateKnowledgeBase,
    deleteKnowledgeBase
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
  
  // Load collections on component mount and when search query changes
  useEffect(() => {
    loadCollections()
  }, [])
  
  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery !== '') {
        loadCollections()
      }
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

  const handleDeleteClick = async (collectionId: string) => {
    const collection = collections.find(c => c.id === collectionId)
    if (!collection) return
    
    if (confirm(`确定要删除知识库 "${collection.name}" 吗？\n\n此操作将永久删除知识库及其所有文档，无法恢复。`)) {
      try {
        await apiClient.deleteCollection(collectionId)
        // Remove from local state
        setCollections(prev => prev.filter(c => c.id !== collectionId))
        // Remove from app store
        deleteKnowledgeBase(collectionId)
        console.log('知识库删除成功:', collection.name)
      } catch (error) {
        console.error('删除知识库失败:', error)
        alert('删除知识库失败: ' + (error as Error).message)
      }
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  }

  const getSourceTypeLabel = (sourceType: string) => {
    switch (sourceType) {
      case 'files': return '本地文件'
      case 'website': return '网站内容'
      case 'mixed': return '混合来源'
      default: return '未知来源'
    }
  }

  return (
    <div className={clsx('h-full flex flex-col', className)}>
      {/* Header */}
      <div className="flex-shrink-0 p-6 bg-gradient-to-r from-white/90 to-white/70 backdrop-blur-sm border-b border-gray-200/50">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">知识库概览</h1>
            <p className="text-gray-600 mt-1">管理您的文档和知识库</p>
          </div>
          
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center space-x-2 bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors shadow-md"
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
          <div className="flex items-center justify-center h-64">
            <div className="text-gray-500">加载中...</div>
          </div>
        ) : filteredCollections.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-500">
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
                  className="flex items-center space-x-2 bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  <PlusIcon className="w-4 h-4" />
                  <span>创建知识库</span>
                </button>
              </>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {filteredCollections.map((collection) => (
              <div
                key={collection.id}
                className="bg-white/80 backdrop-blur-sm rounded-xl border border-gray-200/50 hover:border-gray-300/50 hover:shadow-lg transition-all duration-200 overflow-hidden"
              >
                {/* Card Header */}
                <div className="p-4 pb-3">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center space-x-2">
                      <BookOpenIcon className="w-5 h-5 text-blue-500" />
                      <h3 className="font-semibold text-gray-900 truncate">{collection.name}</h3>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteClick(collection.id)
                      }}
                      className="p-1 hover:bg-red-50 rounded transition-colors group"
                      title="删除知识库"
                    >
                      <TrashIcon className="w-4 h-4 text-gray-400 group-hover:text-red-500" />
                    </button>
                  </div>
                  
                  <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                    {collection.description || '暂无描述'}
                  </p>

                  {/* Metadata */}
                  <div className="space-y-2 text-xs text-gray-500">
                    <div className="flex items-center space-x-2">
                      <CalendarIcon className="w-3 h-3" />
                      <span>创建于 {formatDate(collection.created_at)}</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <DocumentIcon className="w-3 h-3" />
                      <span>{collection.document_count} 个文档</span>
                    </div>
                    <div className="flex items-center space-x-2">
                      <div className="w-3 h-3 rounded-full bg-green-400" />
                      <span>知识库</span>
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="border-t border-gray-200/50 px-4 py-3 bg-gray-50/50 flex space-x-2">
                  <button
                    onClick={() => handleManageClick(collection.id)}
                    className="flex-1 flex items-center justify-center space-x-1 py-2 px-3 bg-white hover:bg-gray-50 border border-gray-200 rounded-md transition-colors text-sm"
                  >
                    <CogIcon className="w-3 h-3" />
                    <span>管理</span>
                  </button>
                  
                  <button
                    onClick={() => handleChatClick(collection.id)}
                    className="flex-1 flex items-center justify-center space-x-1 py-2 px-3 bg-blue-500 hover:bg-blue-600 text-white rounded-md transition-colors text-sm"
                  >
                    <ChatBubbleLeftRightIcon className="w-3 h-3" />
                    <span>聊天</span>
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
    </div>
  )
}

export default KnowledgeBaseOverview