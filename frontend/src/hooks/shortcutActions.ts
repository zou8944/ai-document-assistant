/**
 * Lightweight action registry for keyboard shortcuts.
 *
 * Components register callbacks on mount; the global keyboard shortcut
 * handler looks them up by name and invokes them.  This avoids threading
 * refs through the Zustand store or prop-drilling.
 *
 * Usage:
 *   // In a component:
 *   useEffect(() => {
 *     registerShortcutAction('newChat', handleAddChat)
 *     return () => unregisterShortcutAction('newChat')
 *   }, [handleAddChat])
 *
 *   // In the keyboard shortcut handler:
 *   invokeShortcutAction('newChat')
 */

const actions = new Map<string, () => void>()

export function registerShortcutAction(name: string, fn: () => void) {
  actions.set(name, fn)
}

export function unregisterShortcutAction(name: string) {
  actions.delete(name)
}

export function invokeShortcutAction(name: string): boolean {
  const fn = actions.get(name)
  if (fn) {
    fn()
    return true
  }
  return false
}
