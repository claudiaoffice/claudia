// How the text flows round a floating object of a text (D1061, D1064): four modes and a gap, kept in the object's
// anchor. Pure helpers, so that the menu, the key, the object layer and the tests say the same things. The layout
// engine does the wrapping (print and the page view); the server keeps the choice (`set_wrap`).
import type { Wrap } from '@claudia/layout'
import { translate as t } from './i18n'
import type { ParagraphAnchor } from './objects'

export type { Wrap }
/** The modes, in the order the one key cycles through them: over, around, above and below, behind, and over again. */
export const WRAPS: readonly Wrap[] = ['over', 'around', 'above-below', 'behind']
/** How far the words keep from an object that has no gap of its own, in CSS pixels; the server's own number. */
export const DEFAULT_WRAP_GAP = 8
export const MAX_WRAP_GAP = 200
/** What a new picture, shape or text box gets (the owner's choice, 2026-11-17): the words stop above it and go on below. */
export const NEW_OBJECT_WRAP: Wrap = 'above-below'

/** The wrap and the gap an anchor says; an anchor that says nothing floats over the text. */
export function wrapOf(anchor: Pick<ParagraphAnchor, 'wrap' | 'gap'>): { wrap: Wrap; gap: number } {
  return { wrap: anchor.wrap ?? 'over', gap: anchor.gap ?? DEFAULT_WRAP_GAP }
}

export function nextWrap(wrap: Wrap): Wrap {
  return WRAPS[(WRAPS.indexOf(wrap) + 1) % WRAPS.length]!
}

export function wrapLabel(wrap: Wrap): string {
  switch (wrap) {
    case 'over':
      return t('Over the text')
    case 'around':
      return t('Around the object')
    case 'above-below':
      return t('Above and below the object')
    case 'behind':
      return t('Behind the text')
  }
}

/** What is said aloud (a live region) and shown when the key has moved an object to `wrap`. */
export function wrapAnnouncement(wrap: Wrap): string {
  return t('Text wrap: {mode}', { mode: wrapLabel(wrap) })
}

/** The words of `set_wrap` and of the `wrap` and `gap` a new object may carry: the gap only when one was asked for. */
export function wrapParams(wrap: Wrap, gap?: number): { wrap: Wrap; gap?: number } {
  return gap === undefined ? { wrap } : { wrap, gap: Math.max(0, Math.min(MAX_WRAP_GAP, Math.round(gap))) }
}

/** Can the pointer take hold of an object? One behind the text lies under the words, so a press goes to the words
 * unless Ctrl is held (D1063); every other object is taken hold of as always. */
export function grabbable(wrap: Wrap, ctrl: boolean): boolean {
  return wrap !== 'behind' || ctrl
}
