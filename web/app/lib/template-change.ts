// Format ▸ Template (E10.4, E10.22, E10.23, D1539, D1540): the types of what the Change template and Save as template
// dialogs exchange with the server, and the words they say, as plain functions the dialogs call and the tests check.

import { LANGUAGES } from './i18n'
import { languageName } from './templates'

/** The note a template carries (D1530): what it is called, what it is for, and in which language. */
export interface TemplateNote {
  name: string
  purpose: string
  language: string
}

/** `template_change_preview`: what changing to a template would do, counted (D1540). */
export interface ChangePreview {
  styles_changed: number
  styles_added: number
  styles_kept: number
  colours_changed: number
  colours_added: number
  layouts_matched: number
  layouts_added: number
  layouts_kept: number
  slides_reframed: number
  slides_unchanged: number
}

/** `save_as_template`: the file as base64. */
export interface TemplateFile {
  format: 'claudia-template'
  filename: string
  content_type: string
  data: string
  parts: string[]
}

type T = (msgid: string, vars?: Record<string, string | number>) => string

/** What a dialog says of one part of the change: the heading and a line. */
export interface SummaryLine {
  heading: string
  text: string
}

/** `n` in the sentence for one or for many; both are translated with `{n}` still in them, so that the extractor sees
 * each as the string it is. */
function plural(n: number, one: string, many: string): string {
  return (n === 1 ? one : many).replace('{n}', String(n))
}

/** The parts of a line that are not zero, joined; "nothing changes" when none is. */
function said(parts: (string | false | 0)[], t: T): string {
  return parts.filter(Boolean).join(' · ') || t('nothing changes')
}

/** "3 of yours have no match and stay": what the presentation has and the template has nothing like. */
function unmatched(n: number, t: T): string | false {
  return n > 0 && plural(n, t('1 of yours has no match and stays'), t('{n} of yours have no match and stay'))
}

/** The styles and the palette line: what both Change theme and Change template do to them (D1540). */
function lookLine(preview: ChangePreview, t: T): SummaryLine {
  const text = said(
    [
      preview.styles_changed > 0 && plural(preview.styles_changed, t('{n} style replaced'), t('{n} styles replaced')),
      preview.styles_added > 0 && plural(preview.styles_added, t('{n} style added'), t('{n} styles added')),
      preview.colours_changed > 0 && plural(preview.colours_changed, t('{n} colour replaced'), t('{n} colours replaced')),
      preview.colours_added > 0 && plural(preview.colours_added, t('{n} colour added'), t('{n} colours added')),
      unmatched(preview.styles_kept, t),
    ],
    t,
  )
  return { heading: t('Styles and palette'), text }
}

/** What Change theme would do, in three lines: the styles and the palette change, the layouts and the slides stay. */
export function themeSummary(preview: ChangePreview, t: T): SummaryLine[] {
  return [
    lookLine(preview, t),
    { heading: t('Layouts'), text: t('stay as they are') },
    { heading: t('Slides'), text: t('stay as they are') },
  ]
}

/** What Change template would do, in three lines: the styles and the palette, the layouts and the slides (D1540).
 * Nothing is said of a number that is zero. */
export function templateSummary(preview: ChangePreview, t: T): SummaryLine[] {
  const layouts = said(
    [
      preview.layouts_matched > 0 && plural(preview.layouts_matched, t('{n} layout matched by name'), t('{n} layouts matched by name')),
      preview.layouts_added > 0 && plural(preview.layouts_added, t('{n} layout added'), t('{n} layouts added')),
      unmatched(preview.layouts_kept, t),
    ],
    t,
  )
  const slides = said(
    [
      preview.slides_reframed > 0 && plural(preview.slides_reframed, t('{n} slide takes its layout’s frames'), t('{n} slides take their layout’s frames')),
      preview.slides_unchanged > 0 && plural(preview.slides_unchanged, t('{n} slide is unchanged'), t('{n} slides are unchanged')),
    ],
    t,
  )
  return [lookLine(preview, t), { heading: t('Layouts'), text: layouts }, { heading: t('Slides'), text: slides }]
}

export const MAX_NAME = 80
export const MAX_PURPOSE = 400

/** What is wrong with the note of a template, in a sentence, before it is sent; `''` when nothing is. The server
 * checks the same (D1530) and has the last word. */
export function noteProblem(note: TemplateNote, t: T): string {
  const name = note.name.trim()
  const purpose = note.purpose.trim()
  if (!name) return t('Give the template a name.')
  if (name.length > MAX_NAME) return t('The name has at most {n} characters.', { n: MAX_NAME })
  if (!purpose) return t('Say in a few words what the template is for.')
  if (purpose.length > MAX_PURPOSE) return t('What it is for has at most {n} characters.', { n: MAX_PURPOSE })
  return ''
}

/** The languages Save as template offers: the App Languages by their own names, and the language of the template
 * when it is none of them. */
export function languageChoices(current: string): { tag: string; name: string }[] {
  const choices = LANGUAGES.map(([tag, name]) => ({ tag, name }))
  return choices.some((choice) => choice.tag === current) ? choices : [...choices, { tag: current, name: languageName(current) }]
}
