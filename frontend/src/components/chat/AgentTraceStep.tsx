/**
 * Single agent step rendering - flat, minimal style (Hermes UI inspired)
 */

import React, { useState, useCallback } from 'react'
import {
  LightBulbIcon,
  WrenchIcon,
  ArrowsPointingInIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  XCircleIcon,
  CheckCircleIcon,
  CodeBracketIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { AgentStep } from '../../types/agent'
import { renderToolTitle, renderToolSummary } from './toolRenderers'

export interface AgentTraceStepProps {
  step: AgentStep
  isLast: boolean
}

const StepIcon: React.FC<{ step: AgentStep }> = ({ step }) => {
  switch (step.kind) {
    case 'thinking':
      return <LightBulbIcon className="w-3.5 h-3.5 text-muted" />
    case 'tool':
      if (step.toolStatus === 'error') {
        return <XCircleIcon className="w-3.5 h-3.5 text-red-400" />
      }
      if (step.toolStatus === 'done') {
        return <CheckCircleIcon className="w-3.5 h-3.5 text-muted" />
      }
      return <WrenchIcon className="w-3.5 h-3.5 text-muted" />
    case 'compact':
      return <ArrowsPointingInIcon className="w-3.5 h-3.5 text-muted" />
    default:
      return null
  }
}

const StepLabel: React.FC<{ step: AgentStep }> = ({ step }) => {
  switch (step.kind) {
    case 'thinking':
      return <span className="text-[11px] text-muted font-medium">思考</span>
    case 'tool':
      return <span className="text-[11px] text-ink font-medium">{renderToolTitle(step)}</span>
    case 'compact':
      return (
        <span className="text-[11px] text-muted font-medium">
          压缩上下文
          {step.beforeTokens !== undefined && (
            <span className="text-warm-line font-normal">
              {' '}(~{step.beforeTokens} → ~{step.afterTokens} tokens)
            </span>
          )}
        </span>
      )
    default:
      return null
  }
}

/** Check whether a tool step has meaningful details to expand. */
function hasToolDetails(step: AgentStep): boolean {
  if (step.kind !== 'tool') return false
  const hasPreview = !!step.toolPreview && step.toolPreview.length > 0
  const hasInput = !!step.toolInput && Object.keys(step.toolInput).length > 0
  return hasPreview || hasInput
}

export const AgentTraceStep: React.FC<AgentTraceStepProps> = ({ step }) => {
  const [expanded, setExpanded] = useState(false)
  const [rawExpanded, setRawExpanded] = useState(false)

  const isTool = step.kind === 'tool'
  const hasDetails = hasToolDetails(step)
  const summary = isTool ? renderToolSummary(step) : null

  const toggleExpanded = useCallback(() => {
    if (hasDetails || step.kind === 'thinking') {
      setExpanded((v) => !v)
    }
  }, [hasDetails, step.kind])

  const toggleRawExpanded = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setRawExpanded((v) => !v)
  }, [])

  return (
    <div
      className={clsx(
        'rounded-md px-2 py-1 transition-colors',
        step.kind === 'thinking' && 'hover:bg-paper-dark/20',
        step.kind === 'tool' && 'border border-warm-border hover:bg-paper-dark/15',
        step.kind === 'compact' && 'hover:bg-paper-dark/10',
        (hasDetails || step.kind === 'thinking') && 'cursor-pointer'
      )}
      onClick={toggleExpanded}
    >
      {/* Header row */}
      <div className="flex items-center justify-between"
      >
        <div className="flex items-center space-x-2 min-w-0"
        >
          <StepIcon step={step} />
          <span className="text-xs truncate"
          >
            <StepLabel step={step} />
          </span>
          {step.toolStatus === 'running' && (
            <span className="flex-shrink-0 w-2 h-2 border border-muted border-t-transparent rounded-full animate-spin" />
          )}
          {step.toolMs !== undefined && step.toolStatus !== 'running' && (
            <span className="flex-shrink-0 text-[10px] text-muted">
              {step.toolMs >= 1000
                ? `${(step.toolMs / 1000).toFixed(1)}s`
                : `${step.toolMs}ms`}
            </span>
          )}
        </div>

        {(hasDetails || step.kind === 'thinking') && (
          <span className="flex-shrink-0 ml-2"
          >
            {expanded ? (
              <ChevronDownIcon className="w-3 h-3 text-muted" />
            ) : (
              <ChevronRightIcon className="w-3 h-3 text-muted" />
            )}
          </span>
        )}
      </div>

      {/* Result summary line */}
      {summary && step.toolStatus !== 'running' && (
        <div className="mt-0.5 text-[11px] text-muted leading-relaxed pl-5.5"
        >
          {summary}
        </div>
      )}

      {/* Thinking text (collapsed preview) */}
      {step.kind === 'thinking' && step.text && !expanded && (
        <p className="mt-0.5 text-[11px] text-muted leading-relaxed line-clamp-3 pl-5.5"
        >
          {step.text}
        </p>
      )}

      {/* Expanded content */}
      {expanded && (
        <div className="mt-1.5 space-y-1.5 pl-5.5"
        >
          {/* Thinking text (expanded) */}
          {step.kind === 'thinking' && step.text && (
            <div className="max-h-64 overflow-y-auto"
            >
              <p className="text-[13px] text-muted leading-relaxed whitespace-pre-wrap"
              >
                {step.text}
              </p>
            </div>
          )}

          {/* Tool result preview */}
          {isTool && step.toolPreview && (
            <div className="rounded-md bg-white border border-warm-border p-2"
            >
              <pre className="text-[11px] text-ink overflow-x-auto whitespace-pre-wrap break-all leading-relaxed font-mono"
              >
                {step.toolPreview.length > 500
                  ? step.toolPreview.slice(0, 500) + '...'
                  : step.toolPreview}
              </pre>
            </div>
          )}

          {/* Raw data toggle */}
          {isTool && hasDetails && (
            <div>
              <button
                onClick={toggleRawExpanded}
                className="flex items-center space-x-1 text-[10px] text-muted hover:text-ink transition-colors rounded px-1.5 py-0.5 hover:bg-paper-dark/30"
              >
                <CodeBracketIcon className="w-3 h-3" />
                <span>原始数据</span>
                {rawExpanded ? (
                  <ChevronDownIcon className="w-3 h-3" />
                ) : (
                  <ChevronRightIcon className="w-3 h-3" />
                )}
              </button>

              {rawExpanded && (
                <div className="mt-1.5 space-y-1.5"
                >
                  {step.toolInput && Object.keys(step.toolInput).length > 0 && (
                    <div className="rounded-md bg-white border border-warm-border p-2"
                    >
                      <div className="text-[10px] text-muted mb-1 font-semibold tracking-wide"
                      >输入</div>
                      <pre className="text-[10px] text-ink overflow-x-auto whitespace-pre-wrap break-all leading-relaxed font-mono"
                      >
                        {JSON.stringify(step.toolInput, null, 2)}
                      </pre>
                    </div>
                  )}
                  {step.toolPreview && (
                    <div className="rounded-md bg-white border border-warm-border p-2"
                    >
                      <div className="text-[10px] text-muted mb-1 font-semibold tracking-wide"
                      >输出</div>
                      <pre className="text-[10px] text-ink overflow-x-auto whitespace-pre-wrap break-all leading-relaxed font-mono"
                      >
                        {step.toolPreview}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default AgentTraceStep
