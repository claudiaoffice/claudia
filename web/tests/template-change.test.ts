import { describe, expect, it } from 'vitest'
import {
  languageChoices,
  noteProblem,
  templateSummary,
  themeSummary,
  type ChangePreview,
} from '~/lib/template-change'
import { createTranslator } from '~/lib/i18n'

const t = createTranslator({})

const PREVIEW: ChangePreview = {
  styles_changed: 9,
  styles_added: 0,
  styles_kept: 2,
  colours_changed: 1,
  colours_added: 0,
  layouts_matched: 5,
  layouts_added: 0,
  layouts_kept: 1,
  slides_reframed: 11,
  slides_unchanged: 6,
}

describe('the summary of Change template', () => {
  it('says what happens to the styles and the palette, the layouts and the slides, as the mock does', () => {
    expect(templateSummary(PREVIEW, t)).toEqual([
      { heading: 'Styles and palette', text: '9 styles replaced · 1 colour replaced · 2 of yours have no match and stay' },
      { heading: 'Layouts', text: '5 layouts matched by name · 1 of yours has no match and stays' },
      { heading: 'Slides', text: '11 slides take their layout’s frames · 6 slides are unchanged' },
    ])
  })

  it('says only the styles and the palette for Theme only', () => {
    expect(themeSummary(PREVIEW, t)).toEqual([
      { heading: 'Styles and palette', text: '9 styles replaced · 1 colour replaced · 2 of yours have no match and stay' },
      { heading: 'Layouts', text: 'stay as they are' },
      { heading: 'Slides', text: 'stay as they are' },
    ])
  })

  it('counts what is added, and says one for one', () => {
    const lines = templateSummary(
      { ...PREVIEW, styles_changed: 1, styles_added: 1, styles_kept: 0, colours_changed: 0, colours_added: 2, layouts_matched: 1, layouts_added: 2, layouts_kept: 0, slides_reframed: 1, slides_unchanged: 1 },
      t,
    )
    expect(lines[0]!.text).toBe('1 style replaced · 1 style added · 2 colours added')
    expect(lines[1]!.text).toBe('1 layout matched by name · 2 layouts added')
    expect(lines[2]!.text).toBe('1 slide takes its layout’s frames · 1 slide is unchanged')
  })

  it('says that nothing changes when nothing does', () => {
    const none: ChangePreview = { styles_changed: 0, styles_added: 0, styles_kept: 0, colours_changed: 0, colours_added: 0, layouts_matched: 0, layouts_added: 0, layouts_kept: 0, slides_reframed: 0, slides_unchanged: 0 }
    expect(templateSummary(none, t).map((l) => l.text)).toEqual(['nothing changes', 'nothing changes', 'nothing changes'])
  })
})

describe('the Save as template dialog', () => {
  it('refuses an empty name, and one longer than the server takes, before anything is sent', () => {
    expect(noteProblem({ name: '  ', purpose: 'x', language: 'en' }, t)).toBe('Give the template a name.')
    expect(noteProblem({ name: 'x'.repeat(81), purpose: 'x', language: 'en' }, t)).toBe('The name has at most 80 characters.')
    expect(noteProblem({ name: 'Talk', purpose: 'x'.repeat(401), language: 'en' }, t)).toBe('What it is for has at most 400 characters.')
    expect(noteProblem({ name: 'Talk', purpose: '', language: 'en' }, t)).toBe('Say in a few words what the template is for.')
    expect(noteProblem({ name: 'Talk', purpose: 'Talks', language: 'en' }, t)).toBe('')
  })

  it('offers the App Languages by their own names', () => {
    expect(languageChoices('de')).toEqual([
      { tag: 'en', name: 'English' },
      { tag: 'de', name: 'Deutsch' },
    ])
  })

  it('adds the language of the template when it is none of those', () => {
    expect(languageChoices('fr').at(-1)).toEqual({ tag: 'fr', name: 'français' })
  })
})
