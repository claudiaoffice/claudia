// What the search panel says in its summary line and on its "Look in" button, and that the help it opens is there.
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { createTranslator } from '~/lib/i18n'
import { lookInSummary, matchSummary } from '~/lib/search'
import { textSearchHost } from '~/lib/text-search-host'
import { slideSearchHost } from '~/lib/slide-search-host'
import { sheetSearchHost } from '~/lib/sheet-search-host'

const t = createTranslator({})

describe('the line above the matches', () => {
  it('says there are none, or one', () => {
    expect(matchSummary(0, 0, 'text', t)).toBe('No matches')
    expect(matchSummary(1, 1, 'text', t)).toBe('One match')
  })

  it('says only how many matches in a text: a person thinks of the document as one text', () => {
    expect(matchSummary(9, 6, 'text', t)).toBe('9 matches')
  })

  it('says in how many cells in a workbook, where a person does think in cells', () => {
    expect(matchSummary(9, 6, 'cell', t)).toBe('9 matches in 6 cells')
  })

  it('does not say "in 4 cells" when every match is in a cell of its own', () => {
    expect(matchSummary(4, 4, 'cell', t)).toBe('4 matches')
  })
})

describe('what the "Look in" button says', () => {
  const kinds = (on: boolean[]) => ['Text', 'Headings', 'Remarks', 'Objects', 'Descriptions'].slice(0, on.length).map((label, i) => ({ label, on: on[i]! }))

  it('says everything when every kind is on, with how many there are', () => {
    expect(lookInSummary(kinds([true, true, true, true, true]), t)).toBe('Everything (5)')
  })

  it('names one or two kinds', () => {
    expect(lookInSummary(kinds([true, false, false, false, false]), t)).toBe('Text (1)')
    expect(lookInSummary(kinds([true, false, true, false, false]), t)).toBe('Text, Remarks (2)')
  })

  it('counts instead of naming three or more, so that it fits however many kinds an app has', () => {
    expect(lookInSummary(kinds([true, true, true, false, false]), t)).toBe('3 of 5 kinds')
  })

  it('says nothing when nothing is on', () => {
    expect(lookInSummary(kinds([false, false]), t)).toBe('Nothing')
  })
})

describe('the help the panel opens', () => {
  const session = { state: { role: 'owner' }, searchFind: async () => null }
  const hosts = {
    composes: textSearchHost({ session: session as never, goTo: () => {}, t }),
    creates: slideSearchHost({ session: session as never, showNotes: () => {}, t }),
    computes: sheetSearchHost({ session: session as never, selection: () => ({}) as never, goTo: () => {}, t }),
  }

  it.each(Object.entries(hosts))('is the topic %s ships, by the id its file carries', (app, host) => {
    const file = new URL(`../../packages/claudia-${app}/src/claudia_${app}/help/searching-and-replacing.md`, import.meta.url)
    const id = /^id:\s*(.+)$/m.exec(readFileSync(file, 'utf8'))?.[1]?.trim()
    expect(host.helpTopic).toBe(id)
  })
})
