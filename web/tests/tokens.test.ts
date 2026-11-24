// UX-04's acceptance: a test reads `tokens.css` and checks the text colours against the grounds they appear on, so the
// next change to the palette cannot slip below WCAG 2.1 AA (BITV 2.0, 1.4.3 and 1.4.11) unnoticed.
import { readdirSync, readFileSync } from 'node:fs'
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

  it('the apricot words on their pill read on its tint of 28% apricot (UX-66)', () => {
    const pill = mixedWithWhite('color-mix(in srgb, var(--apricot) 28%, white)')
    expect(contrastRatio(parseHex(rootToken('--apricot-dark')), pill)).toBeGreaterThanOrEqual(AA_TEXT)
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

// UX-66: a colour is a token in `tokens.css`, so it follows the scheme and is checked above; a component's `<style>`
// names tokens only. A hex value or an rgb()/hsl() call there is a literal (a colour keyword such as `white`, the ground
// of a tint, is not counted). The components below had literals when the rule came; each count may only go down, and
// a file leaves the list when it reaches none.
const LITERALS_ALLOWED: Record<string, number> = {
  'AdminFonts.vue': 2,
  'BackChip.vue': 3,
  'ChatInput.vue': 7,
  'ConnectionIndicator.vue': 1,
  'DeleteDocumentDialog.vue': 1,
  'DeleteStyleDialog.vue': 1,
  'DocDetails.vue': 2,
  'DocumentFrame.vue': 4,
  'FollowPill.vue': 1,
  'FontReportBanner.vue': 1,
  'HelpPanel.vue': 14,
  'LineSizeDialog.vue': 1,
  'Modal.vue': 1,
  'ObjectFrame.vue': 2,
  'OutcomePopover.vue': 1,
  'PaletteDialog.vue': 3,
  'PivotPanel.vue': 8,
  'PivotSqlDialog.vue': 1,
  'Popover.vue': 1,
  'PresentShow.vue': 17,
  'PrintPreview.vue': 6,
  'RedactionDialog.vue': 3,
  'RotatePopover.vue': 1,
  'SearchPanel.vue': 1,
  'SheetGrid.vue': 1,
  'SidePanel.vue': 82,
  'SlideCanvas.vue': 2,
  'SlideNotes.vue': 2,
  'SlideView.vue': 1,
  'SqlEditor.vue': 1,
  'StyleBar.vue': 1,
  'StyleColorPicker.vue': 5,
  'StyleCssEditor.vue': 1,
  'StyleMenu.vue': 2,
  'SuggestionPopover.vue': 1,
  'TableDialog.vue': 1,
  'TextEditor.vue': 2,
  'TextObjectLayer.vue': 6,
  'ToggleSwitch.vue': 2,
  'Workspace.vue': 5,
}

const COLOUR_LITERAL = /#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?)\(/gi

function literalsInStyles(): Record<string, number> {
  const dir = new URL('../app/components/', import.meta.url)
  const found: Record<string, number> = {}
  for (const name of readdirSync(dir).filter((n) => n.endsWith('.vue')).sort()) {
    const styles = [...readFileSync(new URL(name, dir), 'utf8').matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map((m) => m[1]!)
    const count = styles.join('\n').replace(/\/\*[\s\S]*?\*\//g, '').match(COLOUR_LITERAL)?.length ?? 0
    if (count) found[name] = count
  }
  return found
}

describe('colours in the components', () => {
  it('no component style has a colour literal beyond the ones it had when the rule came', () => {
    expect(literalsInStyles()).toEqual(LITERALS_ALLOWED)
  })
})

describe('the pills of the Styles dialog (UX-79)', () => {
  const dialog = readFileSync(new URL('../app/components/StylesDialog.vue', import.meta.url), 'utf8')
  /** A declaration of the `.hiddenflag` rule in the dialog's style. */
  function hiddenflag(property: string): string {
    const rule = dialog.split('}').find((block) => block.split('{')[0]!.trim() === '.hiddenflag')
    const found = rule?.match(new RegExp(`(?:^|[\\s;{])${property}:\\s*([^;]+);`))
    if (!found) throw new Error(`.hiddenflag has no ${property}`)
    return found[1]!.trim()
  }
  /** What `var(--name)` is in the light and in the dark scheme (the dark one where the dark scheme sets it again). */
  function bothSchemes(value: string): Rgb[] {
    const name = value.match(/^var\((--[\w-]+)\)$/)?.[1]
    if (!name) throw new Error(`not one colour token: ${value}`)
    const resolve = (raw: string): Rgb => (raw.startsWith('var(') ? resolve(rootToken(raw.slice(4, -1))) : parseHex(raw))
    const light = resolve(rootToken(name))
    let dark = light
    try {
      dark = resolve(token(":root[data-theme='dark']", name))
    } catch {
      // not set again for the dark scheme: the same colour
    }
    return [light, dark]
  }

  it('the word "hidden" reads on its light pill in the light and in the dark scheme', () => {
    const pill = mixedWithWhite(hiddenflag('background'))
    for (const text of bothSchemes(hiddenflag('color'))) {
      expect(contrastRatio(text, pill)).toBeGreaterThanOrEqual(AA_TEXT)
    }
  })
})
