// UX-63: what the print preview says about where a print or a PDF is recorded. It goes into the exit record, which is
// not part of the history (glossary: Exit record, History). Read from the component's source, as nothing mounts it here.
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = readFileSync(new URL('../app/components/PrintPreview.vue', import.meta.url), 'utf8')

/** The English text of the note under the preview's buttons. */
function recordedNote(): string {
  const line = source.split('\n').find((l) => l.includes('data-testid="print-recorded"'))
  const text = line?.match(/t\('((?:[^'\\]|\\.)*)'\)/)?.[1]
  if (text === undefined) throw new Error('the print-recorded note has no translated text')
  return text.replace(/\\'/g, "'")
}

describe('the note in the print preview (UX-63)', () => {
  it('names the exit record, not the history', () => {
    expect(recordedNote()).toContain("the document's exit record")
    expect(recordedNote()).not.toMatch(/history/i)
  })
})
