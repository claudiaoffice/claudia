import { describe, expect, it } from 'vitest'
import type { Block } from '~/lib/blocks'
import { itemLayout } from '~/lib/list-layout'
import type { ListInfo, SchemeInfo } from '~/lib/text-session'

const schemes: SchemeInfo[] = [
  { id: 'bullets', name: 'Bullets', kind: 'bullet', indent: 1.6, gap: 0.25 },
  { id: 'numbers', name: 'Numbers', kind: 'number', indent: 2, gap: 0.5 },
]
const lists: ListInfo[] = [
  { id: 'l1', scheme: 'bullets', start: 1, name: null },
  { id: 'l2', scheme: 'numbers', start: 1, name: null },
]
const plain = (id: string): Block => ({ id, style: 'body', text: id, runs: [] })
const item = (id: string, list: string, level = 0): Block => ({ ...plain(id), item: { list, level } })
const layout = (blocks: Block[], at: number) => itemLayout(blocks, at, lists, schemes)

describe('where a list item sits', () => {
  it('a plain paragraph has no layout of its own', () => {
    expect(layout([plain('a')], 0)).toBeNull()
  })

  it('an item is moved in one step per level, the marker hanging in the step before the text', () => {
    expect(layout([item('a', 'l1', 0)], 0)).toEqual({ '--item-left': '0em', '--item-step': '1.6em', '--item-pad': '1.6em' })
    expect(layout([item('a', 'l2', 2)], 0)).toEqual({ '--item-left': '4em', '--item-step': '2em', '--item-pad': '6em' })
  })

  it('between two items of one list the gap is the scheme’s, whatever their levels', () => {
    const blocks = [item('a', 'l2', 0), item('b', 'l2', 1), item('c', 'l2', 0)]
    expect(layout(blocks, 0)!['--item-gap']).toBe('0.5em')
    expect(layout(blocks, 1)!['--item-gap']).toBe('0.5em')
    expect(layout(blocks, 2)!['--item-gap']).toBeUndefined() // the last keeps the paragraph's own margin
  })

  it('a note or another list after an item ends the tight run', () => {
    expect(layout([item('a', 'l1'), plain('n')], 0)!['--item-gap']).toBeUndefined()
    expect(layout([item('a', 'l1'), item('b', 'l2')], 0)!['--item-gap']).toBeUndefined()
  })

  it('knows a sensible default for a list or scheme it has not been told about yet', () => {
    expect(itemLayout([item('a', 'ghost')], 0, [], [])!['--item-step']).toBe('1.6em')
  })
})
