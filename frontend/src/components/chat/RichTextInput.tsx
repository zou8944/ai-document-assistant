/**
 * 支持@文档的富文本输入框
 */

import React, { useState, useRef, useEffect } from 'react'
import { DocumentIcon } from '@heroicons/react/24/outline'
import { Document } from '../../services/apiClient'
import AtDocumentSelector from './AtDocumentSelector'

interface DocumentMention {
  id: string
  name: string
  start: number
  end: number
}

interface RichTextInputProps {
  value: string
  onChange: (value: string, mentions: DocumentMention[], selectedDocumentIds: string[]) => void
  onKeyDown?: (e: React.KeyboardEvent) => void
  placeholder?: string
  disabled?: boolean
  className?: string
}

export const RichTextInput: React.FC<RichTextInputProps> = ({
  value,
  onChange,
  onKeyDown,
  placeholder,
  disabled,
  className
}) => {
  const [isAtSelectorVisible, setIsAtSelectorVisible] = useState(false)
  const [atSearchTerm, setAtSearchTerm] = useState('')
  const [atPosition, setAtPosition] = useState({ top: 0, left: 0 })
  const [atStartIndex, setAtStartIndex] = useState(-1)
  const [mentions, setMentions] = useState<DocumentMention[]>([])
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  // 解析输入内容，识别@文档
  const parseInput = (text: string): { displayText: string; mentions: DocumentMention[] } => {
    const mentionRegex = /@\[(.*?)\]\(doc:([^)]+)\)/g
    const newMentions: DocumentMention[] = []
    let displayText = text
    let offset = 0

    const matches = Array.from(text.matchAll(mentionRegex))
    for (const match of matches) {
      const [fullMatch, docName, docId] = match
      const start = match.index! - offset
      const end = start + docName.length + 1 // +1 for @

      newMentions.push({
        id: docId,
        name: docName,
        start,
        end
      })

      // 替换为显示文本
      displayText = displayText.replace(fullMatch, `@${docName}`)
      offset += fullMatch.length - (`@${docName}`).length
    }

    return { displayText, mentions: newMentions }
  }

  // 处理输入变化
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value
    const cursorPosition = e.target.selectionStart || 0

    // 检查是否输入了@
    const beforeCursor = newValue.slice(0, cursorPosition)
    const atMatch = beforeCursor.match(/@([^@\s]*)$/)

    if (atMatch) {
      // 显示@选择器
      const searchTerm = atMatch[1]
      setAtSearchTerm(searchTerm)
      setAtStartIndex(atMatch.index!)
      setIsAtSelectorVisible(true)

      // 计算位置 - 显示在输入框上方
      if (inputRef.current && containerRef.current) {
        const inputRect = inputRef.current.getBoundingClientRect()
        const containerRect = containerRef.current.getBoundingClientRect()
        setAtPosition({
          top: inputRect.top - containerRect.top - 270, // 270px是选择器的大概高度
          left: 0 // 使用left-0 right-0类来占满宽度
        })
      }
    } else {
      setIsAtSelectorVisible(false)
    }

    // 解析当前输入
    const { displayText, mentions: newMentions } = parseInput(newValue)
    setMentions(newMentions)

    // 提取选中的文档ID
    const selectedDocumentIds = newMentions.map(mention => mention.id)

    onChange(newValue, newMentions, selectedDocumentIds)
  }

  // 处理@文档选择
  const handleDocumentSelect = (document: Document) => {
    if (!inputRef.current) return

    const input = inputRef.current
    const cursorPosition = input.selectionStart || 0
    const beforeCursor = value.slice(0, cursorPosition)
    const afterCursor = value.slice(cursorPosition)

    // 找到@的开始位置
    const atMatch = beforeCursor.match(/@([^@\s]*)$/)
    if (atMatch) {
      const atStart = atMatch.index!
      // 移除@命令，只保留普通文本
      const newText = beforeCursor.slice(0, atStart) + afterCursor

      // 不在输入框中保留@内容，直接通知父组件添加文档到选择列表
      const { displayText, mentions: newMentions } = parseInput(newText)
      setMentions(newMentions)

      // 将当前文档添加到选中列表（通过回调通知父组件）
      const currentSelectedIds = newMentions.map(mention => mention.id)
      const updatedSelectedIds = [...currentSelectedIds, document.id]

      onChange(newText, newMentions, updatedSelectedIds)

      // 设置光标位置到@的起始位置
      setTimeout(() => {
        input.setSelectionRange(atStart, atStart)
        input.focus()
      }, 150) // 稍微延迟一点确保选择器完全关闭
    }

    setIsAtSelectorVisible(false)
  }

  // 处理键盘事件
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (isAtSelectorVisible && ['ArrowDown', 'ArrowUp', 'Enter', 'Escape'].includes(e.key)) {
      // 让AtDocumentSelector处理这些按键
      return
    }

    if (e.key === 'Escape' && isAtSelectorVisible) {
      setIsAtSelectorVisible(false)
      return
    }

    onKeyDown?.(e)
  }

  // 渲染带有高亮@文档的文本
  const renderHighlightedText = () => {
    const { displayText } = parseInput(value)

    if (mentions.length === 0) {
      return displayText
    }

    const parts: React.ReactNode[] = []
    let lastIndex = 0

    mentions.forEach((mention, index) => {
      // 添加@之前的普通文本
      if (mention.start > lastIndex) {
        parts.push(displayText.slice(lastIndex, mention.start))
      }

      // 添加高亮的@文档
      parts.push(
        <span
          key={`mention-${index}`}
          className="inline-flex items-center bg-green-100 text-green-800 px-1 rounded"
        >
          <DocumentIcon className="w-3 h-3 mr-1" />
          @{mention.name}
        </span>
      )

      lastIndex = mention.end
    })

    // 添加剩余的普通文本
    if (lastIndex < displayText.length) {
      parts.push(displayText.slice(lastIndex))
    }

    return parts
  }

  // 获取用户真实输入内容（去掉@文档）
  const getRealUserInput = (text: string): string => {
    // 移除所有@[docName](doc:docId)格式的内容
    return text.replace(/@\[[^\]]+\]\(doc:[^)]+\)/g, '').trim()
  }

  // 暴露获取真实输入的方法
  useEffect(() => {
    if (inputRef.current) {
      (inputRef.current as any).getRealUserInput = () => getRealUserInput(value)
    }
  }, [value])

  return (
    <div ref={containerRef} className="relative">
      {/* 背景显示层（用于高亮@文档） */}
      <div
        className={`absolute inset-0 pointer-events-none whitespace-pre-wrap break-words ${className} text-transparent`}
        style={{
          font: 'inherit',
          padding: '12px 16px',
          lineHeight: 'inherit',
          border: '1px solid transparent'
        }}
      >
        {/* 这里可以添加高亮背景，但为了简化，我们在textarea中处理 */}
      </div>

      {/* 实际输入框 */}
      <textarea
        ref={inputRef}
        value={parseInput(value).displayText}
        onChange={handleInputChange}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        className={className}
        style={{ minHeight: '48px', maxHeight: '120px' }}
      />

      {/* @文档选择器 */}
      <AtDocumentSelector
        isVisible={isAtSelectorVisible}
        onDocumentSelect={handleDocumentSelect}
        onClose={() => setIsAtSelectorVisible(false)}
        searchTerm={atSearchTerm}
        position={atPosition}
      />
    </div>
  )
}

export default RichTextInput