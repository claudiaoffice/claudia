import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import { layoutText, type TextDocument, type TextObject, type TextStyle } from '../src/apps/composes'
import { walk, type DisplayItem, type GlyphRun, type Rect } from '../src/display/list'
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import { canonicalJson } from '../src/canonical'
import { hyphenatorFor } from './fonts'
import { here } from './helpers'
import { world } from './world'

let fonts: FontSet
let resolver: FontResolver
beforeAll(async () => ({ fonts, resolver } = await world()))

const STYLES: TextStyle[] = JSON.parse(readFileSync(join(here, 'composes-styles.json'), 'utf8'))
const A4 = { paper: 'a4', width: 595276, height: 841890, orientation: 'portrait' as const, margins: [70866, 70866, 70866, 70866] as [number, number, number, number], page_numbers: false }
const GERMAN = { hyphenator: hyphenatorFor('de') }
const SENTENCE = 'Eine Seite ist in Claudia keine Vermutung des Browsers mehr, sondern das Ergebnis einer Rechnung, die auf jedem Rechner dieselben Zahlen liefert. '
const para = (n: number) => SENTENCE.repeat(n).trim()

type Wrap = 'over' | 'around' | 'above-below' | 'behind'
function picture(wrap: Wrap | undefined, extra: object = {}): TextObject {
  return {
    id: 'o1', kind: 'text', w: 200, h: 150, style: 'plain-box', paragraph: { style: 'body', text: 'Bild' }, shape: null, image: null, rotation: 0,
    anchor: { kind: 'block', holder: 'b1', offset: 0, dx: 200, dy: 0, ...(wrap ? { wrap, gap: 8 } : {}), ...extra },
  } as TextObject
}

function doc(objects: TextObject[], paragraphs = 3): TextDocument {
  return {
    blocks: Array.from({ length: paragraphs }, (_, i) => ({ id: `b${i + 1}`, style: 'body', text: para(6) })),
    styles: STYLES, page: A4, language: 'de', objects,
  }
}

const runsOf = (items: DisplayItem[]): GlyphRun[] => [...walk(items)].filter((r): r is GlyphRun => r.kind === 'glyphs')
/** the text runs of a page that are not inside an object, and the object's rectangle */
function split(items: DisplayItem[]): { text: GlyphRun[]; object: Rect | null } {
  const group = items.find((i) => i.kind === 'group')
  const inside = new Set(group && group.kind === 'group' ? runsOf(group.items) : [])
  return { text: runsOf(items.filter((i) => i.kind !== 'group')).filter((r) => !inside.has(r)), object: group && group.kind === 'group' ? group.clip : null }
}
const right = (r: GlyphRun) => r.x + (r.glyphs.at(-1)?.dx ?? 0) // the left edge of the run's last glyph: a lower bound for its end
const MPT8 = 8 * 750

describe('text flowing around a floating object (D1061)', () => {
  it('is the layout it was without a wrap when the wrap is "over the text" or none is saved', () => {
    const plain = layoutText(doc([picture(undefined)]), fonts, resolver, GERMAN)
    const over = layoutText(doc([picture('over')]), fonts, resolver, GERMAN)
    expect(canonicalJson(over.list)).toBe(canonicalJson(plain.list))
  })

  it('keeps every word of "around" text clear of the object and its gap, with text on both sides of it', () => {
    const out = layoutText(doc([picture('around')]), fonts, resolver, GERMAN)
    const { text, object } = split(out.list.pages[0]!.items)
    expect(object).not.toBeNull()
    const o = object!
    const beside = text.filter((r) => r.y > o.y && r.y - 1 < o.y + o.h + MPT8)
    expect(beside.length).toBeGreaterThan(4)
    for (const r of beside) expect(r.x >= o.x + o.w + MPT8 || right(r) <= o.x - MPT8).toBe(true)
    expect(beside.some((r) => r.x < o.x)).toBe(true)
    expect(beside.some((r) => r.x >= o.x + o.w)).toBe(true)
  })

  it('loses no word and keeps their order when it wraps', () => {
    const plain = layoutText(doc([]), fonts, resolver, GERMAN)
    const wrapped = layoutText(doc([picture('around')]), fonts, resolver, GERMAN)
    const words = (pages: typeof plain.list.pages) => pages.flatMap((p) => split(p.items).text).map((r) => r.text).join(' ').replace(/\s+/g, ' ').replace(/- /g, '')
    expect(words(wrapped.list.pages).length).toBeGreaterThan(0)
    const flat = (s: string) => s.replace(/[\s-]/g, '')
    expect(flat(words(wrapped.list.pages))).toBe(flat(words(plain.list.pages)))
  })

  it('leaves the object where the layout without the wrap puts it, at its anchor line', () => {
    const plain = layoutText(doc([picture('over')]), fonts, resolver, GERMAN)
    const wrapped = layoutText(doc([picture('around')]), fonts, resolver, GERMAN)
    expect(split(wrapped.list.pages[0]!.items).object).toEqual(split(plain.list.pages[0]!.items).object)
  })

  it('stops the text above an "above and below" object and goes on below it, none beside it', () => {
    const out = layoutText(doc([picture('above-below', { dy: 60 })]), fonts, resolver, GERMAN)
    const { text, object } = split(out.list.pages[0]!.items)
    const o = object!
    const top = o.y - MPT8
    const bottom = o.y + o.h + MPT8
    expect(text.filter((r) => r.y > top + 12000 && r.y < bottom)).toEqual([]) // no baseline inside the band
    expect(text.some((r) => r.y <= top + 12000)).toBe(true)
    expect(text.some((r) => r.y >= bottom)).toBe(true)
  })

  it('pushes the whole paragraph below an object that hangs at its first line when it is "above and below"', () => {
    const out = layoutText(doc([picture('above-below')]), fonts, resolver, GERMAN)
    const { text, object } = split(out.list.pages[0]!.items)
    const o = object!
    expect(Math.min(...text.map((r) => r.y))).toBeGreaterThanOrEqual(o.y + o.h + MPT8)
  })

  it('draws a "behind" object before the text and lets the text run through it as before', () => {
    const plain = layoutText(doc([]), fonts, resolver, GERMAN)
    const behind = layoutText(doc([picture('behind')]), fonts, resolver, GERMAN)
    const items = behind.list.pages[0]!.items
    expect(items[0]!.kind).toBe('group')
    expect(canonicalJson(items.slice(1))).toBe(canonicalJson(plain.list.pages[0]!.items))
  })

  it('lets the later pages carry what the wrapped page could not hold, and never loses a paragraph', () => {
    const many = doc([picture('around')], 14)
    const out = layoutText(many, fonts, resolver, GERMAN)
    expect(out.notes).toEqual([])
    expect(out.list.pages.length).toBeGreaterThanOrEqual(layoutText(doc([], 14), fonts, resolver, GERMAN).list.pages.length)
    expect(out.pageOf.size).toBe(14)
  })

  it('gives the same list every time', () => {
    const a = layoutText(doc([picture('around')]), fonts, resolver, GERMAN)
    const b = layoutText(doc([picture('around')]), fonts, resolver, GERMAN)
    expect(canonicalJson(a.list)).toBe(canonicalJson(b.list))
  })

  it('wraps round two objects, one in each paragraph, without a line on either', () => {
    const second = { ...picture('around'), id: 'o2', anchor: { kind: 'block', holder: 'b2', offset: 0, dx: 0, dy: 0, wrap: 'around', gap: 8 } } as TextObject
    const out = layoutText(doc([picture('around'), second]), fonts, resolver, GERMAN)
    for (const page of out.list.pages) {
      const groups = page.items.filter((i) => i.kind === 'group')
      const rects = groups.map((g) => (g.kind === 'group' ? g.clip! : null)).filter((r): r is Rect => r !== null)
      for (const r of runsOf(page.items.filter((i) => i.kind !== 'group'))) {
        for (const o of rects) {
          const inBand = r.y > o.y && r.y < o.y + o.h + 1
          expect(inBand && right(r) > o.x && r.x < o.x + o.w).toBe(false)
        }
      }
    }
  })
  it('settles with several objects of every kind over many pages, and puts no word inside any of them', () => {
    const at = (id: string, block: string, wrap: Wrap, dx: number, dy: number, w = 180, h = 120): TextObject =>
      ({ ...picture(wrap), id, w, h, anchor: { kind: 'block', holder: block, offset: 0, dx, dy, wrap, gap: 8 } }) as TextObject
    const objects = [at('a', 'b2', 'around', 0, 20), at('b', 'b5', 'above-below', 100, 0, 300, 90), at('c', 'b9', 'around', 330, 10), at('d', 'b12', 'around', 150, 40, 120, 200)]
    const out = layoutText(doc(objects, 18), fonts, resolver, GERMAN)
    expect(out.notes).toEqual([])
    for (const page of out.list.pages) {
      const rects = page.items.flatMap((i) => (i.kind === 'group' && i.clip ? [i.clip] : []))
      const text = runsOf(page.items.filter((i) => i.kind !== 'group'))
      for (const o of rects) for (const r of text) expect(r.y > o.y && r.y < o.y + o.h + 1 && right(r) > o.x && r.x < o.x + o.w).toBe(false)
    }
    expect(out.pageOf.size).toBe(18)
  })
})
