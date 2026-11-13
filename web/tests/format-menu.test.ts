import { describe, expect, it, vi } from 'vitest'
import { formatItems, noLists, type FormatMenu, type ListMenu } from '~/lib/format-menu'
import { menuCss, type StyleView } from '~/lib/style-css'

const view = (id: string, resolved: Record<string, string> = {}): StyleView => ({
  id,
  name: id[0]!.toUpperCase() + id.slice(1),
  purpose: '',
  based_on: null,
  css: {},
  computed: resolved,
  resolved,
  to_name: false,
  kind: 'paragraph',
})

function listMenu(calls: string[], over: Partial<ListMenu> = {}): ListMenu {
  return {
    current: null,
    canNest: true,
    canContinue: true,
    hints: { bulleted: 'Ctrl+Shift+8', numbered: 'Ctrl+Shift+7', indent: 'Tab', outdent: 'Shift+Tab' },
    bulleted: () => calls.push('bulleted'),
    numbered: () => calls.push('numbered'),
    continueList: () => calls.push('continue'),
    startAt: () => calls.push('start'),
    indent: () => calls.push('indent'),
    outdent: () => calls.push('outdent'),
    ...over,
  }
}

function menu(over: Partial<FormatMenu> = {}) {
  const calls: string[] = []
  const made: FormatMenu = {
    groups: [[view('title', { 'font-family': 'Fraunces', 'font-size': '28pt' })], [view('body')]],
    current: 'body',
    canApply: true,
    apply: (id) => calls.push(`apply ${id}`),
    openApply: () => calls.push('popover'),
    look: { disabled: false, hint: 'Shift+F10', open: () => calls.push('look') },
    allStyles: () => calls.push('all'),
    colours: () => calls.push('colours'),
    list: listMenu(calls),
    ...over,
  }
  return { items: formatItems((s) => s, made), calls }
}

describe('the Format menu (D300)', () => {
  it('has four entries and the list in this order, with Colours set apart', () => {
    const { items } = menu()
    expect(items.map((i) => (i.separator ? '—' : i.label))).toEqual(['Apply Style', 'Edit This Style…', 'All Styles…', 'List', '—', 'Colours…'])
    // The list has no action id: the native shells' manifests have the four of D300 and nothing else yet (E9.21).
    expect(items.map((i) => i.id).filter(Boolean)).toEqual(['format.apply-style', 'format.look', 'format.all-styles', 'format.colours'])
  })

  it('offers the styles in a flyout, in their groups, ticking the one the selection has', () => {
    const flyout = menu().items[0]!.items!
    expect(flyout.map((i) => (i.separator ? '—' : i.label))).toEqual(['Title', '—', 'Body'])
    expect(flyout.find((i) => i.label === 'Body')!.checked).toBe(true)
    expect(flyout.find((i) => i.label === 'Title')!.checked).toBe(false)
  })

  it('draws each style in its look, never its size', () => {
    const title = menu().items[0]!.items![0]!
    expect(title.css!['font-family']).toBe('Fraunces')
    expect(title.css!['font-size']).toBeUndefined()
  })

  it('applies a style from the flyout, and opens the popover from a shell’s single entry (D301)', () => {
    const { items, calls } = menu()
    items[0]!.items![2]!.action!()
    items[0]!.action!()
    expect(calls).toEqual(['apply body', 'popover'])
  })

  it('says what the styles are for, says when nothing fits, and adds what an app has more', () => {
    const clear = { label: 'Clear cell style', action: vi.fn() }
    const flyout = menu({ heading: 'For the 6 selected cells', groups: [[], []], more: [clear] }).items[0]!.items!
    expect(flyout.map((i) => (i.separator ? '—' : i.label))).toEqual(['For the 6 selected cells', 'No styles fit what is selected', '—', 'Clear cell style'])
    expect(flyout[0]!.disabled).toBe(true)
  })

  it('disables the styles, not the menu, when nothing can be applied', () => {
    const { items } = menu({ canApply: false, look: { disabled: true, open: () => undefined } })
    expect(items[0]!.items!.filter((i) => !i.separator).every((i) => i.disabled)).toBe(true)
    expect(items[1]!.disabled).toBe(true)
    expect(items[2]!.disabled).toBeFalsy()
  })
})

describe('the List entry of the Format menu (E9.21)', () => {
  const flyout = (over: Partial<ListMenu> = {}) => {
    const calls: string[] = []
    const items = menu({ list: listMenu(calls, over) }).items.find((i) => i.label === 'List')!.items!
    return { items, calls }
  }

  it('offers bullets and numbers, continuing and starting, and the levels, with the keys beside them', () => {
    const { items } = flyout()
    expect(items.map((i) => (i.separator ? '—' : i.label))).toEqual(['Bulleted List', 'Numbered List', '—', 'Continue Previous List', 'Start At…', '—', 'Indent', 'Outdent'])
    expect(items.filter((i) => i.hint).map((i) => [i.label, i.hint])).toEqual([
      ['Bulleted List', 'Ctrl+Shift+8'],
      ['Numbered List', 'Ctrl+Shift+7'],
      ['Indent', 'Tab'],
      ['Outdent', 'Shift+Tab'],
    ])
  })

  it('does what the entries say', () => {
    const { items, calls } = flyout()
    for (const item of items.filter((i) => !i.separator)) item.action!()
    expect(calls).toEqual(['bulleted', 'numbered', 'continue', 'start', 'indent', 'outdent'])
  })

  it('ticks the kind of list the caret is in', () => {
    expect(flyout({ current: 'numbers' }).items.filter((i) => i.checked).map((i) => i.label)).toEqual(['Numbered List'])
    expect(flyout({ current: null }).items.filter((i) => i.checked)).toEqual([])
  })

  it('leaves what needs an item disabled outside one, and continuing where there is nothing to continue', () => {
    const outside = flyout({ canNest: false, canContinue: false }).items
    expect(outside.filter((i) => i.disabled).map((i) => i.label)).toEqual(['Continue Previous List', 'Start At…', 'Indent', 'Outdent'])
    expect(flyout({ canContinue: false }).items.filter((i) => i.disabled).map((i) => i.label)).toEqual(['Continue Previous List'])
  })

  it('is there but disabled, and says why, in an app that has no lists yet', () => {
    const calls: string[] = []
    const entry = menu({ list: listMenu(calls, { unavailable: 'Cells hold no lists' }) }).items.find((i) => i.label === 'List')!
    expect(entry.items![0]).toMatchObject({ label: 'Cells hold no lists', disabled: true })
    expect(entry.items!.filter((i) => !i.separator).every((i) => i.disabled)).toBe(true)
    expect(entry.disabled).toBe(true)
  })

  it('an app without lists says so with noLists, and nothing in it does anything', () => {
    const entry = menu({ list: noLists('Cells hold no lists') }).items.find((i) => i.label === 'List')!
    expect(entry.disabled).toBe(true)
    expect(entry.items!.map((i) => (i.separator ? '—' : i.label))[0]).toBe('Cells hold no lists')
    for (const item of entry.items!.filter((i) => i.action)) expect(() => item.action!()).not.toThrow()
  })

  it('is disabled for a viewer', () => {
    const entry = menu({ list: listMenu([], { readonly: true }) }).items.find((i) => i.label === 'List')!
    expect(entry.items!.filter((i) => !i.separator).every((i) => i.disabled)).toBe(true)
  })
})

describe('a style as a menu entry (menuCss)', () => {
  it('keeps type and colour, and draws a background and borders as a chip', () => {
    const css = menuCss({ 'font-weight': '600', 'font-size': '40px', 'background-color': '#e9e6f6', 'border-left': '3px solid #5b4bc4', 'padding-top': '12px' })
    expect(css).toMatchObject({ 'font-weight': '600', 'background-color': '#e9e6f6', 'border-left': '2px solid #5b4bc4', padding: '0 6px' })
    expect(css['font-size']).toBeUndefined()
    expect(css['padding-top']).toBeUndefined()
  })

  it('draws no chip for a style without a box', () => {
    expect(menuCss({ 'font-style': 'italic' })).toEqual({ 'font-style': 'italic' })
  })
})
