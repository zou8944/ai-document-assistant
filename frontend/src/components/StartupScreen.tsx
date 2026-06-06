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
        <img src="/logo.png" alt="Logo" className="w-16 h-16 rounded-2xl shadow-lg object-cover" />
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