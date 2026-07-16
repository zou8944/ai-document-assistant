/**
 * Main App component with startup screen, setup wizard, and main layout
 */

import React, { useEffect, useRef, useState } from 'react'
import { Bars3Icon } from '@heroicons/react/24/outline'
import MainLayout from './components/layout/MainLayout'
import StartupScreen from './components/StartupScreen'
import SetupWizard from './components/settings/SetupWizard'
import OnboardingTour, { TourStep } from './components/common/OnboardingTour'
import useStartup from './hooks/useStartup'
import { useAPIClient, extractData } from './services/apiClient'
import { useAppStore } from './store/appStore'
import { ToastContainer } from './components/common/ToastContainer'
import { ErrorBoundary } from './components/common/ErrorBoundary'

const isElectron = typeof window !== 'undefined' && 'electronAPI' in window

const ONBOARDING_STEPS: TourStep[] = [
  {
    target: 'knowledge',
    title: '知识库',
    description: '在这里管理您的文档集合。上传文件或爬取网页，AI 会自动向量化并建立索引，方便后续问答。',
    placement: 'right',
  },
  {
    target: 'new-chat',
    title: '新建聊天',
    description: '点击加号或按 ⌘N 开始新对话。您可以在对话中引用特定文档，获得更精准的回答。',
    placement: 'right',
  },
  {
    target: 'search',
    title: '搜索聊天',
    description: '当对话变多时，使用搜索栏（⌘K）快速找到历史聊天记录。',
    placement: 'right',
  },
  {
    target: 'chat-input',
    title: '开始对话',
    description: '在这里输入问题，AI 会检索相关文档并给出带引用的回答。使用 @ 可以指定特定文档。',
    placement: 'top',
  },
  {
    target: 'settings',
    title: '设置',
    description: '在这里调整模型配置、查看快捷键列表。按 ⌘, 可快速打开设置。',
    placement: 'right',
  },
]

export const App: React.FC = () => {
  const { isLoading, isReady, error, message } = useStartup()
  const apiClient = useAPIClient()
  const setChatSessions = useAppStore((s) => s.setChatSessions)
  const mobileSidebarOpen = useAppStore((s) => s.mobileSidebarOpen)
  const setMobileSidebarOpen = useAppStore((s) => s.setMobileSidebarOpen)
  const hasCompletedOnboarding = useAppStore((s) => s.hasCompletedOnboarding)
  const setHasCompletedOnboarding = useAppStore((s) => s.setHasCompletedOnboarding)
  const bootstrapped = useRef(false)

  // Config completeness state
  const [configChecked, setConfigChecked] = useState(false)
  const [configComplete, setConfigComplete] = useState(true)

  // Once backend is ready, check config status then load chat list
  useEffect(() => {
    if (!isReady || bootstrapped.current) return
    bootstrapped.current = true

    const bootstrap = async () => {
      try {
        // Check config completeness first
        const statusRes = await apiClient.getConfigStatus()
        const status = extractData(statusRes)

        if (!status?.complete) {
          setConfigComplete(false)
          setConfigChecked(true)
          return
        }

        setConfigComplete(true)
        setConfigChecked(true)

        // Load chat list from server
        const res = await apiClient.listChats(0, 1000)
        const data = extractData(res)
        const sessions = data.chats.map((chat) => ({
          id: chat.chat_id,
          name: chat.name,
          knowledgeBaseIds: chat.collection_ids || [],
          createdAt: chat.created_at,
          lastMessageAt: chat.last_message_at || chat.created_at,
          messageCount: chat.message_count || 0,
          boundCollectionId: chat.bound_collection_id,
        }))
        setChatSessions(sessions)
      } catch (err) {
        console.error('Bootstrap failed:', err)
        // If config check fails, assume config is incomplete
        setConfigComplete(false)
        setConfigChecked(true)
      }
    }

    bootstrap()
  }, [isReady, apiClient, setChatSessions])

  // Called when setup wizard completes
  const handleSetupComplete = async () => {
    setConfigComplete(true)
    // Load chats after setup
    try {
      const res = await apiClient.listChats(0, 1000)
      const data = extractData(res)
      const sessions = data.chats.map((chat) => ({
        id: chat.chat_id,
        name: chat.name,
        knowledgeBaseIds: chat.collection_ids || [],
        createdAt: chat.created_at,
        lastMessageAt: chat.last_message_at || chat.created_at,
        messageCount: chat.message_count || 0,
        boundCollectionId: chat.bound_collection_id,
      }))
      setChatSessions(sessions)
    } catch (err) {
      console.error('Failed to load chats after setup:', err)
    }
  }

  // Show startup screen while loading
  if (isLoading || !isReady) {
    return (
      <ErrorBoundary>
        <StartupScreen
          message={error ? `${message} - ${error}` : message}
        />
        <ToastContainer />
      </ErrorBoundary>
    )
  }

  // Show setup wizard if config is incomplete
  if (configChecked && !configComplete) {
    return (
      <ErrorBoundary>
        <SetupWizard onComplete={handleSetupComplete} />
        <ToastContainer />
      </ErrorBoundary>
    )
  }

  // Still checking config
  if (!configChecked) {
    return (
      <ErrorBoundary>
        <StartupScreen message="正在检查配置..." />
        <ToastContainer />
      </ErrorBoundary>
    )
  }

  return (
    <ErrorBoundary>
      <div className="flex flex-col h-screen bg-gradient-to-br from-paper to-paper-dark">
        {/* Title Bar with drag region */}
        <div
          className="flex-shrink-0 h-12 bg-white/70 backdrop-blur-xl border-b border-white/30"
          style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
        >
          <div className="flex items-center justify-between h-full">
            {/* Left side - reserve space for system buttons (about 78px) in Electron */}
            <div className={`flex items-center space-x-3 min-w-0 ${isElectron ? 'pl-20' : 'pl-4'}`}>
              {/* Hamburger for mobile sidebar */}
              <button
                type="button"
                onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
                aria-label="切换侧边栏"
                className="md:hidden inline-flex items-center justify-center min-h-[44px] min-w-[44px] p-2 rounded-lg text-ink/60 hover:text-ink hover:bg-white/50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
              >
                <Bars3Icon className="w-5 h-5" />
              </button>
              <img src="/logo.png" alt="Logo" className="w-6 h-6 rounded-lg object-cover flex-shrink-0" />
              <h1 className="text-lg font-semibold text-ink whitespace-nowrap truncate">
                AI 文档助手
              </h1>
            </div>

            {/* Right side - reserved for future use */}
            <div className="pr-6" />
          </div>
        </div>

        {/* Main Layout */}
        <div className="flex-1 min-h-0">
          <MainLayout />
        </div>
      </div>
      <ToastContainer />

      {/* Onboarding tour — shown once after first setup */}
      {configComplete && !hasCompletedOnboarding && (
        <OnboardingTour
          steps={ONBOARDING_STEPS}
          onComplete={() => setHasCompletedOnboarding(true)}
        />
      )}
    </ErrorBoundary>
  )
}

export default App
