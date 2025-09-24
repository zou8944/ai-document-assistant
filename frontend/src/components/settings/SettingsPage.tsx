/**
 * Settings page for configuring LLM, embedding, and data storage
 */

import React, { useState, useEffect } from 'react'
import {
  Cog6ToothIcon,
  KeyIcon,
  GlobeAltIcon,
  CpuChipIcon,
  DocumentArrowDownIcon,
  ServerStackIcon,
  Squares2X2Icon,
  EyeIcon,
  EyeSlashIcon
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import { AppSettings } from '../../types/app'
import { extractData, getAPIClient } from '../../services/apiClient'

interface SettingsPageProps {
  className?: string
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ className }) => {
  const { settings, updateSettings } = useAppStore()
  const [formData, setFormData] = useState<AppSettings>(settings)
  const [isModified, setIsModified] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [showLLMApiKey, setShowLLMApiKey] = useState(false)
  const [showEmbeddingApiKey, setShowEmbeddingApiKey] = useState(false)
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({})
  const apiClient = getAPIClient()

  // Check if form has been modified and is valid
  useEffect(() => {
    const isChanged = JSON.stringify(formData) !== JSON.stringify(settings)
    setIsModified(isChanged)
  }, [formData, settings])

  // Validate form whenever formData changes
  useEffect(() => {
    if (isModified) {
      validateForm()
    }
  }, [formData, isModified])

  // Load settings from backend on component mount
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const response = await apiClient.getSettings()
        const backendSettings = extractData(response)
        console.log(backendSettings)
        setFormData(backendSettings)
        updateSettings(backendSettings)
      } catch (err) {
        console.error('Failed to load settings:', err)
        setError(err instanceof Error ? err.message : 'Failed to load settings')
      }
    }
    loadSettings()
  }, [])

  const validateForm = () => {
    const errors: Record<string, string> = {}

    // LLM API Key is required
    if (!formData.llm.api_key.trim()) {
      errors['llm.api_key'] = 'LLM API Key is required'
    }

    // LLM Base URL is required
    if (!formData.llm.base_url.trim()) {
      errors['llm.base_url'] = 'LLM Base URL is required'
    }

    // LLM Chat Model is required
    if (!formData.llm.chat_model.trim()) {
      errors['llm.chat_model'] = 'Chat Model is required'
    }

    // Embedding Base URL is required
    if (!formData.embedding.base_url.trim()) {
      errors['embedding.base_url'] = 'Embedding Base URL is required'
    }

    // Embedding Model is required
    if (!formData.embedding.model.trim()) {
      errors['embedding.model'] = 'Embedding Model is required'
    }

    // Knowledge base limits must be positive
    if (formData.knowledge_base.max_crawl_pages <= 0) {
      errors['knowledge_base.max_crawl_pages'] = 'Max crawl pages must be greater than 0'
    }

    if (formData.knowledge_base.max_file_size_mb <= 0) {
      errors['knowledge_base.max_file_size_mb'] = 'Max file size must be greater than 0'
    }

    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleInputChange = (
    section: keyof AppSettings,
    field: string,
    value: string | number
  ) => {
    setFormData(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value
      }
    }))
    setError(null)
    setSuccess(false)

    // Clear validation error for this field
    const fieldKey = `${section}.${field}`
    if (validationErrors[fieldKey]) {
      setValidationErrors(prev => {
        const newErrors = { ...prev }
        delete newErrors[fieldKey]
        return newErrors
      })
    }
  }

  const handleSave = async () => {
    if (!validateForm()) {
      return
    }

    setIsSaving(true)
    setError(null)
    setSuccess(false)

    try {
      const response = await apiClient.updateSettings(formData)
      const updatedSettings = extractData(response)
      updateSettings(updatedSettings as Partial<AppSettings>)
      setFormData(updatedSettings as AppSettings)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setIsSaving(false)
    }
  }

  const handleReset = () => {
    setFormData(settings)
  }


  return (
    <div className={clsx('h-full overflow-y-auto', className)}>
      <div className="max-w-4xl mx-auto p-6 space-y-8">
        {/* Header */}
        <div className="flex items-center space-x-3">
          <Cog6ToothIcon className="w-8 h-8 text-blue-500" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">设置</h1>
            <p className="text-gray-600 mt-1">配置您的AI文档助手</p>
          </div>
        </div>

        {/* LLM Configuration Section */}
        <div className="bg-white/80 backdrop-blur-sm rounded-xl border border-gray-200/50 overflow-hidden">
          <div className="px-6 py-4 bg-gradient-to-r from-blue-50 to-blue-50/50 border-b border-gray-200/50">
            <div className="flex items-center space-x-2">
              <CpuChipIcon className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold text-gray-900">LLM 配置</h2>
            </div>
            <p className="text-sm text-gray-600 mt-1">配置大语言模型的连接参数</p>
          </div>
          
          <div className="p-6 space-y-4">
            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <KeyIcon className="w-4 h-4" />
                <span>API Key</span>
                <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showLLMApiKey ? 'text' : 'password'}
                  value={formData.llm.api_key}
                  onChange={(e) => handleInputChange('llm', 'api_key', e.target.value)}
                  placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
                  className={`w-full px-3 py-2 pr-10 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                    validationErrors['llm.api_key'] ? 'border-red-500' : 'border-gray-300'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowLLMApiKey(!showLLMApiKey)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
                >
                  {showLLMApiKey ? (
                    <EyeSlashIcon className="h-4 w-4" />
                  ) : (
                    <EyeIcon className="h-4 w-4" />
                  )}
                </button>
              </div>
              {validationErrors['llm.api_key'] && (
                <p className="text-red-500 text-xs mt-1">{validationErrors['llm.api_key']}</p>
              )}
            </div>

            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <GlobeAltIcon className="w-4 h-4" />
                <span>Base URL</span>
                <span className="text-red-500">*</span>
              </label>
              <input
                type="url"
                value={formData.llm.base_url}
                onChange={(e) => handleInputChange('llm', 'base_url', e.target.value)}
                placeholder="https://api.openai.com/v1"
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                  validationErrors['llm.base_url'] ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {validationErrors['llm.base_url'] && (
                <p className="text-red-500 text-xs mt-1">{validationErrors['llm.base_url']}</p>
              )}
            </div>

            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <CpuChipIcon className="w-4 h-4" />
                <span>Chat Model</span>
                <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.llm.chat_model}
                onChange={(e) => handleInputChange('llm', 'chat_model', e.target.value)}
                placeholder="gpt-3.5-turbo, gpt-4, claude-3-sonnet, etc."
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                  validationErrors['llm.chat_model'] ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {validationErrors['llm.chat_model'] && (
                <p className="text-red-500 text-xs mt-1">{validationErrors['llm.chat_model']}</p>
              )}
            </div>
          </div>
        </div>

        {/* Embedding Configuration Section */}
        <div className="bg-white/80 backdrop-blur-sm rounded-xl border border-gray-200/50 overflow-hidden">
          <div className="px-6 py-4 bg-gradient-to-r from-green-50 to-green-50/50 border-b border-gray-200/50">
            <div className="flex items-center space-x-2">
              <DocumentArrowDownIcon className="w-5 h-5 text-green-500" />
              <h2 className="text-lg font-semibold text-gray-900">Embedding 配置</h2>
            </div>
            <p className="text-sm text-gray-600 mt-1">配置文档向量化模型的连接参数</p>
          </div>
          
          <div className="p-6 space-y-4">
            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <KeyIcon className="w-4 h-4" />
                <span>API Key</span>
              </label>
              <div className="relative">
                <input
                  type={showEmbeddingApiKey ? 'text' : 'password'}
                  value={formData.embedding.api_key}
                  onChange={(e) => handleInputChange('embedding', 'api_key', e.target.value)}
                  placeholder="留空则使用上述LLM配置"
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                  type="button"
                  onClick={() => setShowEmbeddingApiKey(!showEmbeddingApiKey)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
                >
                  {showEmbeddingApiKey ? (
                    <EyeSlashIcon className="h-4 w-4" />
                  ) : (
                    <EyeIcon className="h-4 w-4" />
                  )}
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-1">如果留空，将使用上述LLM的API Key</p>
            </div>

            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <GlobeAltIcon className="w-4 h-4" />
                <span>Base URL</span>
                <span className="text-red-500">*</span>
              </label>
              <input
                type="url"
                value={formData.embedding.base_url}
                onChange={(e) => handleInputChange('embedding', 'base_url', e.target.value)}
                placeholder="https://api.openai.com/v1"
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                  validationErrors['embedding.base_url'] ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {validationErrors['embedding.base_url'] && (
                <p className="text-red-500 text-xs mt-1">{validationErrors['embedding.base_url']}</p>
              )}
              <p className="text-xs text-gray-500 mt-1">如果留空，将使用上述LLM的Base URL</p>
            </div>

            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <DocumentArrowDownIcon className="w-4 h-4" />
                <span>Embedding Model</span>
                <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.embedding.model}
                onChange={(e) => handleInputChange('embedding', 'model', e.target.value)}
                placeholder="text-embedding-ada-002, text-embedding-3-small, etc."
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                  validationErrors['embedding.model'] ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {validationErrors['embedding.model'] && (
                <p className="text-red-500 text-xs mt-1">{validationErrors['embedding.model']}</p>
              )}
            </div>
          </div>
        </div>

        {/* Knowledge Base Configuration Section */}
        <div className="bg-white/80 backdrop-blur-sm rounded-xl border border-gray-200/50 overflow-hidden">
          <div className="px-6 py-4 bg-gradient-to-r from-purple-50 to-purple-50/50 border-b border-gray-200/50">
            <div className="flex items-center space-x-2">
              <Squares2X2Icon className="w-5 h-5 text-purple-500" />
              <h2 className="text-lg font-semibold text-gray-900">知识库配置</h2>
            </div>
            <p className="text-sm text-gray-600 mt-1">配置文档处理和爬虫相关参数</p>
          </div>

          <div className="p-6 space-y-4">
            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <GlobeAltIcon className="w-4 h-4" />
                <span>最大爬虫页面数</span>
              </label>
              <input
                type="number"
                value={formData.knowledge_base.max_crawl_pages}
                onChange={(e) => handleInputChange('knowledge_base', 'max_crawl_pages', parseInt(e.target.value, 10) || 1000)}
                min="1"
                max="10000"
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                  validationErrors['knowledge_base.max_crawl_pages'] ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {validationErrors['knowledge_base.max_crawl_pages'] && (
                <p className="text-red-500 text-xs mt-1">{validationErrors['knowledge_base.max_crawl_pages']}</p>
              )}
              <p className="text-xs text-gray-500 mt-1">网站爬虫时的最大页面数量限制</p>
            </div>

            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <DocumentArrowDownIcon className="w-4 h-4" />
                <span>最大文件大小 (MB)</span>
              </label>
              <input
                type="number"
                value={formData.knowledge_base.max_file_size_mb}
                onChange={(e) => handleInputChange('knowledge_base', 'max_file_size_mb', parseInt(e.target.value, 10) || 10)}
                min="1"
                max="100"
                className={`w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                  validationErrors['knowledge_base.max_file_size_mb'] ? 'border-red-500' : 'border-gray-300'
                }`}
              />
              {validationErrors['knowledge_base.max_file_size_mb'] && (
                <p className="text-red-500 text-xs mt-1">{validationErrors['knowledge_base.max_file_size_mb']}</p>
              )}
              <p className="text-xs text-gray-500 mt-1">单个文件的最大大小限制</p>
            </div>
          </div>
        </div>

        {/* System Configuration Section */}
        <div className="bg-white/80 backdrop-blur-sm rounded-xl border border-gray-200/50 overflow-hidden">
          <div className="px-6 py-4 bg-gradient-to-r from-orange-50 to-orange-50/50 border-b border-gray-200/50">
            <div className="flex items-center space-x-2">
              <ServerStackIcon className="w-5 h-5 text-orange-500" />
              <h2 className="text-lg font-semibold text-gray-900">系统配置</h2>
            </div>
            <p className="text-sm text-gray-600 mt-1">配置系统运行相关参数</p>
          </div>

          <div className="p-6">
            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <CpuChipIcon className="w-4 h-4" />
                <span>日志级别</span>
              </label>
              <select
                value={formData.system.log_level}
                onChange={(e) => handleInputChange('system', 'log_level', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="debug">Debug</option>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">控制后端服务的日志输出级别</p>
            </div>
          </div>
        </div>

        {/* Status Messages */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="text-red-700 text-sm">{error}</div>
          </div>
        )}

        {success && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="text-green-700 text-sm">设置保存成功！</div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex justify-end space-x-3 pt-6 border-t border-gray-200/50">
          <button
            onClick={handleReset}
            disabled={!isModified || isSaving}
            className="px-4 py-2 border border-gray-300 bg-white hover:bg-gray-50 text-gray-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            重置
          </button>
          <button
            onClick={handleSave}
            disabled={!isModified || isSaving || Object.keys(validationErrors).length > 0}
            className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            {isSaving ? (
              <>
                <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                <span>保存中...</span>
              </>
            ) : (
              <span>保存设置</span>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default SettingsPage