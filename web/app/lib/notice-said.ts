// What a screen reader is told of a notice (UX-88). A live region that appears with its text already in it may not be
// read (BITV 4.1.3), so the region is always on the page and only its text changes: emptied when a notice comes, and
// filled a moment later, so that a second notice with the same text is a change as well and is read again.
import { onScopeDispose, ref, watch, type Ref } from 'vue'
import type { Notice } from './base-session'

/** How long the region stays empty before it says the notice: long enough for a screen reader to see two changes. */
const PAUSE_MS = 100

/** The text for an always-present `role=status` region: the notice's text, or nothing while there is none. */
export function useNoticeSaid(notice: () => Notice | null): Readonly<Ref<string>> {
  const said = ref('')
  let timer: ReturnType<typeof setTimeout> | undefined
  watch(
    () => notice()?.id,
    () => {
      clearTimeout(timer)
      said.value = ''
      const now = notice()
      if (now) timer = setTimeout(() => (said.value = now.text), PAUSE_MS)
    },
    { immediate: true }, // a notice already there when the page comes is said too
  )
  onScopeDispose(() => clearTimeout(timer))
  return said
}
