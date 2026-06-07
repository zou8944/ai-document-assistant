/**
 * Lightweight markdown to HTML converter.
 * Mirrors ReadmePanel's parser with image support and relative URL resolution.
 */

function resolveUrl(url: string, baseUrl?: string): string {
  if (!baseUrl || !url) return url
  if (/^https?:\/\//.test(url)) return url
  if (url.startsWith('data:')) return url
  try {
    return new URL(url, baseUrl).href
  } catch {
    return url
  }
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * Process inline markdown: code, bold, links, images
 */
function processInline(text: string, baseUrl?: string): string {
  // Inline code: ``code`` (double backtick first to avoid partial match)
  text = text.replace(/``([^`]+)``/g, (_, code) => {
    return `<code class="bg-gray-100 text-ink/90 px-1 py-0.5 rounded text-sm font-mono">${escapeHtml(code)}</code>`
  })
  // Inline code: `code`
  text = text.replace(/`([^`]+)`/g, (_, code) => {
    return `<code class="bg-gray-100 text-ink/90 px-1 py-0.5 rounded text-sm font-mono">${escapeHtml(code)}</code>`
  })

  // Images: ![alt](url)
  text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, url) => {
    const resolved = resolveUrl(url, baseUrl)
    return `<img src="${resolved}" alt="${alt}" />`
  })

  // Bold
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')

  // Links
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, url) => {
    return `<a href="${url}" data-doc-link="true">${label}</a>`
  })

  return text
}

function parseTableRow(line: string, baseUrl?: string): string[] {
  let content = line.trim()
  if (content.startsWith('|')) content = content.slice(1)
  if (content.endsWith('|')) content = content.slice(0, -1)

  return content.split('|').map(cell => processInline(cell.trim(), baseUrl))
}

function renderTable(lines: string[], baseUrl?: string): string {
  if (lines.length < 2) return ''

  const headerCells = parseTableRow(lines[0], baseUrl)
  const bodyRows = lines.slice(2).map(line => parseTableRow(line, baseUrl))

  let html = '<div class="overflow-x-auto mb-3"><table class="min-w-full border border-gray-300 text-sm">'

  html += '<thead class="bg-gray-50"><tr>'
  headerCells.forEach(cell => {
    html += `<th class="border border-gray-300 px-3 py-2 text-left font-semibold text-ink">${cell}</th>`
  })
  html += '</tr></thead>'

  if (bodyRows.length > 0) {
    html += '<tbody>'
    bodyRows.forEach(cells => {
      html += '<tr class="border-b border-gray-200">'
      cells.forEach(cell => {
        html += `<td class="border border-gray-300 px-3 py-2 text-ink/90">${cell}</td>`
      })
      html += '</tr>'
    })
    html += '</tbody>'
  }

  html += '</table></div>'
  return html
}

/**
 * Simple markdown to HTML converter.
 * Handles headings, tables, bold, links, images, lists, blockquotes, code blocks, and paragraphs.
 */
export function markdownToHtml(md: string, baseUrl?: string): string {
  const lines = md.split('\n')
  const htmlParts: string[] = []
  let inList = false
  let inBlockquote = false
  let inCodeBlock = false
  let codeLines: string[] = []

  const flushList = () => {
    if (inList) {
      htmlParts.push('</ul>')
      inList = false
    }
  }

  const flushBlockquote = () => {
    if (inBlockquote) {
      htmlParts.push('</blockquote>')
      inBlockquote = false
    }
  }

  const flushCodeBlock = () => {
    if (!inCodeBlock) return
    const code = codeLines.join('\n')
    htmlParts.push(`<pre class="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto text-sm"><code>${escapeHtml(code)}</code></pre>`)
    inCodeBlock = false
    codeLines = []
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    // Code block start/end
    if (trimmed.startsWith('```')) {
      if (inCodeBlock) {
        flushCodeBlock()
      } else {
        flushList()
        flushBlockquote()
        inCodeBlock = true
      }
      continue
    }

    if (inCodeBlock) {
      codeLines.push(line)
      continue
    }

    // Close blockquote if needed
    if (inBlockquote && !trimmed.startsWith('>')) {
      htmlParts.push('</blockquote>')
      inBlockquote = false
    }

    // Close list if needed
    if (inList && !trimmed.startsWith('- ') && !trimmed.startsWith('* ')) {
      htmlParts.push('</ul>')
      inList = false
    }

    if (!trimmed) {
      continue
    }

    // Horizontal rule
    if (/^-{3,}$|^\*{3,}$|^_{3,}$/.test(trimmed)) {
      flushList()
      flushBlockquote()
      htmlParts.push('<hr class="my-4 border-gray-200" />')
      continue
    }

    // Table detection: | ... | followed by separator line
    if (
      trimmed.startsWith('|') &&
      i + 1 < lines.length &&
      /^\|?\s*[-:]+/.test(lines[i + 1].trim())
    ) {
      flushList()
      flushBlockquote()
      const tableLines: string[] = []
      let j = i
      while (j < lines.length && lines[j].trim().startsWith('|')) {
        tableLines.push(lines[j].trim())
        j++
      }
      htmlParts.push(renderTable(tableLines, baseUrl))
      i = j - 1
      continue
    }

    // Blockquote
    if (trimmed.startsWith('>')) {
      flushList()
      if (!inBlockquote) {
        htmlParts.push('<blockquote>')
        inBlockquote = true
      }
      const text = processInline(trimmed.slice(1).trim(), baseUrl)
      htmlParts.push(`<p>${text}</p>`)
      continue
    }

    // Headings
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)/)
    if (headingMatch) {
      flushList()
      flushBlockquote()
      const level = headingMatch[1].length
      const rawText = headingMatch[2]
      let text = processInline(rawText, baseUrl)
      // Strip leading anchor links that are just "#" (common in crawled docs)
      text = text.replace(/^<a[^>]*>#<\/a>\s*/, '')
      const id = rawText.trim()
      htmlParts.push(`<h${level} id="${id}">${text}</h${level}>`)
      continue
    }

    // List items
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (!inList) {
        htmlParts.push('<ul>')
        inList = true
      }
      const text = processInline(trimmed.slice(2), baseUrl)
      htmlParts.push(`<li>${text}</li>`)
      continue
    }

    // Paragraph
    flushList()
    flushBlockquote()
    const text = processInline(trimmed, baseUrl)
    htmlParts.push(`<p>${text}</p>`)
  }

  flushCodeBlock()
  flushList()
  flushBlockquote()

  let html = htmlParts.join('\n')

  // Post-process: remove duplicate consecutive h1 headings (common in crawled docs
  // where a page-level title and an article-level title are both present)
  html = removeDuplicateH1(html)

  return html
}

/**
 * Remove duplicate consecutive h1 headings and any content between them.
 * Handles patterns like: <h1>Title</h1> ... <h1>Title</h1>
 */
function removeDuplicateH1(html: string): string {
  const matches: Array<{ index: number; length: number; text: string }> = []
  const regex = /<h1\b[^>]*>([\s\S]*?)<\/h1>/gi
  let match
  while ((match = regex.exec(html)) !== null) {
    matches.push({
      index: match.index,
      length: match[0].length,
      text: match[1].replace(/<[^\u003e]+>/g, '').trim(),
    })
  }

  for (let i = 0; i < matches.length - 1; i++) {
    if (matches[i].text === matches[i + 1].text) {
      const start = matches[i].index + matches[i].length
      const end = matches[i + 1].index + matches[i + 1].length
      return html.slice(0, start) + html.slice(end)
    }
  }

  return html
}
