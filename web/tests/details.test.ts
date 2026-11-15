import { describe, expect, it } from 'vitest'
import {
  filterByTag,
  filterListed,
  saveDetails,
  summaryOf,
  addTags,
  tagChoices,
  tagCounts,
  tagsFromText,
  type Listed,
} from '~/lib/open'
import { ProtocolError, type LinkLike } from '~/lib/protocol'

const listed = (id: string, description = '', tags: string[] = [], app = 'computes'): Listed => ({
  id,
  app,
  modified: '2026-11-15T10:00:00Z',
  online: 0,
  description,
  tags,
})

describe('searching the list by tags and descriptions', () => {
  const docs = [
    listed('forecast-q3', 'Cash-flow forecast, **Q3**', ['finance', 'forecast']),
    listed('lab-notes', 'Titration series', ['science']),
    listed('untitled-7'),
  ]
  it('finds a word in the description or in a tag, accents and case ignored', () => {
    expect(filterListed(docs, 'CASH-FLOW').map((d) => d.id)).toEqual(['forecast-q3'])
    expect(filterListed(docs, 'science').map((d) => d.id)).toEqual(['lab-notes'])
    expect(filterListed(docs, 'titration finance')).toEqual([])
  })
  it('still finds by id, and copes with a server that says nothing of descriptions and tags', () => {
    const old = [{ id: 'Budget', app: 'computes', modified: '', online: 0 }]
    expect(filterListed(old, 'budget')).toHaveLength(1)
    expect(filterListed(old, 'finance')).toEqual([])
  })
  it('says where a word was found, so that the row can mark the hit', () => {
    expect(filterListed(docs, 'forecast').map((d) => d.id)).toEqual(['forecast-q3'])
  })
  it('narrows to the documents that carry a tag', () => {
    expect(filterByTag(docs, 'finance').map((d) => d.id)).toEqual(['forecast-q3'])
    expect(filterByTag(docs, '')).toHaveLength(3)
    expect(filterByTag(docs, 'FINANCE')).toHaveLength(1)
  })
  it('counts the tags of a place, the most used first and then in alphabetical order', () => {
    const more = [...docs, listed('a', '', ['finance']), listed('b', '', ['2027', 'science'])]
    expect(tagCounts(more)).toEqual([
      { tag: 'finance', count: 2 },
      { tag: 'science', count: 2 },
      { tag: '2027', count: 1 },
      { tag: 'forecast', count: 1 },
    ])
  })
})

describe('the words a person types for tags', () => {
  it('splits at commas, trims, lower-cases and drops repeats and empties', () => {
    expect(tagsFromText(' Finance, 2027 ,finance,, Q3 ')).toEqual(['finance', '2027', 'q3'])
    expect(tagsFromText('')).toEqual([])
  })
  it('offers what the place already uses, matching the start of the word and not yet taken', () => {
    const counts = [
      { tag: 'forms', count: 1 },
      { tag: 'forecast', count: 2 },
      { tag: 'finance', count: 4 },
    ]
    expect(tagChoices(counts, 'fo', ['forecast'])).toEqual([{ tag: 'forms', count: 1 }])
    expect(tagChoices(counts, '', [])).toHaveLength(3)
  })
})

describe('adding what was typed to the tags', () => {
  it('adds every tag of the text at once, in order, and keeps those already there', () => {
    expect(addTags(['a'], 'Finance, forecast,')).toEqual({ tags: ['a', 'finance', 'forecast'], problem: '' })
    expect(addTags([], 'x')).toEqual({ tags: ['x'], problem: '' })
  })
  it('does not add one twice', () => {
    expect(addTags(['a'], 'A, b').tags).toEqual(['a', 'b'])
  })
  it('stops at ten tags and says so', () => {
    const ten = Array.from({ length: 10 }, (_, i) => `t${i}`)
    expect(addTags(ten, 'more')).toEqual({ tags: ten, problem: 'A document has at most 10 tags.' })
    expect(addTags(ten.slice(0, 9), 'a, b').tags).toHaveLength(10)
  })
  it('leaves out a tag that is too long and says so, and adds the others', () => {
    const result = addTags([], `${'x'.repeat(31)}, ok`)
    expect(result.tags).toEqual(['ok'])
    expect(result.problem).toBe('A tag has at most 30 characters.')
  })
})

describe('the one line a list shows of a description', () => {
  it('is the first line with its inline Markdown read as looks, never as HTML', () => {
    const spans = summaryOf('Budget with **three** scenarios\n\nSecond paragraph')
    expect(spans.map((s) => [s.text, s.bold])).toEqual([
      ['Budget with ', false],
      ['three', true],
      [' scenarios', false],
    ])
    expect(summaryOf('<img src=x onerror=alert(1)>').map((s) => s.text).join('')).toBe('<img src=x onerror=alert(1)>')
    expect(summaryOf('')).toEqual([])
  })
})

class FakeLink implements LinkLike {
  requests: [string, unknown][] = []
  closed = false
  constructor(private answer: () => unknown) {}
  async connect() {
    return {} as never
  }
  async request(method: string, params: unknown = {}) {
    this.requests.push([method, params])
    return this.answer() as never
  }
  onEvent() {}
  onClose() {}
  close() {
    this.closed = true
  }
}

describe('saving the details of a document from the front page', () => {
  it('asks the server with the owner’s password and closes the connection', async () => {
    const link = new FakeLink(() => ({ description: 'x', tags: ['a'] }))
    const saved = await saveDetails(() => link, 'secret', 'x', ['a'])
    expect(saved).toEqual({ description: 'x', tags: ['a'] })
    expect(link.requests).toEqual([['set_details', { password: 'secret', description: 'x', tags: ['a'] }]])
    expect(link.closed).toBe(true)
  })
  it('gives back a sentence for a refusal, and still closes', async () => {
    const link = new FakeLink(() => {
      throw new ProtocolError('unauthorized', 'that is not your current password')
    })
    expect(await saveDetails(() => link, 'nope', '', [])).toEqual({ error: 'that is not your current password' })
    expect(link.closed).toBe(true)
  })
})
