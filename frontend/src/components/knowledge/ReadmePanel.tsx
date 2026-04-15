/**
 * README navigation panel - renders AI-generated markdown with doc:// link interception
 */

import React, { useCallback, useMemo } from 'react'

interface ReadmePanelProps {
  readmeContent: string
  onDocClick: (path: string) => void
}

/**
 * Simple markdown to HTML converter for README content.
 * Handles headings, bold, links, lists, and paragraphs.
 */
function markdownToHtml(md: string): string {
  const lines = md.split('\n')
  const htmlParts: string[] = []
  let inList = false

  for (const line of lines) {
    const trimmed = line.trim()

    // Close list if needed
    if (inList && !trimmed.startsWith('- ') && !trimmed.startsWith('* ')) {
      htmlParts.push('</ul>')
      inList = false
    }

    if (!trimmed) {
      continue
    }

    // Headings
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)/)
    if (headingMatch) {
      const level = headingMatch[1].length
      const text = processInline(headingMatch[2])
      htmlParts.push(`<h${level}>${text}</h${level}>`)
      continue
    }

    // List items
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (!inList) {
        htmlParts.push('<ul>')
        inList = true
      }
      const text = processInline(trimmed.slice(2))
      htmlParts.push(`<li>${text}</li>`)
      continue
    }

    // Paragraph
    const text = processInline(trimmed)
    htmlParts.push(`<p>${text}</p>`)
  }

  if (inList) {
    htmlParts.push('</ul>')
  }

  return htmlParts.join('\n')
}

/**
 * Process inline markdown: bold, links
 */
function processInline(text: string): string {
  // Bold
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

  // Links - keep doc:// links, handle external links
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, url) => {
    return `<a href="${url}" data-doc-link="true">${label}</a>`
  })

  return text
}

export const ReadmePanel: React.FC<ReadmePanelProps> = ({
  readmeContent,
  onDocClick,
}) => {
  const html = useMemo(() => markdownToHtml(readmeContent), [readmeContent])

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      const target = e.target as HTMLElement
      if (target.tagName === 'A' && target.getAttribute('data-doc-link')) {
        e.preventDefault()
        const href = target.getAttribute('href')
        if (href) {
          // Parse doc:///path or doc://path
          const match = href.match(/^doc:\/\/\/?(.+)$/)
          if (match) {
            onDocClick('/' + match[1])
          }
        }
      }
    },
    [onDocClick]
  )

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div
        className="prose prose-sm max-w-none
          prose-headings:text-gray-900 prose-headings:font-semibold
          prose-h1:text-2xl prose-h1:mb-6 prose-h1:pb-3 prose-h1:border-b prose-h1:border-gray-200
          prose-h2:text-xl prose-h2:mt-8 prose-h2:mb-4
          prose-h3:text-lg prose-h3:mt-6 prose-h3:mb-3
          prose-p:text-gray-700 prose-p:leading-relaxed
          prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline
          prose-strong:text-gray-900
          prose-ul:text-gray-700 prose-ul:my-3
          prose-li:my-1.5
          [&_a[data-doc-link]]:cursor-pointer
          [&_a[data-doc-link]]:text-blue-600
          [&_a[data-doc-link]]:hover:text-blue-700
          [&_a[data-doc-link]]:font-medium"
        dangerouslySetInnerHTML={{ __html: html }}
        onClick={handleClick}
      />
    </div>
  )
}

export default ReadmePanel
