import { describe, expect, it } from 'vitest'
import {
  applyEvent,
  before,
  countWords,
  deleteRuns,
  eventInUnits,
  pointOf,
  runsToPoints,
  runsToUnits,
  unitOf,
  followPos,
  followSpan,
  insertRuns,
  normalizeRuns,
  sliceRuns,
  textBetween,
  wordEnd,
  wordStart,
  type Block,
  type Run,
  type TextEvent,
} from '~/lib/blocks'

const block = (id: string, text: string, author: string | null = 'ann', style = 'body'): Block => ({
  id,
  style,
  text,
  runs: text ? [[text.length, author, null]] : [],
})

describe('runs', () => {
  it('join neighbours of the same origin and drop empty ones', () => {
    expect(normalizeRuns([[2, 'a', null], [0, 'b', null], [3, 'a', null]])).toEqual([[5, 'a', null]])
    expect(normalizeRuns([[2, 'a', null], [3, 'a', 'ai']])).toEqual([[2, 'a', null], [3, 'a', 'ai']])
  })

  it('are cut, deleted from and inserted into like the server does', () => {
    const runs: Run[] = [[4, 'ann', null], [3, 'ben', null]]
    expect(sliceRuns(runs, 2, 5)).toEqual([[2, 'ann', null], [1, 'ben', null]])
    expect(deleteRuns(runs, 2, 5)).toEqual([[2, 'ann', null], [2, 'ben', null]])
    expect(insertRuns(runs, 4, [[2, 'ai', null]])).toEqual([[4, 'ann', null], [2, 'ai', null], [3, 'ben', null]])
    expect(insertRuns(runs, 1, [[2, 'ann', null]])).toEqual([[6, 'ann', null], [3, 'ben', null]])
  })
})

describe('applying events', () => {
  it('typing and deleting keep the runs as long as the text', () => {
    const blocks = [block('b1', 'hello world')]
    expect(applyEvent(blocks, { type: 'text', block: 'b1', offset: 5, removed: 0, inserted: ' big', runs: [[4, 'ben', null]] })).toBe(true)
    expect(blocks[0]!.text).toBe('hello big world')
    expect(blocks[0]!.runs).toEqual([[5, 'ann', null], [4, 'ben', null], [6, 'ann', null]])
    applyEvent(blocks, { type: 'text', block: 'b1', offset: 0, removed: 6, inserted: '', runs: [] })
    expect(blocks[0]!.text).toBe('big world')
    expect(blocks[0]!.runs).toEqual([[3, 'ben', null], [6, 'ann', null]].map((r) => r) as Run[])
  })

  it('split cuts a paragraph in two, join puts it back', () => {
    const blocks = [block('b1', 'one two')]
    applyEvent(blocks, { type: 'split', block: 'b1', offset: 3, new_id: 'b2', style: 'heading-1' })
    expect(blocks.map((b) => [b.id, b.style, b.text])).toEqual([['b1', 'body', 'one'], ['b2', 'heading-1', ' two']])
    expect(blocks[1]!.runs).toEqual([[4, 'ann', null]])
    expect(applyEvent(blocks, { type: 'join', block: 'b2', into: 'b1', at: 3 })).toBe(true)
    expect(blocks.map((b) => b.text)).toEqual(['one two'])
    expect(blocks[0]!.runs).toEqual([[7, 'ann', null]])
  })

  it('a style change sets the style', () => {
    const blocks = [block('b1', 'x')]
    applyEvent(blocks, { type: 'style', block: 'b1', style: 'title' })
    expect(blocks[0]!.style).toBe('title')
  })

  it('refuse an event that does not fit, so the caller can reload', () => {
    const blocks = [block('b1', 'abc'), block('b2', 'def')]
    expect(applyEvent(blocks, { type: 'text', block: 'b9', offset: 0, removed: 0, inserted: 'x', runs: [[1, 'a', null]] })).toBe(false)
    expect(applyEvent(blocks, { type: 'text', block: 'b1', offset: 2, removed: 5, inserted: '', runs: [] })).toBe(false)
    expect(applyEvent(blocks, { type: 'join', block: 'b2', into: 'b1', at: 2 })).toBe(false)
    expect(applyEvent(blocks, { type: 'split', block: 'b1', offset: 9, new_id: 'b3', style: 'body' })).toBe(false)
  })
})

describe('following events', () => {
  const insert = (offset: number, inserted: string): TextEvent => ({ type: 'text', block: 'b1', offset, removed: 0, inserted, runs: [[inserted.length, 'x', null]] })
  const cut = (offset: number, removed: number): TextEvent => ({ type: 'text', block: 'b1', offset, removed, inserted: '', runs: [] })
  const span = (start: number, end: number) => ({ block: 'b1', start, end })

  it('a caret at the place of an insertion moves behind the new text', () => {
    expect(followPos({ block: 'b1', offset: 3 }, insert(3, 'ab'))).toEqual({ block: 'b1', offset: 5 })
    expect(followPos({ block: 'b1', offset: 2 }, insert(3, 'ab'))).toEqual({ block: 'b1', offset: 2 })
  })

  it('a stretch grows when text is typed inside it and moves when text is typed before it', () => {
    expect(followSpan(span(4, 9), insert(6, 'xx'))).toEqual(span(4, 11))
    expect(followSpan(span(4, 9), insert(2, 'xx'))).toEqual(span(6, 11))
    expect(followSpan(span(4, 9), insert(9, 'xx'))).toEqual(span(4, 9))
    expect(followSpan({ block: 'b2', start: 4, end: 9 }, insert(2, 'xx'))).toEqual({ block: 'b2', start: 4, end: 9 })
  })

  it('a deletion pulls things in, and what was cut away becomes empty', () => {
    expect(followSpan(span(4, 9), cut(0, 2))).toEqual(span(2, 7))
    expect(followSpan(span(4, 9), cut(3, 8))).toEqual(span(3, 3))
    expect(followPos({ block: 'b1', offset: 6 }, cut(4, 4))).toEqual({ block: 'b1', offset: 4 })
  })

  it('a split sends what is behind it to the new paragraph, a join takes it back', () => {
    const split: TextEvent = { type: 'split', block: 'b1', offset: 5, new_id: 'b2', style: 'body' }
    expect(followSpan(span(7, 9), split)).toEqual({ block: 'b2', start: 2, end: 4 })
    expect(followSpan(span(2, 9), split)).toEqual(span(2, 5))
    const join: TextEvent = { type: 'join', block: 'b2', into: 'b1', at: 5 }
    expect(followSpan({ block: 'b2', start: 2, end: 4 }, join)).toEqual(span(7, 9))
  })
})

describe('reading the text', () => {
  const blocks = [block('b1', 'one two'), block('b2', 'three'), block('b3', 'four five')]

  it('orders positions and takes the text between them', () => {
    expect(before(blocks, { block: 'b1', offset: 7 }, { block: 'b2', offset: 0 })).toBe(true)
    expect(before(blocks, { block: 'b2', offset: 1 }, { block: 'b2', offset: 1 })).toBe(false)
    expect(textBetween(blocks, { block: 'b1', offset: 4 }, { block: 'b3', offset: 4 })).toBe('two\nthree\nfour')
    expect(textBetween(blocks, { block: 'b3', offset: 4 }, { block: 'b1', offset: 4 })).toBe('two\nthree\nfour')
    expect(textBetween(blocks, { block: 'b2', offset: 1 }, { block: 'b2', offset: 3 })).toBe('hr')
  })

  it('finds word boundaries for Ctrl+Backspace and Ctrl+Delete', () => {
    expect(wordStart('one two  three', 14)).toBe(9)
    expect(wordStart('one two  three', 8)).toBe(4)
    expect(wordStart('one', 0)).toBe(0)
    expect(wordEnd('one two', 0)).toBe(3)
    expect(wordEnd('one  two', 3)).toBe(8)
  })

  it('counts words', () => {
    expect(countWords(blocks)).toBe(5)
    expect(countWords([block('b1', "It's a well-known fact — 42.")])).toBe(5)
  })
})

describe('characters outside the basic plane', () => {
  const text = 'a😀b' // 4 UTF-16 units, 3 code points

  it('are counted like the server counts them', () => {
    expect(unitOf(text, 2)).toBe(3)
    expect(unitOf(text, 3)).toBe(4)
    expect(unitOf(text, 9)).toBe(4)
    expect(pointOf(text, 3)).toBe(2)
    expect(pointOf(text, 4)).toBe(3)
  })

  it('make runs and events come out in units', () => {
    expect(runsToUnits(text, [[2, 'ann', null], [1, 'ben', null]])).toEqual([[3, 'ann', null], [1, 'ben', null]])
    expect(runsToPoints(text, [[3, 'ann', null], [1, 'ben', null]])).toEqual([[2, 'ann', null], [1, 'ben', null]])
    const blocks = [block('b1', text)]
    const event: TextEvent = { type: 'text', block: 'b1', offset: 2, removed: 1, inserted: '', runs: [] }
    expect(eventInUnits(blocks, event)).toMatchObject({ offset: 3, removed: 1 })
    expect(eventInUnits(blocks, { type: 'split', block: 'b1', offset: 3, new_id: 'b2', style: 'body' })).toMatchObject({ offset: 4 })
    const typed: TextEvent = { type: 'text', block: 'b1', offset: 1, removed: 0, inserted: '😀😀', runs: [[2, 'ann', null]] }
    expect(eventInUnits(blocks, typed)).toMatchObject({ offset: 1, runs: [[4, 'ann', null]] })
  })
})
