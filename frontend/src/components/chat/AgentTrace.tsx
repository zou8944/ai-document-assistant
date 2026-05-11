/**
 * Agent trace panel - flat, integrated into message flow (Hermes UI style)
 */

import React, { useMemo } from 'react'
import {
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
    return ArrowPathIcon
  }, [isError, isCancelled, hasHalted, isDone])

  const statusColorClass = useMemo(() => {
    if (isError) return 'text-red-500'
    if (isCancelled) return 'text-amber-500'
    if (isDone) return 'text-muted'
    return 'text-muted'
  }, [isError, isCancelled, isDone])

  if (visibleSteps.length === 0 && !isRunning && !isDone && !isError && !isCancelled) {
    return null
  }

  return (
    <div className="mb-4"
    >
      {/* Steps - flat style, no card border */}
      {visibleSteps.length > 0 && (
        <div className="space-y-1"
        >
          {visibleSteps.map((step, index) => (
            <AgentTraceStep
              key={`${step.kind}-${step.iteration}-${index}`}
              step={step}
              isLast={index === visibleSteps.length - 1}
            />
          ))}
        </div>
      )}

      {/* Final answer indicator */}
      {(isDone || hasHalted) && state.finalText && (
        <div className="flex items-center space-x-1.5 mt-2 px-1"
        >
          <StatusIcon className={clsx('w-3.5 h-3.5', statusColorClass)} />
          <span className="text-[11px] text-muted"
          >
            {headerText}
            {hasHalted && ' · Halted'}
            {isCancelled && ' · Cancelled'}
          </span>
        </div>
      )}
    </div>
  )
}

export default AgentTrace
