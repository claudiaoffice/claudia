import { describe, expect, it } from 'vitest'
import {
  diffCss,
  familyName,
  fontSizeOf,
  formatCss,
  hasDecoration,
  isBold,
  isItalic,
  paragraphCss,
  previewCss,
  provenance,
  semanticTag,
  styleUses,
  toHex,
  toggleDecoration,
  withFontSize,
  type StyleView,
} from '~/lib/style-css'

const view = (id: string, based_on: string | null, css: Record<string, string>, extra: Partial<StyleView> = {}): StyleView => ({
  id,
  name: id,
  purpose: '',
  based_on,
  css,
  computed: css,
  to_name: false,
  ...extra,
})

const body = view('body', null, { 'font-size': '12pt', color: '#1F1A33', 'font-family': 'Inter, sans-serif' })
const h1 = view('heading-1', 'body', { 'font-size': '19pt', 'font-weight': '500' }, { computed: { ...body.css, 'font-size': '19pt', 'font-weight': '500' } })
const h1x = view('h1-x', 'heading-1', { color: 'red' }, { computed: { ...h1.computed, color: 'red' }, to_name: true })
const styles = [body, h1, h1x]

describe('formatCss', () => {
  it('writes one declaration per line in the order the server uses', () => {
    expect(formatCss({ color: '#000', 'font-size': '12pt', 'font-family': 'serif', 'border-left': '1px solid red' })).toBe(
      'font-family: serif;\nfont-size: 12pt;\ncolor: #000;\nborder-left: 1px solid red;',
    )
    expect(formatCss({})).toBe('')
  })
})

describe('diffCss', () => {
  it('says what to set and what to remove to get from one style to the other', () => {
    expect(diffCss({ color: 'red', 'font-size': '12pt' }, { color: 'blue', 'font-size': '12pt', 'font-style': 'italic' })).toEqual({
      set: { color: 'blue', 'font-style': 'italic' },
      unset: [],
    })
    expect(diffCss({ color: 'red', 'font-size': '12pt' }, { color: 'red' })).toEqual({ set: {}, unset: ['font-size'] })
  })
})

describe('provenance', () => {
  it('names the style each computed property comes from, own properties first-hand', () => {
    const rows = provenance(styles, 'h1-x')
    const byProp = Object.fromEntries(rows.map((r) => [r.property, r]))
    expect(byProp.color).toMatchObject({ value: 'red', from: 'h1-x', inherited: false })
    expect(byProp['font-size']).toMatchObject({ value: '19pt', from: 'heading-1', inherited: true })
    expect(byProp['font-family']).toMatchObject({ value: 'Inter, sans-serif', from: 'body', inherited: true })
  })
  it('lists the properties in the server order', () => {
    expect(provenance(styles, 'h1-x').map((r) => r.property)).toEqual(['font-family', 'font-size', 'font-weight', 'color'])
  })
  it('is empty for a style it does not know', () => {
    expect(provenance(styles, 'nope')).toEqual([])
  })
})

describe('font size', () => {
  it('reads and writes sizes with their unit', () => {
    expect(fontSizeOf({ 'font-size': '12pt' })).toEqual({ value: 12, unit: 'pt' })
    expect(fontSizeOf({ 'font-size': '14.5px' })).toEqual({ value: 14.5, unit: 'px' })
    expect(fontSizeOf({ 'font-size': '110%' })).toEqual({ value: 110, unit: '%' })
    expect(fontSizeOf({})).toBeNull()
    expect(withFontSize(12, 'pt')).toBe('12pt')
    expect(withFontSize(10.123, 'pt')).toBe('10.12pt')
    expect(withFontSize(0, 'pt')).toBe('1pt')
    expect(withFontSize(9999, 'pt')).toBe('400pt')
  })
})

describe('font properties', () => {
  it('knows bold and italic however they are written', () => {
    expect(isBold({ 'font-weight': 'bold' })).toBe(true)
    expect(isBold({ 'font-weight': '700' })).toBe(true)
    expect(isBold({ 'font-weight': '600' })).toBe(true)
    expect(isBold({ 'font-weight': '500' })).toBe(false)
    expect(isBold({})).toBe(false)
    expect(isItalic({ 'font-style': 'italic' })).toBe(true)
    expect(isItalic({ 'font-style': 'oblique' })).toBe(true)
    expect(isItalic({ 'font-style': 'normal' })).toBe(false)
  })
  it('toggles decorations without losing the others', () => {
    expect(hasDecoration({ 'text-decoration': 'underline line-through' }, 'underline')).toBe(true)
    expect(toggleDecoration({}, 'underline')).toBe('underline')
    expect(toggleDecoration({ 'text-decoration': 'underline' }, 'line-through')).toBe('underline line-through')
    expect(toggleDecoration({ 'text-decoration': 'underline line-through' }, 'underline')).toBe('line-through')
    expect(toggleDecoration({ 'text-decoration': 'underline' }, 'underline')).toBe('none')
  })
  it('takes the first font out of a family list', () => {
    expect(familyName({ 'font-family': "'Segoe UI', serif" })).toBe('Segoe UI')
    expect(familyName({ 'font-family': 'Inter, system-ui' })).toBe('Inter')
    expect(familyName({})).toBe('')
  })
})

describe('colours', () => {
  it('gives hex colours to the colour field and nothing for what it cannot show', () => {
    expect(toHex('#1F1A33')).toBe('#1f1a33')
    expect(toHex('#fa0')).toBe('#ffaa00')
    expect(toHex('rgb(31, 26, 51)')).toBe('#1f1a33')
    expect(toHex('rebeccapurple')).toBeNull()
    expect(toHex(undefined)).toBeNull()
  })
})

describe('what the page draws', () => {
  it('uses the computed CSS as it is', () => {
    expect(paragraphCss({ 'font-size': '12pt', color: 'red' })).toEqual({ 'font-size': '12pt', color: 'red' })
  })
  it('keeps the look of a style in a preview but not its size, margins or borders', () => {
    const p = previewCss({ 'font-family': 'serif', 'font-size': '30pt', 'font-weight': '500', 'margin-top': '2em', 'border-left': '3px solid red', color: 'red', 'background-color': '#eee' })
    expect(p).toMatchObject({ 'font-family': 'serif', 'font-weight': '500', color: 'red', 'background-color': '#eee' })
    expect(p['font-size']).toBeUndefined()
    expect(p['margin-top']).toBeUndefined()
    expect(p['border-left']).toBeUndefined()
  })
  it('chooses the tag by the built-in style a style comes from', () => {
    expect(semanticTag(styles, 'body')).toBe('p')
    expect(semanticTag(styles, 'heading-1')).toBe('h2')
    expect(semanticTag(styles, 'h1-x')).toBe('h2')
    expect(semanticTag(styles, 'title')).toBe('h1')
    expect(semanticTag(styles, 'unknown')).toBe('p')
  })
  it('counts the paragraphs of each style', () => {
    const blocks = [{ style: 'body' }, { style: 'heading-1' }, { style: 'body' }] as any
    expect(styleUses(blocks)).toEqual({ body: 2, 'heading-1': 1 })
  })
})
