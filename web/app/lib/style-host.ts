// The style menu is the same in every app (E9.7): it talks to a StyleHost, which says what the thing under the caret is
// styled with and how to change it. A text is one host (paragraph styles); cells and shapes will be others. Nothing in
// the menu knows which.
import {
  fontSizeOf,
  hasDecoration,
  isBold,
  isItalic,
  toggleDecoration as decorationWith,
  withFontSize,
  type Css,
  type CssCheck,
  type CssEdit,
  type StyleView,
} from './style-css'
import { stackFor } from './fonts'
import type { ColourRole, Reading } from './objects'

/** What the thing being styled actually has, and so which controls the menu offers.
 *
 * A paragraph has words. A shape has words *and* a box — a fill and a border, in SVG's vocabulary because a shape
 * is an outline and not a rectangle (D178). A picture has neither: it carries its own colours and holds no text, so
 * those controls are left out rather than shown dead. An empty control that can never do anything is worse than no
 * control at all. */
export interface Parts {
  words: boolean
  box: boolean
}

export interface StyleHost {
  styles: StyleView[]
  /** The style of what the caret is in; undefined while nothing is open. */
  current: StyleView | undefined
  readOnly: boolean
  /** What is styled, singular: “paragraph”, “cell”, “shape”. */
  noun: string
  /** Which groups of controls apply to it. */
  parts: Parts
  /** The document's colour roles, so a control can offer a meaning instead of a hex (D200). Empty for a document
   * whose palette has not arrived (or that has none), and the controls then fall back to plain colours. */
  roles: ColourRole[]
  /** How the roles read against each other, as the server works it out (D202). */
  readings: Reading[]
  /** How many things have each style. */
  uses(): Record<string, number>
  /** Give the selection this style. */
  apply(style: string): Promise<boolean>
  /** Change a style for everything that has it. */
  change(style: string, edit: CssEdit): Promise<boolean>
  /** Change only the selection: it gets a new style, which is named later. */
  deviate(edit: CssEdit): Promise<boolean>
  rename(style: string, name: string): Promise<boolean>
  check(text: string): Promise<CssCheck | null>
  /** Give a colour role another colour: everything in the document that meant it follows (D200). */
  setRole(role: string, colour: string): Promise<boolean>
}

export type Scope = 'new' | 'every'

const STEP: Record<string, number> = { pt: 1, px: 1, em: 0.1, rem: 0.1, '%': 10 }
const START = 12
/** As thick a border as the allow-list will take; past this it is a filled shape with a hole in it. */
const MAX_STROKE = 24
const none: Css = {}

/**
 * What the style menu does with a person's input. A change goes either to this text only (a new style that is named
 * later: “styles first, deviate second”) or to every use of the style; a style that still waits for its name is the
 * person’s own, so changes go into it. Changes are made one after the other, each deciding where to go at its turn.
 */
export class StyleEditor {
  choice: { style: string; scope: Scope } | null = null
  private queue: Promise<unknown> = Promise.resolve()
  /** Styles named or turned down for naming: ids. Public so that a component sees changes. */
  declined: string[] = []

  constructor(private readonly host: StyleHost) {}

  get current(): StyleView | undefined {
    return this.host.current
  }

  /** The css the controls show: what the current style really has, with its palette roles already colours (D200).
   *
   * Resolved rather than computed, because a control has to show a colour it can paint: a swatch given `@accent`
   * would come up blank. The consequence is that picking a colour here writes a literal, which is precisely what
   * leaving the palette means — the menu that offers the roles themselves is the next step. */
  get look(): Css {
    return this.host.current?.resolved ?? none
  }

  /** What the current style *names* for a property: a palette role (`@accent`) where it names one, else the
   * literal value.
   *
   * The colour controls read this rather than `look`, so they can show a person "Accent" and not a hex — the whole
   * point of a role (D200). Everything that has to paint or measure reads `look`, which is already resolved. */
  named(property: string): string | undefined {
    return this.host.current?.computed[property]
  }

  get scope(): Scope {
    const current = this.host.current
    if (this.choice && current && this.choice.style === current.id) return this.choice.scope
    return current?.to_name ? 'every' : 'new'
  }

  setScope(scope: Scope) {
    const current = this.host.current
    if (current) this.choice = { style: current.id, scope }
  }

  get invitesName(): boolean {
    const current = this.host.current
    return !!current?.to_name && !this.declined.includes(current.id) && !this.host.readOnly
  }

  dismissNaming() {
    const current = this.host.current
    if (current) this.declined.push(current.id)
  }

  async name(typed: string): Promise<boolean> {
    const current = this.host.current
    const name = typed.trim()
    if (!current || !name) return false
    const done = await this.host.rename(current.id, name)
    if (done) this.declined.push(current.id)
    return done
  }

  /** Make a change: where it goes is decided when its turn comes. */
  edit(edit: CssEdit): Promise<boolean> {
    if (this.host.readOnly) return Promise.resolve(false)
    const run = this.queue.then(() => {
      const current = this.host.current
      if (!current) return false
      return this.scope === 'every' ? this.host.change(current.id, edit) : this.host.deviate(edit)
    })
    this.queue = run.catch(() => false)
    return run as Promise<boolean>
  }

  set(property: string, value: string) {
    return this.edit({ set: { [property]: value } })
  }

  setColor(property: 'color' | 'background-color', value: string) {
    return this.set(property, value)
  }

  /** Take a property back from the style: it follows its parent again. */
  reset(property: string) {
    return this.edit({ unset: [property] })
  }

  setText(text: string) {
    return this.edit({ text })
  }

  toggleBold() {
    return this.set('font-weight', isBold(this.look) ? 'normal' : 'bold')
  }

  toggleItalic() {
    return this.set('font-style', isItalic(this.look) ? 'normal' : 'italic')
  }

  toggleDecoration(which: 'underline' | 'line-through') {
    return this.set('text-decoration', decorationWith(this.look, which))
  }

  hasDecoration(which: 'underline' | 'line-through') {
    return hasDecoration(this.look, which)
  }

  setSize(value: number, unit: string) {
    return this.set('font-size', withFontSize(value, unit))
  }

  stepSize(direction: 1 | -1) {
    const size = fontSizeOf(this.look) ?? { value: START, unit: 'pt' }
    const step = STEP[size.unit] ?? 1
    const next = fontSizeOf(this.look) ? size.value + direction * step : START + (direction > 0 ? 1 : -1)
    return this.setSize(Math.round(next * 100) / 100, size.unit)
  }

  setFamily(typed: string) {
    return this.set('font-family', stackFor(typed))
  }

  setAlign(align: string) {
    return this.set('text-align', align)
  }

  // -- the box: a shape's own look, in SVG's words because a shape is an outline and not a rectangle (D178)
  setFill(value: string) {
    return this.set('fill', value)
  }

  setStroke(value: string) {
    return this.set('stroke', value)
  }

  setStrokeWidth(px: number) {
    return this.set('stroke-width', `${Math.max(0, Math.min(MAX_STROKE, Math.round(px)))}px`)
  }

  get strokeWidth(): number {
    const match = /([\d.]+)/.exec(this.look['stroke-width'] ?? '')
    return match ? Math.round(Number(match[1])) : 0
  }

  stepStrokeWidth(direction: 1 | -1) {
    return this.setStrokeWidth(this.strokeWidth + direction)
  }
}
