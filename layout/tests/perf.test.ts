// Performance guards: generous limits, so a slow CI machine passes but an accidental quadratic step does not.
import { beforeAll, describe, expect, it } from 'vitest'
import type { FontSet } from '../src/fonts/fontset'
import type { FontResolver } from '../src/fonts/resolve'
import { flowItems, paginate } from '../src/flow/paginate'
import { contentBox, pageGeometry, paperById } from '../src/flow/paper'
import { writePdf } from '../src/pdf/writer'
import { blocks, sampleParagraphs } from './sample'
import { world } from './world'

let fonts: FontSet
let resolver: FontResolver
beforeAll(async () => ({ fonts, resolver } = await world()))

describe('performance', () => {
  it('lays out, paginates and writes about 100 A4 pages in a few seconds', () => {
    const a4 = paperById('a4')!
    const g = pageGeometry(a4.width, a4.height, 'portrait', { top: 70866, right: 70866, bottom: 70866, left: 70866 })
    const paras = sampleParagraphs(700)
    const t0 = performance.now()
    const bs = blocks(fonts, resolver, paras, contentBox(g).w)
    const pages = paginate(bs, g)
    const display = flowItems(fonts, pages, bs, g)
    const t1 = performance.now()
    const pdf = writePdf(display, fonts, () => undefined, { title: 'perf' })
    const t2 = performance.now()
    console.log(`${pages.length} pages: layout ${Math.round(t1 - t0)} ms, PDF ${Math.round(t2 - t1)} ms, ${Math.round(pdf.length / 1024)} KB`)
    expect(pages.length).toBeGreaterThan(80)
    expect(t1 - t0).toBeLessThan(4000)
    expect(t2 - t1).toBeLessThan(6000)
  })
})
