/**
 * Single agent step rendering component
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
      return <LightBulbIcon className="w-3.5 h-3.5 text-amber-400" />
    case 'tool':
      if (step.toolStatus === 'error') {
        return <XCircleIcon className="w-3.5 h-3.5 text-red-400" />
      }
      if (step.toolStatus === 'done') {
        return <CheckCircleIcon className="w-3.5 h-3.5 text-emerald-400" />
      }
      return <WrenchIcon className="w-3.5 h-3.5 text-blue-400" />
    case 'compact':
      return <ArrowsPointingInIcon className="w-3.5 h-3.5 text-purple-400" />
    default:
      return null
  }
}

const StepLabel: React.FC<{ step: AgentStep }> = ({ step }) => {
  switch (step.kind) {
    case 'thinking':
      return <span className="text-amber-300">Thinking</span>
    case 'tool':
      return <span className="text-blue-300">{renderToolTitle(step)}</span>
    case 'compact':
      return (
        <span className="text-purple-300">
          Compact context
          {step.beforeTokens !== undefined && (
            <span className="text-gray-400">
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

export const AgentTraceStep: React.FC<AgentTraceStepProps> = ({ step, isLast }) => {
  const [expanded, setExpanded] = useState(false)
  const [rawExpanded, setRawExpanded] = useState(false)

  const isTool = step.kind === 'tool'
  const hasDetails = hasToolDetails(step)
  const summary = isTool ? renderToolSummary(step) : null

  const toggleExpanded = useCallback(() => {
    if (hasDetails) {
      setExpanded((v) => !v)
    }
  }, [hasDetails])

  const toggleRawExpanded = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
    setRawExpanded((v) => !v)
  }, [])

  return (
    <div className={clsx('relative', !isLast && 'pb-1')}>
      {/* Connector line */}
      {!isLast && (
        <div className="absolute left-[7px] top-5 bottom-0 w-px bg-white/10" />
      )}

      <div className="flex items-start space-x-2">
        {/* Icon dot */}
        <div className="flex-shrink-0 mt-0.5 w-3.5 h-3.5 flex items-center justify-center">
          <StepIcon step={step} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div
            className={clsx(
              'flex items-center space-x-1.5 text-xs',
              hasDetails && 'cursor-pointer hover:opacity-80'
            )}
            onClick={toggleExpanded}
          >
            {hasDetails && (
              <span className="flex-shrink-0">
                {expanded ? (
                  <ChevronDownIcon className="w-3 h-3 text-gray-400" />
                ) : (
                  <ChevronRightIcon className="w-3 h-3 text-gray-400" />
                )}
              </span>
            )}
            <span className="truncate">
              <StepLabel step={step} />
            </span>
            {step.toolStatus === 'running' && (
              <span className="flex-shrink-0 w-2 h-2 border border-blue-400 border-t-transparent rounded-full animate-spin" />
            )}
            {step.toolMs !== undefined && step.toolStatus !== 'running' && (
              <span className="flex-shrink-0 text-[10px] text-gray-500">
                {step.toolMs >= 1000
                  ? `${(step.toolMs / 1000).toFixed(1)}s`
                  : `${step.toolMs}ms`}
              </span>
            )}
          </div>

          {/* Result summary line */}
          {summary && step.toolStatus !== 'running' && (
            <div className="mt-0.5 text-[11px] text-gray-400 leading-relaxed">
              {summary}
            </div>
          )}

          {/* Thinking text */}
          {step.kind === 'thinking' && step.text && (
            <p className="mt-0.5 text-[11px] text-gray-400 leading-relaxed line-clamp-2">
              {step.text}
            </p>
          )}

          {/* Expanded tool details */}
          {isTool && expanded && hasDetails && (
            <div className="mt-1.5 space-y-1.5">
              {/* Human-friendly result preview */}
              {step.toolPreview && (
                <div className="rounded bg-black/20 p-1.5">
                  <div className="text-[10px] text-gray-500 mb-0.5">结果</div>
                  <pre className="text-[10px] text-gray-300 overflow-x-auto whitespace-pre-wrap break-all">
                    {step.toolPreview.length > 500
                      ? step.toolPreview.slice(0, 500) + '...'
                      : step.toolPreview}
                  </pre>
                </div>
              )}

              {/* Raw data toggle */}
              <div>
                <button
                  onClick={toggleRawExpanded}
                  className="flex items-center space-x-1 text-[10px] text-gray-500 hover:text-gray-400 transition-colors"
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
                  <div className="mt-1 space-y-1.5">
                    {step.toolInput && Object.keys(step.toolInput).length > 0 && (
                      <div className="rounded bg-black/20 p-1.5">
                        <div className="text-[10px] text-gray-500 mb-0.5">输入</div>
                        <pre className="text-[10px] text-gray-300 overflow-x-auto whitespace-pre-wrap break-all">
                          {JSON.stringify(step.toolInput, null, 2)}
                        </pre>
                      </div>
                    )}
                    {step.toolPreview && (
                      <div className="rounded bg-black/20 p-1.5">
                        <div className="text-[10px] text-gray-500 mb-0.5">输出</div>
                        <pre className="text-[10px] text-gray-300 overflow-x-auto whitespace-pre-wrap break-all">
                          {step.toolPreview}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default AgentTraceStep
