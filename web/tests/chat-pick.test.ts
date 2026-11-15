import { describe, expect, it } from 'vitest'
import { ChatPick, thingAt } from '../app/lib/chat-pick'

const el = (id: string | null) => ({ closest: () => (id === null ? null : { getAttribute: () => id }) })

function gate(focused = true) {
  const state = { focused }
  return { state, gate: new ChatPick(() => state.focused, (target) => (target as { id: string | null }).id) }
}
const on = (id: string | null) => ({ id })

describe('a click while the chat box has the caret', () => {
  it('is taken as a pick of the thing it began on, and the document hears none of it', () => {
    const { gate: g } = gate()
    expect(g.handle('pointerdown', on('o1'))).toBe('swallow')
    expect(g.handle('mousedown', on('o1'))).toBe('swallow')
    expect(g.picking).toBe(true)
    expect(g.handle('pointerup', on('o1'))).toBe('swallow')
    expect(g.handle('mouseup', on('o1'))).toBe('swallow')
    expect(g.handle('click', on('o1'))).toEqual({ pick: 'o1' })
    expect(g.picking).toBe(false)
  })

  it('is the thing it began on when the button comes up elsewhere', () => {
    const { gate: g } = gate()
    g.handle('mousedown', on('o1'))
    expect(g.handle('mouseup', on('o2'))).toBe('swallow')
    expect(g.handle('click', on('o2'))).toEqual({ pick: 'o1' })
  })

  it('leaves what is no thing to the document', () => {
    const { gate: g } = gate()
    expect(g.handle('pointerdown', on(null))).toBe('pass')
    expect(g.handle('click', on(null))).toBe('pass')
  })

  it('does nothing while the caret is not in the box', () => {
    const { gate: g } = gate(false)
    expect(g.handle('mousedown', on('o1'))).toBe('pass')
    expect(g.handle('click', on('o1'))).toBe('pass')
  })

  it('forgets a click that never ended when the next one begins', () => {
    const { gate: g } = gate()
    g.handle('mousedown', on('o1'))
    expect(g.handle('mousedown', on(null))).toBe('pass')
    expect(g.handle('click', on(null))).toBe('pass')
  })

  it('forgets a click when the box loses the caret', () => {
    const { gate: g } = gate()
    g.handle('mousedown', on('o1'))
    g.reset()
    expect(g.handle('click', on('o1'))).toBe('pass')
  })
})

describe('finding the thing under the pointer', () => {
  it('reads the id off the nearest marked element', () => {
    expect(thingAt(el('s2'))).toBe('s2')
    expect(thingAt(el(null))).toBeNull()
    expect(thingAt(null)).toBeNull()
    expect(thingAt({})).toBeNull()
  })
})
