// What a window that prints has (D906, D918): File ▸ Print… and Ctrl+P open the preview in place of the document,
// and once it is open print; Esc or the arrow go back. And a new document starts in its maker's language (D915, D917).
// The same in composes and creates, so printing reads and behaves the same in both.
import { ref, type Ref } from 'vue'
import { PRINT_CHORD } from '../document-menus'
import type { ShortcutDef } from '../shortcuts'

import { translate as t } from '../i18n'
export interface Printing {
  /** whether the preview is shown in place of the document */
  printing: Ref<boolean>
  /** the preview, once shown: `ref="preview"` on it */
  preview: Ref<{ print(): Promise<void> } | null>
  /** File ▸ Print…: open the preview, or print from it when it is open */
  open(): void
  /** back to the document; `then` puts the focus where it was */
  close(): void
  /** Ctrl+P, for the window's extra shortcuts */
  shortcut: ShortcutDef
}

export function usePrint(then: () => void = () => {}): Printing {
  const printing = ref(false)
  const preview = ref<{ print(): Promise<void> } | null>(null)
  function open() {
    if (printing.value) void preview.value?.print()
    else printing.value = true
  }
  function close() {
    printing.value = false
    setTimeout(then)
  }
  return { printing, preview, open, close, shortcut: { id: 'file.print', get label() { return t('Print…') }, chord: PRINT_CHORD, run: open } }
}
