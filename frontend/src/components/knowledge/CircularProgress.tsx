import React from 'react'

interface CircularProgressProps {
  progress: number
  size?: number
  strokeWidth?: number
  color?: string
  trackColor?: string
}

export const CircularProgress: React.FC<CircularProgressProps> = ({
  progress,
  size = 16,
  strokeWidth = 2.5,
  color = '#3b82f6',
  trackColor = '#e5e7eb',
}) => {
  const normalizedProgress = Math.min(100, Math.max(0, progress))
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const dashOffset = circumference - (normalizedProgress / 100) * circumference

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={trackColor}
        strokeWidth={strokeWidth}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeDasharray={circumference}
        strokeDashoffset={dashOffset}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
    </svg>
  )
}

export default CircularProgress
