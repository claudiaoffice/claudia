// UX-04's acceptance: a test reads `tokens.css` and checks the text colours against the grounds they appear on, so the
// next change to the palette cannot slip below WCAG 2.1 AA (BITV 2.0, 1.4.3 and 1.4.11) unnoticed.
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { contrastRatio, mix, parseHex, type Rgb } from './contrast'

// Comments are cut out first: the ones above a rule would otherwise count as part of its selector.
const css = readFileSync(new URL('../app/assets/tokens.css', import.meta.url), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')

/** The value a custom property is given inside the first rule whose selector is exactly `selector`. */
function token(selector: string, name: string): string {
  const rule = css.split('}').find((block) => block.split('{')[0]!.trim() === selector)
  const found = rule?.match(new RegExp(`${name}:\\s*([^;]+);`))
  if (!found) throw new Error(`${name} is not set in ${selector}`)
  return found[1]!.trim()
}
const rootToken = (name: string) => token(':root', name)
const hex = (selector: string, name: string): Rgb => parseHex(token(selector, name))

/** `color-mix(in srgb, var(--teal) 12%, white)` as the colour it makes, with the variables looked up in `:root`. */
function mixedWithWhite(value: string): Rgb {
  const parts = value.match(/color-mix\(in srgb, var\(--(\w+)\) (\d+)%, white\)/)
  if (!parts) throw new Error(`not a mix with white: ${value}`)
  return mix(parseHex(rootToken(parts[1]!)), Number(parts[2]), parseHex('#ffffff'))
}

const WHITE = parseHex('#ffffff')
const AA_TEXT = 4.5
const AA_COMPONENT = 3

const apps = [
  { name: 'computes', selector: ':root', soft: ':root' },
  { name: 'composes', selector: ":root[data-app='composes']", soft: ":root[data-app='composes']" },
  { name: 'creates', selector: ":root[data-app='creates']", soft: ":root[data-app='creates']" },
]

describe('the accent as text in the light scheme', () => {
  const paper = parseHex(rootToken('--paper'))
  for (const app of apps) {
    const accent = hex(app.selector, '--app-dark')
    const soft = mixedWithWhite(token(app.soft, '--app-soft'))
    it(`${app.name}: --app-dark reads on white, on paper and on its own soft tint`, () => {
      expect(contrastRatio(accent, WHITE)).toBeGreaterThanOrEqual(AA_TEXT)
      expect(contrastRatio(accent, paper)).toBeGreaterThanOrEqual(AA_TEXT)
      expect(contrastRatio(accent, soft)).toBeGreaterThanOrEqual(AA_TEXT)
    })
  }

  it('the error and link shades of rose and teal read on white', () => {
    for (const name of ['--rose-dark', '--teal-dark']) {
      expect(contrastRatio(parseHex(rootToken(name)), WHITE)).toBeGreaterThanOrEqual(AA_TEXT)
    }
  })

  it('white text on the dark shade, as on a hovered button, keeps its contrast', () => {
    for (const app of apps) {
      expect(contrastRatio(WHITE, hex(app.selector, '--app-dark'))).toBeGreaterThanOrEqual(AA_TEXT)
    }
  })
})

describe('text in the dark scheme', () => {
  const surface = parseHex(rootToken('--surface-dark'))
  const page = parseHex(rootToken('--page-dark'))

  it('the muted text and the accent-as-text variants read on the dark surface', () => {
    expect(contrastRatio(parseHex(rootToken('--muted-dark')), surface)).toBeGreaterThanOrEqual(AA_TEXT)
    for (const name of ['--teal-light', '--rose-light', '--apricot-light']) {
      expect(contrastRatio(parseHex(rootToken(name)), surface)).toBeGreaterThanOrEqual(AA_TEXT)
    }
  })

  it('the wordmark reads on the dark page', () => {
    expect(contrastRatio(parseHex(rootToken('--rose-light')), page)).toBeGreaterThanOrEqual(AA_TEXT)
  })
})

describe('the borders of controls', () => {
  it('a field border reaches 3:1 on white and on the dark surface', () => {
    const ink = parseHex(rootToken('--ink'))
    const percent = Number(rootToken('--line-field').match(/(\d+)%/)![1])
    expect(contrastRatio(mix(ink, percent, WHITE), WHITE)).toBeGreaterThanOrEqual(AA_COMPONENT)
    expect(
      contrastRatio(parseHex(rootToken('--line-field-dark')), parseHex(rootToken('--surface-dark'))),
    ).toBeGreaterThanOrEqual(AA_COMPONENT)
  })
})
