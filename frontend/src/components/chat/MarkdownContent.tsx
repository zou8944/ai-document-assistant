/**
 * Markdown content renderer with improved styling
 */

import React, { useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { ClipboardIcon, CheckIcon } from '@heroicons/react/24/outline'

interface MarkdownContentProps {
  content: string
  isUser?: boolean
}

const CodeBlock: React.FC<{
  language: string
  children: React.ReactNode
}> = ({ language, children }) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(() => {
    const text = String(children).replace(/\n$/, '')
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [children])

  return (
    <div className="my-3 rounded-lg overflow-hidden border border-gray-200 bg-[#F9F9F9]">
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#F5F5F5] border-b border-gray-200">
        <span className="text-[11px] font-medium text-muted uppercase tracking-wider font-mono">
          {language || 'code'}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center space-x-1 text-[11px] text-muted hover:text-ink transition-colors"
        >
          {copied ? (
            <>
              <CheckIcon className="w-3 h-3" />
              <span>已复制</span>
            </>
          ) : (
            <>
              <ClipboardIcon className="w-3 h-3" />
              <span>复制</span>
            </>
          )}
        </button>
      </div>
      <pre className="bg-[#F9F9F9] p-3 overflow-x-auto text-[13px] leading-relaxed">
        <code className="font-mono text-ink">{children}</code>
      </pre>
    </div>
  )
}

export const MarkdownContent: React.FC<MarkdownContentProps> = ({ content, isUser = false }) => {
  if (isUser) {
    return <p className="whitespace-pre-wrap leading-relaxed text-base">{content}</p>
  }

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkBreaks]}
      components={{
        h1: ({ children }) => (
          <h1 className="text-xl font-bold mt-6 mb-3 text-ink leading-tight">
            {children}
          </h1>
        ),
        h2: ({ children }) => (
          <h2 className="text-lg font-semibold mt-5 mb-2.5 text-ink leading-tight">
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className="text-base font-semibold mt-4 mb-2 text-ink leading-tight">
            {children}
          </h3>
        ),
        h4: ({ children }) => (
          <h4 className="text-sm font-semibold mt-3 mb-1.5 text-ink">
            {children}
          </h4>
        ),
        p: ({ children }) => (
          <p className="mb-3 last:mb-0 text-ink leading-[1.7]">
            {children}
          </p>
        ),
        ul: ({ children }) => (
          <ul className="list-disc pl-5 mb-3 space-y-1 text-ink">
            {children}
          </ul>
        ),
        ol: ({ children }) => (
          <ol className="list-decimal pl-5 mb-3 space-y-1 text-ink">
            {children}
          </ol>
        ),
        li: ({ children }) => (
          <li className="leading-[1.7] pl-1 marker:text-muted">
            {children}
          </li>
        ),
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-accent pl-4 py-0.5 my-3 text-muted italic text-[15px] leading-[1.7]">
            {children}
          </blockquote>
        ),
        code: ({ className, children, ...props }: React.HTMLAttributes<HTMLElement> & { className?: string }) => {
          const inline = !className
          if (inline) {
            return (
              <code
                className="bg-paper-dark text-ink px-1 py-0.5 rounded text-[13px] font-mono"
                {...props}
              >
                {children}
              </code>
            )
          }
          const language = className?.replace('language-', '') || ''
          return (
            <CodeBlock language={language}>
              {children}
            </CodeBlock>
          )
        },
        table: ({ children }) => (
          <div className="overflow-x-auto my-3">
            <table className="min-w-full text-sm border-collapse">
              {children}
            </table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-paper-dark">{children}</thead>,
        tbody: ({ children }) => <tbody>{children}</tbody>,
        tr: ({ children }) => <tr className="border-b border-warm-border last:border-b-0">{children}</tr>,
        th: ({ children }) => (
          <th className="px-3 py-2 text-left font-semibold text-ink text-sm border-b border-warm-border">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-3 py-2 text-ink text-sm">
            {children}
          </td>
        ),
        strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
        em: ({ children }) => <em className="italic text-muted">{children}</em>,
        a: ({ href, children }) => (
          <a
            href={href}
            className="text-accent hover:text-accent-hover hover:underline transition-colors"
            target="_blank"
            rel="noopener noreferrer"
          >
            {children}
          </a>
        ),
        hr: () => <hr className="my-4 border-warm-border" />,
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

export default MarkdownContent
