/**
 * ErrorBoundary — top-level safety net for unexpected render errors.
 *
 * Catches uncaught React render errors, shows a Glass fallback panel
 * with a "reload" action, and prevents the entire app from unmounting.
 * The last-resort fallback when individual components fail to render.
 */

import React from 'react'
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline'

interface Props {
  children: React.ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary] Caught render error:', error, info)
  }

  private handleReload = () => {
    window.location.reload()
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="fixed inset-0 z-[200] flex items-center justify-center p-6 bg-gradient-to-br from-blue-50 to-indigo-100">
        <div className="glass-morph rounded-2xl border border-white/20 bg-white/90 backdrop-blur-xl shadow-2xl max-w-md w-full p-8 animate-scale-in">
          <div className="flex items-center gap-3 mb-4">
            <ExclamationTriangleIcon className="w-8 h-8 text-red-500 flex-shrink-0" />
            <h1 className="text-xl font-semibold text-ink">应用出现异常</h1>
          </div>
          <p className="text-sm text-ink/65 leading-relaxed mb-4">
            页面渲染时遇到未处理的错误。已记录到控制台。
          </p>
          {this.state.error && (
            <pre className="text-xs text-ink/65 bg-gray-50 border border-gray-200 rounded-lg p-3 mb-6 max-h-40 overflow-auto whitespace-pre-wrap break-words">
              {this.state.error.message}
            </pre>
          )}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={this.handleReset}
              className="px-4 py-2 text-sm text-ink/80 hover:text-ink rounded-lg transition-colors"
            >
              重试
            </button>
            <button
              type="button"
              onClick={this.handleReload}
              className="px-4 py-2 text-sm font-medium text-white bg-accent hover:bg-accent-hover rounded-lg transition-colors"
            >
              重新加载应用
            </button>
          </div>
        </div>
      </div>
    )
  }
}

export default ErrorBoundary
