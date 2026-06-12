/**
 * Agent trace panel — block container with per-message expand/collapse
 *
 * Each trace instance owns its own expand/collapse state. Toggling here only
 * affects this message (and updates the global default for any NEW messages
 * mounted afterwards). Previously-rendered messages are unaffected, so their
 * trace expand state stays where the user left it.
 */

import React, { useMemo, useState } from 'react'
import { ChevronDownIcon, ChevronRightIcon } from '@heroicons/react/24/outline'
import { AgentMessageState } from '../../types/agent'
import { useAppStore } from '../../store/appStore'
import { Collapsible } from './AgentTraceStep'
import AgentTraceStep from './AgentTraceStep'

interface AgentTraceProps {
  state: AgentMessageState
}

/** Tools that are internal plumbing — not useful to show in the trace UI. */
const INTERNAL_TOOL_NAMES = new Set(['cite_sources', 'citations', 'start_answer'])

export const AgentTrace: React.FC<AgentTraceProps> = ({ state }) => {
  const setGlobalExpanded = useAppStore((s) => s.setAgentTraceExpanded)
  // Seed from the current global default at mount time, then detach. Later
  // toggles in other messages won't re-render this instance.
  const [expanded, setLocalExpanded] = useState(() => useAppStore.getState().agentTraceExpanded)

  const handleToggle = () => {
    const next = !expanded
    setLocalExpanded(next)
    // Persist as the new default so future messages adopt this preference.
    setGlobalExpanded(next)
  }

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
  const blockCount = visibleSteps.length

  return (
    <div className="mb-2">
      {/* Header bar — per-message toggle; also seeds the default for new messages */}
      <button
        onClick={handleToggle}
        className="flex items-center space-x-1.5 cursor-pointer py-1.5 px-1 w-full text-left"
      >
        {expanded ? (
          <ChevronDownIcon className="w-4 h-4 text-faint transition-transform duration-200" />
        ) : (
          <ChevronRightIcon className="w-4 h-4 text-faint transition-transform duration-200" />
        )}
        <span className="text-meta-sm text-ink">Activities</span>
        {!expanded && blockCount > 0 && (
          <span className="text-meta-xs text-muted">{blockCount}</span>
        )}
        {isRunning && (
          <span className="w-1.5 h-1.5 rounded-full bg-muted animate-pulse" />
        )}
      </button>

      {/* Expandable steps area with left border */}
      <Collapsible expanded={expanded}>
        <div className="mt-1 ml-[7px] pl-3 border-l border-warm-line space-y-1.5">
          {visibleSteps.map((step, index) => (
            <div key={`${step.kind}-${step.iteration}-${index}`} className="animate-step-in">
              <AgentTraceStep
                step={step}
                isLast={index === visibleSteps.length - 1}
                isRunning={isRunning}
              />
            </div>
          ))}
          {totalTime !== undefined && !isRunning && (
            <div className="text-[10px] text-faint tabular-nums px-1">
              总耗时 {totalTime >= 1000 ? `${(totalTime / 1000).toFixed(1)}s` : `${totalTime}ms`}
              {state.timings && state.timings.iteration_count > 1 && (
                <span> · {state.timings.iteration_count} 轮</span>
              )}
            </div>
          )}
        </div>
      </Collapsible>
    </div>
  )
}

export default AgentTrace
