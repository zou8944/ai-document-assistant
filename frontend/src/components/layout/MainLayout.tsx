/**
 * Main application layout with sidebar and content area.
 * On <md (768px) the sidebar becomes a slide-over sheet with backdrop.
 */

import React, { useEffect } from 'react'
import { useAppStore } from '../../store/appStore'
import Sidebar from './Sidebar'
import ResizableHandle from './ResizableHandle'
import KnowledgeBaseOverview from '../knowledge/KnowledgeBaseOverview'
import KnowledgeBaseManagement from '../knowledge/KnowledgeBaseManagement'
import ChatInterface from '../chat/ChatInterface'
import SettingsPage from '../settings/SettingsPage'

interface MainLayoutProps {
  className?: string
}

export const MainLayout: React.FC<MainLayoutProps> = ({ className }) => {
  const {
    activeSidebarSection,
    activeKnowledgeBase,
    sidebarWidth,
    setSidebarWidth,
    mobileSidebarOpen,
    setMobileSidebarOpen,
  } = useAppStore()

  const renderMainContent = () => {
    switch (activeSidebarSection) {
      case 'knowledge':
        if (activeKnowledgeBase) {
          return <KnowledgeBaseManagement />
        }
        return <KnowledgeBaseOverview />

      case 'chat':
        return <ChatInterface />

      case 'settings':
        return <SettingsPage />

      default:
        return <KnowledgeBaseOverview />
    }
  }

  const MIN_SIDEBAR_WIDTH = 200
  const MAX_SIDEBAR_WIDTH = 480
  const KEYBOARD_STEP = 16

  const clampWidth = (width: number) =>
    Math.max(MIN_SIDEBAR_WIDTH, Math.min(MAX_SIDEBAR_WIDTH, width))

  const handleResize = (deltaX: number) => {
    setSidebarWidth(clampWidth(sidebarWidth + deltaX))
  }

  const handleKeyboardResize = (direction: -1 | 1) => {
    setSidebarWidth(clampWidth(sidebarWidth + direction * KEYBOARD_STEP))
  }

  // Close mobile sidebar when section changes (user tapped a nav item)
  useEffect(() => {
    setMobileSidebarOpen(false)
  }, [activeSidebarSection, setMobileSidebarOpen])

  return (
    <div className={`h-full ${className || ''}`}>
      <div className="flex h-full">
        {/* Desktop sidebar — hidden on <md */}
        <div
          className="hidden md:flex flex-shrink-0 h-full"
          style={{ width: `${sidebarWidth}px` }}
        >
          <Sidebar />
        </div>

        {/* Desktop resizable handle — hidden on <md */}
        <div className="hidden md:block">
          <ResizableHandle
            onResize={handleResize}
            onKeyboardResize={handleKeyboardResize}
            currentWidth={sidebarWidth}
            minWidth={MIN_SIDEBAR_WIDTH}
            maxWidth={MAX_SIDEBAR_WIDTH}
          />
        </div>

        {/* Mobile sidebar sheet — visible on <md when open */}
        {mobileSidebarOpen && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm md:hidden animate-fade-in"
              onClick={() => setMobileSidebarOpen(false)}
              aria-hidden
            />
            {/* Sheet */}
            <div className="fixed inset-y-0 left-0 z-50 w-72 max-w-[80vw] md:hidden animate-slide-in-left">
              <Sidebar className="h-full" />
            </div>
          </>
        )}

        {/* Main Content Area - Flexible width */}
        <div className="flex-1 min-w-0">
          {renderMainContent()}
        </div>
      </div>
    </div>
  )
}

export default MainLayout
