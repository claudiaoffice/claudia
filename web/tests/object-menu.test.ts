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

const actions = () => ({ edit: vi.fn(), remove: vi.fn(), cut: vi.fn(), copy: vi.fn(), properties: vi.fn() })

describe('contextMenuItems', () => {
  it('offers Edit text and Delete for a text object, each wired to its own action', () => {
    const a = actions()
    const items = contextMenuItems(text(), false, a)
    const labels = items.filter((i) => !i.separator).map((i) => i.label)
    expect(labels).toEqual(['Edit text', 'Delete'])

    items.find((i) => i.label === 'Edit text')!.action!()
    expect(a.edit).toHaveBeenCalledOnce()
    expect(a.remove).not.toHaveBeenCalled()

    items.find((i) => i.label === 'Delete')!.action!()
    expect(a.remove).toHaveBeenCalledOnce()
  })

  it('offers Edit text for a shape too, the same as the Edit menu does (Enter/F2 works on it there)', () => {
    const items = contextMenuItems(shape(), false, actions())
    expect(items.map((i) => i.label)).toContain('Edit text')
  })

  it('leaves Edit text and Cut/Copy/Properties off a text object or shape, unchanged from before this bug fix', () => {
    const items = contextMenuItems(shape(), false, actions())
    const labels = items.filter((i) => !i.separator).map((i) => i.label)
    expect(labels).toEqual(['Edit text', 'Delete'])
  })

  it('offers Cut, Copy, Properties and Delete for an image, in that order, no Edit text (it has no text to write)', () => {
    const a = actions()
    const items = contextMenuItems(image(), false, a)
    const labels = items.filter((i) => !i.separator).map((i) => i.label)
    expect(labels).toEqual(['Cut', 'Copy', 'Properties', 'Delete'])

    items.find((i) => i.label === 'Cut')!.action!()
    expect(a.cut).toHaveBeenCalledOnce()
    items.find((i) => i.label === 'Copy')!.action!()
    expect(a.copy).toHaveBeenCalledOnce()
    items.find((i) => i.label === 'Properties')!.action!()
    expect(a.properties).toHaveBeenCalledOnce()
    items.find((i) => i.label === 'Delete')!.action!()
    expect(a.remove).toHaveBeenCalledOnce()
  })

  it('disables Cut and Delete for a viewer, same as the Edit menu already does, but leaves Copy and Properties enabled since those only read', () => {
    const items = contextMenuItems(image(), true, actions())
    expect(items.find((i) => i.label === 'Cut')!.disabled).toBe(true)
    expect(items.find((i) => i.label === 'Delete')!.disabled).toBe(true)
    expect(items.find((i) => i.label === 'Copy')!.disabled).toBeFalsy()
    expect(items.find((i) => i.label === 'Properties')!.disabled).toBeFalsy()
  })

  it('disables every action for a viewer on a text object, same as the Edit menu already does', () => {
    const items = contextMenuItems(text(), true, actions())
    expect(items.filter((i) => !i.separator).every((i) => i.disabled)).toBe(true)
  })

  it('gives Edit text, Cut and Delete their usual keyboard hints, so the menu teaches the shortcut too', () => {
    const textItems = contextMenuItems(text(), false, actions())
    expect(textItems.find((i) => i.label === 'Edit text')!.hint).toBe('Enter')
    expect(textItems.find((i) => i.label === 'Delete')!.hint).toBe('Del')

    const imageItems = contextMenuItems(image(), false, actions())
    expect(imageItems.find((i) => i.label === 'Cut')!.hint).toBe('Ctrl+X')
    expect(imageItems.find((i) => i.label === 'Copy')!.hint).toBe('Ctrl+C')
    expect(imageItems.find((i) => i.label === 'Delete')!.hint).toBe('Del')
  })
})
