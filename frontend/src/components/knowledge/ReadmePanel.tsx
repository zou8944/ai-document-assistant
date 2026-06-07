/**
 * README navigation panel - renders AI-generated markdown with doc:// link interception
 */

import React, { useCallback, useMemo, useRef } from 'react'
import { markdownToHtml } from '../../utils/markdown'

interface ReadmePanelProps {
  readmeContent: string
  readmeContentZh?: string | null
  displayLanguage: 'source' | 'zh'
  isBilingual: boolean
  onDocClick: (path: string) => void
}

export const ReadmePanel: React.FC<ReadmePanelProps> = ({
  readmeContent,
  readmeContentZh,
  displayLanguage,
  isBilingual,
  onDocClick,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const effectiveContent = isBilingual && displayLanguage === 'zh' && readmeContentZh
    ? readmeContentZh
    : readmeContent
  const html = useMemo(() => markdownToHtml(effectiveContent), [effectiveContent])

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      const link = (e.target as HTMLElement).closest('a[data-doc-link]')
      if (!(link instanceof HTMLAnchorElement)) return

      const href = link.getAttribute('href')
      if (!href) return

      // doc:// links - open document
      const docMatch = href.match(/^doc:\/\/\/?(.*)$/)
      if (docMatch) {
        e.preventDefault()
        const path = docMatch[1] || '/'
        onDocClick('/' + path)
        return
      }

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

      // Let other links behave normally
    },
    [onDocClick]
  )

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div
        ref={containerRef}
        className="prose prose-sm max-w-none
          prose-headings:text-ink prose-headings:font-semibold
          prose-h1:text-2xl prose-h1:mb-6 prose-h1:pb-3 prose-h1:border-b prose-h1:border-gray-200
          prose-h2:text-xl prose-h2:mt-8 prose-h2:mb-4
          prose-h3:text-lg prose-h3:mt-6 prose-h3:mb-3
          prose-p:text-ink/80 prose-p:leading-relaxed
          prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline
          prose-strong:text-ink
          prose-ul:text-ink/80 prose-ul:my-3
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
