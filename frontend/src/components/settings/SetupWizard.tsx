/**
 * First-time setup wizard.
 * Shown when critical API keys are missing.
 * Three service groups: Crawl, Embedding, Agent — each with provider/key/base_url/model.
 */

import React, { useState } from 'react'
import {
  EyeIcon,
  EyeSlashIcon,
  CheckCircleIcon,
  CpuChipIcon,
  DocumentArrowDownIcon,
  ChatBubbleLeftRightIcon,
} from '@heroicons/react/24/outline'
import { getAPIClient, extractData, SettingItem } from '../../services/apiClient'

interface SetupWizardProps {
  onComplete: () => void
}

interface FieldDef {
  key: string
  label: string
  type: 'password' | 'text' | 'select'
  placeholder?: string
  description: string
  required: boolean
  options?: { value: string; label: string }[]
}

interface ServiceGroup {
  id: string
  title: string
  subtitle: string
  icon: React.FC<{ className?: string }>
  color: string
  fields: FieldDef[]
}

const SERVICE_GROUPS: ServiceGroup[] = [
  {
    id: 'crawl',
    title: 'Crawl 服务',
    subtitle: '文档爬取、分类和 README 生成',
    icon: CpuChipIcon,
    color: 'blue',
    fields: [
      {
        key: 'CRAWL_PROVIDER',
        label: 'Provider',
        type: 'select',
        description: '服务提供商',
        required: true,
        options: [
          { value: 'openai', label: 'OpenAI' },
        ],
      },
      {
        key: 'CRAWL_API_KEY',
        label: 'API Key',
        type: 'password',
        placeholder: 'sk-xxxxxxxxxxxxxxxxxxxxxxxx',
        description: '调用 Crawl 模型所需的 API 密钥',
        required: true,
      },
      {
        key: 'CRAWL_BASE_URL',
        label: 'Base URL',
        type: 'text',
        placeholder: 'https://api.openai.com/v1',
        description: 'API 请求地址',
        required: true,
      },
      {
        key: 'CRAWL_MODEL',
        label: 'Model',
        type: 'text',
        placeholder: 'gpt-4o',
        description: '使用的模型名称',
        required: true,
      },
    ],
  },
  {
    id: 'embedding',
    title: 'Embedding 服务',
    subtitle: '文档向量化',
    icon: DocumentArrowDownIcon,
    color: 'green',
    fields: [
      {
        key: 'EMBEDDING_PROVIDER',
        label: 'Provider',
        type: 'select',
        description: '服务提供商',
        required: true,
        options: [
          { value: 'openai', label: 'OpenAI' },
        ],
      },
      {
        key: 'EMBEDDING_API_KEY',
        label: 'API Key',
        type: 'password',
        placeholder: '留空则使用 Crawl 的 Key',
        description: '调用 Embedding 模型所需的 API 密钥',
        required: false,
      },
      {
        key: 'EMBEDDING_BASE_URL',
        label: 'Base URL',
        type: 'text',
        placeholder: 'https://api.openai.com/v1',
        description: 'API 请求地址',
        required: true,
      },
      {
        key: 'EMBEDDING_MODEL',
        label: 'Model',
        type: 'text',
        placeholder: 'text-embedding-ada-002',
        description: '使用的向量化模型名称',
        required: true,
      },
    ],
  },
  {
    id: 'agent',
    title: 'Agent 服务',
    subtitle: 'AI 对话',
    icon: ChatBubbleLeftRightIcon,
    color: 'purple',
    fields: [
      {
        key: 'AGENT_PROVIDER',
        label: 'Provider',
        type: 'select',
        description: '服务提供商',
        required: true,
        options: [
          { value: 'anthropic', label: 'Anthropic' },
        ],
      },
      {
        key: 'AGENT_API_KEY',
        label: 'API Key',
        type: 'password',
        placeholder: 'sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx',
        description: '调用 Agent 模型所需的 API 密钥',
        required: true,
      },
      {
        key: 'AGENT_BASE_URL',
        label: 'Base URL',
        type: 'text',
        placeholder: '留空使用 Anthropic 默认地址',
        description: 'API 请求地址，留空使用默认',
        required: false,
      },
      {
        key: 'AGENT_MODEL',
        label: 'Model',
        type: 'text',
        placeholder: 'claude-sonnet-4-20250514',
        description: '使用的模型名称',
        required: true,
      },
    ],
  },
]

const colorClasses: Record<string, { headerBg: string; icon: string; ring: string }> = {
  blue: { headerBg: 'from-blue-50 to-blue-50/50', icon: 'text-blue-500', ring: 'focus:ring-blue-500' },
  green: { headerBg: 'from-green-50 to-green-50/50', icon: 'text-green-500', ring: 'focus:ring-green-500' },
  purple: { headerBg: 'from-purple-50 to-purple-50/50', icon: 'text-purple-500', ring: 'focus:ring-purple-500' },
}

export const SetupWizard: React.FC<SetupWizardProps> = ({ onComplete }) => {
  const [values, setValues] = useState<Record<string, string>>({})
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const apiClient = getAPIClient()

  const handleChange = (key: string, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }))
    setError(null)
  }

  const toggleShow = (key: string) => {
    setShowKeys((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  // All fields without defaults are required
  const canSubmit =
    !!values['CRAWL_API_KEY']?.trim() &&
    !!values['CRAWL_BASE_URL']?.trim() &&
    !!values['CRAWL_MODEL']?.trim() &&
    !!values['EMBEDDING_BASE_URL']?.trim() &&
    !!values['EMBEDDING_MODEL']?.trim() &&
    !!values['AGENT_API_KEY']?.trim() &&
    !!values['AGENT_MODEL']?.trim()

  const handleSave = async () => {
    if (!canSubmit) return

    setIsSaving(true)
    setError(null)

    try {
      const items: SettingItem[] = []
      for (const group of SERVICE_GROUPS) {
        for (const field of group.fields) {
          const val = values[field.key]
          if (val !== undefined && val !== '') {
            items.push({
              key: field.key,
              value: val,
              value_type: field.type === 'select' ? 'string' : field.type === 'password' ? 'string' : 'string',
              category: group.id,
              description: field.description,
              is_sensitive: field.type === 'password',
            })
          }
        }
      }

      const response = await apiClient.upsertSettingsBatch(items)
      const result = extractData(response)

      if (result?.complete) {
        onComplete()
      } else {
        // Even if not "complete" by strict check, if user provided crawl + agent keys, proceed
        // (embedding key can fall back to crawl key)
        onComplete()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '保存失败，请重试')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="h-screen overflow-y-auto bg-gradient-to-br from-paper to-paper-dark">
      <div className="flex flex-col items-center min-h-full px-4 py-8">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <img
            src="/logo.png"
            alt="Logo"
            className="w-16 h-16 rounded-2xl shadow-lg object-cover mx-auto mb-4"
          />
          <h1 className="text-2xl font-bold text-ink mb-2">
            欢迎使用 AI 文档助手
          </h1>
          <p className="text-ink/65">
            请配置以下三个 AI 服务以启用全部功能
          </p>
        </div>

        {/* Step indicator */}
        <ol className="flex gap-2 mb-4" aria-label="配置步骤">
          {SERVICE_GROUPS.map((group) => {
            const isComplete = group.fields
              .filter((f) => f.required)
              .every((f) => !!values[f.key]?.trim())
            return (
              <li
                key={group.id}
                className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium ${
                  isComplete
                    ? 'bg-green-50 text-green-700 border border-green-200'
                    : 'bg-gray-50 text-ink/65 border border-gray-200'
                }`}
              >
                {isComplete && <CheckCircleIcon className="w-3.5 h-3.5" />}
                {group.title}
              </li>
            )
          })}
        </ol>

        {/* Service groups */}
        <div className="space-y-4">
          {SERVICE_GROUPS.map((group) => {
            const Icon = group.icon
            const colors = colorClasses[group.color]
            return (
              <div
                key={group.id}
                className="bg-white/80 backdrop-blur-sm rounded-xl border border-white/40 shadow-sm overflow-hidden"
              >
                <div className={`px-5 py-3 bg-gradient-to-r ${colors.headerBg} border-b border-white/40`}>
                  <div className="flex items-center space-x-2">
                    <Icon className={`w-5 h-5 ${colors.icon}`} />
                    <h2 className="text-base font-semibold text-ink">{group.title}</h2>
                  </div>
                  <p className="text-xs text-ink/65 mt-0.5">{group.subtitle}</p>
                </div>

                <div className="p-5 grid grid-cols-2 gap-4">
                  {group.fields.map((field) => (
                    <div key={field.key} className={field.key.endsWith('API_KEY') || field.key.endsWith('BASE_URL') ? 'col-span-2' : ''}>
                      <label htmlFor={field.key} className="flex items-center space-x-1 text-xs font-medium text-ink/80 mb-1.5">
                        <span>{field.label}</span>
                        {field.required && <span className="text-red-500">*</span>}
                      </label>

                      {field.type === 'select' ? (
                        <select
                          id={field.key}
                          value={values[field.key] || field.options?.[0]?.value || ''}
                          onChange={(e) => handleChange(field.key, e.target.value)}
                          className={`w-full px-3 py-2 border border-gray-300 rounded-lg ${colors.ring} focus:border-transparent text-sm`}
                        >
                          {field.options?.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      ) : field.type === 'password' ? (
                        <div className="relative">
                          <input
                            id={field.key}
                            type={showKeys[field.key] ? 'text' : 'password'}
                            value={values[field.key] || ''}
                            onChange={(e) => handleChange(field.key, e.target.value)}
                            placeholder={field.placeholder}
                            className={`w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg ${colors.ring} focus:border-transparent text-sm`}
                          />
                          <button
                            type="button"
                            onClick={() => toggleShow(field.key)}
                            className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-ink/65"
                          >
                            {showKeys[field.key] ? (
                              <EyeSlashIcon className="h-4 w-4" />
                            ) : (
                              <EyeIcon className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                      ) : (
                        <input
                          id={field.key}
                          type="text"
                          value={values[field.key] || ''}
                          onChange={(e) => handleChange(field.key, e.target.value)}
                          placeholder={field.placeholder}
                          className={`w-full px-3 py-2 border border-gray-300 rounded-lg ${colors.ring} focus:border-transparent text-sm`}
                        />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>

        {/* Error */}
        {error && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-3" role="alert" aria-live="polite">
            <p className="text-red-700 text-sm">{error}</p>
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 flex justify-center">
          <button
            onClick={handleSave}
            disabled={!canSubmit || isSaving}
            className="px-8 py-2.5 bg-accent hover:bg-accent-hover text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
          >
            {isSaving ? (
              <>
                <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                <span>保存中...</span>
              </>
            ) : (
              <>
                <CheckCircleIcon className="w-4 h-4" />
                <span>保存并开始使用</span>
              </>
            )}
          </button>
        </div>

        {/* Footer hint */}
        <p className="text-center text-xs text-ink/50 mt-4">
          密钥将加密存储在本地数据库中，不会上传至任何外部服务
        </p>
      </div>
      </div>
    </div>
  )
}

export default SetupWizard
