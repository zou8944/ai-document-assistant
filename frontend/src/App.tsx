/**
 * Main App component with new layout architecture
 */

import React from 'react'
import MainLayout from './components/layout/MainLayout'

export const App: React.FC = () => {
  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Title Bar with drag region */}
      <div 
        className="flex-shrink-0 h-12 bg-gradient-to-r from-white/80 to-white/60 backdrop-blur-xl border-b border-white/20" 
        style={{ WebkitAppRegion: 'drag' }}
      >
        <div className="flex items-center justify-between h-full">
          {/* Left side - reserve space for system buttons (about 78px) */}
          <div className="flex items-center space-x-3 pl-20">
            <div className="w-6 h-6 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full" />
            <h1 className="text-lg font-semibold text-gray-900">
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