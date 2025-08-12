/**
 * Modal for selecting knowledge bases to add to chat
 */

import React, { useState } from 'react'
import { XMarkIcon, BookOpenIcon } from '@heroicons/react/24/outline'
import { useAppStore } from '../../store/appStore'

interface KnowledgeBaseSelectorProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (kbIds: string[]) => void
  excludeIds?: string[]
}

export const KnowledgeBaseSelector: React.FC<KnowledgeBaseSelectorProps> = ({
  isOpen,
  onClose,
  onSelect,
  excludeIds = []
}) => {
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const { knowledgeBases } = useAppStore()

  // Filter out already included knowledge bases
  const availableKnowledgeBases = knowledgeBases.filter(
    kb => !excludeIds.includes(kb.id)
  )

  const handleToggleSelection = (kbId: string) => {
    setSelectedIds(prev => 
      prev.includes(kbId)
        ? prev.filter(id => id !== kbId)
        : [...prev, kbId]
    )
  }

  const handleConfirm = () => {
    if (selectedIds.length > 0) {
      onSelect(selectedIds)
    }
    setSelectedIds([])
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
              className="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              <span className="sr-only">关闭</span>
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>

          <div className="sm:flex sm:items-start">
            <div className="mt-3 text-center sm:mt-0 sm:text-left w-full">
              <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
                添加知识库到当前对话
              </h3>

              <div className="max-h-64 overflow-y-auto">
                {availableKnowledgeBases.length === 0 ? (
                  <div className="text-center text-gray-500 py-8">
                    <BookOpenIcon className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>没有可添加的知识库</p>
                    <p className="text-sm mt-1">
                      {excludeIds.length > 0 ? '所有知识库都已添加到此对话中' : '请先创建知识库'}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {availableKnowledgeBases.map((kb) => (
                      <label
                        key={kb.id}
                        className="flex items-start space-x-3 p-3 rounded-lg hover:bg-gray-50 cursor-pointer transition-colors"
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
                            <span className="font-medium text-gray-900">{kb.name}</span>
                          </div>
                          {kb.description && (
                            <p className="text-sm text-gray-500 mt-1">{kb.description}</p>
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

              {availableKnowledgeBases.length > 0 && (
                <div className="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse space-y-3 sm:space-y-0 sm:space-x-3 sm:space-x-reverse">
                  <button
                    type="button"
                    onClick={handleConfirm}
                    disabled={selectedIds.length === 0}
                    className="w-full inline-flex justify-center rounded-md border border-transparent bg-blue-600 px-4 py-2 text-base font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed sm:ml-3 sm:w-auto sm:text-sm"
                  >
                    添加 ({selectedIds.length})
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

export default KnowledgeBaseSelector