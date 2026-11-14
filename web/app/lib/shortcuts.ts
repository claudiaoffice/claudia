// The keyboard shortcuts a workspace listens for on the window, in one place (D122): GNOMEish defaults for now (Ctrl is
// GTK's <Primary>, Redo is Ctrl+Shift+Z only — today's extra Ctrl+Y binding is dropped). A later pass can swap this table
// for a per-OS one without touching the three workspaces that use it.
//
// `sharedShortcuts`, `chordLabel`, `matches` and `dispatch` stay framework-free (no Vue, no DOM event classes) so they
// can be unit-tested in Node: `matches` and `dispatch` take a plain object shaped like the KeyboardEvent fields they
// read, not a real one. `installWindowShortcuts` is the one function here that needs Vue and the real `window`.

import { onBeforeUnmount, onMounted } from 'vue'

import type { Menu, MenuItem } from '../components/MenuBar.vue'
import { translate as t } from './i18n'
import { KEYS } from './keys.generated'

export interface KeyChord {
  /** The character the key types (or its name: `F9`, `ArrowUp`), and what the chord is called. */
  key: string
  /** The physical key (`KeyboardEvent.code`, "Digit8"), looked at only when the key typed something other than a letter
   * or a digit: Shift+8 is `*` on a US and `(` on a German keyboard, Option+R is `®` on a Mac. Never first, because the
   * places differ between layouts (Z and Y swap on a German one). */
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
  /** Runs even while someone is typing in an `<input>` or `<textarea>`, where shortcuts are otherwise left to the
   * field: for a key the field has no use for, such as F6 leaving the formula bar. */
  whileTyping?: boolean
}

export interface KeyLike {
  key: string
  code?: string
  ctrlKey: boolean
  metaKey: boolean
  shiftKey: boolean
  altKey: boolean
}

/** The key of a menu action, from the one table of every client (`keys.generated.ts`, made from the shared menu manifest,
 * UX-35). Throws for an id the table does not have: a key written here by hand is how the clients drifted apart. */
export function chordOf(id: string): KeyChord {
  const found = KEYS[id]
  if (!found) throw new Error(`no key for ${id}: add it to the menu manifest and run scripts/generate_keys.py`)
  return found.chord
}

/** What a menu shows beside an entry: its key from the table, or nothing for an entry that has none. */
export function hintOf(id: string | undefined): string | undefined {
  const found = id === undefined ? undefined : KEYS[id]
  return found ? chordLabel(found.chord) : undefined
}

/** Undo, Redo, Save, the same in every app. Each app adds its own (Shift+F10, …); `menuShortcuts` adds the rest. */
export function sharedShortcuts(actions: { undo: () => void; redo: () => void; save: () => void }): ShortcutDef[] {
  return [
    { id: 'edit.undo', get label() { return t('Undo') }, chord: chordOf('edit.undo'), run: actions.undo },
    { id: 'edit.redo', get label() { return t('Redo') }, chord: chordOf('edit.redo'), run: actions.redo },
    { id: 'file.save', get label() { return t('Save') }, chord: chordOf('file.save'), run: actions.save },
  ]
}

/** Every other menu entry's key (UX-35): whatever entry has a key in the table, and is not one the document view or the
 * browser handles itself, runs as if it were clicked, when it is enabled. `taken` are the ids a hand-made shortcut
 * already has (with a rule of its own: only while typing, say), which keep it. */
export function menuShortcuts(menus: Menu[], taken: ReadonlySet<string>): ShortcutDef[] {
  const defs: ShortcutDef[] = []
  const add = (item: MenuItem) => {
    const key = item.id === undefined ? undefined : KEYS[item.id]
    if (!item.id || !key || key.owner === 'view' || !item.action || taken.has(item.id)) return
    const run = item.action
    defs.push({ id: item.id, label: item.label, chord: key.chord, run: () => run(), enabled: () => !item.disabled })
  }
  for (const menu of menus) {
    for (const item of menu.items) {
      if (item.separator) continue
      add(item)
      for (const sub of item.items ?? []) add(sub)
    }
  }
  return defs
}

/** F6 and Shift+F6, which move between the parts of the window (`regions.ts`): how a keyboard user gets out of the grid,
 * where Tab is taken for stepping between cells. */
export function regionShortcuts(actions: { next: () => void; previous: () => void }): ShortcutDef[] {
  return [
    { id: 'view.nextRegion', get label() { return t('Next Part of the Window') }, chord: { key: 'F6' }, run: actions.next, whileTyping: true },
    { id: 'view.previousRegion', get label() { return t('Previous Part of the Window') }, chord: { key: 'F6', shift: true }, run: actions.previous, whileTyping: true },
  ]
}

/** Find and Replace (E5.15, D281): Ctrl+F opens Search & replace, Ctrl+H opens it with Replace already showing. Ctrl+H
 * is only taken where a replacement can be made; for somebody who can only look the browser keeps it. The same
 * two in every app, so the table lives here. */
export function searchShortcuts(actions: { find: () => void; replace: () => void; canReplace: () => boolean }): ShortcutDef[] {
  return [
    { id: 'edit.search-replace', get label() { return t('Search & Replace') }, chord: chordOf('edit.search-replace'), run: actions.find },
    // Ctrl+H has no menu entry of its own (D281), so it is not in the table of menu keys
    { id: 'edit.replace', get label() { return t('Replace') }, chord: { key: 'h', ctrl: true }, run: actions.replace, enabled: actions.canReplace },
  ]
}

const KEY_NAMES: Readonly<Record<string, string>> = { ArrowUp: '↑', ArrowDown: '↓', ArrowLeft: '←', ArrowRight: '→', Delete: 'Del' }

/** `Ctrl+Shift+Z` for the Config ▸ Shortcuts list and the menu's `hint`. A symbol that is typed with Shift (`?`, `_`)
 * is shown as the symbol, without the Shift. */
export function chordLabel(chord: KeyChord): string {
  const parts: string[] = []
  const symbol = chord.key.length === 1 && !/[a-z0-9]/i.test(chord.key)
  if (chord.ctrl) parts.push(t('Ctrl'))
  if (chord.shift && !(symbol && '?_'.includes(chord.key))) parts.push(t('Shift'))
  if (chord.alt) parts.push(t('Alt'))
  parts.push(KEY_NAMES[chord.key] ?? (chord.key.length === 1 ? chord.key.toUpperCase() : chord.key))
  return parts.join('+')
}

export function matches(chord: KeyChord, event: KeyLike): boolean {
  const ctrl = event.ctrlKey || event.metaKey // metaKey: a Mac keyboard reaching a GNOMEish shell through the browser
  const typed = event.key.toLowerCase() === chord.key.toLowerCase()
  // The physical key only when the key typed no letter or digit: the layout or Option made it something else
  const placed = !typed && chord.code !== undefined && event.code === chord.code && !/^[a-z0-9]$/i.test(event.key)
  // A symbol (`?`, `_`) is the character, whatever it took to type it: Shift on one layout, none on another
  const shift = event.shiftKey === !!chord.shift || (typed && chord.key.length === 1 && !/[a-z0-9]/i.test(chord.key))
  return (typed || placed) && ctrl === !!chord.ctrl && shift && event.altKey === !!chord.alt
}

/** The field the event started in: shortcuts do not fire while someone is typing in it. */
export function isTypingTarget(target: { tagName?: string } | null): boolean {
  const tag = target?.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA'
}

/** Runs the first matching, enabled shortcut. Returns it (so the caller knows to `preventDefault()`), or `null`.
 * With `typing` (the event started in a text field) only a shortcut that says `whileTyping` is considered. */
export function dispatch(defs: ShortcutDef[], event: KeyLike, typing = false): ShortcutDef | null {
  const found = defs.find((d) => matches(d.chord, event) && (!typing || d.whileTyping) && (d.enabled ? d.enabled() : true))
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
    if (dispatch(defs(), event, isTypingTarget(event.target as HTMLElement | null))) event.preventDefault()
  }
  onMounted(() => window.addEventListener('keydown', onKeydown))
  onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
}
