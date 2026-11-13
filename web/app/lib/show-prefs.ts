// Whether the speaker notes are shown under the slide (View ▸ Speaker notes, D293): a per-person preference like the
// grid and dark mode (`lib/grid.ts`), never part of the document. On by default: a slide's notes are what a talk is
// prepared with, and a field nobody sees is a field nobody fills in.
import { ref } from 'vue' // only the Vue wiring at the end uses this

const KEY = 'claudia.notes'

export function readStoredNotes(storage: Pick<Storage, 'getItem'> = safeStorage()): boolean {
  try {
    const value = storage.getItem(KEY)
    return value === null ? true : value === 'on'
  } catch {
    return true
  }
}

export function storeNotes(shown: boolean, storage: Pick<Storage, 'setItem'> = safeStorage()): void {
  try {
    storage.setItem(KEY, shown ? 'on' : 'off')
  } catch {
    /* private window: the choice still applies for this visit */
  }
}

function safeStorage(): Pick<Storage, 'getItem' | 'setItem'> {
  try {
    return localStorage
  } catch {
    const memory = new Map<string, string>()
    return { getItem: (k) => memory.get(k) ?? null, setItem: (k, v) => void memory.set(k, v) }
  }
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
