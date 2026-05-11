/**
 * Agent trace panel — block container
 */

import React, { useMemo } from 'react'
import { AgentMessageState } from '../../types/agent'
import AgentTraceStep from './AgentTraceStep'

interface AgentTraceProps {
  state: AgentMessageState
}

export const AgentTrace: React.FC<AgentTraceProps> = ({ state }) => {
  const visibleSteps = useMemo(() => {
    return state.steps.filter((s) => {
      if (s.hidden) return false
      if (s.kind === 'thinking' && (!s.text || s.text.trim() === '')) return false
      return true
    })
  }, [state.steps])

  const isRunning = state.status === 'running'

  if (visibleSteps.length === 0 && !isRunning) {
    return null
  }

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
    </div>
  )
}

export default AgentTrace
