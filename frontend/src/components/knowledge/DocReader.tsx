/**
 * Document reader panel - shows a document's Markdown content with
 * a prominent "Open Original Page" button.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowTopRightOnSquareIcon } from '@heroicons/react/24/outline'
import { useAPIClient, extractData } from '../../services/apiClient'
import { markdownToHtml } from '../../utils/markdown'

interface DocInfo {
  id: string
  name: string
  nameTranslated?: string
  url?: string
}

interface DocReaderProps {
  doc: DocInfo
  collectionId: string
}

export const DocReader: React.FC<DocReaderProps> = ({ doc, collectionId }) => {
  const [markdownContent, setMarkdownContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const apiClient = useAPIClient()
  const containerRef = useRef<HTMLDivElement>(null)

  const loadMarkdown = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiClient.getDocumentContent(collectionId, doc.id)
      const data = extractData(response)
      setMarkdownContent(data.content)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [apiClient, collectionId, doc.id])

  // Load markdown on mount and when document changes
  useEffect(() => {
    setMarkdownContent(null)
    setError(null)
    loadMarkdown()
  }, [doc.id, loadMarkdown])

  const html = useMemo(() => {
    if (!markdownContent) return ''
    return markdownToHtml(markdownContent, doc.url)
  }, [markdownContent, doc.url])

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      const link = (e.target as HTMLElement).closest('a[data-doc-link]')
      if (!(link instanceof HTMLAnchorElement)) return

      const href = link.getAttribute('href')
      if (!href) return

      // Anchor links - scroll within container
      if (href.startsWith('#')) {
        e.preventDefault()
        const targetId = href.slice(1)
        const targetEl = containerRef.current?.querySelector(`[id="${CSS.escape(targetId)}"]`)
        if (targetEl) {
          targetEl.scrollIntoView({ behavior: 'smooth', block: 'start' })
        }
        return
      }

      // External links - open in new tab
      if (href.startsWith('http://') || href.startsWith('https://')) {
        e.preventDefault()
        window.open(href, '_blank', 'noopener,noreferrer')
        return
      }
    },
    []
  )

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Top bar */}
      <div className="flex-shrink-0 flex items-center gap-3 px-4 py-3 border-b border-white/40 bg-white/80 backdrop-blur-sm">
        <h3 className="text-sm font-semibold text-ink truncate flex-1">
          {doc.name}
          {doc.nameTranslated && (
            <span className="text-ink/50 font-normal"> ({doc.nameTranslated})</span>
          )}
        </h3>

        {doc.url ? (
          <a
            href={doc.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
              border border-accent/30 bg-accent/5 text-accent rounded-lg
              hover:bg-accent/10 transition-colors flex-shrink-0
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
          >
            <ArrowTopRightOnSquareIcon className="w-3.5 h-3.5" />
            打开原网页
          </a>
        ) : (
          <button
            disabled
            title="无原始链接"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
              border border-gray-200 bg-gray-50 text-gray-400 rounded-lg
              cursor-not-allowed flex-shrink-0"
          >
            <ArrowTopRightOnSquareIcon className="w-3.5 h-3.5" />
            打开原网页
          </button>
        )}
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-auto bg-white">
        {loading ? (
          <div
            role="status"
            aria-live="polite"
            className="flex items-center justify-center h-full text-sm text-ink/50"
          >
            加载 Markdown 内容...
          </div>
        ) : error ? (
          <div className="flex items-center justify-center h-full text-sm text-red-500">
            加载失败: {error}
          </div>
        ) : !markdownContent ? (
          <div className="flex items-center justify-center h-full text-sm text-gray-400">
            暂无 Markdown 内容
          </div>
        ) : (
          <div className="max-w-3xl mx-auto px-6 py-8">
            <div
              ref={containerRef}
              className="prose prose-sm max-w-none
                prose-headings:text-ink prose-headings:font-semibold
                prose-h1:text-2xl prose-h1:mb-4 prose-h1:pb-2 prose-h1:border-b prose-h1:border-gray-200
                prose-h2:text-xl prose-h2:mt-6 prose-h2:mb-3
                prose-h3:text-lg prose-h3:mt-4 prose-h3:mb-2
                prose-p:text-ink/90 prose-p:leading-relaxed
                prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline
                prose-strong:text-ink
                prose-ul:text-ink/90 prose-ul:my-3
                prose-li:my-1
                prose-img:rounded-lg prose-img:shadow-sm
                prose-blockquote:border-l-4 prose-blockquote:border-gray-300 prose-blockquote:pl-4 prose-blockquote:py-2 prose-blockquote:bg-gray-50 prose-blockquote:text-ink/80 prose-blockquote:italic
                prose-code:bg-gray-100 prose-code:text-ink/90 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-sm prose-code:font-mono
                prose-pre:bg-gray-900 prose-pre:text-gray-100 prose-pre:p-4 prose-pre:rounded-lg prose-pre:overflow-x-auto prose-pre:text-sm"
              dangerouslySetInnerHTML={{ __html: html }}
              onClick={handleClick}
            />
          </div>
        )}
      </div>
    </div>
  )
}

export default DocReader
