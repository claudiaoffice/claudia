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

  it('says nothing when nothing was lost', () => {
    expect(lossLines([], t)).toEqual([])
  })
})
