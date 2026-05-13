/**
 * Agent trace panel — block container
 */

import React, { useMemo } from 'react'
import { AgentMessageState } from '../../types/agent'
import AgentTraceStep from './AgentTraceStep'

interface AgentTraceProps {
  state: AgentMessageState
}

/** Tools that are internal plumbing — not useful to show in the trace UI. */
const INTERNAL_TOOL_NAMES = new Set(['cite_sources', 'citations', 'start_answer'])

export const AgentTrace: React.FC<AgentTraceProps> = ({ state }) => {
  const visibleSteps = useMemo(() => {
    return state.steps.filter((s) => {
      if (s.hidden) return false
      if (s.kind === 'thinking' && (!s.text || s.text.trim() === '')) return false
      if (s.kind === 'tool' && INTERNAL_TOOL_NAMES.has(s.toolName ?? '')) return false
      return true
    })
  }, [state.steps])

  const isRunning = state.status === 'running'

  if (visibleSteps.length === 0 && !isRunning) {
    return null
  }

  const totalTime = state.timings?.total_ms

  return (
    <div className="mb-2 space-y-1.5">
      {visibleSteps.map((step, index) => (
        <AgentTraceStep
          key={`${step.kind}-${step.iteration}-${index}`}
          step={step}
          isLast={index === visibleSteps.length - 1}
          isRunning={isRunning}
        />
      ))}
      {totalTime !== undefined && !isRunning && (
        <div className="text-[11px] text-[#AEAEB2] tabular-nums">
          总耗时 {totalTime >= 1000 ? `${(totalTime / 1000).toFixed(1)}s` : `${totalTime}ms`}
          {state.timings && state.timings.iteration_count > 1 && (
            <span> · {state.timings.iteration_count} 轮</span>
          )}
        </div>
      )}
    </div>
  )
}

export default AgentTrace
