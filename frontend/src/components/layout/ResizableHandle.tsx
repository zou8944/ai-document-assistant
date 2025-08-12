/**
 * Resizable handle component for sidebar width adjustment
 */

import React, { useState, useRef, useEffect } from 'react'
import clsx from 'clsx'

interface ResizableHandleProps {
  onResize: (deltaX: number) => void
  className?: string
}

export const ResizableHandle: React.FC<ResizableHandleProps> = ({ 
  onResize, 
  className 
}) => {
  const [isResizing, setIsResizing] = useState(false)
  const startXRef = useRef<number>(0)

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing) return
      
      const deltaX = e.clientX - startXRef.current
      onResize(deltaX)
      startXRef.current = e.clientX
    }

    const handleMouseUp = () => {
      setIsResizing(false)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    if (isResizing) {
      document.body.style.cursor = 'col-resize'
      document.body.style.userSelect = 'none'
      
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }
  }, [isResizing, onResize])

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(true)
    startXRef.current = e.clientX
  }

  return (
    <div
      className={clsx(
        'group relative w-1 bg-gray-200/50 hover:bg-blue-400 transition-all duration-200 cursor-col-resize',
        'flex items-center justify-center',
        isResizing && 'bg-blue-500',
        className
      )}
      onMouseDown={handleMouseDown}
    >
      {/* Visual indicator */}
      <div 
        className={clsx(
          'absolute inset-y-0 w-3 -left-1 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity',
          isResizing && 'opacity-100'
        )}
      >
        <div className="w-0.5 h-8 bg-gray-400 rounded-full" />
      </div>
      
      {/* Invisible wider hit area */}
      <div className="absolute inset-y-0 -left-2 -right-2 w-5" />
    </div>
  )
}

export default ResizableHandle