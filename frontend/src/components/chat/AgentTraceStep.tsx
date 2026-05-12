/**
 * Agent step blocks — distinct card containers per step
 *
 * Each block is a self-contained card with rounded corners, background fill,
 * and clear visual hierarchy inside.
 */

import React, { useState, useCallback, useEffect, useRef } from 'react'
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

const Collapsible: React.FC<{ expanded: boolean; children: React.ReactNode }> = ({
  expanded,
  children,
}) => {
  const ref = useRef<HTMLDivElement>(null)
  const prevExpanded = useRef(expanded)
  const rafRef = useRef<number>()

  useEffect(() => {
    const el = ref.current
    if (!el) return

    if (rafRef.current) cancelAnimationFrame(rafRef.current)

    if (expanded && !prevExpanded.current) {
      // Expanding
      el.style.overflow = 'hidden'
      el.style.maxHeight = '0px'
      el.style.opacity = '0'
      // Force reflow
      void el.scrollHeight
      rafRef.current = requestAnimationFrame(() => {
        el.style.maxHeight = el.scrollHeight + 'px'
        el.style.opacity = '1'
        const timer = setTimeout(() => {
          el.style.maxHeight = 'none'
          el.style.overflow = ''
        }, 250)
        // Store cleanup reference
        ;(el as any)._cleanupTimer = timer
      })
    } else if (!expanded && prevExpanded.current) {
      // Collapsing
      if ((el as any)._cleanupTimer) clearTimeout((el as any)._cleanupTimer)
      el.style.maxHeight = el.scrollHeight + 'px'
      el.style.overflow = 'hidden'
      void el.scrollHeight
      rafRef.current = requestAnimationFrame(() => {
        el.style.maxHeight = '0px'
        el.style.opacity = '0'
      })
    } else if (expanded) {
      el.style.maxHeight = 'none'
      el.style.opacity = '1'
      el.style.overflow = ''
    } else {
      el.style.maxHeight = '0px'
      el.style.opacity = '0'
      el.style.overflow = 'hidden'
    }

    prevExpanded.current = expanded
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [expanded])

  return (
    <div
      ref={ref}
      className="transition-all duration-250 ease-in-out"
      style={{ maxHeight: 0, opacity: 0, overflow: 'hidden' }}
    >
      {children}
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
      className="rounded-2xl border border-[#D1D1D6] cursor-pointer overflow-hidden"
      onClick={() => setExpanded((v) => !v)}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5">
        <div className="flex items-center space-x-2">
          <SparklesIcon className="w-5 h-5 text-[#8E8E93]" />
          <span className="text-[13px] font-medium text-[#1c1c1e]">思考过程</span>
          {isRunning && (
            <span className="w-1.5 h-1.5 rounded-full bg-[#8E8E93] animate-pulse" />
          )}
        </div>
        <div className="flex items-center space-x-1.5">
          {step.thinkingMs !== undefined && !isRunning && (
            <span className="text-[11px] text-[#AEAEB2] tabular-nums">
              {step.thinkingMs >= 1000
                ? `${(step.thinkingMs / 1000).toFixed(1)}s`
                : `${step.thinkingMs}ms`}
            </span>
          )}
          <div className={clsx('transition-transform duration-200', expanded && 'rotate-180')}>
            <ChevronDownIcon className="w-4 h-4 text-[#AEAEB2]" />
          </div>
        </div>
      </div>

      {/* Body */}
      <Collapsible expanded={expanded}>
        <div className="px-4 pb-3 pt-0 ml-7">
          <p className="text-[13px] text-[#3A3A3C] leading-[1.7] whitespace-pre-wrap">
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
        'rounded-2xl border',
        isError ? 'border-red-200/50' : 'border-[#D1D1D6]'
      )}
    >
      {/* Clickable header area */}
      <div
        className={clsx(
          'px-4 py-2.5',
          hasDetails && 'cursor-pointer'
        )}
        onClick={hasDetails ? () => setExpanded((v) => !v) : undefined}
      >
        {/* Row 1: icon + title + chevron */}
        <div className="flex items-center">
          {/* Status icon */}
          <div className="flex-shrink-0 mr-2">
            {isError ? (
              <XCircleIcon className="w-5 h-5 text-red-400" />
            ) : isDone ? (
              <CheckCircleIcon className="w-5 h-5 text-[#34C759]" />
            ) : isRunning ? (
              <span className="block w-5 h-5 border-2 border-[#007AFF] border-t-transparent rounded-full animate-spin" />
            ) : (
              <CheckCircleIcon className="w-5 h-5 text-[#C7C7CC]" />
            )}
          </div>

          {/* Title */}
          <div className="flex-1 min-w-0">
            <span className="text-[13px] text-[#1c1c1e]">
              {renderToolTitle(step)}
            </span>
          </div>

          {/* Time + chevron */}
          <div className="flex items-center space-x-1.5 flex-shrink-0 ml-3">
            {step.toolMs !== undefined && !isRunning && (
              <span className="text-[11px] text-[#AEAEB2] tabular-nums">
                {step.toolMs >= 1000
                  ? `${(step.toolMs / 1000).toFixed(1)}s`
                  : `${step.toolMs}ms`}
              </span>
            )}
            {hasDetails && (
              <div className={clsx('transition-transform duration-200', expanded && 'rotate-180')}>
                <ChevronDownIcon className="w-4 h-4 text-[#C7C7CC]" />
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Expanded details */}
      <Collapsible expanded={expanded}>
        <div className="px-4 pb-3 ml-7 space-y-2">
          {summary && !isRunning && (
            <div className="text-[12px] text-[#636366]">{summary}</div>
          )}

          {step.toolPreview && (
            <div className="rounded-xl bg-white/50 backdrop-blur-sm border border-[#D1D1D6] p-3">
              <pre className="text-[11px] text-[#3A3A3C] overflow-x-auto whitespace-pre-wrap break-all leading-relaxed font-mono">
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
                className="flex items-center space-x-1 text-[11px] text-[#AEAEB2] hover:text-[#007AFF] transition-colors rounded-lg px-2 py-1 hover:bg-white/50"
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
                    <div className="rounded-xl bg-white/50 backdrop-blur-sm border border-[#D1D1D6] p-3">
                      <div className="text-[10px] text-[#8E8E93] mb-1.5 font-semibold tracking-wide">输入</div>
                      <pre className="text-[10px] text-[#3A3A3C] overflow-x-auto whitespace-pre-wrap break-all leading-relaxed font-mono">
                        {JSON.stringify(step.toolInput, null, 2)}
                      </pre>
                    </div>
                  )}
                  {step.toolPreview && (
                    <div className="rounded-xl bg-white/50 backdrop-blur-sm border border-[#D1D1D6] p-3">
                      <div className="text-[10px] text-[#8E8E93] mb-1.5 font-semibold tracking-wide">输出</div>
                      <pre className="text-[10px] text-[#3A3A3C] overflow-x-auto whitespace-pre-wrap break-all leading-relaxed font-mono">
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
  <div className="rounded-2xl border border-[#D1D1D6] px-4 py-2">
    <span className="text-[11px] text-[#8E8E93]">
      压缩上下文
      {step.beforeTokens !== undefined && (
        <span className="text-[#C7C7CC]">
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
