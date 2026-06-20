/**
 * Slash command selector - appears when user types / at the start of input
 */

import React, { useState, useEffect, useRef, forwardRef, useImperativeHandle } from 'react'
import { CommandLineIcon } from '@heroicons/react/24/outline'

export interface SlashCommand {
  id: string
  label: string
  description: string
}

export interface SlashCommandSelectorHandle {
  handleKeyDown: (e: React.KeyboardEvent) => boolean
}

interface SlashCommandSelectorProps {
  isVisible: boolean
  commands: SlashCommand[]
  searchTerm: string
  onSelect: (commandId: string) => void
  onClose: () => void
}

const SlashCommandSelector = forwardRef<SlashCommandSelectorHandle, SlashCommandSelectorProps>(
  ({ isVisible, commands, searchTerm, onSelect, onClose }, ref) => {
    const [selectedIndex, setSelectedIndex] = useState(0)
    const listRef = useRef<HTMLDivElement>(null)

    const filteredCommands = commands.filter(cmd =>
      cmd.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
      cmd.description.toLowerCase().includes(searchTerm.toLowerCase())
    )

    // Reset selection when search changes
    useEffect(() => {
      setSelectedIndex(0)
    }, [searchTerm])

    // Scroll selected item into view
    useEffect(() => {
      if (listRef.current && filteredCommands.length > 0) {
        setTimeout(() => {
          const items = listRef.current?.querySelectorAll('[data-command-item]')
          const selected = items?.[selectedIndex] as HTMLElement
          selected?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
        }, 0)
      }
    }, [selectedIndex, filteredCommands.length])

    const handleKeyDown = (e: React.KeyboardEvent): boolean => {
      if (!isVisible || filteredCommands.length === 0) return false

      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault()
          setSelectedIndex(prev => Math.min(prev + 1, filteredCommands.length - 1))
          return true
        case 'ArrowUp':
          e.preventDefault()
          setSelectedIndex(prev => Math.max(prev - 1, 0))
          return true
        case 'Enter':
          e.preventDefault()
          if (filteredCommands[selectedIndex]) {
            onSelect(filteredCommands[selectedIndex].id)
          }
          return true
        case 'Escape':
          e.preventDefault()
          onClose()
          return true
        default:
          return false
      }
    }

    useImperativeHandle(ref, () => ({
      handleKeyDown,
    }))

    if (!isVisible || filteredCommands.length === 0) return null

    return (
      <div
        ref={listRef}
        className="absolute z-50 left-0 right-0 bottom-full mb-2 bg-white/95 backdrop-blur-xl rounded-xl shadow-lg border border-white/40 overflow-hidden"
      >
        <div className="py-1.5">
          {filteredCommands.map((cmd, index) => (
            <button
              key={cmd.id}
              data-command-item
              onClick={() => onSelect(cmd.id)}
              className={`w-full px-4 py-2.5 text-left flex items-center space-x-3 transition-colors ${
                index === selectedIndex
                  ? 'bg-blue-50 text-blue-900'
                  : 'hover:bg-gray-50 text-ink'
              }`}
            >
              <CommandLineIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium">{cmd.label}</div>
                <div className="text-xs text-ink/50">{cmd.description}</div>
              </div>
            </button>
          ))}
        </div>
        <div className="px-4 py-2 bg-gray-50/80 border-t border-gray-200/60">
          <div className="text-xs text-ink/40">
            ↑↓ 导航 · Enter 选择 · Esc 取消
          </div>
        </div>
      </div>
    )
  }
)

SlashCommandSelector.displayName = 'SlashCommandSelector'

export default SlashCommandSelector
