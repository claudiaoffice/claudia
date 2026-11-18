// Text that flows around a floating object (D1061) in a text that also holds a table (E9.32): the two features were
// built apart and meet in `layoutText`, where the rows of a wrapped paragraph are indexed by their place in the flow
// and a table is a flow item of its own after the paragraph it hangs from.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { beforeAll, describe, expect, it } from 'vitest'
import { layoutText, type TextDocument, type TextObject, type TextStyle } from '../src/apps/composes'
import { walk, type DisplayItem, type GlyphRun, type Rect } from '../src/display/list'
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import type { TableData } from '../src/flow/table'
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
const MPT8 = 8 * 750

const GARDEN = [
  ['Bed', 'Crop', 'Yield kg'],
  ['North', 'Tomatoes', '212,5'],
  ['South', 'Beans', '88,0'],
]
const TABLE_WORDS = new Set(['Bed', 'Crop', 'Yield', 'kg', 'North', 'Tomatoes', '212,5', 'South', 'Beans', '88,0'])

function table(words: string[][]): TableData {
  const columns = (words[0] ?? []).map((_, c) => ({ id: `c${c + 1}`, kind: 'text', total: null, width: null }))
  const rows = words.map((_, r) => `r${r + 1}`)
  const entries = words.flatMap((line, r) => line.map((text, c): TableData['entries'][number] => [`r${r + 1}`, `c${c + 1}`, { id: `t1/r${r + 1}/c${c + 1}`, style: '', text }]))
  return { id: 't1', columns, rows, entries, merges: [], header_rows: 1, banded: false, look: 'rules', width: null, totals: {} }
}

const picture = (): TextObject =>
  ({
    id: 'o1', kind: 'text', w: 200, h: 150, style: 'plain-box', paragraph: { style: 'body', text: 'Bild' }, rotation: 0,
    anchor: { kind: 'block', container: 'b1', offset: 0, dx: 200, dy: 0, wrap: 'around', gap: 8 },
  }) as TextObject

const tableObject = (): TextObject =>
  ({ id: 'o2', kind: 'table', w: 480, h: 96, style: 'plain-box', paragraph: null, rotation: 0, ref: 't1', anchor: { kind: 'block', container: 'b1', offset: 0 } }) as TextObject

/** b1 flows round the picture and the table hangs from it; b2 follows both. */
const doc = (objects: TextObject[]): TextDocument => ({
  blocks: [
    { id: 'b1', style: 'body', text: SENTENCE.repeat(6).trim() },
    { id: 'b2', style: 'body', text: 'Danach.' },
  ],
  styles: STYLES,
  page: A4,
  language: 'de',
  objects,
  tables: [table(GARDEN)],
})

const runsOf = (items: DisplayItem[]): GlyphRun[] => [...walk(items)].filter((r): r is GlyphRun => r.kind === 'glyphs')
/** the text runs of a page that are not inside an object, and the object's rectangle */
function split(items: DisplayItem[]): { text: GlyphRun[]; object: Rect | null } {
  const group = items.find((i) => i.kind === 'group')
  const inside = new Set(group && group.kind === 'group' ? runsOf(group.items) : [])
  return { text: runsOf(items.filter((i) => i.kind !== 'group')).filter((r) => !inside.has(r)), object: group && group.kind === 'group' ? group.clip : null }
}
const right = (r: GlyphRun) => r.x + (r.glyphs.at(-1)?.dx ?? 0)

describe('a wrapped paragraph and a table in one text', () => {
  const out = () => layoutText(doc([picture(), tableObject()]), fonts, resolver, GERMAN)

  it('settles without a note, with the picture and the table both drawn', () => {
    const laid = out()
    expect(laid.notes.filter((n) => n.kind !== 'hyphenation')).toEqual([])
    const { text, object } = split(laid.list.pages[0]!.items)
    expect(object).not.toBeNull()
    expect(text.map((r) => r.text)).toEqual(expect.arrayContaining(['Bed', 'Tomatoes', '88,0', 'Danach.']))
  })

  it('keeps the words of the wrapped paragraph clear of the picture and its gap', () => {
    const { text, object } = split(out().list.pages[0]!.items)
    const o = object!
    const paragraph = text.filter((r) => !TABLE_WORDS.has(r.text) && r.text !== 'Danach.')
    const beside = paragraph.filter((r) => r.y > o.y && r.y - 1 < o.y + o.h + MPT8)
    expect(beside.length).toBeGreaterThan(4)
    for (const r of beside) expect(r.x >= o.x + o.w + MPT8 || right(r) <= o.x - MPT8).toBe(true)
  })

  it('puts the table below the last line of its paragraph and the next paragraph below the table', () => {
    const { text } = split(out().list.pages[0]!.items)
    const paragraph = text.filter((r) => !TABLE_WORDS.has(r.text) && r.text !== 'Danach.')
    const lowest = Math.max(...paragraph.map((r) => r.y))
    const tableTop = Math.min(...text.filter((r) => TABLE_WORDS.has(r.text)).map((r) => r.y))
    const tableBottom = Math.max(...text.filter((r) => TABLE_WORDS.has(r.text)).map((r) => r.y))
    const danach = text.find((r) => r.text === 'Danach.')!
    expect(tableTop).toBeGreaterThan(lowest)
    expect(danach.y).toBeGreaterThan(tableBottom)
  })

  it('loses no word of the paragraph to the wrapping when a table follows it', () => {
    const words = (objects: TextObject[]) =>
      layoutText(doc(objects), fonts, resolver, GERMAN)
        .list.pages.flatMap((p) => split(p.items).text)
        .filter((r) => !TABLE_WORDS.has(r.text) && r.text !== 'Danach.')
        .map((r) => r.text)
        .join(' ')
        .replace(/\s+/g, ' ')
        .replace(/- /g, '')
    expect(words([picture(), tableObject()])).toBe(words([tableObject()]))
  })
})
