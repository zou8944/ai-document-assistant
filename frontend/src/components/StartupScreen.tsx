/**
 * Startup loading screen — Editorial Library aesthetic
 *
 * Replaces the generic "bouncing dots + spinner" pattern with a refined
 * mark-and-breath composition. The serif wordmark fades in slowly;
 * a single blue dot pulses in a long, calm rhythm. The status text is
 * set in a small eyebrow caps treatment.
 */

import React from 'react'

interface StartupScreenProps {
  message?: string
}

export const StartupScreen: React.FC<StartupScreenProps> = ({
  message = '正在启动应用…',
}) => {
  return (
    <div className="relative flex flex-col items-center justify-center min-h-screen overflow-hidden">
      {/* Floating ambient orbs (drift gently in the background) */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-32 -left-32 w-96 h-96 rounded-full opacity-30 animate-drift"
        style={{
          background:
            'radial-gradient(circle, rgba(255, 220, 160, 0.55), transparent 60%)',
          filter: 'blur(40px)',
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-32 -right-24 w-[28rem] h-[28rem] rounded-full opacity-25 animate-drift"
        style={{
          background:
            'radial-gradient(circle, rgba(170, 200, 255, 0.55), transparent 60%)',
          filter: 'blur(50px)',
          animationDelay: '1.5s',
        }}
      />

      {/* Mark — serif, large, fading in */}
      <div className="reveal flex flex-col items-center gap-2">
        <h1 className="font-display text-5xl md:text-6xl font-medium tracking-tight text-ink">
          AI 文档助手
        </h1>
        <p className="font-display text-lg italic text-muted">
          a reader for your documents
        </p>
      </div>

      {/* Breathing dot — replaces bouncing dots + spinner */}
      <div className="mt-16 flex flex-col items-center gap-6 reveal" style={{ animationDelay: '180ms' }}>
        <div
          className="w-2.5 h-2.5 rounded-full animate-breathe"
          style={{
            background: 'linear-gradient(180deg, #4A9EFF, #007AFF)',
            boxShadow: '0 0 24px rgba(0, 122, 255, 0.45)',
          }}
        />
        <div className="flex flex-col items-center gap-1.5">
          <p className="text-sm font-medium text-ink-soft">{message}</p>
          <p className="section-label">initializing</p>
        </div>
      </div>
    </div>
  )
}

export default StartupScreen
