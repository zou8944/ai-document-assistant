/**
 * Input dialog components
 */

import React, { useState } from 'react'
import { XMarkIcon, PlusIcon, MinusIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'

export interface UrlCrawlConfig {
  urls: string[]
  recursivePrefixes: string[]
  categorizeMode: string
  generateReadme: boolean
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
  const [recursivePrefixes, setRecursivePrefixes] = useState<string[]>([''])
  const [categorizeMode, setCategorizeMode] = useState<string>('ai')
  const [generateReadme, setGenerateReadme] = useState<boolean>(true)
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

  const addUrlField = () => {
    setUrls([...urls, ''])
  }

  const removeUrlField = (index: number) => {
    if (urls.length > 1) {
      setUrls(urls.filter((_, i) => i !== index))
    }
  }

  const updateUrl = (index: number, value: string) => {
    const newUrls = [...urls]
    newUrls[index] = value
    setUrls(newUrls)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const validUrls = urls.filter(url => url.trim())
    const newErrors: string[] = []

    if (validUrls.length === 0) {
      newErrors.push('至少需要输入一个 URL')
    }

    for (const url of validUrls) {
      if (!validateUrl(url)) {
        newErrors.push(`无效的 URL 格式: ${url}`)
      }
    }

    if (newErrors.length > 0) {
      setErrors(newErrors)
      return
    }

    setErrors([])
    const validPrefixes = recursivePrefixes.map(p => p.trim()).filter(p => p)
    onConfirm({
      urls: validUrls,
      recursivePrefixes: validPrefixes,
      categorizeMode,
      generateReadme,
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
                      onChange={(e) => updateUrl(index, e.target.value)}
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
                        onClick={() => removeUrlField(index)}
                        className="p-2 text-macos-gray-400 hover:text-red-500 transition-colors"
                      >
                        <MinusIcon className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addUrlField}
                  className="flex items-center gap-1 text-sm text-macos-blue hover:text-blue-600 transition-colors"
                >
                  <PlusIcon className="w-4 h-4" />
                  添加 URL
                </button>
              </div>
            </div>

            {/* Recursive Prefixes */}
            <div>
              <label className="block text-sm font-medium text-macos-gray-900 mb-3">
                爬取前缀匹配
              </label>
              <div className="space-y-2">
                {recursivePrefixes.map((prefix, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={prefix}
                      onChange={(e) => {
                        const newPrefixes = [...recursivePrefixes]
                        newPrefixes[index] = e.target.value
                        setRecursivePrefixes(newPrefixes)
                      }}
                      placeholder="https://example.com/docs/"
                      className={clsx(
                        'flex-1 px-4 py-2 border border-macos-gray-300 rounded-lg',
                        'focus:ring-2 focus:ring-macos-blue focus:border-macos-blue',
                        'bg-white/70 backdrop-blur-sm text-macos-gray-900 placeholder-macos-gray-500',
                        'transition-all duration-200'
                      )}
                    />
                    {recursivePrefixes.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          setRecursivePrefixes(recursivePrefixes.filter((_, i) => i !== index))
                        }}
                        className="p-2 text-macos-gray-400 hover:text-red-500 transition-colors"
                      >
                        <MinusIcon className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => setRecursivePrefixes([...recursivePrefixes, ''])}
                  className="flex items-center gap-1 text-sm text-macos-blue hover:text-blue-600 transition-colors"
                >
                  <PlusIcon className="w-4 h-4" />
                  添加前缀
                </button>
              </div>
              <p className="mt-1 text-xs text-macos-gray-500">
                只爬取以任一前缀开头的链接，全部为空则爬取同域名下的所有链接
              </p>
            </div>

            {/* Categorization Options */}
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-macos-gray-900 mb-2">
                  文档分类方式
                </label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2 px-4 py-2 rounded-lg border border-macos-gray-200 cursor-pointer hover:bg-macos-gray-50/50 transition-colors">
                    <input
                      type="radio"
                      name="categorizeMode"
                      value="ai"
                      checked={categorizeMode === 'ai'}
                      onChange={(e) => setCategorizeMode(e.target.value)}
                      className="w-4 h-4 text-macos-blue"
                    />
                    <span className="text-sm text-macos-gray-700">AI 智能分类</span>
                  </label>
                  <label className="flex items-center gap-2 px-4 py-2 rounded-lg border border-macos-gray-200 cursor-pointer hover:bg-macos-gray-50/50 transition-colors">
                    <input
                      type="radio"
                      name="categorizeMode"
                      value="path_prefix"
                      checked={categorizeMode === 'path_prefix'}
                      onChange={(e) => setCategorizeMode(e.target.value)}
                      className="w-4 h-4 text-macos-blue"
                    />
                    <span className="text-sm text-macos-gray-700">按路径前缀分类</span>
                  </label>
                </div>
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={generateReadme}
                  onChange={(e) => setGenerateReadme(e.target.checked)}
                  className="w-4 h-4 rounded border-macos-gray-300 text-macos-blue focus:ring-macos-blue"
                />
                <span className="text-sm text-macos-gray-700">生成 README 导航页</span>
              </label>
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
