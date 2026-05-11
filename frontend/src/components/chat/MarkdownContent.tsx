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
    <div className="my-3 rounded-xl overflow-hidden border border-white/40 bg-white/50 backdrop-blur-sm">
      <div className="flex items-center justify-between px-4 py-2 bg-white/30 border-b border-white/30">
        <span className="text-[11px] font-medium text-[#8E8E93] uppercase tracking-wider font-mono">
          {language || 'code'}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center space-x-1 text-[11px] text-[#8E8E93] hover:text-[#007AFF] transition-colors"
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
      <pre className="p-4 overflow-x-auto text-[13px] leading-relaxed">
        <code className="font-mono text-[#1c1c1e]">{children}</code>
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
          <li className="leading-[1.7] pl-1 marker:text-[#8E8E93]">
            {children}
          </li>
        ),
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-[#007AFF] pl-4 py-0.5 my-3 text-[#8E8E93] italic text-[15px] leading-[1.7]">
            {children}
          </blockquote>
        ),
        code: ({ className, children, ...props }: React.HTMLAttributes<HTMLElement> & { className?: string }) => {
          const inline = !className
          if (inline) {
            return (
              <code
                className="bg-white/50 text-[#1c1c1e] px-1.5 py-0.5 rounded-md text-[13px] font-mono border border-white/30"
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
        thead: ({ children }) => <thead className="bg-white/30">{children}</thead>,
        tbody: ({ children }) => <tbody>{children}</tbody>,
        tr: ({ children }) => <tr className="border-b border-[#E5E5EA] last:border-b-0">{children}</tr>,
        th: ({ children }) => (
          <th className="px-3 py-2 text-left font-semibold text-[#1c1c1e] text-sm border-b border-[#E5E5EA]">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-3 py-2 text-[#1c1c1e] text-sm">
            {children}
          </td>
        ),
        strong: ({ children }) => <strong className="font-semibold text-[#1c1c1e]">{children}</strong>,
        em: ({ children }) => <em className="italic text-[#8E8E93]">{children}</em>,
        a: ({ href, children }) => (
          <a
            href={href}
            className="text-[#007AFF] hover:text-[#0066D6] hover:underline transition-colors"
            target="_blank"
            rel="noopener noreferrer"
          >
            {children}
          </a>
        ),
        hr: () => <hr className="my-4 border-[#E5E5EA]" />,
      }}
    >
      {content}
    </ReactMarkdown>
  )
}

export default MarkdownContent
