import { beforeAll, describe, expect, it } from 'vitest'
import { canonicalJson } from '../src/canonical'
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import { flowItems, locate, paginate, type FlowBlock, type FlowPage } from '../src/flow/paginate'
import { contentBox, PAPER_SIZES, pageGeometry, paperById } from '../src/flow/paper'
import { umToMpt } from '../src/units'
import { blocks, sampleParagraphs } from './sample'
import { sha256 } from './helpers'
import { world } from './world'

let fonts: FontSet
let resolver: FontResolver
beforeAll(async () => ({ fonts, resolver } = await world()))

const cm = (n: number) => umToMpt(n * 10_000)
const margins = { top: cm(2.5), right: cm(2.5), bottom: cm(2.5), left: cm(2.5) }

function check(bs: FlowBlock[], pages: FlowPage[], geometry: ReturnType<typeof pageGeometry>) {
  const box = contentBox(geometry)
  // every line placed once, in order
  const seen = pages.flatMap((p) => p.lines.map((l) => `${l.block}:${l.line}`))
  const want = bs.flatMap((b, i) => b.layout.lines.map((_, l) => `${i}:${l}`))
  expect(seen).toEqual(want)
  for (const p of pages) {
    for (const l of p.lines) {
      const line = bs[l.block]!.layout.lines[l.line]!
      expect(l.top).toBeGreaterThanOrEqual(box.y)
      expect(l.top + line.height).toBeLessThanOrEqual(box.y + box.h)
      expect(l.x + line.x + line.natural).toBeLessThanOrEqual(box.x + box.w)
    }
  }
}

describe('flow pagination', () => {
  it('fills pages of any paper size and orientation, never past the margins', () => {
    const paras = sampleParagraphs(40)
    for (const paper of [...PAPER_SIZES, { id: 'custom', width: cm(10), height: cm(15) }]) {
      for (const orientation of ['portrait', 'landscape'] as const) {
        const g = pageGeometry(paper.width, paper.height, orientation, margins)
        const bs = blocks(fonts, resolver, paras, contentBox(g).w)
        const pages = paginate(bs, g)
        check(bs, pages, g)
        if (orientation === 'landscape') expect(g.width).toBeGreaterThan(g.height)
      }
    }
  })

  it('keeps headings with the next paragraph and respects orphans and widows', () => {
    const g = pageGeometry(paperById('a5')!.width, paperById('a5')!.height, 'portrait', margins)
    const bs = blocks(fonts, resolver, sampleParagraphs(60), contentBox(g).w)
    const pages = paginate(bs, g)
    expect(pages.length).toBeGreaterThan(5)
    for (const p of pages) {
      const last = p.lines.at(-1)!
      expect(bs[last.block]!.layout.style.keepWithNext && p.index < pages.length - 1).toBe(false)
      for (const f of p.fragments) {
        const n = f.end - f.first
        const total = bs[f.block]!.layout.lines.length
        if (f.continuesAfter) expect(n).toBeGreaterThanOrEqual(Math.min(2, total))
        if (f.continuesBefore) expect(n).toBeGreaterThanOrEqual(Math.min(2, total))
      }
    }
  })

  it('drops the space above a paragraph at the top of a page and collapses it between paragraphs', () => {
    const g = pageGeometry(cm(10), cm(15), 'portrait', margins)
    const bs = blocks(fonts, resolver, sampleParagraphs(30), contentBox(g).w)
    const pages = paginate(bs, g)
    for (const p of pages) expect(p.fragments[0]!.rect.y).toBe(contentBox(g).y)
    // body after body: the gap is the larger of 0.9em below and nothing above (10.8 pt), not a sum
    const a4 = pageGeometry(paperById('a4')!.width, paperById('a4')!.height, 'portrait', margins)
    const three = blocks(fonts, resolver, [{ style: 'body', text: 'eins' }, { style: 'body', text: 'zwei' }, { style: 'h1', text: 'drei' }], contentBox(a4).w)
    const [f0, f1, f2] = paginate(three, a4)[0]!.fragments
    expect(f1!.rect.y - (f0!.rect.y + f0!.rect.h)).toBe(10800)
    // body (0.9em = 10.8 pt below) before a heading (1.6em of 19 pt = 30.4 pt above): the larger one
    expect(f2!.rect.y - (f1!.rect.y + f1!.rect.h)).toBe(30400)
  })

  it('splits a paragraph taller than a page', () => {
    const g = pageGeometry(cm(10), cm(10), 'portrait', { top: cm(2), right: cm(2), bottom: cm(2), left: cm(2) })
    const bs = blocks(fonts, resolver, [{ style: 'body', text: 'Wort '.repeat(600) }], contentBox(g).w)
    const pages = paginate(bs, g)
    expect(pages.length).toBeGreaterThan(3)
    check(bs, pages, g)
  })

  it('finds where a character ended up', () => {
    const g = pageGeometry(paperById('a4')!.width, paperById('a4')!.height, 'portrait', margins)
    const bs = blocks(fonts, resolver, sampleParagraphs(10), contentBox(g).w)
    const pages = paginate(bs, g)
    const spot = locate(pages, bs, 2, 0)!
    const placed = pages[0]!.lines.find((l) => l.block === 2 && l.line === 0)!
    expect(spot).toMatchObject({ page: 0, top: placed.top, x: placed.x + bs[2]!.layout.lines[0]!.x })
    const later = locate(pages, bs, 2, 40)!
    expect(later.x).toBeGreaterThan(spot.x)
  })

  it('makes the same display list every time', () => {
    const g = pageGeometry(paperById('letter')!.width, paperById('letter')!.height, 'portrait', margins)
    const make = () => {
      const bs = blocks(fonts, resolver, sampleParagraphs(25), contentBox(g).w)
      return sha256(canonicalJson(flowItems(fonts, paginate(bs, g), bs, g)))
    }
    expect(make()).toBe(make())
  })

  it('has one empty page for an empty flow', () => {
    const g = pageGeometry(cm(10), cm(10), 'portrait', margins)
    expect(paginate([], g)).toEqual([{ index: 0, lines: [], fragments: [] }])
  })
})

describe('page geometry', () => {
  it('has exact paper sizes', () => {
    expect(paperById('a4')).toMatchObject({ width: 595276, height: 841890 })
    expect(paperById('letter')).toMatchObject({ width: 612000, height: 792000 })
  })
  it('refuses margins that leave no room', () => {
    expect(() => pageGeometry(cm(10), cm(10), 'portrait', { top: cm(5), right: cm(1), bottom: cm(4.5), left: cm(1) })).toThrow(RangeError)
    expect(() => pageGeometry(cm(1), cm(10), 'portrait', margins)).toThrow(RangeError)
  })
})
