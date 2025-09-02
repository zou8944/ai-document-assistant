/**
 * Custom hook to manage application startup state
 * Monitors backend service status and provides loading state
 */

import { useState, useEffect } from 'react'
import { getProcessManager } from '../services/processManager'

interface StartupState {
  isLoading: boolean
  isReady: boolean
  error: string | null
  message: string
}

export const useStartup = () => {
  const [state, setState] = useState<StartupState>({
    isLoading: true,
    isReady: false,
    error: null,
    message: '正在启动服务...'
  })

  useEffect(() => {
    const processManager = getProcessManager()

    // Update message based on connection status
    const updateMessage = (connected: boolean) => {
      setState(prev => ({
        ...prev,
        message: connected ? '服务已就绪' : '正在连接后端服务...'
      }))
    }

    // Handle server ready event
    const onServerReady = () => {
      setState({
        isLoading: false,
        isReady: true,
        error: null,
        message: '服务已就绪'
      })
    }

    // Handle server disconnected event
    const onServerDisconnected = () => {
      setState(prev => ({
        ...prev,
        isLoading: !prev.isReady, // Only show loading if we weren't ready before
        isReady: false,
        message: '后端服务连接中断'
      }))
    }

    // Handle connection status changes
    const onConnectionStatusChanged = (connected: boolean) => {
      updateMessage(connected)
      if (!connected && state.isReady) {
        setState(prev => ({
          ...prev,
          isReady: false,
          message: '正在重新连接...'
        }))
      }
    }

    // Set up event listeners
    processManager.on('server-ready', onServerReady)
    processManager.on('server-disconnected', onServerDisconnected)
    processManager.on('connection-status-changed', onConnectionStatusChanged)

    // Check initial state
    if (processManager.isServerConnected()) {
      onServerReady()
    } else {
      // Try to wait for server with timeout
      processManager.waitForServer(30000)
        .then(() => {
          // Server is ready, onServerReady will be called by event
        })
        .catch((error) => {
          setState({
            isLoading: false,
            isReady: false,
            error: error.message,
            message: '启动失败'
          })
        })
    }

    // Cleanup event listeners
    return () => {
      processManager.off('server-ready', onServerReady)
      processManager.off('server-disconnected', onServerDisconnected)
      processManager.off('connection-status-changed', onConnectionStatusChanged)
    }
  }, [])

  // Retry connection
  const retry = async () => {
    setState(prev => ({
      ...prev,
      isLoading: true,
      error: null,
      message: '正在重新启动服务...'
    }))

    try {
      const processManager = getProcessManager()
      await processManager.restartServer()
      // onServerReady will be called by event
    } catch (error) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : '启动失败',
        message: '启动失败'
      }))
    }
  }

  return {
    ...state,
    retry
  }
}

export default useStartup