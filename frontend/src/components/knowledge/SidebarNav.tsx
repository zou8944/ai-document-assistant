/**
 * Sidebar navigation for knowledge base - category filtering
 * Supports collapsed state
 */

import React from 'react'
import { FolderIcon, ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline'
import clsx from 'clsx'
import { CategoryGroup } from '../../utils/categoryParser'

interface SidebarNavProps {
  categories: CategoryGroup[]
  activeTab: 'overview' | 'all' | string
  onTabSelect: (tab: 'overview' | 'all' | string) => void
  highlightedCategory: string | null
  totalDocs: number
  readmeDocCount: number
  displayLanguage: 'source' | 'zh'
  isBilingual: boolean
  categoryNameMap: Map<string, string>
  onLanguageToggle: () => void
  collapsed: boolean
  onToggleCollapse: () => void
}

export const SidebarNav: React.FC<SidebarNavProps> = ({
  categories,
  activeTab,
  onTabSelect,
  highlightedCategory,
  totalDocs,
  readmeDocCount,
  displayLanguage,
  isBilingual,
  categoryNameMap,
  onLanguageToggle,
  collapsed,
  onToggleCollapse,
}) => {
  const effectiveActive = (activeTab !== 'overview' && activeTab !== 'all')
    ? activeTab
    : (highlightedCategory || null)

  const getDisplayCategory = (enName: string) => {
    if (!isBilingual || displayLanguage === 'source') return enName
    return categoryNameMap.get(enName) || enName
  }

  const getActiveLabel = () => {
    if (activeTab === 'overview') return '概览'
    if (activeTab === 'all') return '全部'
    return getDisplayCategory(activeTab).slice(0, 2)
  }

  if (collapsed) {
    return (
      <div className="w-10 flex-shrink-0 border-r border-gray-200/50 bg-white/50 backdrop-blur-sm flex flex-col items-center py-2">
        <button
          onClick={onToggleCollapse}
          className="p-1.5 hover:bg-gray-100/80 rounded-lg transition-colors mb-2"
          title="展开分组栏"
        >
          <ChevronRightIcon className="w-4 h-4 text-gray-500" />
        </button>
        <div className="flex-1 flex items-center justify-center">
          <span
            className="text-xs font-medium text-gray-500 tracking-widest"
            style={{ writingMode: 'vertical-rl' }}
            title={getActiveLabel()}
          >
            {getActiveLabel()}
          </span>
        </div>
        {isBilingual && (
          <button
            onClick={onLanguageToggle}
            className="p-1.5 hover:bg-gray-100/80 rounded-lg transition-colors mt-2"
            title={displayLanguage === 'source' ? 'English → 中文' : '中文 → English'}
          >
            <span className="text-[10px] text-gray-500 font-medium">
              {displayLanguage === 'source' ? 'En' : '中'}
            </span>
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="w-60 flex-shrink-0 border-r border-gray-200/50 bg-white/50 backdrop-blur-sm overflow-y-auto flex flex-col">
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200/30">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">分组</span>
        <button
          onClick={onToggleCollapse}
          className="p-1 hover:bg-gray-100/80 rounded transition-colors"
          title="收起分组栏"
        >
          <ChevronLeftIcon className="w-4 h-4 text-gray-400" />
        </button>
      </div>

      <div className="py-2 flex-1">
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
              <span className="truncate">{getDisplayCategory(group.category)}</span>
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

      {/* Language toggle for bilingual collections */}
      {isBilingual && (
        <div className="px-4 py-3 border-t border-gray-200/50">
          <button
            onClick={onLanguageToggle}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-gray-600 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <span>{displayLanguage === 'source' ? 'English' : '中文'}</span>
            <svg className="w-3 h-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
            </svg>
            <span>{displayLanguage === 'source' ? '中文' : 'English'}</span>
          </button>
        </div>
      )}
    </div>
  )
}

export default SidebarNav
