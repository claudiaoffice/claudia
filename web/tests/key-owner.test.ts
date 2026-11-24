import { describe, expect, it } from 'vitest'
import { keysAreTheirs } from '~/lib/key-owner'

/** A thing a key was pressed on. `inside` lists what it sits in or is: a selector matches when one of them does. */
function pressedOn(...inside: string[]) {
  return { closest: (selector: string) => inside.find((name) => selector.split(',').some((s) => s.trim().startsWith(name))) ?? null }
}

describe('whose a key is: the slide or the grid behind it, or the thing it was typed into', () => {
  it('belongs to a dialog that is open on top of the object: Name & describe, Image properties', () => {
    expect(keysAreTheirs(pressedOn('dialog'))).toBe(true)
  })

  it('belongs to a popover that says it is a dialog (Rotate by…)', () => {
    expect(keysAreTheirs(pressedOn('[role=dialog]'))).toBe(true)
  })

  it('belongs to a field that is typed into, wherever it is', () => {
    expect(keysAreTheirs(pressedOn('input:not([type=checkbox])'))).toBe(true)
    expect(keysAreTheirs(pressedOn('textarea'))).toBe(true)
  })

  it('belongs to the slide when the focus is on the slide itself', () => {
    expect(keysAreTheirs(pressedOn())).toBe(false)
  })

  it('belongs to the slide when nothing has the focus', () => {
    expect(keysAreTheirs(null)).toBe(false)
  })
})
