// The keyboard shortcuts a workspace listens for on the window, in one place (D122): GNOMEish defaults for now (Ctrl is
// GTK's <Primary>, Redo is Ctrl+Shift+Z only — today's extra Ctrl+Y binding is dropped). A later pass can swap this table
// for a per-OS one without touching the three workspaces that use it.
//
// `sharedShortcuts`, `chordLabel`, `matches` and `dispatch` stay framework-free (no Vue, no DOM event classes) so they
// can be unit-tested in Node: `matches` and `dispatch` take a plain object shaped like the KeyboardEvent fields they
// read, not a real one. `installWindowShortcuts` is the one function here that needs Vue and the real `window`.

import { onBeforeUnmount, onMounted } from 'vue'

import { translate as t } from './i18n'
import { KEYS } from './menus.generated'

export interface KeyChord {
  /** The character the key types (or its name: `F9`, `ArrowUp`), and what the chord is called. */
  key: string
  /** The physical key (`KeyboardEvent.code`, "Digit8"), looked at only when the key typed something other than a letter
   * or a digit: Shift+8 is `*` on a US and `(` on a German keyboard, Option+R is `®` on a Mac. Never first, because the
   * places differ between layouts (Z and Y swap on a German one). */
  code?: string
  /** Ctrl, and on a Mac Cmd (GTK's `<Primary>`). */
  ctrl?: boolean
  /** The Control key itself, beside Cmd: only in macOS's own keys (D1616). */
  control?: boolean
  shift?: boolean
  alt?: boolean
}

export interface ShortcutDef {
  /** Matches the shell-contract action id where one exists (manifest.py), so Preferences ▸ Shortcuts can show one table. */
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

/** Whether this is a Mac, where macOS keeps some keys for itself (D1616) and the web uses macOS's own (D1648). */
export function onMac(nav: { platform?: string } | undefined = typeof navigator === 'undefined' ? undefined : navigator): boolean {
  return /^Mac/i.test(nav?.platform ?? '')
}
const MAC = onMac()

/** The key of a menu action, from the one table of every client (`menus.generated.ts`, made from the shared menu
 * definition, UX-35); on a Mac macOS's own where it has one. Throws for an id the table does not have: a key written
 * here by hand is how the clients drifted apart. */
export function chordOf(id: string, mac = MAC): KeyChord {
  const found = KEYS[id]
  if (!found) throw new Error(`no key for ${id}: add it to the menu definition and run scripts/generate_menus.py`)
  return (mac && found.mac) || found.chord
}

/** What a menu shows beside an entry: its key from the table, or nothing for an entry that has none. */
export function hintOf(id: string | undefined, mac = MAC): string | undefined {
  return id !== undefined && KEYS[id] ? chordLabel(chordOf(id, mac), mac) : undefined
}

/** Every action's key (UX-35, D1604): whatever action of the definition the page runs and has a key in the table
 * that is not one the document view or the browser handles itself. It runs as its menu entry would, judged when it is
 * pressed: one that does not fit now, hidden or greyed, says why instead (`menus/assemble.ts`). `taken` are the ids a
 * hand-made shortcut already has (with a rule of its own: only while typing, say), which keep it. */
export function actionShortcuts(
  actions: readonly { id: string; label: string }[],
  run: (id: string) => boolean,
  taken: ReadonlySet<string>,
): ShortcutDef[] {
  return actions.flatMap(({ id, label }) => {
    const key = KEYS[id]
    if (!key || key.owner !== 'page' || taken.has(id)) return []
    return [{ id, label, chord: chordOf(id), run: () => void run(id) }]
  })
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

const ARROWS: Readonly<Record<string, string>> = { ArrowUp: '↑', ArrowDown: '↓', ArrowLeft: '←', ArrowRight: '→' }

/** A key as its cap reads, in the language chosen where the cap has words on it (Entf, Eingabe). */
function keyName(key: string): string {
  if (key === 'Delete') return t('Del')
  if (key === 'Enter') return t('Enter')
  return ARROWS[key] ?? (key.length === 1 ? key.toUpperCase() : key)
}

/** `Ctrl+Shift+Z` for Preferences ▸ Shortcuts and the menus; on a Mac as the workbook writes macOS's keys:
 * `Cmd+Ctrl+Shift+Option+…`. A symbol that is typed with Shift (`?`, `_`) is shown as the symbol, without the Shift. */
export function chordLabel(chord: KeyChord, mac = MAC): string {
  const parts: string[] = []
  const symbol = chord.key.length === 1 && !/[a-z0-9]/i.test(chord.key)
  if (chord.ctrl) parts.push(mac ? t('Cmd') : t('Ctrl'))
  if (chord.control) parts.push(t('Ctrl'))
  if (chord.shift && !(symbol && '?_'.includes(chord.key))) parts.push(t('Shift'))
  if (chord.alt) parts.push(mac ? t('Option') : t('Alt'))
  parts.push(keyName(chord.key))
  return parts.join('+')
}

export function matches(chord: KeyChord, event: KeyLike): boolean {
  // Ctrl or Cmd for `ctrl` (a Mac keyboard reaching a GNOMEish shell through the browser); a chord of macOS's own
  // that names the Control key wants it, and Cmd only where it says so too
  const ctrl = chord.control ? event.ctrlKey && event.metaKey === !!chord.ctrl : (event.ctrlKey || event.metaKey) === !!chord.ctrl
  const typed = event.key.toLowerCase() === chord.key.toLowerCase()
  // The physical key only when the key typed no letter or digit: the layout or Option made it something else
  const placed = !typed && chord.code !== undefined && event.code === chord.code && !/^[a-z0-9]$/i.test(event.key)
  // A symbol (`?`, `_`) is the character, whatever it took to type it: Shift on one layout, none on another
  const shift = event.shiftKey === !!chord.shift || (typed && chord.key.length === 1 && !/[a-z0-9]/i.test(chord.key))
  return (typed || placed) && ctrl && shift && event.altKey === !!chord.alt
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
