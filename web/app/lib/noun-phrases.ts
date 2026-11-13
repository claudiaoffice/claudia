// Sentences about "the thing being styled" (a paragraph, a cell, a text box…), one complete sentence per thing.
//
// A noun slotted into a sentence cannot be translated: "This {noun} only" has no German that works for "paragraph"
// (der Absatz), "cell" (die Zelle) and "object" (das Objekt) alike, because the article, the case and the adjective
// ending all follow the noun. So the closed set of things Claudia styles gets its own sentence each, written out
// as plain `t('…')` calls so `scripts/extract_i18n.py` finds every one; a noun this file has never heard of falls
// back to the generic English pattern rather than showing nothing. Generated once from the noun list; add a noun
// by adding it to every switch.
import { translate as t } from './i18n'

/** The thing's own name, lower case, as a sentence would use it on its own. */
export function nounName(noun: string): string {
  switch (noun) {
    case 'paragraph':
      return t('paragraph')
    case 'cell':
      return t('cell')
    case 'text box':
      return t('text box')
    case 'shape':
      return t('shape')
    case 'picture':
      return t('picture')
    case 'chart':
      return t('chart')
    case 'object':
      return t('object')
  }
  return noun
}

/** The "only" choice of the style editor when one thing is selected. */
export function thisOnly(noun: string): string {
  switch (noun) {
    case 'paragraph':
      return t('This paragraph only')
    case 'cell':
      return t('This cell only')
    case 'text box':
      return t('This text box only')
    case 'shape':
      return t('This shape only')
    case 'picture':
      return t('This picture only')
    case 'chart':
      return t('This chart only')
    case 'object':
      return t('This object only')
  }
  return t('This object only')
}

/** Why the "only this" choice is disabled: nothing of that kind is under the cursor. */
export function goToThis(noun: string): string {
  switch (noun) {
    case 'paragraph':
      return t('Go to the paragraph where your cursor is to change this paragraph only')
    case 'cell':
      return t('Go to the cell where your cursor is to change this cell only')
    case 'text box':
      return t('Go to the text box where your cursor is to change this text box only')
    case 'shape':
      return t('Go to the shape where your cursor is to change this shape only')
    case 'picture':
      return t('Go to the picture where your cursor is to change this picture only')
    case 'chart':
      return t('Go to the chart where your cursor is to change this chart only')
    case 'object':
      return t('Go to the object where your cursor is to change this object only')
  }
  return t('Go to the object where your cursor is to change this object only')
}

/** The style picker's tooltip. */
export function markByPurpose(noun: string, caption: string): string {
  switch (noun) {
    case 'paragraph':
      return t('{caption}: mark the paragraph by what it is for', { caption })
    case 'cell':
      return t('{caption}: mark the cell by what it is for', { caption })
    case 'text box':
      return t('{caption}: mark the text box by what it is for', { caption })
    case 'shape':
      return t('{caption}: mark the shape by what it is for', { caption })
    case 'picture':
      return t('{caption}: mark the picture by what it is for', { caption })
    case 'chart':
      return t('{caption}: mark the chart by what it is for', { caption })
    case 'object':
      return t('{caption}: mark the object by what it is for', { caption })
  }
  return t('{caption}: mark the object by what it is for', { caption })
}

/** The style menu's "clear" button (only cells have one today). */
export function clearStyle(): string {
  return t('Clear cell style')
}

/** The Format menu's heading over the style list. */
export function forThe(): string {
  return t('For the cell')
}

/** How many things use a style, as the All styles dialog counts them: "1 paragraph", "3 cells". */
export function usesCount(noun: string, n: number): string {
  switch (noun) {
    case 'paragraph':
      return n === 1 ? t('1 paragraph') : t('{count} paragraphs', { count: n })
    case 'cell':
      return n === 1 ? t('1 cell') : t('{count} cells', { count: n })
    case 'object':
      return n === 1 ? t('1 object') : t('{count} objects', { count: n })
  }
  return n === 1 ? t('1 object') : t('{count} objects', { count: n })
}
