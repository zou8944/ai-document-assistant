/**
 * Main App component with startup screen and main layout
 */

import React, { useEffect, useRef } from 'react'
import MainLayout from './components/layout/MainLayout'
import StartupScreen from './components/StartupScreen'
import useStartup from './hooks/useStartup'
import { useAPIClient, extractData } from './services/apiClient'
import { useAppStore } from './store/appStore'

export const App: React.FC = () => {
  const { isLoading, isReady, error, message } = useStartup()
  const apiClient = useAPIClient()
  const setChatSessions = useAppStore((s) => s.setChatSessions)
  const bootstrapped = useRef(false)

  // Once backend is ready, load chat list from server (single source of truth)
  useEffect(() => {
    if (!isReady || bootstrapped.current) return
    bootstrapped.current = true

    apiClient.listChats(0, 1000)
      .then((res) => {
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
      })
      .catch((err) => {
        console.error('Failed to load chat list:', err)
      })
  }, [isReady, apiClient, setChatSessions])

  // Show startup screen while loading or if there's an error
  if (isLoading || !isReady) {
    return (
      <StartupScreen
        message={error ? `${message} - ${error}` : message}
      />
    )
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