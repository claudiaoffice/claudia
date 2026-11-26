// The second keys that start the show (E10.2, D344).
//
// F5 and Shift+F5 are the habit of every presentation program on Windows and Linux; they are the definition's keys of
// Tools ▸ Present ▸ From Beginning and From Slide. On a Mac they are not ours: F5 is a system key there (the spike's
// Safari result, `spikes/e10-2-presenter-window/results/`), so macOS has letter keys of its own, Ctrl+Option+P and
// Ctrl+Shift+Option+H, which the web on a Mac takes from the definition too (D1616, D1648). Elsewhere the same letter
// keys, Ctrl+Alt+P and Ctrl+Shift+Alt+H, work beside F5, so that a habit from a Mac still starts the show. They are
// written by the physical key (`code`): Option+P types "π" on a Mac.
import { onMac, type KeyChord, type ShortcutDef } from './shortcuts'

export type PresentAction = 'start' | 'here'

const LETTER_KEY: Record<PresentAction, KeyChord> = {
  start: { key: 'p', code: 'KeyP', ctrl: true, alt: true },
  here: { key: 'h', code: 'KeyH', ctrl: true, alt: true, shift: true },
}

/** The letter keys beside F5, outside a Mac (on a Mac they are the definition's own), for the window's key handler and
 * Preferences ▸ Shortcuts. Their ids are their own, so that F5, the entries' key, is listened for too. */
export function presentShortcuts(t: (msgid: string) => string, run: Record<PresentAction, () => void>, mac = onMac()): ShortcutDef[] {
  if (mac) return []
  const label: Record<PresentAction, string> = { start: t('From Beginning'), here: t('From Slide') }
  const id: Record<PresentAction, string> = { start: 'view.present-start.letter', here: 'view.present-here.letter' }
  return (Object.keys(LETTER_KEY) as PresentAction[]).map((action) => ({ id: id[action], label: label[action], chord: LETTER_KEY[action], run: run[action] }))
}
