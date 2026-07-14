/**
 * Keyboard shortcuts help dialog.
 *
 * Shows all registered shortcuts grouped by category, with
 * platform-aware key labels (⌘ on macOS, Ctrl on Windows/Linux).
 *
 * Triggered by Cmd+/ (or Ctrl+/).
 */

import React from 'react'
import { XMarkIcon, CommandLineIcon } from '@heroicons/react/24/outline'
import { displayKey } from '../../hooks/useKeyboardShortcuts'

interface ShortcutDef {
  combo: string
  label: string
}

interface ShortcutGroup {
  title: string
  shortcuts: ShortcutDef[]
}

const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    title: '全局',
    shortcuts: [
      { combo: 'mod+n', label: '新建聊天' },
      { combo: 'mod+k', label: '聚焦搜索栏' },
      { combo: 'mod+/', label: '显示快捷键帮助' },
      { combo: 'mod+,', label: '打开设置' },
      { combo: 'mod+shift+arrowup', label: '上一个聊天' },
      { combo: 'mod+shift+arrowdown', label: '下一个聊天' },
    ],
  },
  {
    title: '聊天',
    shortcuts: [
      { combo: 'mod+shift+o', label: '展开/收起推理过程' },
    ],
  },
  {
    title: '导航',
    shortcuts: [
      { combo: 'mod+1', label: '切换到知识库' },
      { combo: 'mod+2', label: '切换到聊天' },
      { combo: 'mod+3', label: '切换到设置' },
    ],
  },
  {
    title: '文档阅读',
    shortcuts: [
      { combo: 'mod+f', label: '文档内搜索' },
    ],
  },
  {
    title: '通用',
    shortcuts: [
      { combo: 'escape', label: '关闭弹窗 / 取消' },
    ],
  },
]

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({ open, onClose }) => {
  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" aria-hidden />

      {/* Dialog */}
      <div
        role="dialog"
        aria-label="键盘快捷键"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-lg bg-white/90 backdrop-blur-2xl rounded-2xl
          border border-white/40 shadow-[0_8px_40px_rgba(0,0,0,0.12)]
          overflow-hidden animate-fade-in"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200/60">
          <div className="flex items-center gap-2.5">
            <CommandLineIcon className="w-5 h-5 text-accent" />
            <h2 className="text-lg font-semibold text-ink">键盘快捷键</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-gray-100/60 text-muted hover:text-ink transition-colors
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            aria-label="关闭"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4 max-h-[60vh] overflow-y-auto space-y-5">
          {SHORTCUT_GROUPS.map((group) => (
            <div key={group.title}>
              <h3 className="text-xs font-medium text-muted uppercase tracking-wide mb-2">
                {group.title}
              </h3>
              <div className="space-y-1">
                {group.shortcuts.map((s) => (
                  <div
                    key={s.combo}
                    className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-white/60"
                  >
                    <span className="text-sm text-ink">{s.label}</span>
                    <kbd className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-mono
                      bg-gray-100/80 border border-gray-200/60 rounded-md text-gray-600">
                      {displayKey(s.combo)}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Footer hint */}
        <div className="px-6 py-3 border-t border-gray-200/60 text-center">
          <span className="text-xs text-muted">
            按 <kbd className="px-1.5 py-0.5 text-xs font-mono bg-gray-100/80 border border-gray-200/60 rounded text-gray-600">{displayKey('mod+/')}</kbd> 关闭
          </span>
        </div>
      </div>
    </div>
  )
}

export default CommandPalette
