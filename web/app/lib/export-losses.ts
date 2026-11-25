// What a file could not keep, in words (UX-70, D405): the converters report codes (`{kind, detail, count}`), and the
// Export dialog says each kind once, as the agreed design shows it (notes/mockups/export-dialog-tracked-changes.svg,
// panel B): what is not in the file, with how many where that helps, and one sentence saying why or what to do.
import type { ExportLoss } from './base-session'

type Translate = (msgid: string, vars?: Record<string, string | number>) => string

/** One line of the list: what the file does not hold, and why or what to do about it. */
export interface LossLine {
  kind: string
  title: string
  hint: string
}

type Words = (count: number, details: string[], t: Translate) => Omit<LossLine, 'kind'>

/** `title (count)` when there is more than one, so that no sentence needs a plural of its own. */
const counted = (title: string, count: number) => (count > 1 ? `${title} (${count})` : title)

/** The details of a loss that name something (a style, a property), quoted and joined, at most three and "…". */
function named(details: string[]): string {
  const shown = details.filter(Boolean).slice(0, 3).map((detail) => `“${detail}”`)
  return details.length > 3 ? `${shown.join(', ')}…` : shown.join(', ')
}

/** What the facets a format does not write are called (`not-written`, D405): the parts of a document's model. */
function facetWords(facet: string, t: Translate): string {
  const words: Record<string, () => string> = {
    print_setup: () => t('How it is printed: margins and page numbers'),
    print_page: () => t('How it is printed'),
    sheet_print: () => t('How each sheet is printed'),
    language: () => t('The language of the document'),
    descriptions: () => t('Descriptions of things'),
    random: () => t('How random numbers are drawn'),
    tabs: () => t('The order of the tabs'),
    slides: () => t('The slides'),
    tables: () => t('Tables'),
    shapes: () => t('Shapes'),
    charts: () => t('Charts'),
    containers: () => t('Containers'),
    names: () => t('Names'),
    pivots: () => t('Pivot tables'),
    objects: () => t('Objects'),
  }
  return words[facet]?.() ?? facet
}

/** The words of a look a cell format cannot hold (`look` with a detail, D379). */
function lookWords(detail: string, t: Translate): string {
  const words: Record<string, () => string> = {
    rotation: () => t('turned text'),
    pattern: () => t('patterns'),
    gradient: () => t('gradients'),
    'center-across': () => t('centred across cells'),
    fill: () => t('fills'),
    shrink: () => t('shrink to fit'),
    diagonal: () => t('diagonal lines'),
    superscript: () => t('raised and lowered text'),
    'double-underline': () => t('double underlines'),
    'vertical-spread': () => t('text spread from top to bottom'),
    'number-format': () => t('number formats'),
  }
  return words[detail]?.() ?? detail
}

/** The words of every kind of loss a converter reports, by its code. */
const WORDS: Record<string, Words> = {
  authorship: (count, _, t) => ({
    title: counted(t('Who typed which words'), count),
    hint: t('This format has no place to keep it.'),
  }),
  style: (_, details, t) => ({
    title: t('Styles saved as body text: {names}', { names: named(details) }),
    hint: t('Rename a style to Body text, a heading or Quote to keep it.'),
  }),
  'style-property': (_, details, t) => ({
    title: t('Style settings the format cannot hold: {names}', { names: named(details) }),
    hint: t('The rest of each style is in the file.'),
  }),
  remark: (count, _, t) => ({
    title: counted(t('Remarks are not in the file'), count),
    hint: t('A remark proposes no change, so there is nothing to track.'),
  }),
  suggestion: (count, _, t) => ({
    title: counted(t('Open suggestions are not in the file'), count),
    hint: t('Accept or reject them first to have the words you want in the file.'),
  }),
  'suggestion-anchor': (count, _, t) => ({
    title: counted(t('Suggestions that no longer match their words'), count),
    hint: t('They are left out of the file.'),
  }),
  decorative: (count, _, t) => ({
    title: counted(t('Pictures marked as decoration'), count),
    hint: t('The format cannot say that a picture is only decoration.'),
  }),
  'toc-pages': (count, _, t) => ({
    title: counted(t('Page numbers in the table of contents'), count),
    hint: t('The program that opens the file has to update the table to show them.'),
  }),
  agenda: (count, _, t) => ({
    title: counted(t('Agendas are written as the lines they show now'), count),
    hint: t('In the file they no longer follow the slides.'),
  }),
  reference: (count, _, t) => ({
    title: counted(t('References are written as what they read now'), count),
    hint: t('In the file they no longer follow what they point at.'),
  }),
  'list-look': (count, _, t) => ({
    title: counted(t('List marks'), count),
    hint: t('The format shows them in a look of its own.'),
  }),
  'rendering-pending': (count, _, t) => ({
    title: counted(t('Containers that are not drawn yet'), count),
    hint: t('They are empty in the file. Export again once they are drawn.'),
  }),
  'image-missing': (count, _, t) => ({
    title: counted(t('Pictures without their image'), count),
    hint: t('The document does not hold the image, so the file shows nothing there.'),
  }),
  'svg-fallback': (count, _, t) => ({
    title: counted(t('Vector pictures without a plain picture beside them'), count),
    hint: t('A program that cannot draw vector pictures shows nothing there.'),
  }),
  'svg-picture': (count, _, t) => ({
    title: counted(t('Vector pictures'), count),
    hint: t('Some programs cannot show them.'),
  }),
  chart: (count, details, t) => ({
    title: counted(t('Parts of charts'), count),
    hint: details.includes('source')
      ? t('A chart that follows a name is written with the cells it reads now.')
      : t('The format cannot hold all of what these charts show or how they are turned.'),
  }),
  look: (count, details, t) =>
    details.includes('too-many-cells')
      ? { title: counted(t('Cell looks beyond what the format holds'), count), hint: t('The largest areas keep their look; the rest look plain.') }
      : {
          title: counted(t('Cell looks the format cannot hold'), count),
          hint: details.filter(Boolean).length
            ? t('Not kept: {what}.', { what: details.filter(Boolean).map((detail) => lookWords(detail, t)).join(', ') })
            : t('These cells keep the rest of their look.'),
        },
  formula: (count, _, t) => ({
    title: counted(t('Formulas written as their values'), count),
    hint: t('The format has no formula for them, so the file holds what they show now.'),
  }),
  alternatives: (_, __, t) => ({
    title: t('Alternatives'),
    hint: t('Only the alternative in use is in the file.'),
  }),
  layout: (count, _, t) => ({
    title: counted(t('Rows or columns beyond the format’s limits'), count),
    hint: t('They are left out of the file.'),
  }),
  name: (count, details, t) => ({
    title: counted(t('Names the format cannot hold as they are'), count),
    hint: details.includes('result')
      ? t('A name that stands for a result is not in the file.')
      : t('What a name is for, or which table it belongs to, is not in the file.'),
  }),
  object: (count, _, t) => ({
    title: counted(t('Objects added to a file that was imported'), count),
    hint: t('Export to a new file to keep them.'),
  }),
  'pivot-table': (count, _, t) => ({
    title: counted(t('Pivot tables'), count),
    hint: t('Export to a new file to keep them.'),
  }),
  'planned-time': (count, _, t) => ({
    title: counted(t('Planned times of slides'), count),
    hint: t('The only time the format holds is when a slide moves on by itself.'),
  }),
  'notes-link': (count, _, t) => ({ title: counted(t('Links in speaker notes'), count), hint: t('They are written as plain words.') }),
  'notes-image': (count, _, t) => ({ title: counted(t('Pictures in speaker notes'), count), hint: t('They are written as plain words.') }),
  'notes-code': (count, _, t) => ({ title: counted(t('Code in speaker notes'), count), hint: t('They are written as plain words.') }),
  'notes-quote': (count, _, t) => ({ title: counted(t('Quotes in speaker notes'), count), hint: t('They are written as plain words.') }),
  'not-written': (_, details, t) => ({
    title: t('Not in the file: {what}', { what: details.map((facet) => facetWords(facet, t)).join(', ') }),
    hint: t('This format has no place for it.'),
  }),
}

/** One line per kind of loss, in the order the file reported them. A kind nobody has put into words yet is still
 *  said, with its code, rather than left out. */
export function lossLines(losses: readonly ExportLoss[], t: Translate): LossLine[] {
  const kinds = new Map<string, { count: number; details: string[] }>()
  for (const loss of losses) {
    const seen = kinds.get(loss.kind) ?? { count: 0, details: [] }
    seen.count += loss.count
    if (loss.detail && !seen.details.includes(loss.detail)) seen.details.push(loss.detail)
    kinds.set(loss.kind, seen)
  }
  return [...kinds].map(([kind, { count, details }]) => {
    const words = WORDS[kind]
    if (words) return { kind, ...words(count, details, t) }
    return { kind, title: counted(t('Something this format has no place for'), count), hint: t('Its code is “{code}”.', { code: [kind, ...details].join(': ') }) }
  })
}
