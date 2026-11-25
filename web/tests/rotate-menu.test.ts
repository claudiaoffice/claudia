import { describe, expect, it, vi } from 'vitest'
import { rotateItem } from '../app/lib/rotate-menu'

const t = (msgid: string) => msgid
const host = (kind: string | null, readonly = false) => ({ kind: () => kind, readonly: () => readonly, quarter: vi.fn(), by: vi.fn() })

describe('Format ▸ Rotate (D1024, D1232): one submenu in every app that turns objects', () => {
  it('has the three entries, in the order of the manifest', () => {
    const item = rotateItem(t, host('shape'))
    expect(item.items?.map((i) => i.id)).toEqual(['format.rotate-right', 'format.rotate-left', 'format.rotate-by'])
    expect(item.items?.map((i) => i.label)).toEqual(['Rotate Right 90°', 'Rotate Left 90°', 'Rotate By…'])
  })

  it('turns by a quarter each way and opens Rotate By… for what turns', () => {
    const h = host('image')
    const [right, left, by] = rotateItem(t, h).items!
    right!.action!()
    left!.action!()
    by!.action!()
    expect(h.quarter.mock.calls).toEqual([[1], [-1]])
    expect(h.by).toHaveBeenCalledOnce()
  })

  it.each([
    ['nothing selected', null, false],
    ['a chart', 'chart', false],
    ['a table', 'table', false],
    ['a document one can only look at', 'text', true],
  ])('is off for %s', (_name, kind, readonly) => {
    const item = rotateItem(t, host(kind, readonly))
    expect(item.items!.every((i) => i.disabled)).toBe(true)
  })

  it.each(['text', 'shape', 'image', 'container'])('is on for a %s', (kind) => {
    const item = rotateItem(t, host(kind))
    expect(item.disabled).toBe(false)
    expect(item.items!.some((i) => i.disabled)).toBe(false)
  })
})
