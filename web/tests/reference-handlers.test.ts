// A reference's own menu (D1607, UX-96): Show As ▸ its ways and Remove Reference, from the definition like every entry.
import { describe, expect, it, vi } from 'vitest'
import { DEFAULT_POLICY } from '~/lib/fits/policy'
import { assembleMenus, type MenuInput } from '~/lib/menus/assemble'
import { DEFINITIONS } from '~/lib/menus.generated'
import { referenceHandlers, type ReferenceHere } from '~/lib/menus/reference-handlers'
import type { Facts } from '~/lib/fits/facts'

const t = (msgid: string) => msgid

function here(over: Partial<ReferenceHere> = {}): ReferenceHere {
  return { show: 'number', setShow: vi.fn(), remove: vi.fn(), ...over }
}

const owner: Facts = {
  role: 'owner',
  client: 'web',
  ai: true,
  tools: new Set(),
  document: { undo: false, redo: false, references: true, randomNumbers: false, backPlace: false, slides: 1 },
  selection: [],
}

function referenceMenu(handlers: MenuInput['handlers']) {
  const menus = assembleMenus({ definition: DEFINITIONS.composes, handlers, facts: () => owner, policy: DEFAULT_POLICY, t, notice: () => {}, locale: 'en' })
  return menus.context('reference', handlers)
}

describe("a reference's menu", () => {
  it('ticks the way the reference shows now, and shows it another way when chosen', () => {
    const ref = here({ show: 'page' })
    const [showAs] = referenceMenu(referenceHandlers(t, ref))
    expect(showAs!.label).toBe('Show As')
    expect(showAs!.items!.map((c) => [c.label, c.checked])).toEqual([
      ['Number', false],
      ['Text', false],
      ['Number and Text', false],
      ['Page', true],
      ['Name', false],
    ])
    showAs!.items![0]!.action!()
    expect(ref.setShow).toHaveBeenCalledWith('number')
  })

  it('takes the reference out with Remove Reference', () => {
    const ref = here()
    const remove = referenceMenu(referenceHandlers(t, ref)).find((item) => item.label === 'Remove Reference')
    remove!.action!()
    expect(ref.remove).toHaveBeenCalled()
  })

  it('says there is no reference here where there is none, as in the Shortcuts list', () => {
    const handlers = referenceHandlers(t, null)
    expect(handlers['edit.remove-reference']!.notNow!()).toBe('There is no reference here.')
    expect(handlers['format.show-as-text']!.notNow!()).toBe('There is no reference here.')
  })
})
