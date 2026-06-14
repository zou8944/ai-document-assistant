/**
 * URL crawl configuration dialog — built on unified <Modal>.
 */

import React, { useState } from 'react'
import { PlusIcon, MinusIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'
import Modal from './common/Modal'

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
  const [categorizeMode, setCategorizeMode] = useState<string>('auto')
  const [generateReadme, setGenerateReadme] = useState<boolean>(true)
  const [errors, setErrors] = useState<string[]>([])

  const validateUrl = (url: string): boolean => {
    if (!url.trim()) return false
    try {
      new URL(url.trim())
      return true
    } catch {
      return false
    }
  }

  const addUrlField = () => setUrls([...urls, ''])
  const removeUrlField = (index: number) => {
    if (urls.length > 1) setUrls(urls.filter((_, i) => i !== index))
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

  return (
    <Modal
      open={isOpen}
      onClose={onCancel}
      title="配置网站爬取"
      size="lg"
      className={className}
      footer={
        <>
          <button
            type="button"
            onClick={onCancel}
            className="glass-button px-6 py-2 rounded-lg text-sm font-medium text-ink/80 hover:text-ink"
          >
            取消
          </button>
          <button
            type="submit"
            form="url-crawl-form"
            className={clsx(
              'px-6 py-2 text-sm font-medium text-white rounded-lg',
              'bg-accent hover:bg-accent-hover',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              'transition-colors duration-200',
              'focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2'
            )}
          >
            开始爬取
          </button>
        </>
      }
    >
      <form id="url-crawl-form" onSubmit={handleSubmit} className="space-y-6">
        {/* Error Messages */}
        {errors.length > 0 && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <ul className="text-sm text-red-600 space-y-1">
              {errors.map((error, index) => (
                <li key={index}>• {error}</li>
              ))}
            </ul>
          </div>
        )}

        {/* URLs */}
        <div>
          <label className="block text-sm font-medium text-ink mb-3">
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
                    'flex-1 px-4 py-2 border border-gray-300 rounded-lg',
                    'focus:ring-2 focus:ring-accent focus:border-accent',
                    'bg-white/70 backdrop-blur-sm text-ink placeholder-ink/50',
                    'transition-all duration-200'
                  )}
                />
                {urls.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeUrlField(index)}
                    className="p-2 text-ink/50 hover:text-red-500 transition-colors"
                  >
                    <MinusIcon className="w-4 h-4" />
                  </button>
                )}
              </div>
            ))}
            <button
              type="button"
              onClick={addUrlField}
              className="flex items-center gap-1 text-sm text-accent hover:text-accent-hover transition-colors"
            >
              <PlusIcon className="w-4 h-4" />
              添加 URL
            </button>
          </div>
        </div>

        {/* Recursive Prefixes */}
        <div>
          <label className="block text-sm font-medium text-ink mb-3">
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
                    'flex-1 px-4 py-2 border border-gray-300 rounded-lg',
                    'focus:ring-2 focus:ring-accent focus:border-accent',
                    'bg-white/70 backdrop-blur-sm text-ink placeholder-ink/50',
                    'transition-all duration-200'
                  )}
                />
                {recursivePrefixes.length > 1 && (
                  <button
                    type="button"
                    onClick={() => {
                      setRecursivePrefixes(recursivePrefixes.filter((_, i) => i !== index))
                    }}
                    className="p-2 text-ink/50 hover:text-red-500 transition-colors"
                  >
                    <MinusIcon className="w-4 h-4" />
                  </button>
                )}
              </div>
            ))}
            <button
              type="button"
              onClick={() => setRecursivePrefixes([...recursivePrefixes, ''])}
              className="flex items-center gap-1 text-sm text-accent hover:text-accent-hover transition-colors"
            >
              <PlusIcon className="w-4 h-4" />
              添加前缀
            </button>
          </div>
          <p className="mt-1 text-xs text-ink/50">
            只爬取以任一前缀开头的链接，全部为空则爬取同域名下的所有链接
          </p>
        </div>

        {/* Categorization Options */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-ink mb-2">
              文档分类方式
            </label>
            <div className="flex gap-3">
              <label className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50/50 transition-colors">
                <input
                  type="radio"
                  name="categorizeMode"
                  value="auto"
                  checked={categorizeMode === 'auto'}
                  onChange={(e) => setCategorizeMode(e.target.value)}
                  className="w-4 h-4 text-accent"
                />
                <span className="text-sm text-ink/80">自动（路径优先 + AI 兜底）</span>
              </label>
              <label className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50/50 transition-colors">
                <input
                  type="radio"
                  name="categorizeMode"
                  value="path_only"
                  checked={categorizeMode === 'path_only'}
                  onChange={(e) => setCategorizeMode(e.target.value)}
                  className="w-4 h-4 text-accent"
                />
                <span className="text-sm text-ink/80">仅路径分类</span>
              </label>
              <label className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-200 cursor-pointer hover:bg-gray-50/50 transition-colors">
                <input
                  type="radio"
                  name="categorizeMode"
                  value="ai_only"
                  checked={categorizeMode === 'ai_only'}
                  onChange={(e) => setCategorizeMode(e.target.value)}
                  className="w-4 h-4 text-accent"
                />
                <span className="text-sm text-ink/80">仅 AI 分类</span>
              </label>
            </div>
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={generateReadme}
              onChange={(e) => setGenerateReadme(e.target.checked)}
              className="w-4 h-4 rounded border-gray-300 text-accent focus:ring-accent"
            />
            <span className="text-sm text-ink/80">生成 README 导航页</span>
          </label>
        </div>
      </form>
    </Modal>
  )
}

export default UrlInputDialog
