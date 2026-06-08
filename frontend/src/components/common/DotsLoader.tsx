/**
 * DotsLoader — three bouncing dots loading indicator.
 * Unified loading animation across the app.
 */

import React from 'react'
import clsx from 'clsx'

interface DotsLoaderProps {
  className?: string
  dotClassName?: string
}

export const DotsLoader: React.FC<DotsLoaderProps> = ({ className, dotClassName }) => {
  return (
    <div className={clsx('flex space-x-1.5', className)}>
      <div className={clsx('w-2 h-2 bg-warm-line rounded-full animate-bounce', dotClassName)} />
      <div className={clsx('w-2 h-2 bg-warm-line rounded-full animate-bounce', dotClassName)} style={{ animationDelay: '0.1s' }} />
      <div className={clsx('w-2 h-2 bg-warm-line rounded-full animate-bounce', dotClassName)} style={{ animationDelay: '0.2s' }} />
    </div>
  )
}

export default DotsLoader
