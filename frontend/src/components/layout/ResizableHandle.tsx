/**
 * Resizable handle component for sidebar width adjustment
 *
 * - Mouse drag for primary interaction
 * - Arrow ← / → keyboard support (when focused); Home/End jump to min/max
 * - role="separator" + aria-valuenow/min/max for assistive tech
 * - Wider invisible hit area so users can grab it without pixel precision
 */

import React, { useState, useRef, useEffect } from 'react'
import clsx from 'clsx'

interface ResizableHandleProps {
  onResize: (deltaX: number) => void
  onKeyboardResize?: (direction: -1 | 1) => void
  currentWidth?: number
  minWidth?: number
  maxWidth?: number
  className?: string
}

const KEYBOARD_STEP = 16

export const ResizableHandle: React.FC<ResizableHandleProps> = ({
  onResize,
  onKeyboardResize,
  currentWidth,
  minWidth = 200,
  maxWidth = 480,
  className,
}) => {
  const [isResizing, setIsResizing] = useState(false)
  const startXRef = useRef<number>(0)
  const onResizeRef = useRef(onResize)

  // Keep latest onResize in a ref so the mousemove effect doesn't need to
  // re-subscribe on every parent re-render (which happens each time we resize).
  useEffect(() => {
    onResizeRef.current = onResize
  }, [onResize])

  useEffect(() => {
    if (!isResizing) return

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = e.clientX - startXRef.current
      onResizeRef.current(deltaX)
      startXRef.current = e.clientX
    }

    const handleMouseUp = () => {
      setIsResizing(false)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isResizing])

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
    startXRef.current = e.clientX
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!onKeyboardResize) return
    if (e.key === 'ArrowLeft') {
      e.preventDefault()
      onKeyboardResize(-1)
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      onKeyboardResize(1)
    } else if (e.key === 'Home') {
      e.preventDefault()
      const width = currentWidth ?? minWidth
      const steps = Math.ceil((width - minWidth) / KEYBOARD_STEP)
      for (let i = 0; i < steps; i++) onKeyboardResize(-1)
    } else if (e.key === 'End') {
      e.preventDefault()
      const width = currentWidth ?? maxWidth
      const steps = Math.ceil((maxWidth - width) / KEYBOARD_STEP)
      for (let i = 0; i < steps; i++) onKeyboardResize(1)
    }
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="侧边栏宽度调节"
      aria-valuenow={currentWidth}
      aria-valuemin={minWidth}
      aria-valuemax={maxWidth}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      className={clsx(
        'group relative z-20 w-1 bg-gray-200/40 hover:bg-accent/40 transition-all duration-200 cursor-col-resize',
        'flex items-center justify-center',
        'focus-visible:outline-none focus-visible:bg-accent/60 focus-visible:w-1.5',
        isResizing && 'bg-accent',
        className
      )}
      onMouseDown={handleMouseDown}
    >
      {/* Visual indicator — persistent on hover */}
      <div
        aria-hidden
        className={clsx(
          'absolute inset-y-0 w-3 -left-1 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity',
          isResizing && 'opacity-100'
        )}
      >
        <div className="w-0.5 h-8 bg-muted rounded-full" />
      </div>

      {/* Wider invisible hit area for easier grabbing */}
      <div className="absolute inset-y-0 -left-2 -right-2 cursor-col-resize" />
    </div>
  )
}

export default ResizableHandle
