// A dialog is exactly as tall as its content, in every engine. WebKitGTK 2.52 (the Linux client's view) sizes the
// grid's auto rows once while the dialog is capped by `max-height`, and keeps that stretched state: in a window taller
// than the content every gap grew, and a button in a row of its own became a near-circle (the owner's report of
// 2026-11-14, found by measuring in the inspector). Docking the inspector made the dialog snap back, because it shortened
// the window to about the dialog's own height. What stops it is saying that the rows never stretch.
//
// This reads the stylesheet and does not draw it: the stretching only happens in WebKitGTK, which no test here runs.
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = readFileSync(new URL('../app/components/Modal.vue', import.meta.url), 'utf8')
const style = source.slice(source.indexOf('<style')).replace(/<style[^>]*>/, '').replace(/\/\*[\s\S]*?\*\//g, '')

/** The declarations of the first rule whose selector is exactly `selector`, as a map of property to value. */
function declarations(selector: string): Map<string, string> {
  const rule = style.split('}').find((block) => block.split('{')[0]!.trim() === selector)
  if (!rule) throw new Error(`no rule for ${selector} in Modal.vue`)
  const pairs = rule.split('{')[1]!.split(';').map((d) => d.split(/:(.*)/s).map((s) => s.trim()))
  return new Map(pairs.filter((p) => p[0] && p[1]).map((p) => [p[0]!, p[1]!] as [string, string]))
}

describe('the dialog box', () => {
  const modal = declarations('.modal')

  it('never stretches its rows to fill a height it was only allowed, not given', () => {
    expect(modal.get('align-content')).toBe('start')
    expect(modal.get('grid-auto-rows')).toBe('max-content')
  })

  it('is as tall as its content', () => {
    expect(modal.get('height')).toBe('fit-content')
  })
})
