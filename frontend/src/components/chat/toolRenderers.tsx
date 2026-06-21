/**
 * Human-friendly renderers for agent tool steps.
 * Maps tool names to natural-language title / summary generators.
 */

import React from 'react'
import type { AgentStep } from '../../types/agent'

export interface ToolRenderer {
  title: (step: AgentStep) => React.ReactNode
  summary?: (step: AgentStep) => string | null
}

/** Type guard for accessing properties on an unknown object. */
function getProp<T>(obj: object | undefined, key: string, fallback: T): T {
  if (!obj) return fallback
  const val = (obj as Record<string, unknown>)[key]
  return val !== undefined && val !== null ? (val as T) : fallback
}

/** Truncate string to max code points (via Array.from for CJK safety). */
function truncate(str: string, max: number): string {
  const chars = Array.from(str)
  if (chars.length <= max) return str
  return chars.slice(0, max).join('') + '...'
}

/** Safe JSON.stringify that never throws. */
function safeStringify(value: unknown, maxLen = 60): { text: string; truncated: boolean } {
  try {
    const json = JSON.stringify(value)
    if (json.length <= maxLen) return { text: json, truncated: false }
    return { text: json.slice(0, maxLen), truncated: true }
  } catch {
    return { text: '[unserializable]', truncated: false }
  }
}

/* ------------------------------------------------------------------ */
/* search_documents                                                   */
/* ------------------------------------------------------------------ */

const searchDocumentsRenderer: ToolRenderer = {
  title: (step) => {
    const kw: string[] = getProp(step.toolInput, 'keywords', [])
    const category: string | undefined = getProp(step.toolInput, 'category', undefined)
    if (kw.length === 0 && !category) {
      return <>搜索文档</>
    }
    const parts: React.ReactNode[] = []
    if (kw.length > 0) {
      parts.push(
        <React.Fragment key="kw">
          关键词「{truncate(kw.join('、'), 40)}」
        </React.Fragment>
      )
    }
    if (category) {
      parts.push(
        <React.Fragment key="cat">
          {parts.length > 0 ? ' · ' : ''}分类「{truncate(category, 20)}」
        </React.Fragment>
      )
    }
    return <>搜索文档（{parts}）</>
  },
  summary: (step) => {
    const m = step.toolPreview?.match(/Found (\d+) documents?/i)
    if (m) return `找到 ${m[1]} 篇相关文档`
    if (step.toolPreview?.includes('No documents matched')) return '未找到相关文档'
    return null
  },
}

/* ------------------------------------------------------------------ */
/* grep_documents                                                     */
/* ------------------------------------------------------------------ */

const grepDocumentsRenderer: ToolRenderer = {
  title: (step) => {
    const pattern: string = getProp(step.toolInput, 'pattern', '')
    const useRegex: boolean = getProp(step.toolInput, 'regex', false)
    if (!pattern) return <>在文档中查找</>
    return (
      <>
        在文档中查找「{truncate(pattern, 40)}」
        {useRegex && <span className="text-gray-400">（正则）</span>}
      </>
    )
  },
  summary: (step) => {
    const m = step.toolPreview?.match(/Found (\d+) matches?/i)
    if (m) return `找到 ${m[1]} 处匹配`
    if (step.toolPreview?.includes('No matches')) return '未找到匹配'
    return null
  },
}

/* ------------------------------------------------------------------ */
/* get_document                                                       */
/* ------------------------------------------------------------------ */

const getDocumentRenderer: ToolRenderer = {
  title: (step) => {
    const docId: string = getProp(step.toolInput, 'document_id', '')
    const page: number = getProp(step.toolInput, 'page', 1)
    if (!docId) return <>阅读文档</>
    return (
      <>
        阅读文档 <span className="font-mono text-[11px]">{truncate(docId, 20)}</span>
        {page > 1 && <span className="text-gray-400"> · 第 {page} 页</span>}
      </>
    )
  },
  summary: (step) => {
    // Match: Document ID "Title" (page N/M) — tolerant of extra chars between ID and title
    const m = step.toolPreview?.match(/Document\s+\S+\s+"([^"]+)"\s*\(page\s+(\d+)\/(\d+)\)/)
    if (m) {
      const total = parseInt(m[3], 10)
      return total > 1 ? `《${m[1]}》 共 ${total} 页` : `《${m[1]}》`
    }
    return null
  },
}

/* ------------------------------------------------------------------ */
/* list_documents                                                     */
/* ------------------------------------------------------------------ */

const listDocumentsRenderer: ToolRenderer = {
  title: (step) => {
    const search: string | undefined = getProp(step.toolInput, 'search', undefined)
    if (search) {
      return <>浏览文档（筛选「{truncate(search, 30)}」）</>
    }
    return <>浏览文档列表</>
  },
  summary: (step) => {
    const m = step.toolPreview?.match(/共 (\d+) 篇文档/)
    if (m) return `共 ${m[1]} 篇文档`
    if (step.toolPreview?.includes('未找到')) return '未找到文档'
    return null
  },
}

/* ------------------------------------------------------------------ */
/* get_document_summary                                               */
/* ------------------------------------------------------------------ */

const getDocumentSummaryRenderer: ToolRenderer = {
  title: (step) => {
    const docId: string = getProp(step.toolInput, 'document_id', '')
    if (!docId) return <>查看文档摘要</>
    return (
      <>
        查看文档 <span className="font-mono text-[11px]">{truncate(docId, 20)}</span> 的摘要
      </>
    )
  },
  summary: (step) => {
    const m = step.toolPreview?.match(/Summary for\s+\S+\s+"([^"]+)"/)
    if (m) return `《${m[1]}》`
    return null
  },
}

/* ------------------------------------------------------------------ */
/* list_collections                                                   */
/* ------------------------------------------------------------------ */

const listCollectionsRenderer: ToolRenderer = {
  title: () => <>查看知识库列表</>,
  summary: (step) => {
    const m = step.toolPreview?.match(/Available collections? \((\d+)\)/i)
    if (m) return `共 ${m[1]} 个知识库`
    if (step.toolPreview?.includes('No collections')) return '暂无知识库'
    return null
  },
}

/* ------------------------------------------------------------------ */
/* get_collection_overview                                            */
/* ------------------------------------------------------------------ */

const getCollectionOverviewRenderer: ToolRenderer = {
  title: (step) => {
    const cid: string = getProp(step.toolInput, 'collection_id', '')
    if (!cid) return <>查看知识库概览</>
    return (
      <>
        查看知识库 <span className="font-mono text-[11px]">{truncate(cid, 20)}</span> 的概览
      </>
    )
  },
  summary: (step) => {
    const m = step.toolPreview?.match(/^# Collection:\s*(.+)$/m)
    if (m) return `《${m[1].trim()}》`
    return null
  },
}

/* ------------------------------------------------------------------ */
/* citations                                                          */
/* ------------------------------------------------------------------ */

const citationsRenderer: ToolRenderer = {
  title: () => <>生成引用标记</>,
  summary: (step) => {
    if (!step.toolPreview) return null
    // Only count citation markers that appear at line start after whitespace,
    // or at the very beginning of the text. This avoids false positives in code.
    const m = step.toolPreview.match(/(^|\n)\s*\[\d+\]/g)
    if (m) return `共 ${m.length} 条引用`
    return null
  },
}

/* ------------------------------------------------------------------ */
/* start_answer                                                       */
/* ------------------------------------------------------------------ */

const startAnswerRenderer: ToolRenderer = {
  title: () => <>准备输出答案</>,
}

/* ------------------------------------------------------------------ */
/* list_chats                                                         */
/* ------------------------------------------------------------------ */

const listChatsRenderer: ToolRenderer = {
  title: () => <>查看所有会话</>,
  summary: (step) => {
    const m = step.toolPreview?.match(/共有 (\d+) 个聊天会话/)
    if (m) return `共 ${m[1]} 个会话`
    if (step.toolPreview?.includes('暂无')) return '暂无会话'
    return null
  },
}

/* ------------------------------------------------------------------ */
/* chat_info                                                          */
/* ------------------------------------------------------------------ */

const chatInfoRenderer: ToolRenderer = {
  title: (step) => {
    const newName: string | undefined = getProp(step.toolInput, 'new_name', undefined)
    if (newName) {
      return <>修改会话标题为「{truncate(newName, 30)}」</>
    }
    return <>查看会话信息</>
  },
  summary: (step) => {
    if (step.toolPreview?.includes('已更新为')) return step.toolPreview
    return null
  },
}

/* ------------------------------------------------------------------ */
/* Registry                                                           */
/* ------------------------------------------------------------------ */

export const toolRenderers: Record<string, ToolRenderer> = {
  search_documents: searchDocumentsRenderer,
  grep_documents: grepDocumentsRenderer,
  get_document: getDocumentRenderer,
  get_document_summary: getDocumentSummaryRenderer,
  list_documents: listDocumentsRenderer,
  list_collections: listCollectionsRenderer,
  get_collection_overview: getCollectionOverviewRenderer,
  citations: citationsRenderer,
  cite_sources: citationsRenderer,
  start_answer: startAnswerRenderer,
  chat_info: chatInfoRenderer,
  list_chats: listChatsRenderer,
}

/**
 * Get a human-friendly title for a tool step.
 * Falls back to toolName + truncated JSON if no renderer is registered.
 */
export function renderToolTitle(step: AgentStep): React.ReactNode {
  const renderer = step.toolName ? toolRenderers[step.toolName] : undefined
  if (renderer) {
    return renderer.title(step)
  }
  // Fallback: raw toolName + JSON
  const { text: inputStr, truncated } = step.toolInput
    ? safeStringify(step.toolInput, 60)
    : { text: '', truncated: false }
  return (
    <>
      {step.toolName || 'tool'}
      {inputStr && (
        <span className="text-gray-300">
          ({inputStr}
          {truncated && '...'})
        </span>
      )}
    </>
  )
}

/**
 * Get a one-line summary of the tool result, if available.
 */
export function renderToolSummary(step: AgentStep): string | null {
  const renderer = step.toolName ? toolRenderers[step.toolName] : undefined
  if (renderer?.summary) {
    return renderer.summary(step)
  }
  return null
}
