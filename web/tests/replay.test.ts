import { describe, expect, it } from 'vitest'
import {
  WheelStepper,
  holderOf,
  firstFocus,
  groupStart,
  keyStep,
  nearest,
  stateOf,
  step,
  timeline,
  type Item,
} from '~/lib/replay'
import type { ChatMessage, Step } from '~/lib/base-session'

const entry = (n: number, author = 'ann', extra: Partial<Step> = {}): Step => ({
  revision: `main:${n}`,
  author,
  origin: 'do',
  time: `2026-11-14T16:0${n}:00Z`,
  label: 'Set cell',
  summary: `${author} set A${n}`,
  ...extra,
})
const say = (number: number, at: string | null, author = 'bob'): ChatMessage => ({
  number,
  author,
  to: '*',
  text: `message ${number}`,
  time: '2026-11-14T16:00:00Z',
  at,
})

const entries = [entry(1), entry(2, 'ann'), entry(3, 'bob'), entry(4, 'bob')]

describe('the timeline', () => {
  it('puts a chat message after the change it was written at', () => {
    const items = timeline(entries, [say(1, 'main:2'), say(2, null)], 'all')
    expect(items.map((i) => (i.kind === 'change' ? i.revision : `chat ${i.number}`))).toEqual([
      'chat 2', // written before the first change
      'main:1',
      'main:2',
      'chat 1',
      'main:3',
      'main:4',
    ])
  })

  it('puts a message that was written before there was anything at the very start', () => {
    const items = timeline(entries, [say(1, null)], 'all')
    expect(items[0]).toMatchObject({ kind: 'chat', number: 1 })
  })

  it('puts a message written at a change older than the history shown at the start too', () => {
    const items = timeline(entries, [say(1, 'main:0')], 'all')
    expect(items[0]).toMatchObject({ kind: 'chat', number: 1 })
    expect(items).toHaveLength(5)
  })

  it('shows only the changes, or only the conversation, when asked', () => {
    const chat = [say(1, 'main:2')]
    expect(timeline(entries, chat, 'steps').every((i) => i.kind === 'change')).toBe(true)
    expect(timeline(entries, chat, 'chat')).toHaveLength(1)
  })

  it('gives each row the state of the document it stands for', () => {
    const items = timeline(entries, [say(1, 'main:2'), say(2, null)], 'all')
    expect(items.map((i) => i.state)).toEqual([null, 'main:1', 'main:2', 'main:2', 'main:3', 'main:4'])
    expect(stateOf(items[0]!)).toBeNull() // before the first change there is nothing to see yet
  })
})

describe('stepping', () => {
  const items: Item[] = timeline(entries, [], 'all')

  it('moves one row and stops at the ends', () => {
    expect(step(items, 1, 1)).toBe(2)
    expect(step(items, 3, 1)).toBe(3)
    expect(step(items, 0, -1)).toBe(0)
  })

  it('moves to where the next author starts when stepping by author', () => {
    expect(step(items, 0, 1, 'author')).toBe(2) // ann ann | bob bob
    expect(step(items, 2, -1, 'author')).toBe(0)
    expect(step(items, 3, -1, 'author')).toBe(2)
    expect(step(items, 3, 1, 'author')).toBe(3)
  })

  it('knows where a run of one author starts', () => {
    expect(groupStart(items, 3)).toBe(2)
    expect(groupStart(items, 1)).toBe(0)
  })

  it('finds the row of a revision, or the nearest one before it', () => {
    expect(nearest(items, 'main:3')).toBe(2)
    expect(nearest(items, 'main:99')).toBe(3)
    expect(nearest([], 'main:1')).toBe(-1)
  })
})

describe('the wheel', () => {
  it('turns a notch of a mouse wheel into one step, whichever system measures it', () => {
    const wheel = new WheelStepper()
    expect(wheel.feed(100)).toBe(1)
    expect(wheel.feed(120)).toBe(1)
    expect(wheel.feed(-100)).toBe(-1)
    expect(wheel.feed(0)).toBe(0)
  })

  it('gathers the small deltas of a trackpad until they make a step', () => {
    const wheel = new WheelStepper()
    const steps = [30, 30, 30, 30].map((d) => wheel.feed(d))
    expect(steps).toEqual([0, 1, 0, 1])
  })

  it('does not carry a half step into the other direction', () => {
    const wheel = new WheelStepper()
    wheel.feed(30)
    expect(wheel.feed(-30)).toBe(0)
    expect(wheel.feed(-30)).toBe(-1)
  })
})

describe('the keys', () => {
  it('says what Alt+PageUp, Alt+PageDown, Alt+Home, End and Escape mean', () => {
    expect(keyStep({ key: 'PageUp', altKey: true })).toEqual({ by: -1 })
    expect(keyStep({ key: 'PageDown', altKey: true })).toEqual({ by: 1 })
    expect(keyStep({ key: 'Home', altKey: true })).toEqual({ to: 'start' })
    expect(keyStep({ key: 'End' })).toEqual({ to: 'now' })
    expect(keyStep({ key: 'Escape' })).toEqual({ to: 'now' })
    expect(keyStep({ key: 'PageUp' })).toBeNull()
    expect(keyStep({ key: 'a', altKey: true })).toBeNull()
  })
})

describe('where to look', () => {
  const objects = { kind: 'objects', holder: 's2', ids: ['o1'] } as const
  const cells = { kind: 'cells', range: { first: { row: 3, col: 1, sheet: 'sales' }, last: { row: 4, col: 1, sheet: 'sales' } } } as const
  const text = { kind: 'text', paragraph: 'b4', start: 0, end: 3 } as const

  it('takes the first place a step touched', () => {
    expect(firstFocus([cells, objects])).toBe(cells)
    expect(firstFocus([])).toBeNull()
  })

  it('says which slide, sheet or paragraph a place lies in', () => {
    expect(holderOf(objects)).toBe('s2')
    expect(holderOf(cells)).toBe('sales')
    expect(holderOf(text)).toBe('b4')
    expect(holderOf(null)).toBeNull()
  })
})

describe('who can only look', () => {
  it('is somebody who views, or anybody while the past is shown', async () => {
    const { lookOnly, roleNow } = await import('~/lib/replay')
    expect(lookOnly({ me: { role: 'editor' }, replay: null })).toBe(false)
    expect(lookOnly({ me: { role: 'editor' } })).toBe(false)
    expect(lookOnly({ me: { role: 'viewer' }, replay: null })).toBe(true)
    expect(lookOnly({ me: { role: 'editor' }, replay: {} })).toBe(true)
    expect(roleNow({ me: { role: 'owner' }, replay: {} })).toBe('viewer')
    expect(roleNow({ me: { role: 'owner' }, replay: null })).toBe('owner')
  })
})

describe('what a wheel event moved', () => {
  it('counts lines and pages as pixels, and Shift+wheel by the sideways delta', async () => {
    const { wheelDelta } = await import('~/lib/replay')
    expect(wheelDelta({ deltaY: 100 })).toBe(100)
    expect(wheelDelta({ deltaY: 3, deltaMode: 1 })).toBe(120)
    expect(wheelDelta({ deltaY: 1, deltaMode: 2 })).toBe(800)
    expect(wheelDelta({ deltaY: 0, deltaX: -100, shiftKey: true })).toBe(-100)
    expect(wheelDelta({ deltaY: 50, deltaX: -100, shiftKey: true })).toBe(50)
  })
})
