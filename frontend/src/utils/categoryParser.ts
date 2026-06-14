/**
 * Utilities for parsing and working with nested category/README data
 */

export interface SitemapPage {
  path: string
  title: string
  title_zh?: string
  description?: string
}

export interface CategoryNode {
  category: string
  category_zh?: string
  pages: SitemapPage[]
  children?: CategoryNode[]
}

// Backward-compatible alias
export type CategoryGroup = CategoryNode

/**
 * Parse categories JSON string into typed array (nested structure)
 */
export function parseCategories(json: string | null): CategoryNode[] {
  if (!json) return []
  try {
    const parsed = JSON.parse(json)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (g): g is CategoryNode =>
        g && typeof g.category === 'string' && Array.isArray(g.pages)
    )
  } catch {
    return []
  }
}

/**
 * Recursively collect all category names from nested structure
 */
export function getCategoryNames(groups: CategoryNode[]): string[] {
  const names: string[] = []
  for (const g of groups) {
    names.push(g.category)
    if (g.children?.length) {
      names.push(...getCategoryNames(g.children))
    }
  }
  return names
}

/**
 * Recursively count total pages in a node (including children)
 */
export function countPages(node: CategoryNode): number {
  let count = node.pages.length
  if (node.children) {
    for (const child of node.children) {
      count += countPages(child)
    }
  }
  return count
}

/**
 * Get page count per category (flattened, using full path keys like "SDK/iOS")
 */
export function getPageCountByCategory(groups: CategoryNode[], parentPath = ''): Map<string, number> {
  const map = new Map<string, number>()
  for (const g of groups) {
    const fullPath = parentPath ? `${parentPath}/${g.category}` : g.category
    map.set(fullPath, countPages(g))
    if (g.children?.length) {
      const childMap = getPageCountByCategory(g.children, fullPath)
      for (const [key, val] of childMap) {
        map.set(key, val)
      }
    }
  }
  return map
}

/**
 * Find which category a document belongs to, by matching source_path (recursive)
 * Returns the full path like "SDK/iOS"
 */
export function findCategoryForPath(
  groups: CategoryNode[],
  sourcePath: string,
  parentPath = ''
): string | null {
  for (const g of groups) {
    const fullPath = parentPath ? `${parentPath}/${g.category}` : g.category
    // Check pages at this level
    if (g.pages.some(p => p.path === sourcePath)) {
      return fullPath
    }
    // Check children recursively
    if (g.children?.length) {
      const found = findCategoryForPath(g.children, sourcePath, fullPath)
      if (found) return found
    }
  }
  return null
}

/**
 * Get all pages for a specific category (by full path, recursive)
 */
export function getPagesForCategory(
  groups: CategoryNode[],
  category: string,
  parentPath = ''
): SitemapPage[] {
  for (const g of groups) {
    const fullPath = parentPath ? `${parentPath}/${g.category}` : g.category
    if (fullPath === category) {
      return collectAllPages(g)
    }
    if (g.children?.length) {
      const found = getPagesForCategory(g.children, category, fullPath)
      if (found.length > 0) return found
    }
  }
  return []
}

/**
 * Collect all pages from a node and its children
 */
export function collectAllPages(node: CategoryNode): SitemapPage[] {
  const pages = [...node.pages]
  if (node.children) {
    for (const child of node.children) {
      pages.push(...collectAllPages(child))
    }
  }
  return pages
}

/**
 * Get total page count across all categories (recursive)
 */
export function getTotalPageCount(groups: CategoryNode[]): number {
  let total = 0
  for (const g of groups) {
    total += countPages(g)
  }
  return total
}

/**
 * Flatten nested categories into a flat list with full path keys
 */
export function flattenCategories(groups: CategoryNode[], parentPath = ''): Array<{ path: string; node: CategoryNode }> {
  const result: Array<{ path: string; node: CategoryNode }> = []
  for (const g of groups) {
    const fullPath = parentPath ? `${parentPath}/${g.category}` : g.category
    result.push({ path: fullPath, node: g })
    if (g.children?.length) {
      result.push(...flattenCategories(g.children, fullPath))
    }
  }
  return result
}
