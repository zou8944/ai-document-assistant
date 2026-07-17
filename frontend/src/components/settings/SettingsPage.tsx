/**
 * Settings page for configuring Document Preparation, Document Chat and System.
 * Backed by the database settings table.
 */

import React, { useState, useEffect } from 'react'
import {
  Cog6ToothIcon,
  DocumentArrowDownIcon,
  ChatBubbleLeftRightIcon,
  EyeIcon,
  EyeSlashIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { SettingItem } from '../../services/apiClient'

interface SettingsPageProps {
  className?: string
}

interface FieldDef {
  key: string
  label: string
  type: 'password' | 'text' | 'number' | 'select' | 'boolean'
  placeholder?: string
  description: string
  options?: { value: string; label: string }[]
}

interface SubsectionDef {
  title: string
  category: string
  fields: FieldDef[]
}

interface SectionDef {
  id: string
  title: string
  subtitle: string
  icon: React.FC<{ className?: string }>
  color: string
  subsections: SubsectionDef[]
}

const SECTIONS: SectionDef[] = [
  {
    id: 'document-preparation',
    title: '文档准备',
    subtitle: '爬虫、嵌入和文本分块配置',
    icon: DocumentArrowDownIcon,
    color: 'blue',
    subsections: [
      {
        title: '爬虫服务',
        category: 'crawl',
        fields: [
          { key: 'CRAWL_PROVIDER', label: 'Provider', type: 'select', description: '服务提供商', options: [{ value: 'openai', label: 'OpenAI' }] },
          { key: 'CRAWL_API_KEY', label: 'API Key', type: 'password', placeholder: 'sk-xxxxxxxx', description: '调用 Crawl 模型所需的 API 密钥' },
          { key: 'CRAWL_BASE_URL', label: 'Base URL', type: 'text', placeholder: 'https://api.openai.com/v1', description: 'API 请求地址' },
          { key: 'CRAWL_MODEL', label: 'Model', type: 'text', placeholder: 'gpt-4o', description: '使用的模型名称' },
        ],
      },
      {
        title: '嵌入服务',
        category: 'embedding',
        fields: [
          { key: 'EMBEDDING_PROVIDER', label: 'Provider', type: 'select', description: '服务提供商', options: [{ value: 'openai', label: 'OpenAI' }] },
          { key: 'EMBEDDING_API_KEY', label: 'API Key', type: 'password', placeholder: '留空则使用 Crawl 的 Key', description: '调用 Embedding 模型所需的 API 密钥' },
          { key: 'EMBEDDING_BASE_URL', label: 'Base URL', type: 'text', placeholder: 'https://api.openai.com/v1', description: 'API 请求地址' },
          { key: 'EMBEDDING_MODEL', label: 'Model', type: 'text', placeholder: 'text-embedding-ada-002', description: '使用的向量化模型名称' },
        ],
      },
      {
        title: '文本处理',
        category: 'business',
        fields: [
          { key: 'CHUNK_SIZE', label: '文本块大小', type: 'number', description: '文档切分时每段最大字符数' },
          { key: 'CHUNK_OVERLAP', label: '文本块重叠', type: 'number', description: '相邻文本块之间的重叠字符数' },
          { key: 'CRAWLER_MAX_DEPTH', label: '爬虫最大深度', type: 'number', description: '从初始 URL 开始递归抓取的最大深度' },
        ],
      },
    ],
  },
  {
    id: 'chat',
    title: '文档聊天',
    subtitle: 'AI 对话和检索配置',
    icon: ChatBubbleLeftRightIcon,
    color: 'purple',
    subsections: [
      {
        title: 'AI 服务',
        category: 'agent',
        fields: [
          { key: 'AGENT_PROVIDER', label: 'Provider', type: 'select', description: '服务提供商', options: [{ value: 'anthropic', label: 'Anthropic' }] },
          { key: 'AGENT_API_KEY', label: 'API Key', type: 'password', placeholder: 'sk-ant-xxxxxxxx', description: '调用 Agent 模型所需的 API 密钥' },
          { key: 'AGENT_BASE_URL', label: 'Base URL', type: 'text', placeholder: '留空使用默认地址', description: 'API 请求地址，留空使用默认' },
          { key: 'AGENT_MODEL', label: 'Model', type: 'text', placeholder: 'claude-sonnet-4-20250514', description: '使用的模型名称' },
        ],
      },
      {
        title: '检索与生成',
        category: 'business',
        fields: [
          { key: 'RAG_TOP_K', label: '检索文档数', type: 'number', description: '检索最相似文档片段的数量' },
          { key: 'AGENT_TEMPERATURE', label: 'AI 随机度', type: 'number', description: '值越低越稳定，越高越有创造性' },
          { key: 'ENABLE_TRANSCRIPT', label: '对话日志', type: 'boolean', description: '开启后，每次 AI 对话会生成详细的事件日志文件，用于调试和审计。日志保存在服务端 agent_transcripts 目录下' },
        ],
      },
    ],
  },
]

const colorMap: Record<string, { bg: string; text: string; ring: string }> = {
  blue: { bg: 'from-blue-50 to-blue-50/50', text: 'text-blue-500', ring: 'focus:ring-blue-500' },
  purple: { bg: 'from-purple-50 to-purple-50/50', text: 'text-purple-500', ring: 'focus:ring-purple-500' },
  gray: { bg: 'from-gray-50 to-gray-50/50', text: 'text-ink/50', ring: 'focus:ring-gray-500' },
}

// Collect all fields across sections for save iteration
function getAllFields(): { field: FieldDef; category: string }[] {
  const result: { field: FieldDef; category: string }[] = []
  for (const section of SECTIONS) {
    for (const sub of section.subsections) {
      for (const field of sub.fields) {
        result.push({ field, category: sub.category })
      }
    }
  }
  return result
}

export const SettingsPage: React.FC<SettingsPageProps> = ({ className }) => {
  const [values, setValues] = useState<Record<string, string>>({})
  const [originalValues, setOriginalValues] = useState<Record<string, string>>({})
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({})
  const [isModified, setIsModified] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [activeSection, setActiveSection] = useState(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('section') || 'document-preparation'
  })
  const [testingService, setTestingService] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; message: string }>>({})

  const handleSectionChange = (sectionId: string) => {
    setActiveSection(sectionId)
    const url = new URL(window.location.href)
    url.searchParams.set('section', sectionId)
    window.history.replaceState({}, '', url.toString())
  }

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const resp = await fetch('/api/v1/settings/items')
        const json = await resp.json()
        const items: SettingItem[] = json.data ?? json

        if (!Array.isArray(items)) {
          setError('Unexpected response format')
          return
        }

        const vals: Record<string, string> = {}
        for (const item of items) {
          vals[item.key] = item.value || ''
        }
        setValues(vals)
        setOriginalValues({ ...vals })
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load settings')
      }
    }
    loadSettings()
  }, [])

  useEffect(() => {
    setIsModified(JSON.stringify(values) !== JSON.stringify(originalValues))
  }, [values, originalValues])

  const handleChange = (key: string, value: string) => {
    setValues((prev) => ({ ...prev, [key]: value }))
    setError(null)
    setSuccess(false)
  }

  const toggleShow = (key: string) => {
    setShowKeys((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    setError(null)
    setSuccess(false)

    try {
      const changedItems: SettingItem[] = []
      for (const { field, category } of getAllFields()) {
        const newVal = values[field.key]
        const oldVal = originalValues[field.key]
        if (newVal === oldVal) continue

        changedItems.push({
          key: field.key,
          value: newVal || '',
          value_type: field.type === 'number' ? 'number' : 'string',
          category,
          description: field.description,
          is_sensitive: field.type === 'password',
        })
      }

      if (changedItems.length > 0) {
        const resp = await fetch('/api/v1/settings/items/batch', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items: changedItems }),
        })
        const json = await resp.json()
        if (json.code !== 'Success') {
          throw new Error(json.message || 'Save failed')
        }
      }

      setOriginalValues({ ...values })
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save settings')
    } finally {
      setIsSaving(false)
    }
  }

  const handleReset = () => {
    setValues({ ...originalValues })
  }

  const handleTestConnection = async (service: string) => {
    setTestingService(service)
    setTestResults((prev) => {
      const next = { ...prev }
      delete next[service]
      return next
    })

    const keyPrefix = service === 'crawl' ? 'CRAWL' : service === 'embedding' ? 'EMBEDDING' : 'AGENT'
    const apiKey = values[`${keyPrefix}_API_KEY`] || ''
    const baseUrl = values[`${keyPrefix}_BASE_URL`] || ''
    const model = values[`${keyPrefix}_MODEL`] || ''

    try {
      const resp = await fetch('/api/v1/settings/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service, api_key: apiKey, base_url: baseUrl, model }),
      })
      const json = await resp.json()
      const data = json.data ?? json
      setTestResults((prev) => ({ ...prev, [service]: { success: data.success, message: data.message } }))
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [service]: { success: false, message: err instanceof Error ? err.message : '请求失败' },
      }))
    } finally {
      setTestingService(null)
    }
  }

  return (
    <div className={clsx('h-full flex flex-col', className)}>
      <div className="max-w-5xl w-full mx-auto flex flex-col flex-1 min-h-0 p-6">
        {/* Header */}
        <div className="flex-shrink-0 flex items-center space-x-3 mb-6">
          <Cog6ToothIcon className="w-8 h-8 text-accent" />
          <div>
            <h1 className="text-2xl font-bold text-ink">设置</h1>
            <p className="text-ink/65 mt-1">配置您的 AI 文档助手</p>
          </div>
        </div>

        <div className="flex gap-6 flex-1 min-h-0">
          {/* Left nav */}
          <nav className="flex-shrink-0 w-44 space-y-1 pt-1">
            {SECTIONS.map((section) => {
              const Icon = section.icon
              const colors = colorMap[section.color]
              return (
                <button
                  key={section.id}
                  onClick={() => handleSectionChange(section.id)}
                  className={clsx(
                    'w-full flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-left',
                    activeSection === section.id
                      ? 'bg-accent/10 text-accent'
                      : 'text-ink/65 hover:bg-gray-50 hover:text-ink'
                  )}
                >
                  <Icon className={clsx('w-4 h-4', activeSection === section.id ? colors.text : '')} />
                  <span>{section.title}</span>
                </button>
              )
            })}
          </nav>

          {/* Right content */}
          <div className="flex-1 space-y-6 overflow-y-auto min-h-0">
            {SECTIONS.filter((s) => s.id === activeSection).map((section) => {
              const Icon = section.icon
              const colors = colorMap[section.color]
              return (
                <div key={section.id} className="bg-white/80 backdrop-blur-sm rounded-xl border border-white/40 overflow-hidden">
                  <div className={clsx('px-6 py-4 bg-gradient-to-r border-b border-white/40', colors.bg)}>
                    <div className="flex items-center space-x-2">
                      <Icon className={clsx('w-5 h-5', colors.text)} />
                      <h2 className="text-lg font-semibold text-ink">{section.title}</h2>
                    </div>
                    <p className="text-sm text-ink/65 mt-1">{section.subtitle}</p>
                  </div>

                  <div className="p-6 space-y-4">
                    {section.subsections.map((sub) => {
                      const isTestable = ['crawl', 'embedding', 'agent'].includes(sub.category)
                      return (
                      <div key={sub.title} className="bg-gray-50/60 rounded-lg border border-gray-200/70 p-4">
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-sm font-semibold text-ink/90">{sub.title}</h3>
                          {isTestable && (
                            <button
                              type="button"
                              onClick={() => handleTestConnection(sub.category)}
                              disabled={testingService === sub.category}
                              className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-300 bg-white text-ink/70 hover:bg-gray-50 hover:text-ink transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {testingService === sub.category ? (
                                <>
                                  <div className="w-3 h-3 border-2 border-gray-300 border-t-accent rounded-full animate-spin" />
                                  <span>测试中...</span>
                                </>
                              ) : (
                                <span>测试连接</span>
                              )}
                            </button>
                          )}
                        </div>
                        {isTestable && testResults[sub.category] && (
                          <div
                            className={`flex items-center space-x-2 mb-3 px-3 py-2 rounded-lg text-xs ${
                              testResults[sub.category].success
                                ? 'bg-green-50 text-green-700'
                                : 'bg-red-50 text-red-700'
                            }`}
                          >
                            {testResults[sub.category].success ? (
                              <CheckCircleIcon className="w-4 h-4 shrink-0" />
                            ) : (
                              <XCircleIcon className="w-4 h-4 shrink-0" />
                            )}
                            <span>{testResults[sub.category].message}</span>
                          </div>
                        )}
                        <div className="space-y-4">
                          {sub.fields.map((field) => (
                            <div key={field.key}>
                              {field.type === 'boolean' ? (
                                <div className="flex items-center justify-between py-1">
                                  <div>
                                    <span className="text-sm font-medium text-ink/80">{field.label}</span>
                                    <p className="text-xs text-muted mt-0.5">{field.description}</p>
                                  </div>
                                  <button
                                    type="button"
                                    role="switch"
                                    aria-checked={values[field.key] === 'true'}
                                    onClick={() => handleChange(field.key, values[field.key] === 'true' ? 'false' : 'true')}
                                    className={clsx(
                                      'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2',
                                      values[field.key] === 'true' ? 'bg-accent' : 'bg-gray-200'
                                    )}
                                  >
                                    <span
                                      className={clsx(
                                        'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
                                        values[field.key] === 'true' ? 'translate-x-5' : 'translate-x-0'
                                      )}
                                    />
                                  </button>
                                </div>
                              ) : (
                              <>
                              <label htmlFor={field.key} className="flex items-center space-x-2 text-sm font-medium text-ink/80 mb-1.5">
                                <span>{field.label}</span>
                              </label>

                              {field.type === 'select' ? (
                                <select
                                  id={field.key}
                                  value={values[field.key] || ''}
                                  onChange={(e) => handleChange(field.key, e.target.value)}
                                  className={clsx('w-full px-3 py-2 border border-gray-300 rounded-lg bg-white', colors.ring, 'focus:border-transparent')}
                                >
                                  {field.options?.map((opt) => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
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
                                    className={clsx('w-full px-3 py-2 pr-10 border border-gray-300 rounded-lg text-sm bg-white', colors.ring, 'focus:border-transparent')}
                                  />
                                  <button
                                    type="button"
                                    onClick={() => toggleShow(field.key)}
                                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-ink/65"
                                  >
                                    {showKeys[field.key] ? <EyeSlashIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                                  </button>
                                </div>
                              ) : (
                                <input
                                  id={field.key}
                                  type="text"
                                  inputMode={field.type === 'number' ? 'numeric' : undefined}
                                  value={values[field.key] || ''}
                                  onChange={(e) => handleChange(field.key, e.target.value)}
                                  placeholder={field.placeholder}
                                  className={clsx('w-full px-3 py-2 border border-gray-300 rounded-lg bg-white', colors.ring, 'focus:border-transparent')}
                                />
                              )}

                              <p className="text-xs text-ink/50 mt-1">{field.description}</p>
                              </>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}

            {/* Status messages */}
            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4" role="alert" aria-live="assertive">
                <div className="text-red-700 text-sm">{error}</div>
              </div>
            )}
            {success && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="text-green-700 text-sm">设置保存成功！</div>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex justify-end space-x-3 pt-4 border-t border-white/40">
              <button
                onClick={handleReset}
                disabled={!isModified || isSaving}
                className="px-4 py-2 border border-gray-300 bg-white hover:bg-gray-50 text-ink/80 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                重置
              </button>
              <button
                onClick={handleSave}
                disabled={!isModified || isSaving}
                className="px-4 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
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
      </div>
    </div>
  )
}

export default SettingsPage
