/**
 * Agent trace panel - collapsible card showing agent execution steps
 */

import React, { useState, useMemo } from 'react'
import {
  ChevronDownIcon,
  ChevronRightIcon,
  CpuChipIcon,
  CheckCircleIcon,
  XCircleIcon,
  NoSymbolIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { AgentMessageState } from '../../types/agent'
import AgentTraceStep from './AgentTraceStep'

interface AgentTraceProps {
  state: AgentMessageState
}

export const AgentTrace: React.FC<AgentTraceProps> = ({ state }) => {
  const [expanded, setExpanded] = useState(true)

  // Filter out hidden and empty thinking steps
  const visibleSteps = useMemo(() => {
    return state.steps.filter((s) => {
      if (s.hidden) return false
      if (s.kind === 'thinking' && (!s.text || s.text.trim() === '')) return false
      return true
    })
  }, [state.steps])

  const stepCount = visibleSteps.length
  const isRunning = state.status === 'running'
  const isError = state.status === 'error'
  const isCancelled = state.status === 'cancelled'
  const isDone = state.status === 'done'
  const hasHalted = state.halted

  // Compute total tool time
  const totalToolMs = useMemo(() => {
    return visibleSteps
      .filter((s) => s.kind === 'tool' && s.toolMs !== undefined)
      .reduce((sum, s) => sum + (s.toolMs || 0), 0)
  }, [visibleSteps])

  const headerText = useMemo(() => {
    const parts: string[] = []
    if (stepCount > 0) {
      parts.push(`${stepCount} step${stepCount > 1 ? 's' : ''}`)
    }
    if (totalToolMs > 0) {
      parts.push(
        totalToolMs >= 1000
          ? `${(totalToolMs / 1000).toFixed(1)}s`
          : `${totalToolMs}ms`
      )
    }
    if (parts.length === 0) {
      return isRunning ? 'Agent' : 'Agent finished'
    }
    return `Agent (${parts.join(' \u00b7 ')})`
  }, [stepCount, totalToolMs, isRunning])

  const StatusIcon = useMemo(() => {
    if (isError) return XCircleIcon
    if (isCancelled) return NoSymbolIcon
    if (hasHalted) return CheckCircleIcon
    if (isDone) return CheckCircleIcon
    return CpuChipIcon
  }, [isError, isCancelled, hasHalted, isDone])

  const statusColorClass = useMemo(() => {
    if (isError) return 'text-red-400'
    if (isCancelled) return 'text-amber-400'
    if (isDone) return 'text-emerald-400'
    return 'text-blue-400'
  }, [isError, isCancelled, isDone])

  if (visibleSteps.length === 0 && !isRunning && !isDone && !isError && !isCancelled) {
    return null
  }

  return (
    <div className="mb-2 rounded-xl border border-white/10 backdrop-blur-md bg-white/5 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center space-x-2">
          <StatusIcon className={clsx('w-4 h-4', statusColorClass)} />
          <span className="text-xs font-medium text-gray-300">{headerText}</span>
          {isRunning && (
            <ArrowPathIcon className="w-3 h-3 text-blue-400 animate-spin" />
          )}
        </div>
        <div className="flex items-center space-x-1">
          {hasHalted && (
            <span className="text-[10px] text-amber-400">Halted</span>
          )}
          {isCancelled && (
            <span className="text-[10px] text-amber-400">Cancelled</span>
          )}
          {expanded ? (
            <ChevronDownIcon className="w-3.5 h-3.5 text-gray-500" />
          ) : (
            <ChevronRightIcon className="w-3.5 h-3.5 text-gray-500" />
          )}
        </div>
      </button>

      {/* Steps */}
      {expanded && visibleSteps.length > 0 && (
        <div className="px-3 pb-2.5 pt-0.5">
          {visibleSteps.map((step, index) => (
            <AgentTraceStep
              key={`${step.kind}-${step.iteration}-${index}`}
              step={step}
              isLast={index === visibleSteps.length - 1}
            />
          ))}

          {/* Final answer indicator */}
          {(isDone || hasHalted) && state.finalText && (
            <div className="relative pt-1">
              <div className="flex items-start space-x-2">
                <div className="flex-shrink-0 mt-0.5 w-3.5 h-3.5 flex items-center justify-center">
                  <CheckCircleIcon className="w-3.5 h-3.5 text-emerald-400" />
                </div>
                <span className="text-xs text-emerald-300">Final answer</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default AgentTrace
