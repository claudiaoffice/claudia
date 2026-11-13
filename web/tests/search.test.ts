import { describe, expect, it } from 'vitest'
import { createTranslator } from '~/lib/i18n'
import {
  addKept,
  emptyModel,
  explainError,
  excerptOf,
  keptNames,
  latest,
  marksFor,
  newCondition,
  newPart,
  normalizeReplacement,
  sentence,
  shownMatches,
  toPattern,
  toQuery,
  whereLabel,
  whyLeftOut,
  type SearchMatch,
  type SearchModel,
} from '~/lib/search'

const t = createTranslator({})

function builder(patch: Partial<SearchModel> = {}): SearchModel {
  return { ...emptyModel(), mode: 'builder', ...patch }
}
const part = (what: Parameters<typeof newPart>[0], extra: Partial<ReturnType<typeof newPart>> = {}) => ({ ...newPart(what), ...extra })

describe('what a search asks the server', () => {
  it('has nothing to ask while nothing is typed', () => {
    expect(toQuery(emptyModel())).toBeNull()
    expect(toQuery(builder())).toBeNull()
    expect(toQuery({ ...emptyModel(), mode: 'pattern' })).toBeNull()
  })

  it('sends the quick field as text, which the server never reads as a pattern', () => {
    const model = { ...emptyModel(), quick: 'Rates (2027)', matchCase: true, whole: 'entire' as const }
    expect(toQuery(model)).toEqual({ mode: 'text', text: 'Rates (2027)', match_case: true, whole: 'entire' })
  })

  it('sends the builder as parts and conditions, leaving out what is at its default', () => {
    const model = builder({
      parts: [part('any_of', { chars: '€$£' }), part('number', { keep: 'amount' })],
      conditions: [{ ...newCondition('not_contains'), text: 'EUR' }],
    })
    expect(toQuery(model)).toEqual({
      mode: 'builder',
      parts: [{ what: 'any_of', chars: '€$£' }, { what: 'number', keep: 'amount' }],
      conditions: [{ kind: 'not_contains', text: 'EUR' }],
      combine: 'all',
      match_case: false,
      whole: 'none',
    })
  })

  it('sends how many, with its numbers only where they belong', () => {
    const model = builder({
      parts: [
        part('digit', { count: 'exactly', n: 4 }),
        part('space', { count: 'between', n: 1, m: 3 }),
        part('letter', { count: 'one_or_more' }),
      ],
    })
    expect(toQuery(model)?.parts).toEqual([
      { what: 'digit', count: 'exactly', n: 4 },
      { what: 'space', count: 'between', n: 1, m: 3 },
      { what: 'letter', count: 'one_or_more' },
    ])
  })

  it('leaves out a part that has not been given what it needs yet', () => {
    const model = builder({ parts: [part('text', { value: '' }), part('any_of', { chars: '' }), part('digit')] })
    expect(toQuery(model)?.parts).toEqual([{ what: 'digit' }])
  })

  it('leaves out a condition that is still empty', () => {
    const model = builder({ parts: [part('digit')], conditions: [{ ...newCondition('contains'), text: '' }] })
    expect(toQuery(model)?.conditions).toEqual([])
  })

  it('can search with conditions alone: the whole cell is the match', () => {
    const model = builder({ conditions: [{ ...newCondition('starts_with'), text: 'Total' }] })
    expect(toQuery(model)).toMatchObject({ parts: [], conditions: [{ kind: 'starts_with', text: 'Total' }] })
  })

  it('sends the characters of an "any of" condition as chars', () => {
    const model = builder({ conditions: [{ ...newCondition('contains_any_of'), text: '€$' }] })
    expect(toQuery(model)?.conditions).toEqual([{ kind: 'contains_any_of', chars: '€$' }])
  })

  it('sends the typed pattern in its own three fields', () => {
    const model: SearchModel = { ...emptyModel(), mode: 'pattern', pattern: { find: '€\\s?(\\d+)', filter: '^(?!.*EUR)', replace: '\\1 EUR' } }
    expect(toQuery(model, { replace: true })).toEqual({
      mode: 'pattern',
      find: '€\\s?(\\d+)',
      filter: '^(?!.*EUR)',
      replace: '\\1 EUR',
      match_case: false,
    })
    expect(toQuery(model)).not.toHaveProperty('replace')
  })

  it('adds the replacement only when asked, as texts and kept parts', () => {
    const model = builder({
      parts: [part('any_of', { chars: '€' }), part('number', { keep: 'amount' })],
      replace: [{ keep: 'amount' }, { text: ' EUR' }],
    })
    expect(toQuery(model)).not.toHaveProperty('replace')
    expect(toQuery(model, { replace: true })?.replace).toEqual([{ keep: 'amount' }, { text: ' EUR' }])
  })

  it('replaces a quick text by plain text', () => {
    const model = { ...emptyModel(), quick: '€', replace: [{ text: 'EUR ' }] }
    expect(toQuery(model, { replace: true })).toMatchObject({ mode: 'text', text: '€', replace: [{ text: 'EUR ' }] })
  })

  it('does not send a kept part that is no longer there', () => {
    const model = builder({ parts: [part('digit')], replace: [{ keep: 'gone' }, { text: 'x' }] })
    expect(toQuery(model, { replace: true })?.replace).toEqual([{ text: 'x' }])
  })

  it('a replacement of nothing is an empty list, which deletes what was found', () => {
    expect(toQuery({ ...emptyModel(), quick: 'x', replace: [] }, { replace: true })?.replace).toEqual([])
  })
})

describe('kept parts and the replacement', () => {
  it('lists the names parts are kept under, once each', () => {
    const model = builder({ parts: [part('number', { keep: 'amount' }), part('digit', { keep: '  ' }), part('letter', { keep: 'amount' })] })
    expect(keptNames(model)).toEqual(['amount'])
  })

  it('names a part when it is kept, so that two never share a name', () => {
    const model = builder({ parts: [part('number', { keep: 'number' }), part('digit')] })
    const named = addKept(model, 1)
    expect(named.parts[1]!.keep).toBe('digit')
    expect(addKept(named, 0).parts[0]!.keep).toBe('number')
    const again = addKept({ ...named, parts: [...named.parts, part('digit')] }, 2)
    expect(again.parts[2]!.keep).toBe('digit 2')
  })

  it('drops empty texts from a replacement but keeps the order', () => {
    expect(normalizeReplacement([{ text: '' }, { keep: 'a' }, { text: ' EUR' }, { text: '' }])).toEqual([{ keep: 'a' }, { text: ' EUR' }])
  })
})

describe('the sentence that says what the builder does', () => {
  it('describes the example of the design: any of three signs, in cells without EUR', () => {
    const model = builder({
      parts: [part('any_of', { chars: '€ $ £' })],
      conditions: [{ ...newCondition('not_contains'), text: 'EUR' }],
    })
    expect(sentence(model, t)).toBe('Finds any one of € $ £ in cells that do not contain “EUR”.')
  })

  it('names each part with how many of it, in order', () => {
    const model = builder({
      parts: [part('text', { value: '€' }), part('space', { count: 'optional' }), part('number', { keep: 'amount' })],
    })
    expect(sentence(model, t)).toBe('Finds the text “€”, then a space, optionally, then a number (kept as “amount”).')
  })

  it('counts out loud', () => {
    expect(sentence(builder({ parts: [part('digit', { count: 'exactly', n: 4 })] }), t)).toBe('Finds a digit, exactly 4 times.')
    expect(sentence(builder({ parts: [part('digit', { count: 'between', n: 2, m: 5 })] }), t)).toBe('Finds a digit, 2 to 5 times.')
    expect(sentence(builder({ parts: [part('digit', { count: 'one_or_more' })] }), t)).toBe('Finds a digit, one or more times.')
    expect(sentence(builder({ parts: [part('letter', { count: 'any' })] }), t)).toBe('Finds a letter, any number of times.')
  })

  it('says what it is, not how: places, sets and references', () => {
    expect(sentence(builder({ parts: [part('start'), part('none_of', { chars: '0-9' })] }), t)).toBe(
      'Finds the start of the cell, then any character except 0-9.',
    )
    expect(sentence(builder({ parts: [part('any')] }), t)).toBe('Finds any character.')
    expect(sentence(builder({ parts: [part('cellref')] }), t)).toBe('Finds a cell reference.')
    expect(sentence(builder({ parts: [part('end')] }), t)).toBe('Finds the end of the cell.')
  })

  it('joins several conditions with and, or with or', () => {
    const conditions = [
      { ...newCondition('starts_with'), text: 'A' },
      { ...newCondition('ends_with'), text: 'Z' },
    ]
    expect(sentence(builder({ conditions }), t)).toBe('Finds the cells that start with “A” and end with “Z”.')
    expect(sentence(builder({ conditions, combine: 'any' }), t)).toBe('Finds the cells that start with “A” or end with “Z”.')
  })

  it('knows every condition', () => {
    const phrase = (kind: Parameters<typeof newCondition>[0], text: string) =>
      sentence(builder({ conditions: [{ ...newCondition(kind), text }] }), t)
    expect(phrase('contains', 'x')).toBe('Finds the cells that contain “x”.')
    expect(phrase('is', 'x')).toBe('Finds the cells that are exactly “x”.')
    expect(phrase('contains_any_of', 'xy')).toBe('Finds the cells that contain one of xy.')
    expect(phrase('not_contains_any_of', 'xy')).toBe('Finds the cells that contain none of xy.')
  })

  it('adds what whole cell and whole word mean', () => {
    const model = builder({ parts: [part('digit')], whole: 'entire' })
    expect(sentence(model, t)).toBe('Finds a digit. Only when it is the whole cell.')
    expect(sentence({ ...model, whole: 'word' }, t)).toBe('Finds a digit. Only whole words.')
  })

  it('has nothing to say about nothing, and skips what is not filled in', () => {
    expect(sentence(builder(), t)).toBe('')
    expect(sentence(builder({ parts: [part('text', { value: '' })] }), t)).toBe('')
  })

  it('is translatable as whole strings with placeholders', () => {
    const german = createTranslator({
      'Finds {parts}.': 'Findet {parts}.',
      'a digit': 'eine Ziffer',
      '{what}, exactly {n} times': '{what}, genau {n} Mal',
    })
    expect(sentence(builder({ parts: [part('digit', { count: 'exactly', n: 3 })] }), german)).toBe('Findet eine Ziffer, genau 3 Mal.')
  })
})

describe('errors in a typed pattern, in words', () => {
  it('says that a bracket is never closed, and where it is', () => {
    const e = explainError({ message: 'missing ), unterminated subpattern', field: 'find', position: 4 }, t)
    expect(e.headline).toBe('A bracket is never closed.')
    expect(e.detail).toBe('The “(” at character 5 has no “)”. Nothing is replaced.')
    expect(e.field).toBe('find')
  })

  it('knows the usual mistakes', () => {
    expect(explainError({ message: 'unbalanced parenthesis', field: 'find', position: 3 }, t).headline).toBe('A closing bracket has no opening one.')
    expect(explainError({ message: 'nothing to repeat', field: 'filter', position: 0 }, t).headline).toBe('Something is repeated that is not there.')
    expect(explainError({ message: 'unterminated character set', field: 'find', position: 2 }, t).headline).toBe('A square bracket is never closed.')
    expect(explainError({ message: 'bad escape \\q', field: 'find', position: 1 }, t).headline).toBe('This backslash does not mean anything here.')
  })

  it('says why a pattern that could take forever is not run', () => {
    const e = explainError({ message: 'this pattern could backtrack without end on some texts: it repeats something', field: 'find', position: null }, t)
    expect(e.headline).toBe('This pattern could take far too long on some texts.')
    expect(e.detail).toBe('It is not run, so nothing is found or replaced. Try making the repeated part more specific.')
  })

  it('names the field the mistake is in', () => {
    expect(explainError({ message: 'nothing to repeat', field: 'filter', position: 0 }, t).where).toBe('Only in cells matching')
    expect(explainError({ message: 'invalid group reference 3', field: 'replace', position: null }, t).where).toBe('Replace with')
  })

  it('shows the server’s own sentence for anything it does not know', () => {
    const e = explainError({ message: 'something new', field: 'query', position: null }, t)
    expect(e).toMatchObject({ headline: 'something new', detail: '' })
  })
})

describe('where a match is and how it reads', () => {
  const match: SearchMatch = {
    sheet: 's1',
    row: 1,
    col: 1,
    kind: 'text',
    number: 0,
    start: 2,
    end: 5,
    parts: [],
    after: null,
    text: '€ 980 (EUR)',
    excerpt: [2, 5],
    clipped: [false, false],
  }

  it('names the cell with its sheet', () => {
    expect(whereLabel(match, (id) => (id === 's1' ? 'Costs' : id))).toBe('Costs!B2')
  })

  it('cuts the excerpt into before, match and after', () => {
    expect(excerptOf(match)).toEqual({ before: '€ ', hit: '980', after: ' (EUR)' })
  })

  it('marks a cut excerpt with dots', () => {
    const cut = { ...match, text: 'x'.repeat(60) + 'NEEDLE' + 'y'.repeat(60), excerpt: [60, 66] as [number, number], start: 500, end: 506, clipped: [true, true] as [boolean, boolean] }
    expect(excerptOf(cut)).toEqual({ before: '…' + 'x'.repeat(60), hit: 'NEEDLE', after: 'y'.repeat(60) + '…' })
  })
})

describe('the matches a person asked to see', () => {
  const at = (row: number, kind: SearchMatch['kind'], number = 0): SearchMatch => ({
    sheet: 's1',
    row,
    col: 0,
    kind,
    number,
    start: 0,
    end: 1,
    parts: [],
    after: null,
    text: 'x',
    excerpt: [0, 1],
    clipped: [false, false],
  })
  const all = [at(0, 'text'), at(1, 'formula'), at(2, 'value'), at(3, 'text')]

  it('shows only the kinds that are switched on', () => {
    expect(shownMatches(all, { text: true, formulas: false, values: false }).map((m) => m.row)).toEqual([0, 3])
    expect(shownMatches(all, { text: true, formulas: true, values: true }).map((m) => m.row)).toEqual([0, 1, 2, 3])
  })

  it('marks cells on one sheet: every match, the current one apart, formulas known', () => {
    const marks = marksFor([at(0, 'text'), at(1, 'formula'), { ...at(2, 'text'), sheet: 's2' }], 's1', 1)
    expect([...marks.cells.entries()].map(([k, v]) => [k, v.current, v.formula])).toEqual([
      [0, false, false],
      [100_000, true, true],
    ])
  })

  it('shows one mark per cell, the current one winning', () => {
    const marks = marksFor([at(0, 'text', 0), at(0, 'text', 1)], 's1', 1)
    expect(marks.cells.size).toBe(1)
    expect(marks.cells.get(0)?.current).toBe(true)
  })

  it('shows what a replacement would make of a cell, and which cells it skips', () => {
    const marks = marksFor([at(0, 'text')], 's1', null, {
      changes: [{ sheet: 's1', row: 0, col: 0, kind: 'text', before: 'x', after: 'y' }, { sheet: 's2', row: 0, col: 0, kind: 'text', before: 'a', after: 'b' }],
      skipped: [{ sheet: 's1', row: 3, col: 0, kind: 'text', reason: 'locked', by: 'anna' }],
    })
    expect(marks.after.get(0)).toBe('y')
    expect(marks.after.size).toBe(1)
    expect(marks.blocked.get(300_000)).toBe('anna')
  })
})

describe('only the newest answer counts', () => {
  it('drops the answer of a request that a newer one has overtaken', async () => {
    const wait = latest<string>()
    let finishFirst: (v: string) => void = () => {}
    const first = wait(() => new Promise<string>((resolve) => (finishFirst = resolve)))
    const second = wait(() => Promise.resolve('second'))
    finishFirst('first')
    expect(await second).toBe('second')
    expect(await first).toBeNull()
  })

  it('gives the answer when nothing overtook it', async () => {
    const wait = latest<number>()
    expect(await wait(() => Promise.resolve(7))).toBe(7)
  })

  it('treats a failure as no answer, so that typing is never interrupted by it', async () => {
    const wait = latest<number>()
    expect(await wait(() => Promise.reject(new Error('lost')))).toBeNull()
  })
})

describe('why a cell was left out', () => {
  it('says what the cell does that a condition did not allow', () => {
    expect(whyLeftOut({ kind: 'not_contains', text: 'EUR' }, t)).toBe('contain “EUR”')
    expect(whyLeftOut({ kind: 'contains', text: 'EUR' }, t)).toBe('do not contain “EUR”')
    expect(whyLeftOut({ kind: 'starts_with', text: 'A' }, t)).toBe('do not start with “A”')
    expect(whyLeftOut({ kind: 'ends_with', text: 'Z' }, t)).toBe('do not end with “Z”')
    expect(whyLeftOut({ kind: 'is', text: 'x' }, t)).toBe('are not exactly “x”')
    expect(whyLeftOut({ kind: 'contains_any_of', chars: 'xy' }, t)).toBe('contain none of xy')
    expect(whyLeftOut({ kind: 'not_contains_any_of', chars: 'xy' }, t)).toBe('contain one of xy')
  })

  it('has one sentence for a cell that did not match the person’s own filter pattern', () => {
    expect(whyLeftOut({ kind: 'filter' }, t)).toBe('do not match the pattern for cells')
  })
})

describe('writing the pattern yourself', () => {
  it('starts from what the builder made and keeps what else was chosen', () => {
    const model = builder({ matchCase: true, whole: 'entire', parts: [part('digit')] })
    const typed = toPattern(model, { find: '\\d', filter: '^x', replace: '' })
    expect(typed).toMatchObject({ mode: 'pattern', matchCase: true, pattern: { find: '\\d', filter: '^x', replace: '' } })
    expect(model.mode).toBe('builder') // (the builder's own state is left as it was, to go back to)
  })
})
