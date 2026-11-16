// The heading level of a style, as the style editor offers it (E9.22): the style's own setting, with what "as its
// parent" means for this style said in words, so that nobody has to know the parent to read the choice.
import { describe, expect, it } from 'vitest'
import { headingChoices, headingSetting, settingValue } from '~/lib/heading-level'
import type { StyleView } from '~/lib/style-css'

const view = (id: string, based_on: string | null, heading: number | null, heading_level?: number | 'body') =>
  ({ id, name: id === 'h2' ? 'Heading 2' : id, based_on, heading, ...(heading_level === undefined ? {} : { heading_level }) }) as unknown as StyleView
const STYLES = [view('body', null, null), view('h2', 'body', 2, 2), view('h2x', 'h2', 2), view('aside', 'h2', null, 'body')]

describe('the heading level in the style editor', () => {
  it('offers as the parent, no heading, the title and the nine levels, saying what the parent gives', () => {
    const choices = headingChoices(STYLES[2]!, STYLES)
    expect(choices.map((c) => c.value)).toEqual(['inherit', 'body', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9'])
    expect(choices[0]!.label).toBe('As “Heading 2”: Level 2')
    expect(choices[1]!.label).toBe('No heading')
    expect(choices[2]!.label).toBe('Title')
    expect(choices[4]!.label).toBe('Level 2')
    expect(headingChoices(STYLES[0]!, STYLES)[0]!.label).toBe('No heading (no parent)')
  })
  it('shows a style’s own setting and turns a choice back into one', () => {
    expect(STYLES.map((s) => settingValue(s))).toEqual(['inherit', '2', 'inherit', 'body'])
    expect(['inherit', 'body', '0', '7'].map(headingSetting)).toEqual([null, 'body', 0, 7])
  })
})
