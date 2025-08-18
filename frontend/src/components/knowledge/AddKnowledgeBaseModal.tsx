/**
 * Modal for adding new knowledge base
 */

import React, { useState } from 'react'
import { XMarkIcon } from '@heroicons/react/24/outline'
import { useAppStore } from '../../store/appStore'
import { useAPIClient, extractData } from '../../services/apiClient'

interface AddKnowledgeBaseModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

export const AddKnowledgeBaseModal: React.FC<AddKnowledgeBaseModalProps> = ({
  isOpen,
  onClose,
  onSuccess
}) => {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const apiClient = useAPIClient()
  
  const { addKnowledgeBase, setActiveKnowledgeBase } = useAppStore()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return

    setIsSubmitting(true)

    try {
      // Create collection via API
      const collectionId = `kb_${Date.now()}`
      const response = await apiClient.createCollection({
        id: collectionId,
        name: name.trim(),
        description: description.trim() || undefined
      })
      
      const collection = extractData(response)
      
      // Map collection to knowledge base format for app store
      const newKb = {
        id: collection.id,
        name: collection.name,
        description: collection.description || '',
        createdAt: collection.created_at,
        documentCount: collection.document_count,
        sourceType: 'files' as const
      }

      // Add to app store for UI consistency
      addKnowledgeBase(newKb)
      setActiveKnowledgeBase(newKb.id)
      
      // Reset form
      setName('')
      setDescription('')
      
      // Call success callback to refresh the list
      if (onSuccess) {
        onSuccess()
      }
      
      onClose()
    } catch (error) {
      console.error('创建知识库失败:', error)
      alert('创建知识库失败: ' + (error as Error).message)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    if (!isSubmitting) {
      setName('')
      setDescription('')
      onClose()
    }
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
              disabled={isSubmitting}
              className="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
            >
              <span className="sr-only">关闭</span>
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>

          <div className="sm:flex sm:items-start">
            <div className="mt-3 text-center sm:mt-0 sm:text-left w-full">
              <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
                创建新知识库
              </h3>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                    知识库名称 *
                  </label>
                  <input
                    type="text"
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    placeholder="请输入知识库名称"
                    required
                    disabled={isSubmitting}
                  />
                </div>

                <div>
                  <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                    描述
                  </label>
                  <textarea
                    id="description"
                    rows={3}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                    placeholder="请输入知识库描述（可选）"
                    disabled={isSubmitting}
                  />
                </div>

                <div className="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse space-y-3 sm:space-y-0 sm:space-x-3 sm:space-x-reverse">
                  <button
                    type="submit"
                    disabled={!name.trim() || isSubmitting}
                    className="w-full inline-flex justify-center rounded-md border border-transparent bg-blue-600 px-4 py-2 text-base font-medium text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed sm:ml-3 sm:w-auto sm:text-sm"
                  >
                    {isSubmitting ? '创建中...' : '创建知识库'}
                  </button>
                  <button
                    type="button"
                    onClick={handleClose}
                    disabled={isSubmitting}
                    className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-base font-medium text-gray-700 shadow-sm hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed sm:mt-0 sm:w-auto sm:text-sm"
                  >
                    取消
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AddKnowledgeBaseModal