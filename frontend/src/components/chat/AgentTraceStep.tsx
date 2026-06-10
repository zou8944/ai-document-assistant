/**
 * Agent step blocks — distinct card containers per step
 *
 * Each block is a self-contained card with rounded corners, background fill,
 * and clear visual hierarchy inside.
 */

import React, { useState, useCallback, useEffect } from 'react'
import {
  ChevronDownIcon,
  CheckCircleIcon,
  XCircleIcon,
  SparklesIcon,
  CodeBracketIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { AgentStep } from '../../types/agent'
import { renderToolTitle, renderToolSummary } from './toolRenderers'

export interface AgentTraceStepProps {
  step: AgentStep
  isLast: boolean
  isRunning: boolean
}

function hasToolDetails(step: AgentStep): boolean {
  if (step.kind !== 'tool') return false
  return !!step.toolPreview || (!!step.toolInput && Object.keys(step.toolInput).length > 0)
}

/* ================================================================ */
/* Collapsible — smooth CSS transition wrapper                       */
/* ================================================================ */

export const Collapsible: React.FC<{ expanded: boolean; children: React.ReactNode }> = ({
  expanded,
  children,
}) => {
  return (
    <div
      className={clsx(
        'grid transition-[grid-template-rows] duration-200 ease-out',
        expanded ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
      )}
    >
      <div className="overflow-hidden">{children}</div>
    </div>
  )
}

/* ================================================================ */
/* Thinking block — glass card                                       */
/* ================================================================ */

const ThinkingBlock: React.FC<{ step: AgentStep; isRunning: boolean }> = ({ step, isRunning }) => {
  const [expanded, setExpanded] = useState(isRunning)

  useEffect(() => {
    if (isRunning) setExpanded(true)
  }, [isRunning])

  if (!step.text) return null

  return (
    <div
      className="rounded-xl border border-warm-line cursor-pointer overflow-hidden"
      onClick={() => setExpanded((v) => !v)}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center space-x-2">
          <SparklesIcon className="w-4 h-4 text-muted" />
          <span className="text-meta-xs text-ink">思考过程</span>
          {isRunning && (
            <span className="w-1.5 h-1.5 rounded-full bg-muted animate-pulse" />
          )}
        </div>
        <div className="flex items-center space-x-1">
          {step.thinkingMs !== undefined && !isRunning && (
            <span className="text-[10px] text-faint tabular-nums">
              {step.thinkingMs >= 1000
                ? `${(step.thinkingMs / 1000).toFixed(1)}s`
                : `${step.thinkingMs}ms`}
            </span>
          )}
          <div className={clsx('transition-transform duration-200', expanded && 'rotate-180')}>
            <ChevronDownIcon className="w-3.5 h-3.5 text-faint" />
          </div>
        </div>
      </div>

      {/* Body */}
      <Collapsible expanded={expanded}>
        <div className="px-3 pb-2 pt-0 ml-6">
          <p className="text-meta-xs text-inverse leading-[1.5] whitespace-pre-wrap">
            {step.text}
          </p>
        </div>
      </Collapsible>
    </div>
  )
}

/* ================================================================ */
/* Tool block — border-only card                                     */
/* ================================================================ */

const ToolBlock: React.FC<{ step: AgentStep }> = ({ step }) => {
  const [expanded, setExpanded] = useState(false)
  const [rawExpanded, setRawExpanded] = useState(false)

  const hasDetails = hasToolDetails(step)
  const summary = renderToolSummary(step)

  const toggleRawExpanded = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setRawExpanded((v) => !v)
  }, [])

  const isRunning = step.toolStatus === 'running'
  const isDone = step.toolStatus === 'done'
  const isError = step.toolStatus === 'error'

  return (
    <div
      className={clsx(
        'rounded-xl border',
        isError ? 'border-red-200/50' : 'border-warm-line'
      )}
    >
      {/* Clickable header area */}
      <div
        className={clsx(
          'px-3 py-2',
          hasDetails && 'cursor-pointer'
        )}
        onClick={hasDetails ? () => setExpanded((v) => !v) : undefined}
      >
        {/* Row 1: icon + title + chevron */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2 min-w-0">
            {/* Status icon */}
            <div className="flex-shrink-0">
              {isError ? (
                <XCircleIcon className="w-4 h-4 text-red-400" />
              ) : isDone ? (
                <CheckCircleIcon className="w-4 h-4 text-apple-green" />
              ) : isRunning ? (
                <span className="block w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
              ) : (
                <CheckCircleIcon className="w-4 h-4 text-subtle" />
              )}
            </div>

            {/* Title */}
            <span className="text-meta-xs text-ink truncate">
              {renderToolTitle(step)}
            </span>
          </div>

          {/* Time + chevron */}
          <div className="flex items-center space-x-1 flex-shrink-0 ml-2">
            {step.toolMs !== undefined && !isRunning && (
              <span className="text-[10px] text-faint tabular-nums">
                {step.toolMs >= 1000
                  ? `${(step.toolMs / 1000).toFixed(1)}s`
                  : `${step.toolMs}ms`}
              </span>
            )}
            {hasDetails && (
              <div className={clsx('transition-transform duration-200', expanded && 'rotate-180')}>
                <ChevronDownIcon className="w-3.5 h-3.5 text-faint" />
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Expanded details */}
      <Collapsible expanded={expanded}>
        <div className="px-3 pb-3 ml-6 space-y-2">
          {summary && !isRunning && (
            <div className="text-meta-xs text-inverse">{summary}</div>
          )}

          {step.toolPreview && (
            <div className="rounded-xl bg-white/50 backdrop-blur-sm border border-warm-line p-3">
              <pre className="text-[10px] text-inverse overflow-x-auto whitespace-pre-wrap break-all leading-relaxed font-mono">
                {step.toolPreview.length > 500
                  ? step.toolPreview.slice(0, 500) + '...'
                  : step.toolPreview}
              </pre>
            </div>
          )}

          {hasDetails && (
            <div>
              <button
                onClick={toggleRawExpanded}
                className="flex items-center space-x-1 text-[10px] text-faint hover:text-accent transition-colors rounded-lg px-2 py-1 hover:bg-white/50"
              >
                <CodeBracketIcon className="w-3.5 h-3.5" />
                <span>原始数据</span>
                <div className={clsx('transition-transform duration-200', rawExpanded && 'rotate-180')}>
                  <ChevronDownIcon className="w-3 h-3" />
                </div>
              </button>

              <Collapsible expanded={rawExpanded}>
                <div className="mt-2 space-y-2">
                  {step.toolInput && Object.keys(step.toolInput).length > 0 && (
                    <div className="rounded-xl bg-white/50 backdrop-blur-sm border border-warm-line p-3">
                      <div className="text-[10px] text-muted mb-1.5 font-semibold tracking-wide">输入</div>
                      <pre className="text-[10px] text-inverse overflow-x-auto whitespace-pre-wrap break-all leading-relaxed font-mono">
                        {JSON.stringify(step.toolInput, null, 2)}
                      </pre>
                    </div>
                  )}
                  {step.toolPreview && (
                    <div className="rounded-xl bg-white/50 backdrop-blur-sm border border-warm-line p-3">
                      <div className="text-[10px] text-muted mb-1.5 font-semibold tracking-wide">输出</div>
                      <pre className="text-[10px] text-inverse overflow-x-auto whitespace-pre-wrap break-all leading-relaxed font-mono">
                        {step.toolPreview}
                      </pre>
                    </div>
                  )}
                </div>
              </Collapsible>
            </div>
          )}
        </div>
      </Collapsible>
    </div>
  )
}

/* ================================================================ */
/* Compact block                                                     */
/* ================================================================ */

const CompactBlock: React.FC<{ step: AgentStep }> = ({ step }) => (
  <div className="rounded-xl border border-warm-line px-3 py-2">
    <span className="text-[10px] text-muted">
      压缩上下文
      {step.beforeTokens !== undefined && (
        <span className="text-subtle">
          {' '}(~{step.beforeTokens} &rarr; ~{step.afterTokens} tokens)
        </span>
      )}
    </span>
  </div>
)

/* ================================================================ */
/* Main                                                              */
/* ================================================================ */

export const AgentTraceStep: React.FC<AgentTraceStepProps> = ({ step, isRunning }) => {
  if (step.kind === 'thinking') return <ThinkingBlock step={step} isRunning={isRunning} />
  if (step.kind === 'tool') return <ToolBlock step={step} />
  if (step.kind === 'compact') return <CompactBlock step={step} />
  return null
}

export default AgentTraceStep
