/**
 * URLInput component with validation and domain preview.
 * Following Apple Liquid Glass design with smooth animations.
 */

import React, { useState, useEffect } from 'react'
import { GlobeAltIcon, ExclamationTriangleIcon, CheckCircleIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'

interface URLInputProps {
  onUrlSubmit: (url: string) => void
  isProcessing?: boolean
  className?: string
}

export const URLInput: React.FC<URLInputProps> = ({
  onUrlSubmit,
  isProcessing = false,
  className
}) => {
  const [url, setUrl] = useState('')
  const [isValid, setIsValid] = useState<boolean | null>(null)
  const [domain, setDomain] = useState('')
  const [error, setError] = useState('')

  const validateUrl = (inputUrl: string): boolean => {
    try {
      const urlObj = new URL(inputUrl)
      return urlObj.protocol === 'http:' || urlObj.protocol === 'https:'
    } catch {
      return false
    }
  }

  const extractDomain = (inputUrl: string): string => {
    try {
      const urlObj = new URL(inputUrl)
      return urlObj.hostname
    } catch {
      return ''
    }
  }

  useEffect(() => {
    if (!url.trim()) {
      setIsValid(null)
      setDomain('')
      setError('')
      return
    }

    const valid = validateUrl(url)
    setIsValid(valid)

    if (valid) {
      setDomain(extractDomain(url))
      setError('')
    } else {
      setDomain('')
      setError('请输入有效的网址（以 http:// 或 https:// 开头）')
    }
  }, [url])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    if (isProcessing || !isValid || !url.trim()) return

    onUrlSubmit(url.trim())
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setUrl(e.target.value)
  }

  const getValidationIcon = () => {
    if (isValid === null) return null
    
    if (isValid) {
      return <CheckCircleIcon className="w-5 h-5 text-green-500" />
    } else {
      return <ExclamationTriangleIcon className="w-5 h-5 text-red-500" />
    }
  }

  return (
    <div className={clsx('space-y-4', className)}>
      <form onSubmit={handleSubmit} className="glass-morph rounded-xl p-6 animate-fade-in">
        <div className="space-y-4">
          <div className="text-center space-y-2">
            <GlobeAltIcon className="w-12 h-12 mx-auto text-macos-blue" />
            <h3 className="text-lg font-medium text-macos-gray-900">
              抓取网站内容
            </h3>
            <p className="text-sm text-macos-gray-600">
              输入网址，我们将抓取同一域名下的所有页面
            </p>
          </div>

          <div className="space-y-3">
            <div className="relative">
              <input
                type="text"
                value={url}
                onChange={handleInputChange}
                placeholder="https://example.com"
                disabled={isProcessing}
                className={clsx(
                  'w-full px-4 py-3 pr-12 rounded-lg border',
                  'glass-morph text-macos-gray-900 placeholder-macos-gray-500',
                  'focus:outline-none focus:ring-2 focus:ring-macos-blue focus:border-macos-blue',
                  'transition-all duration-200',
                  isValid === false && 'border-red-300 focus:ring-red-500 focus:border-red-500',
                  isValid === true && 'border-green-300',
                  isProcessing && 'opacity-50 cursor-not-allowed'
                )}
              />
              
              <div className="absolute inset-y-0 right-0 flex items-center pr-3">
                {getValidationIcon()}
              </div>
            </div>

            {error && (
              <p className="text-sm text-red-600 animate-slide-up">
                {error}
              </p>
            )}

            {domain && isValid && (
              <div className="glass-morph rounded-lg p-3 animate-slide-up">
                <p className="text-xs text-macos-gray-600 mb-1">将要抓取的域名：</p>
                <p className="text-sm font-medium text-macos-blue">{domain}</p>
                <p className="text-xs text-macos-gray-500 mt-1">
                  仅会抓取此域名下的页面，确保安全和相关性
                </p>
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={!isValid || isProcessing || !url.trim()}
            className={clsx(
              'w-full py-3 px-4 rounded-lg font-medium text-white',
              'bg-macos-blue hover:bg-blue-600',
              'disabled:bg-macos-gray-400 disabled:cursor-not-allowed',
              'transition-all duration-200 transform',
              'hover:scale-105 hover:shadow-lg',
              'focus:outline-none focus:ring-2 focus:ring-macos-blue focus:ring-offset-2',
              isProcessing && 'animate-pulse'
            )}
          >
            {isProcessing ? '正在抓取...' : '开始抓取网站'}
          </button>
        </div>
      </form>

      {/* Crawling Guidelines */}
      <div className="glass-morph rounded-xl p-4">
        <h4 className="text-sm font-medium text-macos-gray-900 mb-2">
          抓取说明
        </h4>
        <ul className="text-xs text-macos-gray-600 space-y-1">
          <li>• 仅抓取同一域名下的页面，保证内容相关性</li>
          <li>• 遵循网站的 robots.txt 规则</li>
          <li>• 控制抓取速度，避免给服务器造成压力</li>
          <li>• 最多抓取 50 个页面，确保处理效率</li>
        </ul>
      </div>
    </div>
  )
}

export default URLInput