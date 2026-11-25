import { describe, expect, it } from 'vitest'
import { lossLines } from '../app/lib/export-losses'
import { createTranslator } from '../app/lib/i18n'

const t = createTranslator({})

// UX-70, D405: what an export could not keep is said in words, once per kind (the agreed design, panel B of
// notes/mockups/export-dialog-tracked-changes.svg).
describe('what the Export dialog says a file does not hold', () => {
  it('says each kind once, adding up its counts, in the order the file reported them', () => {
    const lines = lossLines(
      [
        { kind: 'authorship', detail: '', count: 2 },
        { kind: 'style', detail: 'remark', count: 1 },
        { kind: 'authorship', detail: '', count: 1 },
        { kind: 'style', detail: 'aside', count: 4 },
      ],
      t,
    )
    expect(lines.map((line) => line.kind)).toEqual(['authorship', 'style'])
    expect(lines[0]!.title).toBe('Who typed which words (3)')
    expect(lines[1]!.title).toBe('Styles saved as body text: “remark”, “aside”')
  })

  it('gives every line a sentence saying why or what to do', () => {
    const lines = lossLines([{ kind: 'remark', detail: '', count: 1 }], t)
    expect(lines[0]).toEqual({ kind: 'remark', title: 'Remarks are not in the file', hint: 'A remark proposes no change, so there is nothing to track.' })
  })

  it('names the parts of a document a format has no place for', () => {
    const [line] = lossLines([{ kind: 'not-written', detail: 'print_setup', count: 1 }, { kind: 'not-written', detail: 'language', count: 1 }], t)
    expect(line!.title).toBe('Not in the file: How it is printed: margins and page numbers, The language of the document')
  })

  it('still says a kind nobody has put into words, with its code', () => {
    const [line] = lossLines([{ kind: 'hologram', detail: 'blue', count: 2 }], t)
    expect(line).toEqual({ kind: 'hologram', title: 'Something this format has no place for (2)', hint: 'Its code is “hologram: blue”.' })
  })

  it('says what went with a deleted part of a kept file, by the kind of thing it was', () => {
    const lines = lossLines([{ kind: 'removed-comment', detail: '', count: 2 }, { kind: 'removed-tracked-change', detail: '', count: 1 }], t)
    expect(lines.map((line) => line.title)).toEqual(['Went with what you deleted: comments (2)', 'Went with what you deleted: tracked changes'])
    expect(lines[0]!.hint).toBe('They were in the original file, in a part this program does not show.')
  })

  it('still says what went with a deleted part when nobody has put that kind into words, with its code', () => {
    const [line] = lossLines([{ kind: 'removed-hidden-row', detail: '', count: 3 }], t)
    expect(line).toEqual({
      kind: 'removed-hidden-row',
      title: 'Went with what you deleted: things this program does not show (3)',
      hint: 'Its code is “removed-hidden-row”.',
    })
  })

  it('says when a kept file could not be changed in place and was written anew', () => {
    const [line] = lossLines([{ kind: 'not-patched', detail: 'adding a slide cannot be patched yet', count: 1 }], t)
    expect(line).toEqual({
      kind: 'not-patched',
      title: 'The file was written anew, not changed in place',
      hint: 'So what this program does not show of the original is not in it.',
    })
  })

  // the codes the converters report on an export (tests/test_loss_words.py holds the list against the Python sources)
  const EXPORT_CODES = [
    'authorship', 'style', 'style-property', 'remark', 'suggestion', 'suggestion-anchor', 'decorative', 'toc-pages',
    'agenda', 'reference', 'list-look', 'rendering-pending', 'image-missing', 'svg-fallback', 'svg-picture', 'chart',
    'look', 'formula', 'alternatives', 'layout', 'name', 'object', 'pivot-table', 'planned-time', 'stale-reference',
    'not-patched', 'not-written', 'notes-link', 'notes-image', 'notes-code', 'notes-quote', 'removed-link',
    'removed-formatting', 'removed-footnote', 'removed-endnote', 'removed-note', 'removed-field', 'removed-frame',
    'removed-ruby', 'removed-ruby-text', 'removed-text', 'removed-notes', 'removed-transition', 'removed-animation',
    'removed-chart', 'removed-picture', 'removed-object', 'removed-formula', 'removed-look', 'removed-validation',
  ]

  it.each(EXPORT_CODES)('has words of its own for %s, and a sentence', (kind) => {
    const [line] = lossLines([{ kind, detail: '', count: 1 }], t)
    expect(line!.title).not.toContain('Something this format has no place for')
    expect(line!.hint).not.toBe('')
    expect(`${line!.title} ${line!.hint}`).not.toMatch(/[{}]/)
  })

  it.each(['print_setup', 'print_page', 'sheet_print', 'language', 'descriptions', 'random', 'tabs', 'slides', 'tables', 'shapes', 'charts', 'containers', 'names', 'pivots', 'objects'])(
    'names the part %s of a document in words',
    (facet) => {
      const [line] = lossLines([{ kind: 'not-written', detail: facet, count: 1 }], t)
      expect(line!.title).not.toBe(`Not in the file: ${facet}`) // what a part without words is called
    },
  )

  it.each(['rotation', 'pattern', 'gradient', 'center-across', 'fill', 'shrink', 'diagonal', 'superscript', 'double-underline', 'vertical-spread', 'number-format'])(
    'names the cell look %s in words',
    (detail) => {
      const [line] = lossLines([{ kind: 'look', detail, count: 1 }], t)
      expect(line!.hint).not.toBe(`Not kept: ${detail}.`) // what a look without words is called
    },
  )

  it('says nothing when nothing was lost', () => {
    expect(lossLines([], t)).toEqual([])
  })
})
