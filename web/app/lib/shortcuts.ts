// The keyboard shortcuts a workspace listens for on the window, in one place (D122): GNOMEish defaults for now (Ctrl is
// GTK's <Primary>, Redo is Ctrl+Shift+Z only — today's extra Ctrl+Y binding is dropped). A later pass can swap this table
// for a per-OS one without touching the three workspaces that use it.
//
// `sharedShortcuts`, `chordLabel`, `matches` and `dispatch` stay framework-free (no Vue, no DOM event classes) so they
// can be unit-tested in Node: `matches` and `dispatch` take a plain object shaped like the KeyboardEvent fields they
// read, not a real one. `installWindowShortcuts` is the one function here that needs Vue and the real `window`.

import { onBeforeUnmount, onMounted } from 'vue'

export interface KeyChord {
  /** What the chord is called, and — without `code` — the character the key types. */
  key: string
  /** The physical key (`KeyboardEvent.code`, "Digit8"): for a chord that is defined by where the key is, because the
   * character it types depends on the keyboard layout (Shift+8 is `*` on a US and `(` on a German keyboard). */
  code?: string
  ctrl?: boolean
  shift?: boolean
  alt?: boolean
}

export interface ShortcutDef {
  /** Matches the shell-contract action id where one exists (manifest.py), so Config ▸ Shortcuts can show one table. */
  id: string
  label: string
  chord: KeyChord
  run: () => void
  /** Skipped (and left to whatever the focused field does) while this is true. Defaults to always enabled. */
  enabled?: () => boolean
}

export interface KeyLike {
  key: string
  code?: string
  ctrlKey: boolean
  metaKey: boolean
  shiftKey: boolean
  altKey: boolean
}

/** The GNOMEish defaults every workspace starts from: Undo, Redo, Save. Each app appends its own (Shift+F10, …). */
export function sharedShortcuts(actions: { undo: () => void; redo: () => void; save: () => void }): ShortcutDef[] {
  return [
    { id: 'edit.undo', label: 'Undo', chord: { key: 'z', ctrl: true }, run: actions.undo },
    { id: 'edit.redo', label: 'Redo', chord: { key: 'z', ctrl: true, shift: true }, run: actions.redo },
    { id: 'file.save', label: 'Save', chord: { key: 's', ctrl: true }, run: actions.save },
  ]
}

/** `Ctrl+Shift+Z` for the Config ▸ Shortcuts list and the menu's `hint`. */
export function chordLabel(chord: KeyChord): string {
  const parts: string[] = []
  if (chord.ctrl) parts.push('Ctrl')
  if (chord.shift) parts.push('Shift')
  if (chord.alt) parts.push('Alt')
  parts.push(chord.key.length === 1 ? chord.key.toUpperCase() : chord.key)
  return parts.join('+')
}

export function matches(chord: KeyChord, event: KeyLike): boolean {
  const ctrl = event.ctrlKey || event.metaKey // metaKey: a Mac keyboard reaching a GNOMEish shell through the browser
  const same = chord.code ? event.code === chord.code : event.key.toLowerCase() === chord.key.toLowerCase()
  return same && ctrl === !!chord.ctrl && event.shiftKey === !!chord.shift && event.altKey === !!chord.alt
}

/** The field the event started in: shortcuts do not fire while someone is typing in it. */
export function isTypingTarget(target: { tagName?: string } | null): boolean {
  const tag = target?.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA'
}

/** Runs the first matching, enabled shortcut. Returns it (so the caller knows to `preventDefault()`), or `null`. */
export function dispatch(defs: ShortcutDef[], event: KeyLike): ShortcutDef | null {
  const found = defs.find((d) => matches(d.chord, event) && (d.enabled ? d.enabled() : true))
  if (found) found.run()
  return found ?? null
}

/**
 * Wires `defs()` to the window's `keydown`, replacing the three near-identical `onWindowKey` handlers that
 * `TextWorkspace.vue`, `Workspace.vue` and `DocumentFrame.vue` each had of their own (D122). Call it once from a
 * workspace's `<script setup>`; it attaches on mount and detaches on unmount.
 */
export function installWindowShortcuts(defs: () => ShortcutDef[]): void {
  function onKeydown(event: KeyboardEvent) {
    if (isTypingTarget(event.target as HTMLElement | null)) return
    if (dispatch(defs(), event)) event.preventDefault()
  }
  onMounted(() => window.addEventListener('keydown', onKeydown))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
}
