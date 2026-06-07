/**
 * Modal for adding new knowledge base — built on unified <Modal>.
 */

import React, { useState } from 'react'
import { useAppStore } from '../../store/appStore'
import { useAPIClient, extractData } from '../../services/apiClient'
import Modal from '../common/Modal'

interface AddKnowledgeBaseModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

export const AddKnowledgeBaseModal: React.FC<AddKnowledgeBaseModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
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
      const collectionId = `kb_${Date.now()}`
      const response = await apiClient.createCollection({
        id: collectionId,
        name: name.trim(),
        description: description.trim() || undefined
      })

      const collection = extractData(response)

      const newKb = {
        id: collection.id,
        name: collection.name,
        description: collection.description || '',
        createdAt: collection.created_at,
        documentCount: collection.document_count,
        sourceType: 'files' as const
      }

      addKnowledgeBase(newKb)
      setActiveKnowledgeBase(newKb.id)

      setName('')
      setDescription('')

      if (onSuccess) onSuccess()
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

  return (
    <Modal
      open={isOpen}
      onClose={handleClose}
      title="创建新知识库"
      size="md"
      dismissible={!isSubmitting}
      footer={
        <>
          <button
            type="button"
            onClick={handleClose}
            disabled={isSubmitting}
            className="px-4 py-2 text-sm text-ink/80 hover:text-ink rounded-lg transition-colors disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="submit"
            form="add-kb-form"
            disabled={!name.trim() || isSubmitting}
            className="px-4 py-2 text-sm font-medium text-white bg-accent hover:bg-accent-hover rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? '创建中...' : '创建知识库'}
          </button>
        </>
      }
    >
      <form id="add-kb-form" onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="kb-name" className="block text-sm font-medium text-ink/80">
            知识库名称 *
          </label>
          <input
            type="text"
            id="kb-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            placeholder="请输入知识库名称"
            required
            disabled={isSubmitting}
          />
        </div>

        <div>
          <label htmlFor="kb-description" className="block text-sm font-medium text-ink/80">
            描述
          </label>
          <textarea
            id="kb-description"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            placeholder="请输入知识库描述（可选）"
            disabled={isSubmitting}
          />
        </div>
      </form>
    </Modal>
  )
}

export default AddKnowledgeBaseModal
