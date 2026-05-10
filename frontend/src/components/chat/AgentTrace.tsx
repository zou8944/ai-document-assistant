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
    const totalMs = state.timings?.total_ms ?? totalToolMs
    if (totalMs > 0) {
      parts.push(
        totalMs >= 1000
          ? `${(totalMs / 1000).toFixed(1)}s`
          : `${totalMs}ms`
      )
    }
    if (parts.length === 0) {
      return isRunning ? 'Agent' : 'Agent finished'
    }
    return `Agent (${parts.join(' \u00b7 ')})`
  }, [stepCount, totalToolMs, isRunning, state.timings])

  const StatusIcon = useMemo(() => {
    if (isError) return XCircleIcon
    if (isCancelled) return NoSymbolIcon
    if (hasHalted) return CheckCircleIcon
    if (isDone) return CheckCircleIcon
    return CpuChipIcon
  }, [isError, isCancelled, hasHalted, isDone])

  const statusColorClass = useMemo(() => {
    if (isError) return 'text-red-600'
    if (isCancelled) return 'text-amber-600'
    if (isDone) return 'text-emerald-600'
    return 'text-blue-600'
  }, [isError, isCancelled, isDone])

  if (visibleSteps.length === 0 && !isRunning && !isDone && !isError && !isCancelled) {
    return null
  }

  return (
    <div className="mb-2 rounded-xl border border-amber-200/50 backdrop-blur-sm bg-amber-50/60 overflow-hidden shadow-sm">
      {/* Header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left bg-amber-100/40 hover:bg-amber-100/60 transition-colors"
      >
        <div className="flex items-center space-x-2">
          <StatusIcon className={clsx('w-4 h-4', statusColorClass)} />
          <span className="text-xs font-semibold text-gray-800">{headerText}</span>
          {isRunning && (
            <ArrowPathIcon className="w-3 h-3 text-blue-600 animate-spin" />
          )}
        </div>
        <div className="flex items-center space-x-1">
          {hasHalted && (
            <span className="text-[10px] font-medium text-amber-700">Halted</span>
          )}
          {isCancelled && (
            <span className="text-[10px] font-medium text-amber-700">Cancelled</span>
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
        <div className="px-2.5 pb-2.5 pt-1.5 space-y-1.5">
          {visibleSteps.map((step, index) => (
            <AgentTraceStep
              key={`${step.kind}-${step.iteration}-${index}`}
              step={step}
              isLast={index === visibleSteps.length - 1}
            />
          ))}

          {/* Final answer indicator */}
          {(isDone || hasHalted) && state.finalText && (
            <div className="flex items-center space-x-2 px-2 py-1">
              <CheckCircleIcon className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-xs font-medium text-emerald-700">Final answer</span>
            </div>
          )}

          {/* Timing details */}
          {state.timings && (
            <div className="pt-2 mt-0.5 border-t border-amber-200/40">
              <div className="text-[10px] text-gray-500 space-x-1.5 px-2">
                <span>总计 {(state.timings.total_ms / 1000).toFixed(1)}s</span>
                <span>·</span>
                <span>LLM {(state.timings.llm_total_ms / 1000).toFixed(1)}s</span>
                <span>·</span>
                <span>Tools {(state.timings.tools_total_ms / 1000).toFixed(1)}s</span>
                <span>·</span>
                <span>{state.timings.iteration_count} 轮迭代</span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default AgentTrace
