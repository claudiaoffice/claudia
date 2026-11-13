/**
 * How one paragraph's text looks, in resolved form: one face, one size, one colour (claudia keeps one style per
 * paragraph, D300ff). Lengths in mpt. {@link paragraphStyleFromCss} in `css.ts` makes one from a style's CSS.
 *
 * @module
 */
import type { FaceRef } from '../fonts/fontset'

/** A colour as 0…255 red, green, blue and alpha. */
export interface Rgba {
  r: number
  g: number
  b: number
  a: number
}

export type TextAlign = 'left' | 'right' | 'center' | 'justify'

export interface ParagraphStyle {
  face: FaceRef
  /** font size, mpt */
  size: number
  /** height of one line box, mpt (CSS `line-height` resolved) */
  lineHeight: number
  align: TextAlign
  indentLeft: number
  indentRight: number
  /** extra indent of the first line (CSS `text-indent`), may be negative */
  firstLine: number
  spaceBefore: number
  spaceAfter: number
  color: Rgba
  /** extra space after every glyph cluster, mpt (CSS `letter-spacing`) */
  letterSpacing: number
  /** extra width of every space, mpt (CSS `word-spacing`) */
  wordSpacing: number
  underline: boolean
  strike: boolean
  /** `nowrap`: the paragraph is one line (it may overflow); `pre-wrap`: spaces are kept as typed */
  whiteSpace: 'normal' | 'nowrap' | 'pre-wrap'
  /** keep the paragraph's last line on the page of the next paragraph's first line (headings) */
  keepWithNext: boolean
  /** the least number of lines left at the foot of a page / carried to the next one */
  orphans: number
  widows: number
  /** BCP 47 language of the text, given to the shaper */
  language?: string
  /**
   * CSS `hyphens`: `none` never breaks a word with a hyphen; `manual` (the default) breaks it only at a soft hyphen
   * (U+00AD) typed into it; `auto` also where the language's patterns allow (D912)
   */
  hyphens?: 'none' | 'manual' | 'auto'
}

export const BLACK: Rgba = { r: 0, g: 0, b: 0, a: 255 }

/** A style with every optional part at its default, for tests and simple callers. */
export function paragraphStyle(face: FaceRef, size: number, rest: Partial<ParagraphStyle> = {}): ParagraphStyle {
  return {
    face,
    size,
    lineHeight: Math.round(size * 1.2),
    align: 'left',
    indentLeft: 0,
    indentRight: 0,
    firstLine: 0,
    spaceBefore: 0,
    spaceAfter: 0,
    color: BLACK,
    letterSpacing: 0,
    wordSpacing: 0,
    underline: false,
    strike: false,
    whiteSpace: 'normal',
    keepWithNext: false,
    orphans: 2,
    widows: 2,
    ...rest,
  }
}
