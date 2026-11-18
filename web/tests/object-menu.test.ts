import { describe, expect, it, vi } from 'vitest'
import { contextMenuItems, type MenuSubject } from '~/lib/object-menu'

const text = (extra: Partial<MenuSubject> = {}): MenuSubject => ({ kind: 'text', snap: true, ...extra })
const shape = (extra: Partial<MenuSubject> = {}): MenuSubject => text({ kind: 'shape', ...extra })
const image = (extra: Partial<MenuSubject> = {}): MenuSubject => text({ kind: 'image', ...extra })
const chart = (extra: Partial<MenuSubject> = {}): MenuSubject => text({ kind: 'diagram', ...extra })
const container = (extra: Partial<MenuSubject> = {}): MenuSubject => text({ kind: 'rendered', ...extra })

const actions = () => ({
  describe: vi.fn(),
  edit: vi.fn(),
  style: vi.fn(),
  rotateBy: vi.fn(),
  remove: vi.fn(),
  cut: vi.fn(),
  copy: vi.fn(),
  setSnap: vi.fn(),
  setWrap: vi.fn(),
  setGap: vi.fn(),
})
const labels = (items: ReturnType<typeof contextMenuItems>) => items.filter((i) => !i.separator).map((i) => i.label)
const groups = (items: ReturnType<typeof contextMenuItems>) => {
  const out: string[][] = [[]]
  for (const i of items) {
    if (i.separator) out.push([])
    else out.at(-1)!.push(i.label)
  }
  return out
}

describe('the object menu is one list (D1225)', () => {
  it('for a text box in creates: Describe, Edit text, Style, Rotate by, then the grid, then Delete — no 90° entries', () => {
    const items = contextMenuItems(text(), false, actions(), { grid: true })
    expect(groups(items)).toEqual([['Describe…', 'Edit Text', 'Style…', 'Rotate By…'], ['Release from grid'], ['Delete']])
  })

  it('for a picture: no Edit text, Cut and Copy in a group of their own, and no "Properties" (Style… holds it)', () => {
    const items = contextMenuItems(image(), false, actions(), { grid: true })
    expect(groups(items)).toEqual([['Describe…', 'Style…', 'Rotate By…'], ['Cut', 'Copy'], ['Release from grid'], ['Delete']])
  })

  it('for a shape and for a container (rendered text): the same as for a text box', () => {
    for (const o of [shape(), container()]) expect(labels(contextMenuItems(o, false, actions(), { grid: true }))).toEqual(['Describe…', 'Edit Text', 'Style…', 'Rotate By…', 'Release from grid', 'Delete'])
  })

  it('for a chart: no Rotate by… (D1021) and no Edit text, since it holds no paragraph', () => {
    expect(labels(contextMenuItems(chart(), false, actions(), { grid: true }))).toEqual(['Describe…', 'Style…', 'Release from grid', 'Delete'])
  })

  it('offers the grid only where the app has one: computes and composes have none', () => {
    expect(labels(contextMenuItems(text(), false, actions()))).not.toContain('Release from grid')
    expect(labels(contextMenuItems(text(), false, actions()))).not.toContain('Snap to grid')
  })

  it('never offers Rotate Right 90° or Rotate Left 90° (Rotate by… does them)', () => {
    for (const o of [text(), shape(), image(), chart(), container()]) {
      expect(labels(contextMenuItems(o, false, actions(), { grid: true })).some((l) => l.startsWith('Rotate') && l !== 'Rotate By…')).toBe(false)
    }
  })
})

describe('each entry is wired to its own action', () => {
  it('runs describe, edit, style, rotate by and delete, and nothing else', () => {
    const a = actions()
    const items = contextMenuItems(text(), false, a, { grid: true })
    for (const label of ['Describe…', 'Edit Text', 'Style…', 'Rotate By…', 'Delete']) items.find((i) => i.label === label)!.action!()
    expect([a.describe, a.edit, a.style, a.rotateBy, a.remove].map((f) => f.mock.calls.length)).toEqual([1, 1, 1, 1, 1])
    expect([a.cut, a.copy, a.setSnap, a.setWrap].map((f) => f.mock.calls.length)).toEqual([0, 0, 0, 0])
  })
  it('runs Cut and Copy for a picture', () => {
    const a = actions()
    const items = contextMenuItems(image(), false, a)
    items.find((i) => i.label === 'Cut')!.action!()
    items.find((i) => i.label === 'Copy')!.action!()
    expect([a.cut.mock.calls.length, a.copy.mock.calls.length]).toEqual([1, 1])
  })
})

describe('keys', () => {
  it('shows the key every entry has in the menus (Enter, Ctrl+Alt+D, Ctrl+Alt+A, Ctrl+Shift+Alt+Z, Del, Ctrl+X, Ctrl+C)', () => {
    const items = contextMenuItems(image(), false, actions(), { grid: true })
    const hint = (label: string) => items.find((i) => i.label === label)!.hint
    expect([hint('Describe…'), hint('Style…'), hint('Rotate By…'), hint('Cut'), hint('Copy'), hint('Delete')]).toEqual(['Ctrl+Alt+D', 'Ctrl+Alt+A', 'Ctrl+Shift+Alt+Z', 'Ctrl+X', 'Ctrl+C', 'Del'])
    expect(contextMenuItems(text(), false, actions()).find((i) => i.label === 'Edit Text')!.hint).toBe('Enter')
  })
})

describe('a viewer may look but not change', () => {
  it('disables every entry except Copy, which only reads', () => {
    const items = contextMenuItems(image(), true, actions(), { grid: true })
    for (const i of items.filter((x) => !x.separator)) expect(!!i.disabled, i.label).toBe(i.label !== 'Copy')
  })
  it('disables every entry for a text box', () => {
    expect(contextMenuItems(text(), true, actions(), { grid: true }).filter((i) => !i.separator).every((i) => i.disabled)).toBe(true)
  })
})

describe('the grid toggle (E10.15)', () => {
  it('is "Release from grid" for an object that snaps and sets snap off', () => {
    const a = actions()
    contextMenuItems(text({ snap: true }), false, a, { grid: true }).find((i) => i.label === 'Release from grid')!.action!()
    expect(a.setSnap).toHaveBeenCalledWith(false)
  })
  it('is "Snap to grid" for an object that was released and sets snap on', () => {
    const a = actions()
    contextMenuItems(text({ snap: false }), false, a, { grid: true }).find((i) => i.label === 'Snap to grid')!.action!()
    expect(a.setSnap).toHaveBeenCalledWith(true)
  })
})

describe('Wrap text… (composes only, D1061)', () => {
  const wrapEntry = (items: ReturnType<typeof contextMenuItems>) => items.find((i) => i.label === 'Wrap Text…')!

  it('is a submenu of the four modes with a tick on the current one, then Gap…, and shows the key that cycles them', () => {
    const entry = wrapEntry(contextMenuItems(image(), false, actions(), { wrap: 'around' }))
    expect(entry.hint).toBe('Ctrl+Alt+R')
    const modes = entry.items!.filter((i) => !i.separator)
    expect(modes.map((i) => i.label)).toEqual(['Over the text', 'Around the object', 'Above and below the object', 'Behind the text', 'Gap…'])
    expect(modes.map((i) => i.checked)).toEqual([false, true, false, false, undefined])
  })

  it('sets the mode that is chosen, and opens the gap', () => {
    const a = actions()
    const entry = wrapEntry(contextMenuItems(shape(), false, a, { wrap: 'over' }))
    entry.items!.find((i) => i.label === 'Behind the text')!.action!()
    expect(a.setWrap).toHaveBeenCalledWith('behind')
    entry.items!.find((i) => i.label === 'Gap…')!.action!()
    expect(a.setGap).toHaveBeenCalledOnce()
  })

  it('sits between Rotate by… and the Cut/Copy group, in the first group', () => {
    expect(groups(contextMenuItems(image(), false, actions(), { wrap: 'over' }))[0]).toEqual(['Describe…', 'Style…', 'Rotate By…', 'Wrap Text…'])
  })

  it('is left off where the app has no wrap, and disabled for a viewer', () => {
    expect(labels(contextMenuItems(image(), false, actions(), { grid: true }))).not.toContain('Wrap Text…')
    expect(wrapEntry(contextMenuItems(image(), true, actions(), { wrap: 'over' })).disabled).toBe(true)
  })

  it('is offered for a chart, which floats in composes like any other object', () => {
    expect(labels(contextMenuItems(chart(), false, actions(), { wrap: 'over' }))).toContain('Wrap Text…')
  })
})
