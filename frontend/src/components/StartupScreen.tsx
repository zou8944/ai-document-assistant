/**
 * Startup loading screen component
 * Shows loading animation while backend service is starting up
 */

import React from 'react'

interface StartupScreenProps {
  message?: string
}

export const StartupScreen: React.FC<StartupScreenProps> = ({ 
  message = '正在启动应用...' 
}) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {/* Logo and title */}
      <div className="flex items-center space-x-4 mb-8">
        <div className="w-16 h-16 bg-gradient-to-r from-blue-500 to-purple-500 rounded-2xl flex items-center justify-center shadow-lg">
          <svg 
            className="w-8 h-8 text-white" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" 
            />
          </svg>
        </div>
        <h1 className="text-3xl font-bold text-gray-900">AI 文档助手</h1>
      </div>

      {/* Loading animation */}
      <div className="mb-6">
        <div className="flex space-x-2">
          <div className="w-3 h-3 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
          <div className="w-3 h-3 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
          <div className="w-3 h-3 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
        </div>
      </div>

      {/* Status message */}
      <div className="text-center">
        <p className="text-gray-700 text-lg font-medium mb-2">{message}</p>
        <p className="text-gray-500 text-sm">
          请稍候，正在初始化应用...
        </p>
      </div>

      {/* Loading spinner */}
      <div className="mt-8">
        <div className="w-8 h-8 border-2 border-blue-200 border-t-blue-500 rounded-full animate-spin"></div>
      </div>
    </div>
  )
}

export default StartupScreen