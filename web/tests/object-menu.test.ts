import { describe, expect, it, vi } from 'vitest'
import { contextMenuItems } from '~/lib/object-menu'
import type { SlideObject } from '~/lib/slide-session'

const text = (extra: object = {}): SlideObject => ({
  id: 't1',
  slide: 's1',
  kind: 'text',
  x: 0,
  y: 0,
  w: 100,
  h: 100,
  style: 'body-text',
  text: 'hello',
  shape: null,
  image: null,
  imported: null,
  ...extra,
})
const shape = (extra: object = {}): SlideObject => ({ ...text(extra), id: 's1-shape', kind: 'shape', shape: 'circle' })
const image = (extra: object = {}): SlideObject => ({ ...text(extra), id: 'i1', kind: 'image', shape: null, image: 'a'.repeat(64) })

describe('contextMenuItems', () => {
  it('offers Edit text and Delete for a text object, each wired to its own action', () => {
    const edit = vi.fn()
    const remove = vi.fn()
    const items = contextMenuItems(text(), false, { edit, remove })
    const labels = items.filter((i) => !i.separator).map((i) => i.label)
    expect(labels).toEqual(['Edit text', 'Delete'])

    items.find((i) => i.label === 'Edit text')!.action!()
    expect(edit).toHaveBeenCalledOnce()
    expect(remove).not.toHaveBeenCalled()

    items.find((i) => i.label === 'Delete')!.action!()
    expect(remove).toHaveBeenCalledOnce()
  })

  it('offers Edit text for a shape too, the same as the Edit menu does (Enter/F2 works on it there)', () => {
    const items = contextMenuItems(shape(), false, { edit: vi.fn(), remove: vi.fn() })
    expect(items.map((i) => i.label)).toContain('Edit text')
  })

  it('leaves Edit text off the menu entirely for an image, which has no text to write', () => {
    const items = contextMenuItems(image(), false, { edit: vi.fn(), remove: vi.fn() })
    expect(items.map((i) => i.label)).not.toContain('Edit text')
    expect(items.map((i) => i.label)).toEqual(['Delete'])
  })

  it('disables every action for a viewer, same as the Edit menu already does', () => {
    const items = contextMenuItems(text(), true, { edit: vi.fn(), remove: vi.fn() })
    expect(items.filter((i) => !i.separator).every((i) => i.disabled)).toBe(true)
  })

  it('gives Edit text and Delete their usual keyboard hints, so the menu teaches the shortcut too', () => {
    const items = contextMenuItems(text(), false, { edit: vi.fn(), remove: vi.fn() })
    expect(items.find((i) => i.label === 'Edit text')!.hint).toBe('Enter')
    expect(items.find((i) => i.label === 'Delete')!.hint).toBe('Del')
  })
})
