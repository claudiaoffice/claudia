// UX-67: the Heading and Numbering choices of the style editor are native selects with the app's field look (the
// `.field select` rule of app.css), like every other select of the app, not the browser's own. Read from the
// component's source, as nothing mounts it here.
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = readFileSync(new URL('../app/components/StyleSpec.vue', import.meta.url), 'utf8')
const appCss = readFileSync(new URL('../app/assets/app.css', import.meta.url), 'utf8')

/** The classes of the `<label>` that holds the select marked `testid`. */
function classesAround(testid: string): string[] {
  const before = source.slice(0, source.indexOf(`data-testid="${testid}"`))
  const label = before.slice(before.lastIndexOf('<label'))
  expect(label).not.toContain('</label>')
  return label.match(/\sclass="([^"]*)"/)?.[1]?.split(/\s+/) ?? []
}

describe('the selects of the paragraph part of the style editor (UX-67)', () => {
  it('Heading and Numbering are native selects inside a field, which gives them the look of the app', () => {
    expect(appCss).toMatch(/\.field select\b/)
    for (const testid of ['heading-level', 'heading-numbering']) {
      expect(source).toMatch(new RegExp(`<select[^>]*data-testid="${testid}"`))
      expect(classesAround(testid)).toContain('field')
    }
  })
})
