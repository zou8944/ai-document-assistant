/**
 * Input dialog components
 */

import React, { useState } from 'react'
import { XMarkIcon, PlusIcon, MinusIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'

interface UrlCrawlConfig {
  urls: string[]
  excludeUrls: string[]
  maxDepth: number
  recursivePrefix: string
}

interface UrlInputDialogProps {
  isOpen: boolean
  onConfirm: (config: UrlCrawlConfig) => void
  onCancel: () => void
  className?: string
}

export const UrlInputDialog: React.FC<UrlInputDialogProps> = ({
  isOpen,
  onConfirm,
  onCancel,
  className
}) => {
  const [urls, setUrls] = useState<string[]>([''])
  const [excludeUrls, setExcludeUrls] = useState<string[]>([''])
  const [maxDepth, setMaxDepth] = useState<number>(0)
  const [recursivePrefix, setRecursivePrefix] = useState<string>('')
  const [errors, setErrors] = useState<string[]>([])

  if (!isOpen) return null

  const validateUrl = (url: string): boolean => {
    if (!url.trim()) return false
    try {
      new URL(url.trim())
      return true
    } catch {
      return false
    }
  }

  const addUrlField = (type: 'urls' | 'excludeUrls') => {
    if (type === 'urls') {
      setUrls([...urls, ''])
    } else {
      setExcludeUrls([...excludeUrls, ''])
    }
  }

  const removeUrlField = (type: 'urls' | 'excludeUrls', index: number) => {
    if (type === 'urls') {
      if (urls.length > 1) {
        setUrls(urls.filter((_, i) => i !== index))
      }
    } else {
      if (excludeUrls.length > 1) {
        setExcludeUrls(excludeUrls.filter((_, i) => i !== index))
      }
    }
  }

  const updateUrl = (type: 'urls' | 'excludeUrls', index: number, value: string) => {
    if (type === 'urls') {
      const newUrls = [...urls]
      newUrls[index] = value
      setUrls(newUrls)
    } else {
      const newExcludeUrls = [...excludeUrls]
      newExcludeUrls[index] = value
      setExcludeUrls(newExcludeUrls)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    // 验证 URLs
    const validUrls = urls.filter(url => url.trim())
    const validExcludeUrls = excludeUrls.filter(url => url.trim())
    
    const newErrors: string[] = []
    
    // 检查是否有有效的 URL
    if (validUrls.length === 0) {
      newErrors.push('至少需要输入一个 URL')
    }
    
    // 验证 URL 格式
    for (const url of validUrls) {
      if (!validateUrl(url)) {
        newErrors.push(`无效的 URL 格式: ${url}`)
      }
    }
    
    for (const url of validExcludeUrls) {
      if (!validateUrl(url)) {
        newErrors.push(`无效的排除 URL 格式: ${url}`)
      }
    }
    
    if (newErrors.length > 0) {
      setErrors(newErrors)
      return
    }
    
    setErrors([])
    onConfirm({
      urls: validUrls,
      excludeUrls: validExcludeUrls,
      maxDepth,
      recursivePrefix: recursivePrefix.trim()
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onCancel()
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/30 backdrop-blur-sm transition-opacity"
        onClick={onCancel}
      />
      
      {/* Dialog */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div 
          className={clsx(
            'glass-morph rounded-xl border border-white/20 p-6 w-full max-w-2xl',
            'bg-white/90 backdrop-blur-xl shadow-xl',
            'animate-slide-up max-h-[90vh] overflow-y-auto',
            className
          )}
          onKeyDown={handleKeyDown}
        >
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-macos-gray-900">
              配置网站爬取
            </h3>
            <button
              onClick={onCancel}
              className="p-1 hover:bg-macos-gray-100/50 rounded-lg transition-colors"
            >
              <XMarkIcon className="w-5 h-5 text-macos-gray-400" />
            </button>
          </div>

          {/* Error Messages */}
          {errors.length > 0 && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
              <ul className="text-sm text-red-600 space-y-1">
                {errors.map((error, index) => (
                  <li key={index}>• {error}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* URLs */}
            <div>
              <label className="block text-sm font-medium text-macos-gray-900 mb-3">
                需要爬取的 URL <span className="text-red-500">*</span>
              </label>
              <div className="space-y-2">
                {urls.map((url, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <input
                      type="url"
                      value={url}
                      onChange={(e) => updateUrl('urls', index, e.target.value)}
                      placeholder="https://example.com"
                      className={clsx(
                        'flex-1 px-4 py-2 border border-macos-gray-300 rounded-lg',
                        'focus:ring-2 focus:ring-macos-blue focus:border-macos-blue',
                        'bg-white/70 backdrop-blur-sm text-macos-gray-900 placeholder-macos-gray-500',
                        'transition-all duration-200'
                      )}
                    />
                    {urls.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeUrlField('urls', index)}
                        className="p-2 text-macos-gray-400 hover:text-red-500 transition-colors"
                      >
                        <MinusIcon className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => addUrlField('urls')}
                  className="flex items-center gap-1 text-sm text-macos-blue hover:text-blue-600 transition-colors"
                >
                  <PlusIcon className="w-4 h-4" />
                  添加 URL
                </button>
              </div>
            </div>

            {/* Exclude URLs */}
            <div>
              <label className="block text-sm font-medium text-macos-gray-900 mb-3">
                需要排除的 URL
              </label>
              <div className="space-y-2">
                {excludeUrls.map((url, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <input
                      type="url"
                      value={url}
                      onChange={(e) => updateUrl('excludeUrls', index, e.target.value)}
                      placeholder="https://example.com/exclude"
                      className={clsx(
                        'flex-1 px-4 py-2 border border-macos-gray-300 rounded-lg',
                        'focus:ring-2 focus:ring-macos-blue focus:border-macos-blue',
                        'bg-white/70 backdrop-blur-sm text-macos-gray-900 placeholder-macos-gray-500',
                        'transition-all duration-200'
                      )}
                    />
                    {excludeUrls.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeUrlField('excludeUrls', index)}
                        className="p-2 text-macos-gray-400 hover:text-red-500 transition-colors"
                      >
                        <MinusIcon className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => addUrlField('excludeUrls')}
                  className="flex items-center gap-1 text-sm text-macos-blue hover:text-blue-600 transition-colors"
                >
                  <PlusIcon className="w-4 h-4" />
                  添加排除 URL
                </button>
              </div>
            </div>

            {/* Max Depth */}
            <div>
              <label htmlFor="maxDepth" className="block text-sm font-medium text-macos-gray-900 mb-2">
                递归爬取层数 <span className="text-red-500">*</span>
              </label>
              <input
                type="number"
                id="maxDepth"
                value={maxDepth}
                onChange={(e) => setMaxDepth(parseInt(e.target.value) || 0)}
                min="0"
                max="10"
                className={clsx(
                  'w-full px-4 py-2 border border-macos-gray-300 rounded-lg',
                  'focus:ring-2 focus:ring-macos-blue focus:border-macos-blue',
                  'bg-white/70 backdrop-blur-sm text-macos-gray-900',
                  'transition-all duration-200'
                )}
              />
              <p className="mt-1 text-xs text-macos-gray-500">
                0 表示不递归爬取，只爬取指定的 URL
              </p>
            </div>

            {/* Recursive Prefix */}
            <div>
              <label htmlFor="recursivePrefix" className="block text-sm font-medium text-macos-gray-900 mb-2">
                递归爬取前缀匹配
              </label>
              <input
                type="text"
                id="recursivePrefix"
                value={recursivePrefix}
                onChange={(e) => setRecursivePrefix(e.target.value)}
                placeholder="https://example.com/docs/"
                className={clsx(
                  'w-full px-4 py-2 border border-macos-gray-300 rounded-lg',
                  'focus:ring-2 focus:ring-macos-blue focus:border-macos-blue',
                  'bg-white/70 backdrop-blur-sm text-macos-gray-900 placeholder-macos-gray-500',
                  'transition-all duration-200'
                )}
              />
              <p className="mt-1 text-xs text-macos-gray-500">
                只爬取以此前缀开头的链接，为空则爬取同域名下的所有链接
              </p>
            </div>
            
            {/* Actions */}
            <div className="flex justify-end space-x-3 pt-4 border-t border-macos-gray-200">
              <button
                type="button"
                onClick={onCancel}
                className={clsx(
                  'glass-button px-6 py-2 rounded-lg text-sm font-medium',
                  'text-macos-gray-700 hover:text-macos-gray-900',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                取消
              </button>
              <button
                type="submit"
                className={clsx(
                  'px-6 py-2 text-sm font-medium text-white rounded-lg',
                  'bg-macos-blue hover:bg-blue-600',
                  'disabled:bg-macos-gray-300 disabled:cursor-not-allowed',
                  'transition-colors duration-200',
                  'focus:outline-none focus:ring-2 focus:ring-macos-blue focus:ring-offset-2'
                )}
              >
                开始爬取
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

export default UrlInputDialog
