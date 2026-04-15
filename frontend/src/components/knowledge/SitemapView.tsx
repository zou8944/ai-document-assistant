/**
 * Sitemap tree view component for displaying crawled site structure
 */

import React, { useState, useMemo } from 'react'
import {
  ChevronRightIcon,
  ChevronDownIcon,
  FolderIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline'
import clsx from 'clsx'

interface SitemapPage {
  path: string
  description?: string
  category?: string
}

interface TreeNode {
  name: string
  path: string
  children: TreeNode[]
  page?: SitemapPage
  category?: string
}

interface SitemapViewProps {
  sitemapJson: string | null
  onPageClick: (path: string) => void
}

function buildTree(pages: SitemapPage[]): TreeNode {
  const root: TreeNode = { name: '/', path: '', children: [] }

  for (const page of pages) {
    const segments = page.path.replace(/^\//, '').split('/').filter(Boolean)
    let current = root

    for (let i = 0; i < segments.length; i++) {
      const segment = segments[i]
      const partialPath = '/' + segments.slice(0, i + 1).join('/')
      let child = current.children.find(c => c.name === segment)

      if (!child) {
        child = {
          name: segment,
          path: partialPath,
          children: [],
          category: page.category,
        }
        current.children.push(child)
      }

      if (i === segments.length - 1) {
        child.page = page
        child.category = page.category
      }

      current = child
    }
  }

  return root
}

const TreeNodeItem: React.FC<{
  node: TreeNode
  depth: number
  onPageClick: (path: string) => void
}> = ({ node, depth, onPageClick }) => {
  const [expanded, setExpanded] = useState(depth < 2)
  const hasChildren = node.children.length > 0
  const isPage = !!node.page

  const handleClick = () => {
    if (hasChildren) {
      setExpanded(!expanded)
    }
    if (isPage) {
      onPageClick(node.page!.path)
    }
  }

  const categoryColor = useMemo(() => {
    const colors = [
      'text-blue-600',
      'text-purple-600',
      'text-green-600',
      'text-orange-600',
      'text-pink-600',
      'text-teal-600',
    ]
    if (!node.category) return ''
    let hash = 0
    for (const ch of node.category) {
      hash = ((hash << 5) - hash) + ch.charCodeAt(0)
    }
    return colors[Math.abs(hash) % colors.length]
  }, [node.category])

  return (
    <div>
      <div
        className={clsx(
          'flex items-center py-1.5 px-2 rounded-lg cursor-pointer transition-colors group',
          'hover:bg-blue-50/60',
          isPage && 'hover:bg-blue-100/60'
        )}
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
        onClick={handleClick}
      >
        {hasChildren ? (
          expanded ? (
            <ChevronDownIcon className="w-4 h-4 text-gray-400 flex-shrink-0 mr-1" />
          ) : (
            <ChevronRightIcon className="w-4 h-4 text-gray-400 flex-shrink-0 mr-1" />
          )
        ) : (
          <span className="w-5 flex-shrink-0 mr-1" />
        )}

        {hasChildren ? (
          <FolderIcon className="w-4 h-4 text-yellow-500 flex-shrink-0 mr-2" />
        ) : (
          <DocumentTextIcon className={clsx('w-4 h-4 flex-shrink-0 mr-2', categoryColor || 'text-gray-400')} />
        )}

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={clsx(
              'text-sm truncate',
              isPage ? 'text-gray-800 font-medium' : 'text-gray-600'
            )}>
              {node.name}
            </span>
            {node.category && (
              <span className={clsx(
                'text-xs px-1.5 py-0.5 rounded-full bg-gray-100 flex-shrink-0',
                categoryColor
              )}>
                {node.category}
              </span>
            )}
          </div>
          {isPage && node.page!.description && (
            <p className="text-xs text-gray-500 truncate mt-0.5">
              {node.page!.description}
            </p>
          )}
        </div>
      </div>

      {hasChildren && expanded && (
        <div>
          {node.children
            .sort((a, b) => {
              // Folders first, then files
              if (a.children.length > 0 && b.children.length === 0) return -1
              if (a.children.length === 0 && b.children.length > 0) return 1
              return a.name.localeCompare(b.name)
            })
            .map(child => (
              <TreeNodeItem
                key={child.path}
                node={child}
                depth={depth + 1}
                onPageClick={onPageClick}
              />
            ))}
        </div>
      )}
    </div>
  )
}

export const SitemapView: React.FC<SitemapViewProps> = ({ sitemapJson, onPageClick }) => {
  const pages = useMemo(() => {
    if (!sitemapJson) return []
    try {
      const parsed = JSON.parse(sitemapJson)
      return parsed.pages || []
    } catch {
      return []
    }
  }, [sitemapJson])

  const tree = useMemo(() => buildTree(pages), [pages])

  if (!sitemapJson || pages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-gray-500">
        <FolderIcon className="w-12 h-12 mb-2 opacity-50" />
        <p>暂无站点结构</p>
        <p className="text-sm">导入网页 URL 后将自动生成</p>
      </div>
    )
  }

  return (
    <div className="py-2">
      {tree.children
        .sort((a, b) => {
          if (a.children.length > 0 && b.children.length === 0) return -1
          if (a.children.length === 0 && b.children.length > 0) return 1
          return a.name.localeCompare(b.name)
        })
        .map(child => (
          <TreeNodeItem
            key={child.path}
            node={child}
            depth={0}
            onPageClick={onPageClick}
          />
        ))}
    </div>
  )
}

export default SitemapView
