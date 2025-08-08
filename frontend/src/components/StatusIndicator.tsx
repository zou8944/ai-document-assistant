/**
 * StatusIndicator component for showing processing progress and status.
 * Following Apple Liquid Glass design with smooth progress animations.
 */

import React from 'react'
import { 
  CheckCircleIcon, 
  XCircleIcon, 
  ExclamationTriangleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline'
import clsx from 'clsx'

export type StatusType = 'idle' | 'processing' | 'progress' | 'success' | 'error' | 'warning'

interface StatusIndicatorProps {
  status: StatusType
  message?: string
  progress?: {
    current: number
    total: number
    label?: string
  }
  details?: string[]
  className?: string
  onDismiss?: () => void
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  message,
  progress,
  details = [],
  className,
  onDismiss
}) => {
  if (status === 'idle') {
    return null
  }

  const getStatusIcon = () => {
    switch (status) {
      case 'processing':
        return <ArrowPathIcon className="w-5 h-5 text-macos-blue animate-spin" />
      case 'progress':
        return <ArrowPathIcon className="w-5 h-5 text-macos-blue animate-spin" />
      case 'success':
        return <CheckCircleIcon className="w-5 h-5 text-green-500" />
      case 'error':
        return <XCircleIcon className="w-5 h-5 text-red-500" />
      case 'warning':
        return <ExclamationTriangleIcon className="w-5 h-5 text-yellow-500" />
      default:
        return null
    }
  }

  const getStatusColor = () => {
    switch (status) {
      case 'processing':
      case 'progress':
        return 'border-macos-blue bg-blue-50/50'
      case 'success':
        return 'border-green-300 bg-green-50/50'
      case 'error':
        return 'border-red-300 bg-red-50/50'
      case 'warning':
        return 'border-yellow-300 bg-yellow-50/50'
      default:
        return 'border-macos-gray-300'
    }
  }

  const getProgressPercentage = () => {
    if (!progress || progress.total === 0) return 0
    return Math.round((progress.current / progress.total) * 100)
  }

  const formatProgressLabel = () => {
    if (!progress) return ''
    
    const percentage = getProgressPercentage()
    const label = progress.label || '进度'
    
    return `${label}: ${progress.current}/${progress.total} (${percentage}%)`
  }

  return (
    <div 
      className={clsx(
        'glass-morph rounded-xl p-4 border-2 transition-all duration-300',
        getStatusColor(),
        'animate-slide-up',
        className
      )}
    >
      <div className="flex items-start space-x-3">
        <div className="flex-shrink-0 mt-0.5">
          {getStatusIcon()}
        </div>
        
        <div className="flex-1 min-w-0">
          {message && (
            <div className={clsx(
              'text-sm font-medium mb-2',
              status === 'error' ? 'text-red-700' :
              status === 'warning' ? 'text-yellow-700' :
              status === 'success' ? 'text-green-700' :
              'text-macos-gray-900'
            )}>
              {message}
            </div>
          )}

          {/* Progress Bar */}
          {(status === 'progress' || status === 'processing') && progress && (
            <div className="space-y-2 mb-3">
              <div className="flex justify-between items-center">
                <span className="text-xs text-macos-gray-600">
                  {formatProgressLabel()}
                </span>
              </div>
              
              <div className="w-full bg-macos-gray-200 rounded-full h-2 overflow-hidden">
                <div
                  className={clsx(
                    'h-2 rounded-full transition-all duration-500 ease-out',
                    'bg-gradient-to-r from-macos-blue to-blue-500'
                  )}
                  style={{ 
                    width: `${getProgressPercentage()}%`,
                    transform: 'translateX(0%)',
                  }}
                />
              </div>
            </div>
          )}

          {/* Processing Animation for non-progress states */}
          {status === 'processing' && !progress && (
            <div className="mb-3">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-macos-blue rounded-full animate-bounce" />
                <div className="w-2 h-2 bg-macos-blue rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                <div className="w-2 h-2 bg-macos-blue rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
              </div>
            </div>
          )}

          {/* Details */}
          {details.length > 0 && (
            <div className="space-y-1">
              {details.map((detail, index) => (
                <div 
                  key={index}
                  className="text-xs text-macos-gray-600 flex items-center space-x-1"
                >
                  <span className="w-1 h-1 bg-macos-gray-400 rounded-full" />
                  <span>{detail}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Dismiss Button */}
        {onDismiss && (status === 'success' || status === 'error' || status === 'warning') && (
          <button
            onClick={onDismiss}
            className={clsx(
              'flex-shrink-0 p-1 rounded hover:bg-white/20 transition-colors',
              'text-macos-gray-400 hover:text-macos-gray-600'
            )}
          >
            <XCircleIcon className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  )
}

// Convenience components for specific status types
export const ProcessingIndicator: React.FC<Omit<StatusIndicatorProps, 'status'>> = (props) => (
  <StatusIndicator {...props} status="processing" />
)

export const ProgressIndicator: React.FC<Omit<StatusIndicatorProps, 'status'>> = (props) => (
  <StatusIndicator {...props} status="progress" />
)

export const SuccessIndicator: React.FC<Omit<StatusIndicatorProps, 'status'>> = (props) => (
  <StatusIndicator {...props} status="success" />
)

export const ErrorIndicator: React.FC<Omit<StatusIndicatorProps, 'status'>> = (props) => (
  <StatusIndicator {...props} status="error" />
)

export const WarningIndicator: React.FC<Omit<StatusIndicatorProps, 'status'>> = (props) => (
  <StatusIndicator {...props} status="warning" />
)

export default StatusIndicator