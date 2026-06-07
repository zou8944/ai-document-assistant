/**
 * Agent trace panel — block container with global expand/collapse
 *
 * The entire trace area can be expanded or collapsed via a header bar.
 * User preference is stored globally and applies to new messages too.
 * When collapsed, the header shows the live count of visible blocks.
 * Individual block expand/collapse states inside are preserved.
 */

import React, { useMemo } from 'react'
import { SparklesIcon, ChevronDownIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'
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
  const expanded = useAppStore((s) => s.agentTraceExpanded)
  const setExpanded = useAppStore((s) => s.setAgentTraceExpanded)

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
      {/* Header bar — controls global expand/collapse */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={clsx(
          'w-full flex items-center justify-between px-4 py-2.5 rounded-2xl border transition-colors',
          expanded
            ? 'border-warm-line bg-transparent cursor-pointer hover:bg-white/40'
            : 'border-warm-line bg-white/40 cursor-pointer hover:bg-white/60'
        )}
      >
        <div className="flex items-center space-x-2">
          <SparklesIcon className="w-4 h-4 text-muted" />
          <span className="text-meta-md font-medium text-ink">思考过程</span>
          {!expanded && blockCount > 0 && (
            <span className="text-meta-sm text-muted">{blockCount} 个步骤</span>
          )}
          {isRunning && (
            <span className="w-1.5 h-1.5 rounded-full bg-muted animate-pulse" />
          )}
        </div>
        <div className={clsx('transition-transform duration-200', expanded && 'rotate-180')}>
          <ChevronDownIcon className="w-4 h-4 text-faint" />
        </div>
      </button>

      {/* Expandable steps area */}
      <Collapsible expanded={expanded}>
        <div className="mt-1.5 space-y-1.5">
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
            <div className="text-meta-xs text-faint tabular-nums px-1">
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
