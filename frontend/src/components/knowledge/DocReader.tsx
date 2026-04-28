/**
 * Document reader panel - shows a document in HTML (iframe) or Markdown view
 */

import React, { useCallback, useEffect, useState } from 'react'
import { ArrowTopRightOnSquareIcon, DocumentTextIcon, CodeBracketIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { useAPIClient, extractData } from '../../services/apiClient'

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

  const loadMarkdown = useCallback(async () => {
    if (markdownContent !== null || loading) return
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
  }, [apiClient, collectionId, doc.id, markdownContent, loading])

  useEffect(() => {
    if (viewMode === 'markdown') {
      loadMarkdown()
    }
  }, [viewMode, loadMarkdown])

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Top bar */}
      <div className="flex-shrink-0 flex items-center gap-3 px-4 py-3 border-b border-gray-200/50 bg-white/80 backdrop-blur-sm">
        <h3 className="text-sm font-semibold text-gray-900 truncate flex-1">
          {doc.name}
          {doc.nameTranslated && (
            <span className="text-gray-500 font-normal"> ({doc.nameTranslated})</span>
          )}
        </h3>

        {/* View mode toggle */}
        <div className="flex items-center bg-gray-100 rounded-lg p-0.5 flex-shrink-0">
          <button
            onClick={() => setViewMode('html')}
            className={clsx(
              'flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
              viewMode === 'html'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            )}
            title="HTML 预览"
          >
            <CodeBracketIcon className="w-3.5 h-3.5" />
            HTML
          </button>
          <button
            onClick={() => setViewMode('markdown')}
            className={clsx(
              'flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
              viewMode === 'markdown'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
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
              <div className="flex items-center justify-center h-full text-sm text-gray-500">
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
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={{
                    h1: ({ children }) => (
                      <h1 className="text-2xl font-bold mb-4 text-gray-900">{children}</h1>
                    ),
                    h2: ({ children }) => (
                      <h2 className="text-xl font-semibold mb-3 mt-6 text-gray-900">{children}</h2>
                    ),
                    h3: ({ children }) => (
                      <h3 className="text-lg font-semibold mb-2 mt-4 text-gray-900">{children}</h3>
                    ),
                    p: ({ children }) => (
                      <p className="mb-3 last:mb-0 text-gray-800 leading-relaxed">{children}</p>
                    ),
                    ul: ({ children }) => (
                      <ul className="list-disc list-inside mb-3 space-y-1 text-gray-800">{children}</ul>
                    ),
                    ol: ({ children }) => (
                      <ol className="list-decimal list-inside mb-3 space-y-1 text-gray-800">{children}</ol>
                    ),
                    li: ({ children }) => <li className="text-gray-800">{children}</li>,
                    blockquote: ({ children }) => (
                      <blockquote className="border-l-4 border-gray-300 pl-4 py-2 mb-3 bg-gray-50 text-gray-700 italic">
                        {children}
                      </blockquote>
                    ),
                    code: ({ className, children, ...props }: any) => {
                      const inline = !className
                      if (inline) {
                        return (
                          <code
                            className="bg-gray-100 text-gray-800 px-1 py-0.5 rounded text-sm font-mono"
                            {...props}
                          >
                            {children}
                          </code>
                        )
                      }
                      return (
                        <div className="my-3">
                          <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto text-sm">
                            <code className={className} {...props}>
                              {children}
                            </code>
                          </pre>
                        </div>
                      )
                    },
                    table: ({ children }) => (
                      <div className="overflow-x-auto mb-3">
                        <table className="min-w-full border border-gray-300 text-sm">
                          {children}
                        </table>
                      </div>
                    ),
                    thead: ({ children }) => <thead className="bg-gray-50">{children}</thead>,
                    tbody: ({ children }) => <tbody>{children}</tbody>,
                    tr: ({ children }) => <tr className="border-b border-gray-200">{children}</tr>,
                    th: ({ children }) => (
                      <th className="border border-gray-300 px-3 py-2 text-left font-semibold text-gray-900">
                        {children}
                      </th>
                    ),
                    td: ({ children }) => (
                      <td className="border border-gray-300 px-3 py-2 text-gray-800">{children}</td>
                    ),
                    strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
                    em: ({ children }) => <em className="italic text-gray-900">{children}</em>,
                    a: ({ href, children }) => (
                      <a
                        href={href}
                        className="text-blue-600 hover:text-blue-800 underline"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {children}
                      </a>
                    ),
                    hr: () => <hr className="my-4 border-gray-200" />,
                  }}
                >
                  {markdownContent}
                </ReactMarkdown>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default DocReader
