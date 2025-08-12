/**
 * Knowledge base management page with import area and document list
 */

import React, { useState } from 'react'
import {
  ArrowLeftIcon,
  CloudArrowUpIcon,
  DocumentIcon,
  GlobeAltIcon,
  FolderIcon,
  ArrowDownTrayIcon,
  TrashIcon
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import { Document, ImportProgress } from '../../types/app'

interface KnowledgeBaseManagementProps {
  className?: string
}

// Mock documents data - replace with real data
const mockDocuments: Document[] = [
  {
    id: '1',
    name: 'user_guide.pdf',
    source: '本地文件',
    createdAt: '2024-01-15T10:30:00Z',
    size: '2.1MB',
    type: 'file'
  },
  {
    id: '2',
    name: 'api_docs.md',
    source: '本地文件',
    createdAt: '2024-01-14T15:20:00Z',
    size: '856KB',
    type: 'file'
  },
  {
    id: '3',
    name: 'FAQ页面',
    source: 'https://example.com/faq',
    url: 'https://example.com/faq',
    createdAt: '2024-01-13T09:15:00Z',
    size: '1.2MB',
    type: 'website'
  }
]

export const KnowledgeBaseManagement: React.FC<KnowledgeBaseManagementProps> = ({
  className
}) => {
  const { getCurrentKnowledgeBase, setActiveKnowledgeBase } = useAppStore()
  const [importProgress, setImportProgress] = useState<ImportProgress>({
    isActive: false,
    progress: 0,
    total: 0,
    message: ''
  })
  const [documents] = useState<Document[]>(mockDocuments)

  const currentKb = getCurrentKnowledgeBase()

  if (!currentKb) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-gray-500">
          <DocumentIcon className="w-16 h-16 mx-auto mb-4 opacity-50" />
          <p>找不到知识库</p>
        </div>
      </div>
    )
  }

  const handleBack = () => {
    setActiveKnowledgeBase(null)
  }

  const handleFileUpload = () => {
    // Mock import progress
    setImportProgress({
      isActive: true,
      currentFile: 'document.pdf',
      progress: 80,
      total: 100,
      message: '正在处理文档...'
    })
    
    // Simulate completion after 3 seconds
    setTimeout(() => {
      setImportProgress({
        isActive: false,
        progress: 0,
        total: 0,
        message: ''
      })
    }, 3000)
  }

  const handleUrlImport = () => {
    const url = prompt('请输入要导入的网页URL:')
    if (url) {
      setImportProgress({
        isActive: true,
        currentFile: url,
        progress: 45,
        total: 100,
        message: '正在抓取网页内容...'
      })
      
      setTimeout(() => {
        setImportProgress({
          isActive: false,
          progress: 0,
          total: 0,
          message: ''
        })
      }, 3000)
    }
  }

  const handleFolderUpload = () => {
    setImportProgress({
      isActive: true,
      currentFile: 'project_docs/',
      progress: 60,
      total: 100,
      message: '正在处理文件夹...'
    })
    
    setTimeout(() => {
      setImportProgress({
        isActive: false,
        progress: 0,
        total: 0,
        message: ''
      })
    }, 3000)
  }

  const handleDownload = (doc: Document) => {
    console.log('下载文档:', doc.name)
    // TODO: Implement download functionality
  }

  const handleDelete = (doc: Document) => {
    if (confirm(`确定要删除 "${doc.name}" 吗？`)) {
      console.log('删除文档:', doc.name)
      // TODO: Implement delete functionality
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return (
    <div className={clsx('h-full flex flex-col', className)}>
      {/* Header */}
      <div className="flex-shrink-0 p-6 bg-gradient-to-r from-white/90 to-white/70 backdrop-blur-sm border-b border-gray-200/50">
        <div className="flex items-center space-x-4 mb-4">
          <button
            onClick={handleBack}
            className="p-2 hover:bg-gray-100/50 rounded-lg transition-colors"
          >
            <ArrowLeftIcon className="w-5 h-5 text-gray-600" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{currentKb.name}</h1>
            <p className="text-gray-600 mt-1">知识库管理</p>
          </div>
        </div>
      </div>

      {/* Import Area - Top 1/3 */}
      <div className="flex-shrink-0 h-1/3 p-6 border-b border-gray-200/50">
        <div className="h-full bg-white/80 backdrop-blur-sm rounded-xl border border-gray-200/50 p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">文档导入区域</h2>
          
          {/* Import Options */}
          <div className="flex space-x-4 mb-6">
            <button
              onClick={handleFileUpload}
              disabled={importProgress.isActive}
              className="flex-1 flex flex-col items-center justify-center p-4 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <DocumentIcon className="w-8 h-8 text-gray-400 mb-2" />
              <span className="text-sm font-medium text-gray-700">📁 本地文件</span>
              <span className="text-xs text-gray-500 mt-1">拖拽或点击</span>
            </button>

            <button
              onClick={handleUrlImport}
              disabled={importProgress.isActive}
              className="flex-1 flex flex-col items-center justify-center p-4 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <GlobeAltIcon className="w-8 h-8 text-gray-400 mb-2" />
              <span className="text-sm font-medium text-gray-700">🌐 网页URL</span>
              <span className="text-xs text-gray-500 mt-1">输入链接地址</span>
            </button>

            <button
              onClick={handleFolderUpload}
              disabled={importProgress.isActive}
              className="flex-1 flex flex-col items-center justify-center p-4 border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <FolderIcon className="w-8 h-8 text-gray-400 mb-2" />
              <span className="text-sm font-medium text-gray-700">📂 文件夹</span>
              <span className="text-xs text-gray-500 mt-1">选择整个目录</span>
            </button>
          </div>

          {/* Progress Bar */}
          {importProgress.isActive && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">
                  进度: {importProgress.progress}% 
                  {importProgress.currentFile && ` 正在处理: ${importProgress.currentFile}`}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${importProgress.progress}%` }}
                />
              </div>
              {importProgress.message && (
                <p className="text-sm text-gray-500">{importProgress.message}</p>
              )}
            </div>
          )}

          {!importProgress.isActive && (
            <div className="flex justify-end">
              <button
                onClick={() => handleFileUpload()}
                className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors"
              >
                开始导入
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Document List - Bottom 2/3 */}
      <div className="flex-1 p-6 overflow-hidden">
        <div className="h-full bg-white/80 backdrop-blur-sm rounded-xl border border-gray-200/50 overflow-hidden">
          <div className="p-6 border-b border-gray-200/50">
            <h2 className="text-lg font-semibold text-gray-900">文档列表</h2>
          </div>
          
          <div className="flex-1 overflow-y-auto">
            {documents.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-gray-500">
                <DocumentIcon className="w-12 h-12 mb-2 opacity-50" />
                <p>暂无文档</p>
                <p className="text-sm">请使用上方导入区域添加文档</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50/50 sticky top-0">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        文档名称
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        来源
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        创建时间
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        大小
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        操作
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200/50">
                    {documents.map((doc) => (
                      <tr key={doc.id} className="hover:bg-gray-50/30 transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            {doc.type === 'website' ? (
                              <GlobeAltIcon className="w-4 h-4 text-blue-500 mr-2" />
                            ) : (
                              <DocumentIcon className="w-4 h-4 text-gray-400 mr-2" />
                            )}
                            <span className="text-sm font-medium text-gray-900">
                              {doc.name}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {doc.url ? (
                            <a
                              href={doc.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-500 hover:text-blue-600 underline"
                            >
                              {doc.source}
                            </a>
                          ) : (
                            doc.source
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatDate(doc.createdAt)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {doc.size}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                          <div className="flex items-center justify-end space-x-2">
                            <button
                              onClick={() => handleDownload(doc)}
                              className="p-1 hover:bg-gray-100 rounded transition-colors"
                              title="下载"
                            >
                              <ArrowDownTrayIcon className="w-4 h-4 text-gray-400 hover:text-blue-500" />
                            </button>
                            <button
                              onClick={() => handleDelete(doc)}
                              className="p-1 hover:bg-gray-100 rounded transition-colors"
                              title="删除"
                            >
                              <TrashIcon className="w-4 h-4 text-gray-400 hover:text-red-500" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default KnowledgeBaseManagement