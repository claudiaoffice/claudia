// Whether the speaker notes are shown under the slide (View ▸ Speaker notes, D342): a per-person preference like the
// grid and dark mode (`lib/grid.ts`), never part of the document. On by default: a slide's notes are what a talk is
// prepared with, and a field nobody sees is a field nobody fills in.
import { ref } from 'vue' // only the Vue wiring at the end uses this
import { safeStorage } from './storage'

const KEY = 'claudia.notes'

export function readStoredNotes(storage: Pick<Storage, 'getItem'> = safeStorage()): boolean {
  const value = storage.getItem(KEY)
  return value === null ? true : value === 'on'
}

export function storeNotes(shown: boolean, storage: Pick<Storage, 'setItem'> = safeStorage()): void {
  storage.setItem(KEY, shown ? 'on' : 'off')
}

/** The View menu's "Speaker notes" checkbox. */
export function useNotesShown() {
  const shown = ref<boolean>(readStoredNotes())
  function toggle() {
    shown.value = !shown.value
    storeNotes(shown.value)
  }
  return { shown, toggle }
}
