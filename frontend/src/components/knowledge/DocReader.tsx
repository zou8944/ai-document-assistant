/**
 * Document reader panel - shows a document in HTML (iframe) or Markdown view
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ArrowTopRightOnSquareIcon, DocumentTextIcon, CodeBracketIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'
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
  previewUrl: string
  collectionId: string
}

type ViewMode = 'html' | 'markdown'

export const DocReader: React.FC<DocReaderProps> = ({ doc, previewUrl, collectionId }) => {
  const [viewMode, setViewMode] = useState<ViewMode>('html')
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

  // Reset markdown content when document changes
  useEffect(() => {
    setMarkdownContent(null)
    setError(null)
  }, [doc.id])

  useEffect(() => {
    if (viewMode === 'markdown') {
      loadMarkdown()
    }
  }, [viewMode, loadMarkdown])

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

        {/* View mode toggle */}
        <div className="flex items-center bg-gray-100 rounded-lg p-0.5 flex-shrink-0">
          <button
            onClick={() => setViewMode('html')}
            className={clsx(
              'flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors',
              viewMode === 'html'
                ? 'bg-white text-ink shadow-sm'
                : 'text-ink/50 hover:text-ink/80'
            )}
            title="HTML 预览"
          >
            <CodeBracketIcon className="w-3.5 h-3.5" />
            HTML
          </button>
          <button
            onClick={() => setViewMode('markdown')}
            className={clsx(
              'flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors',
              viewMode === 'markdown'
                ? 'bg-white text-ink shadow-sm'
                : 'text-ink/50 hover:text-ink/80'
            )}
            title="Markdown 原文"
          >
            <DocumentTextIcon className="w-3.5 h-3.5" />
            Markdown
          </button>
        </div>

        {doc.url && (
          <a
            href={doc.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-blue-500 hover:text-blue-600 flex-shrink-0"
          >
            <ArrowTopRightOnSquareIcon className="w-3.5 h-3.5" />
            原文
          </a>
        )}
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-hidden">
        {viewMode === 'html' ? (
          <iframe
            src={previewUrl}
            className="w-full h-full border-0"
            title={doc.name}
            sandbox="allow-same-origin"
          />
        ) : (
          <div className="w-full h-full overflow-auto bg-white">
            {loading ? (
              <div className="flex items-center justify-center h-full text-sm text-ink/50">
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
        )}
      </div>
    </div>
  )
}

export default DocReader
