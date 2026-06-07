/**
 * Markdown content renderer with improved styling
 */

import React, { useState, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import SyntaxHighlighterLib from 'react-syntax-highlighter/dist/esm/prism'
import type { SyntaxHighlighterProps } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { ClipboardIcon, CheckIcon } from '@heroicons/react/24/outline'

// react-syntax-highlighter types are not compatible with React 19 JSX types
const SyntaxHighlighter = SyntaxHighlighterLib as unknown as React.FC<SyntaxHighlighterProps>

interface MarkdownContentProps {
  content: string
  isUser?: boolean
}

const CodeBlock: React.FC<{
  language: string
  children: React.ReactNode
}> = ({ language, children }) => {
  const [copied, setCopied] = useState(false)
  const code = String(children).replace(/\n$/, '')

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [code])

  return (
    <div className="my-3 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-[#1E1E1E] border-b border-[#404040]">
        <span className="text-[11px] font-medium text-[#ABB2BF] uppercase tracking-wider font-mono">
          {language || 'code'}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center space-x-1 text-[11px] text-[#ABB2BF] hover:text-white transition-colors"
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
      <SyntaxHighlighter
        language={language || undefined}
        style={vscDarkPlus}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          padding: '1rem',
          fontSize: '13px',
          lineHeight: '1.6',
          background: '#1E1E1E',
        }}
        codeTagProps={{
          style: {
            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
          },
        }}
      >
        {code}
      </SyntaxHighlighter>
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
                className="bg-warm-border text-ink px-1.5 py-0.5 rounded-lg text-[13px] font-mono border border-warm-line"
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
        thead: ({ children }) => <thead className="bg-warm-border">{children}</thead>,
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
