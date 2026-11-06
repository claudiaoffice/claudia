/**
 * Edit ▸ Copy / Cut / Paste / Paste as plain text, callable from a menu click rather than a native keyboard shortcut.
 *
 * The browser already gives Ctrl+C/X/V to whatever has focus for free — that's why `HelpDialog`'s old key table could
 * say "also from and to other programs" without any code behind it. A *menu item* is different: the thing with the
 * selection (a paragraph in composes, a cell in computes) is not the menu, so by the time an item's `action` runs,
 * `document.activeElement` must still be that element, not the menu button. That's `MenuBar.vue`'s job (it keeps
 * focus on the bar across a click), not this file's — this file only has to work once it's handed the right element.
 *
 * `execCommand` is deprecated but still the only cross-browser way to make Copy/Cut honour an arbitrary selection
 * (a run of table cells, say) the way the native shortcut does; the async Clipboard API has no "cut" and its
 * "copy" only takes an explicit string, which would mean re-deriving the selection ourselves. For *paste*, the async
 * Clipboard API is used instead — `execCommand('paste')` is blocked in every current browser — which is also what
 * makes "paste as plain text" possible at all: the clipboard's own formatting never enters the page.
 */

/** The parts of an editable surface this module needs — an `HTMLInputElement`/`HTMLTextAreaElement` satisfies it
 * as-is; a contenteditable element can be adapted to it (see `pasteAsPlainText`). Kept narrow and structural so the
 * text-splicing logic below is testable with a plain fake, no DOM required. */
export interface PlainTextField {
  value: string
  selectionStart: number | null
  selectionEnd: number | null
  setRangeText(text: string, start?: number, end?: number, mode?: 'select' | 'end'): void
}

/** True for the two native form controls that carry their own selection range and can splice text directly —
 * everything else (a contenteditable paragraph) needs `execCommand('insertText', …)` instead, below. */
export function isPlainTextField(el: unknown): el is PlainTextField {
  const tag = (el as { tagName?: string } | null)?.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA'
}

/** Replaces the current selection in an `<input>`/`<textarea>`-shaped field with `text`, leaving the caret after it.
 * Pure and synchronous — no clipboard, no DOM beyond what `field` itself exposes — so a fake satisfying
 * `PlainTextField` is enough to test it. */
export function spliceSelection(field: PlainTextField, text: string): void {
  const start = field.selectionStart ?? field.value.length
  const end = field.selectionEnd ?? field.value.length
  field.setRangeText(text, start, end, 'end')
}

/** Best-effort clipboard write for Copy/Cut: relies on the current DOM selection, so it only does anything useful
 * when something is actually selected in `document`. Returns false rather than throwing when the browser refuses
 * (an insecure context, a permissions policy) — callers already treat a menu action as fire-and-forget. */
export function copySelection(doc: Document = document): boolean {
  try {
    return doc.execCommand('copy')
  } catch {
    return false
  }
}

export function cutSelection(doc: Document = document): boolean {
  try {
    return doc.execCommand('cut')
  } catch {
    return false
  }
}

/** Reads the clipboard as plain text and inserts it at the current selection of `el`, with no formatting carried
 * over — the point of "Paste as plain text" as distinct from the native Ctrl+V. Returns false if the clipboard
 * couldn't be read (no permission, no secure context, nothing textual on it) or `el` isn't an editable surface this
 * module knows how to splice into; the caller shows no error for either case, the same as a native paste that found
 * an empty clipboard. */
export async function pasteAsPlainText(el: Element | null, doc: Document = document): Promise<boolean> {
  let text: string
  try {
    text = await navigator.clipboard.readText()
  } catch {
    return false
  }
  if (!text) return false

  if (isPlainTextField(el)) {
    spliceSelection(el, text)
    return true
  }
  if (el instanceof HTMLElement && el.isContentEditable) {
    try {
      return doc.execCommand('insertText', false, text)
    } catch {
      return false
    }
  }
  return false
}
