/**
 * Sidebar navigation for knowledge base - category filtering
 */

import React from 'react'
import { FolderIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { CategoryGroup } from '../../utils/categoryParser'

interface SidebarNavProps {
  categories: CategoryGroup[]
  activeTab: 'overview' | 'all' | string
  onTabSelect: (tab: 'overview' | 'all' | string) => void
  highlightedCategory: string | null
  totalDocs: number
  readmeDocCount: number
}

export const SidebarNav: React.FC<SidebarNavProps> = ({
  categories,
  activeTab,
  onTabSelect,
  highlightedCategory,
  totalDocs,
  readmeDocCount,
}) => {
  const effectiveActive = (activeTab !== 'overview' && activeTab !== 'all')
    ? activeTab
    : (highlightedCategory || null)

  return (
    <div className="w-60 flex-shrink-0 border-r border-gray-200/50 bg-white/50 backdrop-blur-sm overflow-y-auto">
      <div className="py-2">
        {/* Overview (README) */}
        <button
          onClick={() => onTabSelect('overview')}
          className={clsx(
            'w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors',
            activeTab === 'overview'
              ? 'bg-blue-50/80 text-blue-600 font-medium'
              : 'text-gray-700 hover:bg-gray-50/80'
          )}
        >
          <span className="flex items-center gap-2">
            <FolderIcon className="w-4 h-4 flex-shrink-0" />
            概览
          </span>
          <span className={clsx(
            'text-xs px-1.5 py-0.5 rounded-full',
            activeTab === 'overview' ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-500'
          )}>
            {readmeDocCount}
          </span>
        </button>

        {/* All Documents */}
        <button
          onClick={() => onTabSelect('all')}
          className={clsx(
            'w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors',
            activeTab === 'all'
              ? 'bg-blue-50/80 text-blue-600 font-medium'
              : 'text-gray-700 hover:bg-gray-50/80'
          )}
        >
          <span className="flex items-center gap-2">
            <FolderIcon className="w-4 h-4 flex-shrink-0" />
            全部文档
          </span>
          <span className={clsx(
            'text-xs px-1.5 py-0.5 rounded-full',
            activeTab === 'all' ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-500'
          )}>
            {totalDocs}
          </span>
        </button>

        {/* Category Items */}
        {categories.map((group) => {
          const isActive = effectiveActive === group.category
          return (
            <button
              key={group.category}
              onClick={() => onTabSelect(group.category)}
              className={clsx(
                'w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors',
                isActive
                  ? 'bg-blue-50/80 text-blue-600 font-medium'
                  : 'text-gray-700 hover:bg-gray-50/80'
              )}
            >
              <span className="truncate">{group.category}</span>
              <span className={clsx(
                'text-xs px-1.5 py-0.5 rounded-full flex-shrink-0 ml-2',
                isActive ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-500'
              )}>
                {group.pages.length}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default SidebarNav
