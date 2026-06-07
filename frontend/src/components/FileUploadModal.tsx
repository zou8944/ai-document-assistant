/**
 * File upload modal — built on unified <Modal>.
 */

import React from 'react'
import FileUpload from './FileUpload'
import Modal from './common/Modal'

interface FileUploadModalProps {
  isOpen: boolean
  onFilesSelected: (files: string[]) => void
  onClose: () => void
  isProcessing?: boolean
  className?: string
}

export const FileUploadModal: React.FC<FileUploadModalProps> = ({
  isOpen,
  onFilesSelected,
  onClose,
  isProcessing = false,
  className
}) => {
  const handleFilesSelected = (files: string[]) => {
    onFilesSelected(files)
    onClose()
  }

  return (
    <Modal
      open={isOpen}
      onClose={() => { if (!isProcessing) onClose() }}
      title="选择文件或文件夹"
      size="lg"
      dismissible={!isProcessing}
      className={className}
      footer={
        !isProcessing ? (
          <button
            type="button"
            onClick={onClose}
            className="glass-button px-4 py-2 rounded-lg text-sm font-medium text-ink/80 hover:text-ink"
          >
            取消
          </button>
        ) : null
      }
    >
      <FileUpload
        onFilesSelected={handleFilesSelected}
        isProcessing={isProcessing}
      />
    </Modal>
  )
}

export default FileUploadModal
