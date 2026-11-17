// The pages of a text in Page view (E9.31, steps F and I): where each paragraph starts, as the printed pages have it,
// for the page numbers of a table of contents and of page references. The same layout as the print preview, so Page view, print and PDF agree; it runs
// only in Page view, only while the text has a table that shows pages, and once the typing has paused.
import { onScopeDispose, shallowRef, watch, type ShallowRef } from 'vue'
import type { TextSession } from '../text-session'
import { printAssets } from './assets'
import { textSource } from './source'

/** How long the text has to rest before it is laid out again, in ms. */
export const PAGES_AFTER_MS = 1200

/** The page (from 1) each paragraph starts on, by id, while `on()`; `null` before the first layout or when off. */
export function usePageNumbers(session: TextSession, on: () => boolean, after = PAGES_AFTER_MS): ShallowRef<ReadonlyMap<string, number> | null> {
  const pages = shallowRef<ReadonlyMap<string, number> | null>(null)
  const state = session.state
  // a table that shows pages, or a reference to a page (step I)
  const wanted = () => on() && state.blocks.some((b) => b.generated?.places || b.shown?.some((s) => s.state === 'page'))
  let timer: ReturnType<typeof setTimeout> | null = null
  let run = 0
  async function layOut() {
    const mine = ++run
    try {
      const laid = await textSource(session).layOut(await printAssets())
      if (mine === run && wanted()) pages.value = laid.pageOf ?? null
    } catch {
      if (mine === run) pages.value = null // no fonts (an older server): the table shows no pages, as in flow
    }
  }
  watch(
    () => [wanted(), state.blocks, state.styles, state.page, state.language],
    () => {
      if (timer) clearTimeout(timer)
      if (!wanted()) {
        run++
        pages.value = null
        return
      }
      timer = setTimeout(() => void layOut(), after)
    },
    { deep: true, immediate: true },
  )
  onScopeDispose(() => {
    if (timer) clearTimeout(timer)
    run++
  })
  return pages
}
