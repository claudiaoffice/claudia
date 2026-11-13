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
  snap: true,
  ...extra,
})
const shape = (extra: object = {}): SlideObject => ({ ...text(extra), id: 's1-shape', kind: 'shape', shape: 'circle' })
const image = (extra: object = {}): SlideObject => ({ ...text(extra), id: 'i1', kind: 'image', shape: null, image: 'a'.repeat(64) })

const actions = () => ({ edit: vi.fn(), remove: vi.fn(), cut: vi.fn(), copy: vi.fn(), properties: vi.fn(), setSnap: vi.fn(), style: vi.fn() })

describe('contextMenuItems', () => {
  it('offers Edit text, the grid toggle and Delete for a text object, each wired to its own action', () => {
    const a = actions()
    const items = contextMenuItems(text(), false, a)
    const labels = items.filter((i) => !i.separator).map((i) => i.label)
    expect(labels).toEqual(['Style…', 'Edit text', 'Release from grid', 'Delete'])

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

  it('leaves Cut/Copy/Properties off a text object or shape, unchanged from before the image-properties bug fix', () => {
    const items = contextMenuItems(shape(), false, actions())
    const labels = items.filter((i) => !i.separator).map((i) => i.label)
    expect(labels).toEqual(['Style…', 'Edit text', 'Release from grid', 'Delete'])
  })

  it('offers Cut, Copy, Properties, the grid toggle and Delete for an image, in that order, no Edit text (it has no text to write)', () => {
    const a = actions()
    const items = contextMenuItems(image(), false, a)
    const labels = items.filter((i) => !i.separator).map((i) => i.label)
    expect(labels).toEqual(['Style…', 'Cut', 'Copy', 'Properties', 'Release from grid', 'Delete'])

    items.find((i) => i.label === 'Cut')!.action!()
    expect(a.cut).toHaveBeenCalledOnce()
    items.find((i) => i.label === 'Copy')!.action!()
    expect(a.copy).toHaveBeenCalledOnce()
    items.find((i) => i.label === 'Properties')!.action!()
    expect(a.properties).toHaveBeenCalledOnce()
    items.find((i) => i.label === 'Delete')!.action!()
    expect(a.remove).toHaveBeenCalledOnce()
  })

  it('disables Cut, Delete and the grid toggle for a viewer, but leaves Copy and Properties enabled since those only read', () => {
    const items = contextMenuItems(image(), true, actions())
    expect(items.find((i) => i.label === 'Cut')!.disabled).toBe(true)
    expect(items.find((i) => i.label === 'Delete')!.disabled).toBe(true)
    expect(items.find((i) => i.label === 'Release from grid')!.disabled).toBe(true)
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

  describe('the grid toggle (E10.15)', () => {
    it('offers "Release from grid" for an object that snaps, and calls setSnap(false)', () => {
      const acts = actions()
      const items = contextMenuItems(text({ snap: true }), false, acts)
      const toggle = items.find((i) => i.label === 'Release from grid')!
      toggle.action!()
      expect(acts.setSnap).toHaveBeenCalledWith(false)
    })

    it('offers "Snap to grid" for an object that was released, and calls setSnap(true)', () => {
      const acts = actions()
      const items = contextMenuItems(text({ snap: false }), false, acts)
      const toggle = items.find((i) => i.label === 'Snap to grid')!
      toggle.action!()
      expect(acts.setSnap).toHaveBeenCalledWith(true)
    })

    it('is offered for a shape and an image too, not only a text box', () => {
      expect(contextMenuItems(shape({ snap: false }), false, actions()).map((i) => i.label)).toContain('Snap to grid')
      expect(contextMenuItems(image({ snap: false }), false, actions()).map((i) => i.label)).toContain('Snap to grid')
    })
  })
})

describe('Style… (E9.7, D203)', () => {
  it('is offered first for every kind, because every object has a look of its own', () => {
    for (const o of [text(), shape(), image()]) {
      const items = contextMenuItems(o, false, actions())
      expect(items.filter((i) => !i.separator)[0]!.label).toBe('Style…')
    }
  })

  it('calls the action the canvas supplies, which opens the style menu where the click was', () => {
    const a = actions()
    contextMenuItems(shape(), false, a).find((i) => i.label === 'Style…')!.action!()
    expect(a.style).toHaveBeenCalledOnce()
  })

  it('is disabled for a viewer: a style change is a change to the document', () => {
    const items = contextMenuItems(shape(), true, actions())
    expect(items.find((i) => i.label === 'Style…')!.disabled).toBe(true)
  })
})
