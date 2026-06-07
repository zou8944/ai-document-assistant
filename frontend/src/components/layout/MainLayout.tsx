/**
 * Main application layout with sidebar and content area
 */

import React from 'react'
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
    setSidebarWidth
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

  return (
    <div className={`h-full ${className || ''}`}>
      <div className="flex h-full">
        {/* Sidebar - Dynamic width */}
        <div
          className="flex-shrink-0 h-full"
          style={{ width: `${sidebarWidth}px` }}
        >
          <Sidebar />
        </div>

        {/* Resizable handle */}
        <ResizableHandle
          onResize={handleResize}
          onKeyboardResize={handleKeyboardResize}
          currentWidth={sidebarWidth}
          minWidth={MIN_SIDEBAR_WIDTH}
          maxWidth={MAX_SIDEBAR_WIDTH}
        />

        {/* Main Content Area - Flexible width */}
        <div className="flex-1 min-w-0">
          {renderMainContent()}
        </div>
      </div>
    </div>
  )
}

export default MainLayout