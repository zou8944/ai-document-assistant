/**
 * Utilities for parsing and working with category/README data
 */

export interface SitemapPage {
  path: string
  title: string
  description?: string
}

export interface CategoryGroup {
  category: string
  pages: SitemapPage[]
}

/**
 * Parse categories JSON string into typed array
 */
export function parseCategories(json: string | null): CategoryGroup[] {
  if (!json) return []
  try {
    const parsed = JSON.parse(json)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (g): g is CategoryGroup =>
        g && typeof g.category === 'string' && Array.isArray(g.pages)
    )
  } catch {
    return []
  }
}

/**
 * Extract unique category names from parsed groups
 */
export function getCategoryNames(groups: CategoryGroup[]): string[] {
  return groups.map(g => g.category)
}

/**
 * Get page count per category
 */
export function getPageCountByCategory(groups: CategoryGroup[]): Map<string, number> {
  const map = new Map<string, number>()
  for (const g of groups) {
    map.set(g.category, g.pages.length)
  }
  return map
}

/**
 * Find which category a document belongs to, by matching source_path
 */
export function findCategoryForPath(
  groups: CategoryGroup[],
  sourcePath: string
): string | null {
  for (const g of groups) {
    if (g.pages.some(p => p.path === sourcePath)) {
      return g.category
    }
  }
  return null
}

/**
 * Get all pages for a specific category
 */
export function getPagesForCategory(
  groups: CategoryGroup[],
  category: string
): SitemapPage[] {
  const group = groups.find(g => g.category === category)
  return group ? group.pages : []
}

/**
 * Get total page count across all categories
 */
export function getTotalPageCount(groups: CategoryGroup[]): number {
  return groups.reduce((sum, g) => sum + g.pages.length, 0)
}
