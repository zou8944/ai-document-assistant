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

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Title Bar with drag region */}
      <div
        className="flex-shrink-0 h-12 bg-white/70 backdrop-blur-xl border-b border-white/30"
        style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
      >
        <div className="flex items-center justify-between h-full">
          {/* Left side - reserve space for system buttons (about 78px) */}
          <div className="flex items-center space-x-3 pl-20">
            <img src="/logo.png" alt="Logo" className="w-6 h-6 rounded-md object-cover" />
            <h1 className="text-lg font-semibold text-[#1c1c1e]">
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
  )
}

export default App
