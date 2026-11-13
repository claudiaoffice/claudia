// The keys that start the show and that belong to its notes and times (E10.2, D295).
//
// F5 and Shift+F5 are the habit of every presentation program on Windows and Linux. On a Mac they are not ours: F5 is a
// system key there (the spike's Safari result, `spikes/e10-2-presenter-window/results/`), and a browser gets it only
// with Fn held, and not every combination at all. So each action has a second chord on a letter, written by the
// physical key (`code`): Option+P types "π" on a Mac, so its `key` is of no use. The menus show the chord that works
// on the keyboard in front of the person.
import type { KeyChord, ShortcutDef } from './shortcuts'

export type PresentAction = 'start' | 'here' | 'notes' | 'time'

const FUNCTION_KEY: Partial<Record<PresentAction, KeyChord>> = {
  start: { key: 'F5' },
  here: { key: 'F5', shift: true },
}
const LETTER_KEY: Record<PresentAction, KeyChord> = {
  start: { key: 'p', code: 'KeyP', ctrl: true, alt: true },
  here: { key: 'p', code: 'KeyP', ctrl: true, alt: true, shift: true },
  notes: { key: 'n', code: 'KeyN', ctrl: true, alt: true },
  time: { key: 'd', code: 'KeyD', ctrl: true, alt: true },
}

/** Whether this is a Mac, where F5 is not ours. */
export function onMac(nav: { platform?: string } | undefined = typeof navigator === 'undefined' ? undefined : navigator): boolean {
  return /^Mac/i.test(nav?.platform ?? '')
}

/** The chord a menu names for an action: the letter one on a Mac, the function key where there is one elsewhere. */
export function presentChord(action: PresentAction, mac: boolean): KeyChord {
  return (!mac && FUNCTION_KEY[action]) || LETTER_KEY[action]
}

/** How a chord is written in a menu: `F5`, `Shift+F5`, `Ctrl+Alt+P`, and on a Mac `Ctrl+Option+P`: the combination
 * the spike's Safari report showed arriving (Ctrl+Alt+N). Cmd works for the page too (`matches` takes either), but
 * only Ctrl was seen to reach it, so that is the one a menu names. */
export function presentHint(action: PresentAction, mac: boolean): string {
  const chord = presentChord(action, mac)
  const parts = [chord.ctrl && 'Ctrl', chord.alt && (mac ? 'Option' : 'Alt'), chord.shift && 'Shift']
  return [...parts.filter(Boolean), chord.key.length === 1 ? chord.key.toUpperCase() : chord.key].join('+')
}

/** Every chord that does something, for the window's key handler and Config ▸ Shortcuts. Both of an action's chords
 * work on every system: only the one a menu names differs. */
export function presentShortcuts(
  t: (msgid: string) => string,
  run: Record<PresentAction, () => void>,
  enabled: Partial<Record<PresentAction, () => boolean>> = {},
): ShortcutDef[] {
  const label: Record<PresentAction, string> = {
    start: t('Present from the first slide'),
    here: t('Present from this slide'),
    notes: t('Show or hide the speaker notes'),
    time: t('Plan the time of this slide'),
  }
  const id: Record<PresentAction, string> = {
    start: 'view.present-start',
    here: 'view.present-here',
    notes: 'view.speaker-notes',
    time: 'edit.slide-time',
  }
  const out: ShortcutDef[] = []
  for (const action of Object.keys(LETTER_KEY) as PresentAction[]) {
    for (const chord of [FUNCTION_KEY[action], LETTER_KEY[action]]) {
      if (chord) out.push({ id: id[action], label: label[action], chord, run: run[action], enabled: enabled[action] })
    }
  }
  return out
}
