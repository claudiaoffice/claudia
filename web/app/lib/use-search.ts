// The panel's side of Search & replace in a workspace (E5.15, D281), the same in text and slides: whether it is open,
// whether it opened with Replace showing, the panel to talk to and what the document should draw for what it found.
// The sheet has its own wiring (it draws on a grid); this is for the apps whose documents draw marks in text or on slides.
import { nextTick, ref } from 'vue'
import type { PreviewAnswer, SearchMatch } from './search'

export interface SearchView {
  matches: SearchMatch[]
  current: number | null
  preview: PreviewAnswer | null
}

interface PanelHandle {
  focus: () => void
  openReplace: () => void
  seed: (text: string) => void
}

const NOTHING: SearchView = { matches: [], current: null, preview: null }

/** `canReplace` says whether this person may write; `afterClose` gives the focus back to the document. */
export function useSearch(canReplace: () => boolean, afterClose: () => void) {
  const open = ref(false)
  const replace = ref(false)
  const panel = ref<PanelHandle | null>(null)
  const view = ref<SearchView>(NOTHING)

  /** Open the panel (Edit ▸ Search & Replace…, Ctrl+F; Ctrl+H with `withReplace`), starting from `seed`, the text that
   *  was selected in the document, if there is one. */
  function openSearch(withReplace = false, seed = '') {
    open.value = true
    replace.value = withReplace && canReplace()
    void nextTick(() => {
      panel.value?.seed(seed)
      if (replace.value) panel.value?.openReplace()
      else panel.value?.focus()
    })
  }
  function closeSearch() {
    open.value = false
    replace.value = false
    view.value = NOTHING
    afterClose()
  }
  return { open, replace, panel, view, openSearch, closeSearch }
}
