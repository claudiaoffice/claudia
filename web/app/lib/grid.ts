// Whether the grid is drawn on a slide (E10.15): a per-person, client-local preference — like dark mode, not part
// of the document, never sent to the server and never undoable. On by default. This is purely about what the view
// draws: whether an object actually *snaps* to the grid is a different, real and persisted thing
// (`SlideObject.snap`, set with `set_snap`); an object keeps snapping even while this preference hides the lines,
// unless it has itself been released (object-menu.ts).
import { ref } from 'vue' // only the Vue wiring at the end uses these

const KEY = 'claudia.grid'

export function readStoredGrid(storage: Pick<Storage, 'getItem'> = safeStorage()): boolean {
  try {
    const value = storage.getItem(KEY)
    return value === null ? true : value === 'on'
  } catch {
    return true
  }
}

export function storeGrid(shown: boolean, storage: Pick<Storage, 'setItem'> = safeStorage()): void {
  try {
    storage.setItem(KEY, shown ? 'on' : 'off')
  } catch {
    /* private window: nothing to remember, the choice still applies for this visit */
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

// ------------------------------------------------------------------------------------------------------- Vue wiring

/** The View menu's "Show grid" checkbox. */
export function useGrid() {
  const shown = ref<boolean>(readStoredGrid())
  function toggle() {
    shown.value = !shown.value
    storeGrid(shown.value)
  }
  return { shown, toggle }
}
