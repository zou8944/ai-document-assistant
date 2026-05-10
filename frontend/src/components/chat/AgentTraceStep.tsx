/**
 * Single agent step rendering component - card style
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
      return <LightBulbIcon className="w-3.5 h-3.5 text-amber-600" />
    case 'tool':
      if (step.toolStatus === 'error') {
        return <XCircleIcon className="w-3.5 h-3.5 text-red-600" />
      }
      if (step.toolStatus === 'done') {
        return <CheckCircleIcon className="w-3.5 h-3.5 text-emerald-600" />
      }
      return <WrenchIcon className="w-3.5 h-3.5 text-blue-600" />
    case 'compact':
      return <ArrowsPointingInIcon className="w-3.5 h-3.5 text-purple-600" />
    default:
      return null
  }
}

const StepLabel: React.FC<{ step: AgentStep }> = ({ step }) => {
  switch (step.kind) {
    case 'thinking':
      return <span className="font-medium text-amber-800">思考过程</span>
    case 'tool':
      return <span className="font-medium text-gray-800">{renderToolTitle(step)}</span>
    case 'compact':
      return (
        <span className="font-medium text-purple-800">
          压缩上下文
          {step.beforeTokens !== undefined && (
            <span className="text-gray-500 font-normal">
              {' '}(~{step.beforeTokens} tokens)
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

/** Determine card background based on step kind. */
function cardBgClass(step: AgentStep): string {
  switch (step.kind) {
    case 'thinking':
      return 'bg-amber-100/50 border-amber-200/50'
    case 'compact':
      return 'bg-purple-50/60 border-purple-200/40'
    default:
      return 'bg-white/70 border-gray-200/50'
  }
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
        'rounded-lg border p-2 transition-colors',
        cardBgClass(step),
        (hasDetails || step.kind === 'thinking') && 'cursor-pointer hover:bg-opacity-80'
      )}
      onClick={toggleExpanded}
    >
      {/* Header row */}
      <div className="flex items-center justify-between"
      >
        <div className="flex items-center space-x-2 min-w-0">
          <StepIcon step={step} />
          <span className="text-xs truncate">
            <StepLabel step={step} />
          </span>
          {step.toolStatus === 'running' && (
            <span className="flex-shrink-0 w-2 h-2 border border-blue-600 border-t-transparent rounded-full animate-spin" />
          )}
          {step.toolMs !== undefined && step.toolStatus !== 'running' && (
            <span className="flex-shrink-0 text-[10px] text-gray-400">
              {step.toolMs >= 1000
                ? `${(step.toolMs / 1000).toFixed(1)}s`
                : `${step.toolMs}ms`}
            </span>
          )}
        </div>

        {(hasDetails || step.kind === 'thinking') && (
          <span className="flex-shrink-0 ml-2">
            {expanded ? (
              <ChevronDownIcon className="w-3.5 h-3.5 text-gray-400" />
            ) : (
              <ChevronRightIcon className="w-3.5 h-3.5 text-gray-400" />
            )}
          </span>
        )}
      </div>

      {/* Result summary line */}
      {summary && step.toolStatus !== 'running' && (
        <div className="mt-0.5 text-[11px] text-gray-500 leading-relaxed pl-5.5">
          {summary}
        </div>
      )}

      {/* Thinking text (collapsed preview) */}
      {step.kind === 'thinking' && step.text && !expanded && (
        <p className="mt-0.5 text-[11px] text-gray-600 leading-relaxed line-clamp-2 pl-5.5">
          {step.text}
        </p>
      )}

      {/* Expanded content */}
      {expanded && (
        <div className="mt-1.5 space-y-1.5 pl-5.5">
          {/* Thinking text (expanded) */}
          {step.kind === 'thinking' && step.text && (
            <p className="text-[11px] text-gray-700 leading-relaxed">
              {step.text}
            </p>
          )}

          {/* Tool result preview */}
          {isTool && step.toolPreview && (
            <div className="rounded-md bg-slate-100/80 border border-slate-200/60 p-2">
              <div className="text-[10px] text-gray-500 mb-1 font-semibold tracking-wide">结果</div>
              <pre className="text-[10px] text-gray-800 overflow-x-auto whitespace-pre-wrap break-all leading-relaxed">
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
                className="flex items-center space-x-1 text-[10px] text-gray-500 hover:text-gray-700 transition-colors rounded px-1.5 py-0.5 bg-slate-100/60 hover:bg-slate-100"
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
                <div className="mt-1.5 space-y-1.5">
                  {step.toolInput && Object.keys(step.toolInput).length > 0 && (
                    <div className="rounded-md bg-slate-100/80 border border-slate-200/60 p-2">
                      <div className="text-[10px] text-gray-500 mb-1 font-semibold tracking-wide">输入</div>
                      <pre className="text-[10px] text-gray-800 overflow-x-auto whitespace-pre-wrap break-all leading-relaxed">
                        {JSON.stringify(step.toolInput, null, 2)}
                      </pre>
                    </div>
                  )}
                  {step.toolPreview && (
                    <div className="rounded-md bg-slate-100/80 border border-slate-200/60 p-2">
                      <div className="text-[10px] text-gray-500 mb-1 font-semibold tracking-wide">输出</div>
                      <pre className="text-[10px] text-gray-800 overflow-x-auto whitespace-pre-wrap break-all leading-relaxed">
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
