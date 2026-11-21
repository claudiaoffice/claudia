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
  type Paragraph,
  type Run,
  type TextEvent,
} from '~/lib/paragraphs'

const paragraph = (id: string, text: string, author: string | null = 'ann', style = 'body'): Paragraph => ({
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
    const paragraphs = [paragraph('b1', 'hello world')]
    expect(applyEvent(paragraphs, { type: 'text', paragraph: 'b1', offset: 5, removed: 0, inserted: ' big', runs: [[4, 'ben', null]] })).toBe(true)
    expect(paragraphs[0]!.text).toBe('hello big world')
    expect(paragraphs[0]!.runs).toEqual([[5, 'ann', null], [4, 'ben', null], [6, 'ann', null]])
    applyEvent(paragraphs, { type: 'text', paragraph: 'b1', offset: 0, removed: 6, inserted: '', runs: [] })
    expect(paragraphs[0]!.text).toBe('big world')
    expect(paragraphs[0]!.runs).toEqual([[3, 'ben', null], [6, 'ann', null]].map((r) => r) as Run[])
  })

  it('split cuts a paragraph in two, join puts it back', () => {
    const paragraphs = [paragraph('b1', 'one two')]
    applyEvent(paragraphs, { type: 'split', paragraph: 'b1', offset: 3, new_id: 'b2', style: 'heading-1' })
    expect(paragraphs.map((b) => [b.id, b.style, b.text])).toEqual([['b1', 'body', 'one'], ['b2', 'heading-1', ' two']])
    expect(paragraphs[1]!.runs).toEqual([[4, 'ann', null]])
    expect(applyEvent(paragraphs, { type: 'join', paragraph: 'b2', into: 'b1', at: 3 })).toBe(true)
    expect(paragraphs.map((b) => b.text)).toEqual(['one two'])
    expect(paragraphs[0]!.runs).toEqual([[7, 'ann', null]])
  })

  it('a style change sets the style', () => {
    const paragraphs = [paragraph('b1', 'x')]
    applyEvent(paragraphs, { type: 'style', paragraph: 'b1', style: 'title' })
    expect(paragraphs[0]!.style).toBe('title')
  })

  it('refuse an event that does not fit, so the caller can reload', () => {
    const paragraphs = [paragraph('b1', 'abc'), paragraph('b2', 'def')]
    expect(applyEvent(paragraphs, { type: 'text', paragraph: 'b9', offset: 0, removed: 0, inserted: 'x', runs: [[1, 'a', null]] })).toBe(false)
    expect(applyEvent(paragraphs, { type: 'text', paragraph: 'b1', offset: 2, removed: 5, inserted: '', runs: [] })).toBe(false)
    expect(applyEvent(paragraphs, { type: 'join', paragraph: 'b2', into: 'b1', at: 2 })).toBe(false)
    expect(applyEvent(paragraphs, { type: 'split', paragraph: 'b1', offset: 9, new_id: 'b3', style: 'body' })).toBe(false)
  })
})

describe('following events', () => {
  const insert = (offset: number, inserted: string): TextEvent => ({ type: 'text', paragraph: 'b1', offset, removed: 0, inserted, runs: [[inserted.length, 'x', null]] })
  const cut = (offset: number, removed: number): TextEvent => ({ type: 'text', paragraph: 'b1', offset, removed, inserted: '', runs: [] })
  const span = (start: number, end: number) => ({ paragraph: 'b1', start, end })

  it('a caret at the place of an insertion moves behind the new text', () => {
    expect(followPos({ paragraph: 'b1', offset: 3 }, insert(3, 'ab'))).toEqual({ paragraph: 'b1', offset: 5 })
    expect(followPos({ paragraph: 'b1', offset: 2 }, insert(3, 'ab'))).toEqual({ paragraph: 'b1', offset: 2 })
  })

  it('a stretch grows when text is typed inside it and moves when text is typed before it', () => {
    expect(followSpan(span(4, 9), insert(6, 'xx'))).toEqual(span(4, 11))
    expect(followSpan(span(4, 9), insert(2, 'xx'))).toEqual(span(6, 11))
    expect(followSpan(span(4, 9), insert(9, 'xx'))).toEqual(span(4, 9))
    expect(followSpan({ paragraph: 'b2', start: 4, end: 9 }, insert(2, 'xx'))).toEqual({ paragraph: 'b2', start: 4, end: 9 })
  })

  it('a deletion pulls things in, and what was cut away becomes empty', () => {
    expect(followSpan(span(4, 9), cut(0, 2))).toEqual(span(2, 7))
    expect(followSpan(span(4, 9), cut(3, 8))).toEqual(span(3, 3))
    expect(followPos({ paragraph: 'b1', offset: 6 }, cut(4, 4))).toEqual({ paragraph: 'b1', offset: 4 })
  })

  it('a split sends what is behind it to the new paragraph, a join takes it back', () => {
    const split: TextEvent = { type: 'split', paragraph: 'b1', offset: 5, new_id: 'b2', style: 'body' }
    expect(followSpan(span(7, 9), split)).toEqual({ paragraph: 'b2', start: 2, end: 4 })
    expect(followSpan(span(2, 9), split)).toEqual(span(2, 5))
    const join: TextEvent = { type: 'join', paragraph: 'b2', into: 'b1', at: 5 }
    expect(followSpan({ paragraph: 'b2', start: 2, end: 4 }, join)).toEqual(span(7, 9))
  })
})

describe('reading the text', () => {
  const paragraphs = [paragraph('b1', 'one two'), paragraph('b2', 'three'), paragraph('b3', 'four five')]

  it('orders positions and takes the text between them', () => {
    expect(before(paragraphs, { paragraph: 'b1', offset: 7 }, { paragraph: 'b2', offset: 0 })).toBe(true)
    expect(before(paragraphs, { paragraph: 'b2', offset: 1 }, { paragraph: 'b2', offset: 1 })).toBe(false)
    expect(textBetween(paragraphs, { paragraph: 'b1', offset: 4 }, { paragraph: 'b3', offset: 4 })).toBe('two\nthree\nfour')
    expect(textBetween(paragraphs, { paragraph: 'b3', offset: 4 }, { paragraph: 'b1', offset: 4 })).toBe('two\nthree\nfour')
    expect(textBetween(paragraphs, { paragraph: 'b2', offset: 1 }, { paragraph: 'b2', offset: 3 })).toBe('hr')
  })

  it('finds word boundaries for Ctrl+Backspace and Ctrl+Delete', () => {
    expect(wordStart('one two  three', 14)).toBe(9)
    expect(wordStart('one two  three', 8)).toBe(4)
    expect(wordStart('one', 0)).toBe(0)
    expect(wordEnd('one two', 0)).toBe(3)
    expect(wordEnd('one  two', 3)).toBe(8)
  })

  it('counts words', () => {
    expect(countWords(paragraphs)).toBe(5)
    expect(countWords([paragraph('b1', "It's a well-known fact — 42.")])).toBe(5)
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
    const paragraphs = [paragraph('b1', text)]
    const event: TextEvent = { type: 'text', paragraph: 'b1', offset: 2, removed: 1, inserted: '', runs: [] }
    expect(eventInUnits(paragraphs, event)).toMatchObject({ offset: 3, removed: 1 })
    expect(eventInUnits(paragraphs, { type: 'split', paragraph: 'b1', offset: 3, new_id: 'b2', style: 'body' })).toMatchObject({ offset: 4 })
    const typed: TextEvent = { type: 'text', paragraph: 'b1', offset: 1, removed: 0, inserted: '😀😀', runs: [[2, 'ann', null]] }
    expect(eventInUnits(paragraphs, typed)).toMatchObject({ offset: 1, runs: [[4, 'ann', null]] })
  })
})

describe('list items', () => {
  const item = (list: string, level = 0) => ({ list, level })

  it('an item event makes a paragraph an item and takes it out again', () => {
    const paragraphs = [paragraph('b1', 'one')]
    expect(applyEvent(paragraphs, { type: 'item', paragraph: 'b1', item: item('l1', 1) })).toBe(true)
    expect(paragraphs[0]!.item).toEqual(item('l1', 1))
    applyEvent(paragraphs, { type: 'item', paragraph: 'b1', item: null })
    expect(paragraphs[0]!.item).toBeNull()
    expect(applyEvent(paragraphs, { type: 'item', paragraph: 'b9', item: null })).toBe(false)
  })

  it('a labels event sets the markers it names and removes the ones it sends as null', () => {
    const paragraphs = [paragraph('b1', 'one'), paragraph('b2', 'two'), paragraph('b3', 'three')]
    paragraphs[0]!.label = { marker: '1.', path: [1] }
    expect(
      applyEvent(paragraphs, {
        type: 'labels',
        labels: { b1: null, b2: { marker: '•', path: null }, b3: { marker: 'a.', path: [1, 1] } },
      }),
    ).toBe(true)
    expect(paragraphs.map((b) => b.label ?? null)).toEqual([null, { marker: '•', path: null }, { marker: 'a.', path: [1, 1] }])
  })

  it('a split gives the new paragraph the item of the one it cuts, as the model does, but no label of its own yet', () => {
    const paragraphs = [paragraph('b1', 'one two')]
    paragraphs[0]!.item = item('l1', 2)
    paragraphs[0]!.label = { marker: 'i.', path: [1, 1, 1] }
    applyEvent(paragraphs, { type: 'split', paragraph: 'b1', offset: 3, new_id: 'b2', style: 'body' })
    expect(paragraphs[1]!.item).toEqual(item('l1', 2))
    expect(paragraphs[1]!.item).not.toBe(paragraphs[0]!.item) // the replica never shares what it may change
    expect(paragraphs[1]!.label).toBeUndefined()
    expect(paragraphs[0]!.label).toEqual({ marker: 'i.', path: [1, 1, 1] })
  })

  it('a join keeps the first paragraphs item and label', () => {
    const paragraphs = [paragraph('b1', 'one'), paragraph('b2', ' two')]
    paragraphs[1]!.item = item('l1')
    paragraphs[1]!.label = { marker: '1.', path: [1] }
    applyEvent(paragraphs, { type: 'join', paragraph: 'b2', into: 'b1', at: 3 })
    expect(paragraphs).toHaveLength(1)
    expect(paragraphs[0]!.item ?? null).toBeNull()
    expect(paragraphs[0]!.label).toBeUndefined()
  })

  it('moves nothing and passes through the conversion of positions', () => {
    const events: TextEvent[] = [
      { type: 'item', paragraph: 'b1', item: item('l1') },
      { type: 'labels', labels: { b1: null } },
    ]
    for (const ev of events) {
      expect(eventInUnits([paragraph('b1', 'x')], ev)).toEqual(ev)
      expect(followSpan({ paragraph: 'b1', start: 1, end: 2 }, ev)).toEqual({ paragraph: 'b1', start: 1, end: 2 })
    }
  })
})
