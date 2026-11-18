import { describe, expect, it } from 'vitest'
import { floatFor, floatStyle, measureFloats, objectRect, takesRoom } from '~/lib/wrap-flow'

const paragraph = { left: 100, top: 50, width: 400 }

describe('which modes take room from the lines', () => {
  it('takes it for around and above-below only', () => {
    expect(['over', 'around', 'above-below', 'behind'].map((w) => takesRoom(w as never))).toEqual([false, true, true, false])
  })
  it('makes no float for the others', () => {
    expect(floatFor('over', 8, { left: 120, top: 60, width: 50, height: 50 }, paragraph)).toBeNull()
    expect(floatFor('behind', 8, { left: 120, top: 60, width: 50, height: 50 }, paragraph)).toBeNull()
  })
})

describe('around', () => {
  it('takes the left side for an object in the left half, from the edge to its far side and the gap', () => {
    const f = floatFor('around', 8, { left: 110, top: 80, width: 100, height: 60 }, paragraph)
    expect(f).toEqual({ side: 'left', width: 110 + 100 + 8 - 100, height: 76, top: 80 - 8 - 50 })
  })
  it('takes the right side for an object in the right half', () => {
    const f = floatFor('around', 8, { left: 380, top: 80, width: 100, height: 60 }, paragraph)
    expect(f).toEqual({ side: 'right', width: 500 - (380 - 8), height: 76, top: 22 })
  })
  it('never starts above its paragraph, and never reaches past it', () => {
    const f = floatFor('around', 8, { left: 90, top: 20, width: 700, height: 30 }, paragraph)
    expect(f?.top).toBe(0)
    expect(f?.width).toBeLessThanOrEqual(paragraph.width)
    expect(f?.width).toBeGreaterThanOrEqual(0)
  })
  it('takes no room that is not there when the object is left of the paragraph', () => {
    expect(floatFor('around', 0, { left: 0, top: 60, width: 50, height: 50 }, paragraph)?.width).toBe(0)
  })
})

describe('above and below', () => {
  it('takes the whole width, as high as the object and its gap above and below', () => {
    expect(floatFor('above-below', 10, { left: 150, top: 90, width: 80, height: 40 }, paragraph)).toEqual({
      side: 'left',
      width: 400,
      height: 60,
      top: 30,
    })
  })
  it('keeps the same room whatever the width of the object', () => {
    const narrow = floatFor('above-below', 8, { left: 150, top: 90, width: 20, height: 40 }, paragraph)
    const wide = floatFor('above-below', 8, { left: 150, top: 90, width: 300, height: 40 }, paragraph)
    expect(narrow).toEqual(wide)
  })
})

describe('where the object is drawn', () => {
  const column = { left: 100, top: 0, width: 400, height: 1000 }
  it('is the anchor, moved by the offset', () => {
    expect(objectRect({ left: 120, top: 200 }, { dx: 30, dy: -10 }, 80, 50, column)).toEqual({ left: 150, top: 190, width: 80, height: 50 })
  })
  it('is kept inside the column, the left edge winning when it is wider', () => {
    expect(objectRect({ left: 450, top: 0 }, { dx: 90 }, 100, 50, column).left).toBe(400)
    expect(objectRect({ left: 120, top: 0 }, {}, 600, 50, column).left).toBe(100)
  })
})

describe('the style of the float', () => {
  it('hides a box that has no float yet', () => {
    expect(floatStyle(undefined)).toEqual({ display: 'none' })
  })
  it('floats it to its side with its room', () => {
    expect(floatStyle({ side: 'right', width: 120, height: 76, top: 22 })).toEqual({ float: 'right', width: '120px', height: '76px', marginTop: '22px' })
  })
})

describe('measuring the floats of a page', () => {
  /** A page of paragraphs `lineHeight` high with `lines` lines each: a float that is put in pushes down every paragraph
   * below the one it is in by the room it takes there (what a float above-below does to the lines under it). */
  const column = { left: 100, top: 0, width: 400, height: 1000 }
  function page(blocks: string[], lineHeight = 20, lines = 3, jump = 0) {
    // `jump`: how far the browser moves the view when the floats are taken out of the lines (it keeps what is shown)
    let scrolled = 0
    const put = new Map<string, { block: string; f: ReturnType<typeof floatFor> }>()
    const shift = (block: string) => {
      let down = 0
      for (const p of put.values()) {
        if (blocks.indexOf(p.block) < blocks.indexOf(block) && p.f?.width === 400) down += p.f.height
      }
      return down
    }
    const top = (block: string) => blocks.indexOf(block) * lineHeight * lines + shift(block) - scrolled
    const calls: string[] = []
    const host = {
      clear: () => {
        put.clear()
        scrolled = jump
        calls.push('clear')
      },
      origin: () => ({ left: 100, top: -scrolled }),
      column: () => column,
      spotOf: (block: string) => ({ left: 100, top: top(block) }),
      paragraphOf: (block: string) => ({ left: 100, top: top(block), width: 400 }),
      put: (id: string, f: ReturnType<typeof floatFor>) => {
        put.set(id, { block: blocks.find((b) => id.startsWith(b)) ?? '', f })
        calls.push(`put ${id}`)
      },
    }
    return { host, calls }
  }
  const hung = (id: string, block: string, wrap: 'around' | 'above-below') => ({ id, block, offset: 0, wrap, gap: 8, w: 80, h: 40 })

  it('measures the second object with the first one in the lines, and the first with nothing before it', () => {
    const { host } = page(['b1', 'b2'])
    const { floats, spots } = measureFloats([hung('b1-x', 'b1', 'above-below'), hung('b2-x', 'b2', 'above-below')], host)
    expect(spots.get('b1:0')?.top).toBe(0)
    expect(spots.get('b2:0')?.top).toBe(60 + 56) // the second paragraph, pushed down by the room of the first (40 + 2 × 8)
    expect(Object.keys(floats)).toEqual(['b1-x', 'b2-x'])
  })

  it('keeps each place from the top left of the text, so a view that moves while it measures does not move them', () => {
    const still = page(['b1', 'b2'])
    const moved = page(['b1', 'b2'], 20, 3, 150)
    const list = [hung('b1-x', 'b1', 'above-below'), hung('b2-x', 'b2', 'above-below')]
    expect([...measureFloats(list, moved.host).spots]).toEqual([...measureFloats(list, still.host).spots])
  })

  it('starts by taking every float out of the lines', () => {
    const { host, calls } = page(['b1'])
    measureFloats([hung('b1-x', 'b1', 'around')], host)
    expect(calls[0]).toBe('clear')
  })

  it('gives the same floats when it is run again on the same text', () => {
    const { host } = page(['b1', 'b2', 'b3'])
    const list = [hung('b1-x', 'b1', 'above-below'), hung('b2-x', 'b2', 'around'), hung('b3-x', 'b3', 'above-below')]
    const first = measureFloats(list, host)
    const second = measureFloats(list, host)
    expect(second.floats).toEqual(first.floats)
    expect([...second.spots]).toEqual([...first.spots])
  })

  it('puts the float of an object that takes no room as none', () => {
    const { host, calls } = page(['b1'])
    const { floats } = measureFloats([{ ...hung('b1-x', 'b1', 'around'), wrap: 'over' }], host)
    expect(floats).toEqual({})
    expect(calls).toContain('put b1-x')
  })

  it('leaves out an object whose paragraph is not on the page', () => {
    const missing = { clear() {}, origin: () => ({ left: 0, top: 0 }), column: () => column, spotOf: () => null, paragraphOf: () => null, put() {} }
    expect(measureFloats([hung('x', 'b9', 'around')], missing).floats).toEqual({})
  })
})
