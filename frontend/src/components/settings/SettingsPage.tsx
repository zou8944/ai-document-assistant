/**
 * Settings page for configuring LLM, embedding, and data storage
 */

import React, { useState, useEffect } from 'react'
import {
  Cog6ToothIcon,
  FolderIcon,
  KeyIcon,
  GlobeAltIcon,
  CpuChipIcon,
  DocumentArrowDownIcon
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { useAppStore } from '../../store/appStore'
import { AppSettings } from '../../types/app'

interface SettingsPageProps {
  className?: string
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ className }) => {
  const { settings, updateSettings } = useAppStore()
  const [formData, setFormData] = useState<AppSettings>(settings)
  const [isModified, setIsModified] = useState(false)
  const [isSaving, setIsSaving] = useState(false)

  // Check if form has been modified
  useEffect(() => {
    const isChanged = JSON.stringify(formData) !== JSON.stringify(settings)
    setIsModified(isChanged)
  }, [formData, settings])

  const handleInputChange = (
    section: keyof AppSettings,
    field: string,
    value: string
  ) => {
    setFormData(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [field]: value
      }
    }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    
    // Simulate save delay
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    updateSettings(formData)
    setIsSaving(false)
    
    // Show success feedback (you could add a toast notification here)
    console.log('Settings saved successfully')
  }

  const handleReset = () => {
    setFormData(settings)
  }

  const handleBrowseDataLocation = () => {
    // In a real app, this would open a directory picker
    const newPath = prompt('请输入数据存储路径:', formData.dataLocation)
    if (newPath) {
      setFormData(prev => ({
        ...prev,
        dataLocation: newPath
      }))
    }
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
              </label>
              <input
                type="password"
                value={formData.llm.apiKey}
                onChange={(e) => handleInputChange('llm', 'apiKey', e.target.value)}
                placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <GlobeAltIcon className="w-4 h-4" />
                <span>Base URL</span>
              </label>
              <input
                type="url"
                value={formData.llm.baseUrl}
                onChange={(e) => handleInputChange('llm', 'baseUrl', e.target.value)}
                placeholder="https://api.openai.com/v1"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <CpuChipIcon className="w-4 h-4" />
                <span>Chat Model</span>
              </label>
              <select
                value={formData.llm.chatModel}
                onChange={(e) => handleInputChange('llm', 'chatModel', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
                <option value="gpt-4">gpt-4</option>
                <option value="gpt-4-turbo-preview">gpt-4-turbo-preview</option>
                <option value="claude-3-sonnet">claude-3-sonnet</option>
                <option value="claude-3-opus">claude-3-opus</option>
              </select>
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
              <input
                type="password"
                value={formData.embedding.apiKey}
                onChange={(e) => handleInputChange('embedding', 'apiKey', e.target.value)}
                placeholder="留空则使用上述LLM配置"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-500 mt-1">如果留空，将使用上述LLM的API Key</p>
            </div>

            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <GlobeAltIcon className="w-4 h-4" />
                <span>Base URL</span>
              </label>
              <input
                type="url"
                value={formData.embedding.baseUrl}
                onChange={(e) => handleInputChange('embedding', 'baseUrl', e.target.value)}
                placeholder="留空则使用上述LLM配置"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <p className="text-xs text-gray-500 mt-1">如果留空，将使用上述LLM的Base URL</p>
            </div>

            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <DocumentArrowDownIcon className="w-4 h-4" />
                <span>Embedding Model</span>
              </label>
              <select
                value={formData.embedding.embeddingModel}
                onChange={(e) => handleInputChange('embedding', 'embeddingModel', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="text-embedding-ada-002">text-embedding-ada-002</option>
                <option value="text-embedding-3-small">text-embedding-3-small</option>
                <option value="text-embedding-3-large">text-embedding-3-large</option>
              </select>
            </div>
          </div>
        </div>

        {/* Data Storage Section */}
        <div className="bg-white/80 backdrop-blur-sm rounded-xl border border-gray-200/50 overflow-hidden">
          <div className="px-6 py-4 bg-gradient-to-r from-purple-50 to-purple-50/50 border-b border-gray-200/50">
            <div className="flex items-center space-x-2">
              <FolderIcon className="w-5 h-5 text-purple-500" />
              <h2 className="text-lg font-semibold text-gray-900">数据存储位置</h2>
            </div>
            <p className="text-sm text-gray-600 mt-1">配置文档和向量数据的存储位置</p>
          </div>
          
          <div className="p-6">
            <div>
              <label className="flex items-center space-x-2 text-sm font-medium text-gray-700 mb-2">
                <FolderIcon className="w-4 h-4" />
                <span>数据目录</span>
              </label>
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={formData.dataLocation}
                  onChange={(e) => setFormData(prev => ({ ...prev, dataLocation: e.target.value }))}
                  placeholder="/path/to/data/directory"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <button
                  type="button"
                  onClick={handleBrowseDataLocation}
                  className="px-4 py-2 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-lg transition-colors text-sm"
                >
                  浏览...
                </button>
              </div>
              <p className="text-xs text-gray-500 mt-1">
                包括爬虫输出的markdown文档、导入的文件、ChromaDB数据库等
              </p>
            </div>
          </div>
        </div>

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
            disabled={!isModified || isSaving}
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