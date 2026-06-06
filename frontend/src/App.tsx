/**
 * Main App component with startup screen, setup wizard, and main layout
 */

import React, { useEffect, useRef, useState } from 'react'
import MainLayout from './components/layout/MainLayout'
import StartupScreen from './components/StartupScreen'
import SetupWizard from './components/settings/SetupWizard'
import useStartup from './hooks/useStartup'
import { useAPIClient, extractData } from './services/apiClient'
import { useAppStore } from './store/appStore'

export const App: React.FC = () => {
  const { isLoading, isReady, error, message } = useStartup()
  const apiClient = useAPIClient()
  const setChatSessions = useAppStore((s) => s.setChatSessions)
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
      <StartupScreen
        message={error ? `${message} - ${error}` : message}
      />
    )
  }

  // Show setup wizard if config is incomplete
  if (configChecked && !configComplete) {
    return <SetupWizard onComplete={handleSetupComplete} />
  }

  // Still checking config
  if (!configChecked) {
    return <StartupScreen message="正在检查配置..." />
  }

  const {
    activeSidebarSection,
    activeChat,
    chatSessions,
  } = useAppStore()

  const currentChat = chatSessions.find((c) => c.id === activeChat)
  const sectionLabel: Record<string, string> = {
    knowledge: '知识库',
    chat: '聊天',
    settings: '设置',
  }

  return (
    <div className="flex flex-col h-screen surface-paper">
      {/* Title Bar with drag region */}
      <div
        className="flex-shrink-0 h-14 surface-glass border-b border-paper-edge/60"
        style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
      >
        <div className="flex items-center justify-between h-full px-5">
          {/* Left side - brand mark + current section context */}
          <div className="flex items-center gap-3 pl-16">
            <div className="w-7 h-7 rounded-md overflow-hidden shadow-sm">
              <img src="/logo.png" alt="Logo" className="w-full h-full object-cover" />
            </div>
            <div className="flex items-baseline gap-2">
              <h1 className="font-display text-xl font-medium tracking-tight text-ink leading-none">
                AI 文档助手
              </h1>
              <span className="hidden sm:inline-block text-[10px] font-semibold tracking-[0.18em] uppercase text-muted">
                {sectionLabel[activeSidebarSection] || ''}
              </span>
            </div>
          </div>

          {/* Right side - current chat breadcrumb (if any) */}
          <div className="flex items-center gap-3 pr-2" style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}>
            {currentChat && activeSidebarSection === 'chat' && (
              <div className="flex items-center gap-2 text-sm">
                <span className="w-1.5 h-1.5 rounded-full bg-sage animate-breathe" />
                <span className="font-display italic text-muted-soft max-w-[28ch] truncate">
                  {currentChat.name}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Layout */}
      <div className="flex-1 min-h-0">
        <MainLayout />
      </div>
    </div>
  )
}

export default App
