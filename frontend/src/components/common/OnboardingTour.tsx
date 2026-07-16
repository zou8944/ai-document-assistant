/**
 * Spotlight-style onboarding tour.
 *
 * Highlights UI elements (found via `data-tour` attributes) with a
 * cutout overlay and shows a tooltip card with feature descriptions.
 *
 * Steps are defined externally and passed in; the component manages
 * positioning, animation, and keyboard navigation.
 */

import React, { useEffect, useState, useCallback, useRef } from 'react'
import {
  ChevronRightIcon,
  ChevronLeftIcon,
  XMarkIcon,
  RocketLaunchIcon,
} from '@heroicons/react/24/outline'

export interface TourStep {
  /** Value of the `data-tour` attribute on the target element. */
  target: string
  title: string
  description: string
  /** Optional: 'bottom' | 'top' | 'right' | 'left'. Defaults to 'right'. */
  placement?: 'bottom' | 'top' | 'right' | 'left'
}

interface OnboardingTourProps {
  steps: TourStep[]
  onComplete: () => void
}

const SPOTLIGHT_PADDING = 8
const TOOLTIP_OFFSET = 12

export const OnboardingTour: React.FC<OnboardingTourProps> = ({ steps, onComplete }) => {
  const [current, setCurrent] = useState(0)
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null)
  const [tooltipPos, setTooltipPos] = useState<{ top: number; left: number }>({ top: 0, left: 0 })
  const tooltipRef = useRef<HTMLDivElement>(null)
  const [tooltipSize, setTooltipSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 })
  const [visible, setVisible] = useState(false)

  const step = steps[current]
  const isFirst = current === 0
  const isLast = current === steps.length - 1

  // Measure tooltip after render
  useEffect(() => {
    if (tooltipRef.current) {
      setTooltipSize({
        w: tooltipRef.current.offsetWidth,
        h: tooltipRef.current.offsetHeight,
      })
    }
  }, [current, visible])

  // Locate target element and compute positions
  useEffect(() => {
    if (!step) return

    const updatePosition = () => {
      const el = document.querySelector(`[data-tour="${step.target}"]`)
      if (!el) {
        // Target not found — skip this step
        setTargetRect(null)
        return
      }
      const rect = el.getBoundingClientRect()
      setTargetRect(rect)

      // Scroll target into view if needed
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' })
    }

    // Small delay to allow layout to settle after section switches
    const timer = window.setTimeout(updatePosition, 150)
    return () => window.clearTimeout(timer)
  }, [step])

  // Compute tooltip position based on target rect and placement
  useEffect(() => {
    if (!targetRect || !tooltipSize.w) return

    const placement = step?.placement || 'right'
    let top = 0
    let left = 0

    switch (placement) {
      case 'right':
        top = targetRect.top + targetRect.height / 2 - tooltipSize.h / 2
        left = targetRect.right + TOOLTIP_OFFSET
        break
      case 'left':
        top = targetRect.top + targetRect.height / 2 - tooltipSize.h / 2
        left = targetRect.left - tooltipSize.w - TOOLTIP_OFFSET
        break
      case 'bottom':
        top = targetRect.bottom + TOOLTIP_OFFSET
        left = targetRect.left + targetRect.width / 2 - tooltipSize.w / 2
        break
      case 'top':
        top = targetRect.top - tooltipSize.h - TOOLTIP_OFFSET
        left = targetRect.left + targetRect.width / 2 - tooltipSize.w / 2
        break
    }

    // Clamp to viewport
    const margin = 12
    top = Math.max(margin, Math.min(top, window.innerHeight - tooltipSize.h - margin))
    left = Math.max(margin, Math.min(left, window.innerWidth - tooltipSize.w - margin))

    setTooltipPos({ top, left })
  }, [targetRect, tooltipSize, step])

  // Fade in on mount
  useEffect(() => {
    const t = window.setTimeout(() => setVisible(true), 50)
    return () => window.clearTimeout(t)
  }, [])

  const goNext = useCallback(() => {
    if (isLast) {
      setVisible(false)
      window.setTimeout(onComplete, 300)
    } else {
      setCurrent((c) => c + 1)
    }
  }, [isLast, onComplete])

  const goPrev = useCallback(() => {
    if (!isFirst) setCurrent((c) => c - 1)
  }, [isFirst])

  const handleSkip = useCallback(() => {
    setVisible(false)
    window.setTimeout(onComplete, 300)
  }, [onComplete])

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        handleSkip()
      } else if (e.key === 'Enter' || e.key === 'ArrowRight') {
        e.preventDefault()
        goNext()
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault()
        goPrev()
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [goNext, goPrev, handleSkip])

  if (!step) return null

  // Build the spotlight cutout path
  const spotlightPath = (() => {
    if (!targetRect) return ''
    const x = targetRect.left - SPOTLIGHT_PADDING
    const y = targetRect.top - SPOTLIGHT_PADDING
    const w = targetRect.width + SPOTLIGHT_PADDING * 2
    const h = targetRect.height + SPOTLIGHT_PADDING * 2
    const r = 8 // corner radius

    // Full-screen rect with a rounded-rect hole
    return (
      `M0,0H${window.innerWidth}V${window.innerHeight}H0Z` +
      `M${x + r},${y}` +
      `H${x + w - r}Q${x + w},${y},${x + w},${y + r}` +
      `V${y + h - r}Q${x + w},${y + h},${x + w - r},${y + h}` +
      `H${x + r}Q${x},${y + h},${x},${y + h - r}` +
      `V${y + r}Q${x},${y},${x + r},${y}Z`
    )
  })()

  const isFirstStep = current === 0

  return (
    <div
      className="fixed inset-0 z-[200]"
      style={{ opacity: visible ? 1 : 0, transition: 'opacity 300ms ease' }}
    >
      {/* Overlay with spotlight cutout */}
      <svg className="absolute inset-0 w-full h-full" aria-hidden>
        <path
          d={spotlightPath}
          fill="rgba(0,0,0,0.5)"
          fillRule="evenodd"
          style={{ transition: 'all 300ms ease' }}
        />
      </svg>

      {/* Tooltip card */}
      <div
        ref={tooltipRef}
        role="dialog"
        aria-label={step.title}
        className="absolute w-80 bg-white/95 backdrop-blur-xl rounded-2xl
          border border-white/40 shadow-[0_8px_40px_rgba(0,0,0,0.18)]
          overflow-hidden"
        style={{
          top: `${tooltipPos.top}px`,
          left: `${tooltipPos.left}px`,
          transition: 'top 300ms ease, left 300ms ease',
        }}
      >
        {/* Header */}
        <div className="px-5 pt-4 pb-2 flex items-start justify-between">
          <div className="flex items-center gap-2">
            {isFirstStep && (
              <RocketLaunchIcon className="w-5 h-5 text-accent flex-shrink-0" />
            )}
            <h3 className="text-base font-semibold text-ink">{step.title}</h3>
          </div>
          <button
            onClick={handleSkip}
            className="p-1 -mr-1 rounded-lg text-muted hover:text-ink hover:bg-gray-100/60 transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            aria-label="跳过引导"
          >
            <XMarkIcon className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 pb-3">
          <p className="text-sm text-ink/70 leading-relaxed">{step.description}</p>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 bg-gray-50/60 border-t border-gray-200/40 flex items-center justify-between">
          {/* Step dots */}
          <div className="flex items-center gap-1.5">
            {steps.map((_, i) => (
              <div
                key={i}
                className={`w-1.5 h-1.5 rounded-full transition-colors ${
                  i === current ? 'bg-accent' : 'bg-gray-300'
                }`}
              />
            ))}
          </div>

          {/* Nav buttons */}
          <div className="flex items-center gap-2">
            {!isFirst && (
              <button
                onClick={goPrev}
                className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-muted
                  hover:text-ink rounded-lg hover:bg-gray-100/60 transition-colors
                  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
              >
                <ChevronLeftIcon className="w-3.5 h-3.5" />
                上一步
              </button>
            )}
            <button
              onClick={goNext}
              className="flex items-center gap-1 px-4 py-1.5 text-xs font-medium text-white
                bg-accent hover:bg-accent-hover rounded-lg transition-colors
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-1"
            >
              {isLast ? '开始使用' : '下一步'}
              {!isLast && <ChevronRightIcon className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default OnboardingTour
