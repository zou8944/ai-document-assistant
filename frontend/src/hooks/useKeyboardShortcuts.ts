/**
 * Global keyboard shortcut system.
 *
 * Registers a single `keydown` listener on the document and dispatches
 * actions based on the pressed key combo.  Shortcuts that involve text
 * input are intentionally skipped when the event originates from an
 * `<input>`, `<textarea>`, or `[contenteditable]` element so they don't
 * interfere with normal typing.
 *
 * Platform-aware: uses ⌘ on macOS and Ctrl on Windows/Linux.
 */

import { useEffect, useCallback } from 'react'

export type ShortcutMap = Record<string, (e: KeyboardEvent) => void>

const isMac =
  typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.userAgent)

const MOD = isMac ? 'meta' : 'ctrl'

/**
 * Build a normalised combo string from a KeyboardEvent.
 * Format: `{mod}+{shift}+{key}` (shift and mod are optional prefixes).
 * Examples: `"n"`, `"meta+n"`, `"meta+shift+k"`.
 */
function comboFromEvent(e: KeyboardEvent): string {
  const parts: string[] = []
  if (e.metaKey || e.ctrlKey) parts.push(MOD)
  if (e.shiftKey) parts.push('shift')
  if (e.altKey) parts.push('alt')
  // Use e.key lowercased; special keys keep their name (escape, enter, …)
  parts.push(e.key.toLowerCase())
  return parts.join('+')
}

/**
 * Returns `true` when the event target is an editable element whose
 * keyboard behaviour should take precedence over global shortcuts.
 */
function isEditing(e: KeyboardEvent): boolean {
  const el = e.target as HTMLElement | null
  if (!el) return false
  const tag = el.tagName
  return (
    tag === 'INPUT' ||
    tag === 'TEXTAREA' ||
    el.isContentEditable
  )
}

/**
 * Hook that registers global keyboard shortcuts.
 *
 * @param shortcuts – an object mapping combo strings to handlers.
 *   Combo format: `"mod+n"`, `"mod+shift+k"`, `"escape"`, `"mod+/"`, etc.
 *   Use `"mod"` as a platform-agnostic stand-in for ⌘ / Ctrl.
 *
 * @param options.skipWhileEditing – when `true` (default), shortcuts that
 *   include the modifier key are still fired even inside inputs, but
 *   bare-key shortcuts are suppressed.  Set to `false` to never skip.
 */
export function useKeyboardShortcuts(
  shortcuts: ShortcutMap,
  options: { skipWhileEditing?: boolean } = {}
) {
  const { skipWhileEditing = true } = options

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      const combo = comboFromEvent(e)

      // Normalise user-provided "mod" to the platform key
      const normalise = (c: string) => c.replace(/\bmod\b/g, MOD)
      const handler = shortcuts[normalise(combo)]
      if (!handler) return

      // Decide whether to suppress while editing.
      // Rule: if the combo includes the modifier key (⌘/Ctrl), always fire.
      // Bare keys (like escape, or just "k") are suppressed in inputs.
      if (skipWhileEditing && isEditing(e)) {
        const hasModifier = e.metaKey || e.ctrlKey
        if (!hasModifier) return
      }

      handler(e)
    },
    [shortcuts, skipWhileEditing]
  )

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])
}

/** Human-readable key label for display. */
export function displayKey(combo: string): string {
  const isMacPlatform =
    typeof navigator !== 'undefined' && /Mac|iPod|iPhone|iPad/.test(navigator.userAgent)

  return combo
    .replace(/\bmod\b/g, isMacPlatform ? '⌘' : 'Ctrl')
    .replace(/\bshift\b/g, isMacPlatform ? '⇧' : 'Shift')
    .replace(/\balt\b/g, isMacPlatform ? '⌥' : 'Alt')
    .replace(/\bescape\b/, 'Esc')
    .replace(/\benter\b/, '↵')
    .replace(/\barrowup\b/, '↑')
    .replace(/\barrowdown\b/, '↓')
    .replace(/\barrowleft\b/, '←')
    .replace(/\barrowright\b/, '→')
    .replace(/\b\//g, '/')
    .replace(/\b,\b/g, ',')
    .split('+')
    .join(isMacPlatform ? '' : '+')
}
