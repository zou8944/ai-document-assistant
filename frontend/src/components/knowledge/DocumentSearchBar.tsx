/**
 * In-document search bar with Cmd+F support.
 * Highlights all matches and navigates between them.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import {
  ChevronUpIcon,
  ChevronDownIcon,
  XMarkIcon,
  MagnifyingGlassIcon,
} from '@heroicons/react/24/outline'

const HIGHLIGHT_CLASS = 'doc-search-highlight'
const ACTIVE_CLASS = 'doc-search-highlight-active'

interface DocumentSearchBarProps {
  /** The container element whose text content is searched */
  containerRef: React.RefObject<HTMLDivElement | null>
  onClose: () => void
}

export const DocumentSearchBar: React.FC<DocumentSearchBarProps> = ({
  containerRef,
  onClose,
}) => {
  const [query, setQuery] = useState('')
  const [current, setCurrent] = useState(0)
  const [total, setTotal] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
    inputRef.current?.select()
  }, [])

  // Clear highlights on unmount
  useEffect(() => {
    return () => {
      clearHighlights(containerRef.current)
    }
  }, [containerRef])

  const doSearch = useCallback(
    (searchQuery: string) => {
      clearHighlights(containerRef.current)

      if (!searchQuery || !containerRef.current) {
        setTotal(0)
        setCurrent(0)
        return
      }

      const count = highlightMatches(containerRef.current, searchQuery)
      setTotal(count)
      setCurrent(count > 0 ? 1 : 0)

      if (count > 0) {
        scrollToActive(containerRef.current)
      }
    },
    [containerRef]
  )

  // Search when query changes
  useEffect(() => {
    doSearch(query)
  }, [query, doSearch])

  const goNext = useCallback(() => {
    if (total === 0) return
    const next = current >= total ? 1 : current + 1
    setCurrent(next)
    setActive(containerRef.current, next)
    scrollToActive(containerRef.current)
  }, [current, total, containerRef])

  const goPrev = useCallback(() => {
    if (total === 0) return
    const prev = current <= 1 ? total : current - 1
    setCurrent(prev)
    setActive(containerRef.current, prev)
    scrollToActive(containerRef.current)
  }, [current, total, containerRef])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault()
        if (e.shiftKey) {
          goPrev()
        } else {
          goNext()
        }
      } else if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    },
    [goNext, goPrev, onClose]
  )

  return (
    <div
      className="absolute top-2 right-4 z-50 flex items-center gap-1.5 px-2 py-1.5
        bg-white/95 backdrop-blur-md border border-gray-200 rounded-lg shadow-lg"
      style={{ minWidth: 320 }}
    >
      <MagnifyingGlassIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />

      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="搜索文档..."
        className="flex-1 min-w-0 bg-transparent text-sm text-ink placeholder-gray-400
          outline-none border-none py-0.5"
      />

      {query && (
        <span className="text-xs text-gray-500 flex-shrink-0 tabular-nums select-none px-1">
          {total > 0 ? `${current}/${total}` : '无结果'}
        </span>
      )}

      <button
        onClick={goPrev}
        disabled={total === 0}
        className="p-0.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        title="上一个 (Shift+Enter)"
      >
        <ChevronUpIcon className="w-4 h-4 text-gray-600" />
      </button>

      <button
        onClick={goNext}
        disabled={total === 0}
        className="p-0.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        title="下一个 (Enter)"
      >
        <ChevronDownIcon className="w-4 h-4 text-gray-600" />
      </button>

      <button
        onClick={onClose}
        className="p-0.5 rounded hover:bg-gray-100 transition-colors ml-0.5"
        title="关闭 (Esc)"
      >
        <XMarkIcon className="w-4 h-4 text-gray-500" />
      </button>
    </div>
  )
}

// --- DOM manipulation helpers ---

function clearHighlights(container: HTMLElement | null) {
  if (!container) return
  const marks = container.querySelectorAll(`.${HIGHLIGHT_CLASS}`)
  marks.forEach((mark) => {
    const parent = mark.parentNode
    if (!parent) return
    while (mark.firstChild) {
      parent.insertBefore(mark.firstChild, mark)
    }
    parent.removeChild(mark)
    parent.normalize()
  })
}

function highlightMatches(container: HTMLElement, query: string): number {
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(escaped, 'gi')
  let count = 0

  // Collect all text nodes first (stable iteration)
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null)
  const textNodes: Text[] = []
  let node: Text | null
  while ((node = walker.nextNode() as Text | null)) {
    textNodes.push(node)
  }

  for (const textNode of textNodes) {
    const text = textNode.textContent || ''
    regex.lastIndex = 0
    if (!regex.test(text)) continue

    // Build replacement fragment
    const fragment = document.createDocumentFragment()
    regex.lastIndex = 0
    let lastIdx = 0
    let match: RegExpExecArray | null

    while ((match = regex.exec(text)) !== null) {
      // Text before match
      if (match.index > lastIdx) {
        fragment.appendChild(
          document.createTextNode(text.slice(lastIdx, match.index))
        )
      }

      const mark = document.createElement('mark')
      mark.className = HIGHLIGHT_CLASS
      mark.textContent = match[0]
      count++
      if (count === 1) mark.classList.add(ACTIVE_CLASS)
      fragment.appendChild(mark)

      lastIdx = match.index + match[0].length
    }

    // Remaining text after last match
    if (lastIdx < text.length) {
      fragment.appendChild(document.createTextNode(text.slice(lastIdx)))
    }

    textNode.parentNode?.replaceChild(fragment, textNode)
  }

  return count
}

function setActive(container: HTMLElement | null, index: number) {
  if (!container) return
  const marks = container.querySelectorAll(`.${HIGHLIGHT_CLASS}`)
  marks.forEach((m, i) => {
    if (i === index - 1) {
      m.classList.add(ACTIVE_CLASS)
    } else {
      m.classList.remove(ACTIVE_CLASS)
    }
  })
}

function scrollToActive(container: HTMLElement | null) {
  if (!container) return
  const active = container.querySelector(`.${ACTIVE_CLASS}`)
  if (active) {
    active.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
}

export default DocumentSearchBar
