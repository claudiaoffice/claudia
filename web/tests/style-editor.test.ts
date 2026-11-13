import { describe, expect, it } from 'vitest'
import type { Css, CssCheck, CssEdit, StyleView } from '~/lib/style-css'
import { SIDES, StyleEditor, borderOf, facetsOfKind, facetsOfSlot, galleryFor, type StyleHost } from '~/lib/style-host'
import { STYLE_MODEL } from './style-model.fixture'

const view = (id: string, css: Css, based_on: string | null = null, to_name = false, name = id): StyleView => ({ id, name, purpose: '', based_on, css, computed: css, resolved: css, to_name })

class FakeHost implements StyleHost {
  styles = [view('body', { 'font-size': '11pt', 'font-weight': 'normal', color: '#1F1A33' }), view('quote', { 'font-style': 'italic' }, 'body')]
  currentId = 'body'
  readOnly = false
  noun = 'paragraph'
  sent: [string, ...unknown[]][] = []
  get current() {
    return this.styles.find((s) => s.id === this.currentId)
  }
  uses = () => ({ body: 3, quote: 1 })
  async apply(style: string) {
    this.sent.push(['apply', style])
    this.currentId = style
    return true
  }
  async change(style: string, edit: CssEdit) {
    this.sent.push(['change', style, edit])
    return true
  }
  async deviate(edit: CssEdit) {
    this.sent.push(['deviate', edit])
    this.styles.push(view('body-changed', { ...this.current!.css, ...edit.set }, 'body', true, 'Body text (changed)'))
    this.currentId = 'body-changed'
    return true
  }
  async rename(style: string, name: string) {
    this.sent.push(['rename', style, name])
    return true
  }
  async check(text: string): Promise<CssCheck | null> {
    return { css: {}, text, problems: [] }
  }
}

describe('where a change goes', () => {
  it('a style that is named is changed for this text only, by default', () => {
    expect(new StyleEditor(new FakeHost()).scope).toBe('new')
  })

  it('a style that waits for its name is changed where it is: it is the person’s own', () => {
    const host = new FakeHost()
    host.currentId = 'body'
    host.styles[0] = view('body', {}, null, true)
    expect(new StyleEditor(host).scope).toBe('every')
  })

  it('the person can choose, and the choice is forgotten when the caret moves to another style', () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    editor.setScope('every')
    expect(editor.scope).toBe('every')
    host.currentId = 'quote'
    expect(editor.scope).toBe('new')
  })

  it('“this text only” deviates; “every use” changes the style', async () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    await editor.setColor('color', '#D6477A')
    expect(host.sent).toEqual([['deviate', { set: { color: '#D6477A' } }]])
    // the deviation is the caret’s style now, and waits for its name: the next change goes into it
    await editor.setColor('color', '#13917F')
    expect(host.sent[1]).toEqual(['change', 'body-changed', { set: { color: '#13917F' } }])
  })

  it('edits made at once run one after the other, each deciding where it goes when its turn comes', async () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    await Promise.all([editor.toggleBold(), editor.toggleItalic()])
    expect(host.sent.map((s) => s[0])).toEqual(['deviate', 'change'])
  })

  it('does nothing when the document can only be looked at', async () => {
    const host = new FakeHost()
    host.readOnly = true
    expect(await new StyleEditor(host).toggleBold()).toBe(false)
    expect(host.sent).toEqual([])
  })
})

describe('the controls', () => {
  it('bold and italic switch on what is not and off what is', async () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    editor.setScope('every')
    await editor.toggleBold()
    await editor.toggleItalic()
    expect(host.sent).toEqual([
      ['change', 'body', { set: { 'font-weight': 'bold' } }],
      ['change', 'body', { set: { 'font-style': 'italic' } }],
    ])
  })

  it('underline and strike-through combine in text-decoration', async () => {
    const host = new FakeHost()
    host.styles[0] = view('body', { 'text-decoration': 'underline' })
    const editor = new StyleEditor(host)
    editor.setScope('every')
    await editor.toggleDecoration('line-through')
    await editor.toggleDecoration('underline')
    expect(host.sent).toEqual([
      ['change', 'body', { set: { 'text-decoration': 'underline line-through' } }],
      ['change', 'body', { set: { 'text-decoration': 'none' } }],
    ])
  })

  it('a size is written with its unit, rounded and kept within limits', async () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    editor.setScope('every')
    await editor.setSize(12.345, 'pt')
    await editor.setSize(900, 'pt')
    expect(host.sent.map((s) => (s[2] as CssEdit).set)).toEqual([{ 'font-size': '12.35pt' }, { 'font-size': '400pt' }])
  })

  it('stepping the size goes by a point for pt and px, by a tenth for em', async () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    editor.setScope('every')
    await editor.stepSize(1)
    host.styles[0] = view('body', { 'font-size': '1.2em' })
    await editor.stepSize(-1)
    expect(host.sent.map((s) => (s[2] as CssEdit).set)).toEqual([{ 'font-size': '12pt' }, { 'font-size': '1.1em' }])
  })

  it('a style without a size of its own does not step from nothing: it takes 12pt as the start', async () => {
    const host = new FakeHost()
    host.styles[0] = view('body', {})
    const editor = new StyleEditor(host)
    editor.setScope('every')
    await editor.stepSize(1)
    expect((host.sent[0]![2] as CssEdit).set).toEqual({ 'font-size': '13pt' })
  })

  it('a family is written as a stack', async () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    editor.setScope('every')
    await editor.setFamily('Fraunces')
    await editor.setFamily('Comic Sans MS')
    expect(host.sent.map((s) => (s[2] as CssEdit).set)).toEqual([{ 'font-family': 'Fraunces, Georgia, serif' }, { 'font-family': "'Comic Sans MS', sans-serif" }])
  })

  it('taking a property back removes it from the style so that it follows its parent again', async () => {
    const host = new FakeHost()
    host.currentId = 'quote'
    const editor = new StyleEditor(host)
    editor.setScope('every')
    await editor.reset('font-style')
    expect(host.sent).toEqual([['change', 'quote', { unset: ['font-style'] }]])
  })

  it('writing the CSS of a style sends its text', async () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    await editor.setText('color: red;')
    expect(host.sent).toEqual([['deviate', { text: 'color: red;' }]])
  })
})

describe('picking a style to inspect, without applying it (UX-14)', () => {
  it('picking nothing shows the caret’s own style, exactly as before', () => {
    const editor = new StyleEditor(new FakeHost())
    expect(editor.current?.id).toBe('body')
    expect(editor.isPicked).toBe(false)
  })

  it('picking a style shows its look, and does not call apply or change the document', () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    editor.pick('quote')
    expect(editor.current?.id).toBe('quote')
    expect(editor.look).toEqual(host.styles[1]!.resolved)
    expect(host.sent).toEqual([]) // nothing was sent to the document just by looking
    expect(host.currentId).toBe('body') // the caret’s own paragraph is untouched
  })

  it('picking a style other than the caret’s own forces “every use”; “this text only” is unavailable', () => {
    const editor = new StyleEditor(new FakeHost())
    editor.pick('quote')
    expect(editor.scope).toBe('every')
    expect(editor.canDeviate).toBe(false)
    editor.setScope('new') // asking for "this text only" while picked has no effect
    expect(editor.scope).toBe('every')
  })

  it('an edit while a style is picked changes that style for everyone, never the caret’s own as a deviation', async () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    editor.pick('quote')
    await editor.toggleItalic()
    expect(host.sent).toEqual([['change', 'quote', { set: { 'font-style': 'normal' } }]])
  })

  it('picking the style that is already the caret’s own is the same as not picking', () => {
    const editor = new StyleEditor(new FakeHost())
    editor.pick('body')
    expect(editor.isPicked).toBe(false)
    expect(editor.canDeviate).toBe(true)
    expect(editor.scope).toBe('new') // the ordinary default for a named style, unaffected
  })

  it('picking back the caret’s own style after picking another restores the ordinary behaviour', async () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    editor.pick('quote')
    editor.pick('body')
    expect(editor.canDeviate).toBe(true)
    await editor.toggleBold()
    expect(host.sent).toEqual([['deviate', { set: { 'font-weight': 'bold' } }]])
  })

  it('after picking back the caret’s own style, a deviation is followed: the new style is shown and named', async () => {
    // e2e/styling.cjs: picking `body` back left `body` pinned, so after "this paragraph only" made `body-changed`
    // the menu kept showing `body` (no invitation to name, and the next edit went to `body` for everyone).
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    editor.pick('quote')
    editor.pick('body')
    await editor.toggleBold()
    expect(editor.current?.id).toBe('body-changed')
    expect(editor.invitesName).toBe(true)
    await editor.toggleItalic()
    expect(host.sent.at(-1)).toEqual(['change', 'body-changed', { set: { 'font-style': 'italic' } }])
  })
})

describe('naming', () => {
  it('invites a name for a style made by deviating, once, until it is dismissed or named', async () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    expect(editor.invitesName).toBe(false)
    await editor.toggleBold()
    expect(editor.invitesName).toBe(true)
    editor.dismissNaming()
    expect(editor.invitesName).toBe(false)
  })

  it('naming the style asks the server and ends the invitation', async () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    await editor.toggleBold()
    expect(await editor.name('  Accent ')).toBe(true)
    expect(host.sent.at(-1)).toEqual(['rename', 'body-changed', 'Accent'])
    expect(await editor.name('   ')).toBe(false)
  })
})

describe('the gallery of a slot (D316, style-editor-two-slots.svg)', () => {
  const s = (id: string, kind: string, computed: Css = {}): StyleView => ({ ...view(id, computed), kind })
  const styles = [
    s('body-text', 'paragraph'),
    s('definition', 'paragraph', { 'background-color': '#eee', 'border-left': '3px solid #13917f' }),
    s('plain-box', 'box'),
    s('callout', 'box', { 'background-color': '#e9e6f6' }),
    s('plain-shape', 'outline', { fill: '#eee' }),
  ]

  it('offers a box its own box styles, then the whole styles that set a box', () => {
    const { own, bundles } = galleryFor(styles, STYLE_MODEL.slots.text[0], STYLE_MODEL)
    expect(own.map((x) => x.id)).toEqual(['plain-box', 'callout'])
    expect(bundles.map((x) => x.id)).toEqual(['definition']) // Body text sets no box: nothing would change
  })

  it('offers words only paragraph styles, and an outline only outline styles', () => {
    expect(galleryFor(styles, STYLE_MODEL.slots.text[1], STYLE_MODEL)).toEqual({ own: [styles[0], styles[1]], bundles: [] })
    expect(galleryFor(styles, STYLE_MODEL.slots.shape[0], STYLE_MODEL).own.map((x) => x.id)).toEqual(['plain-shape'])
  })

  it('offers nothing without a slot', () => {
    expect(galleryFor(styles, undefined, STYLE_MODEL)).toEqual({ own: [], bundles: [] })
  })

  it('shows the facets of a slot and of a kind in the editor’s order', () => {
    expect(facetsOfSlot(STYLE_MODEL.slots.text[1])).toEqual(['text', 'paragraph'])
    expect(facetsOfSlot(STYLE_MODEL.slots.paragraph[0])).toEqual(['text', 'paragraph', 'box'])
    expect(facetsOfKind(STYLE_MODEL, 'outline')).toEqual(['outline'])
    expect(facetsOfKind(null, 'paragraph')).toEqual([])
  })
})

describe('a box: borders per side and padding', () => {
  it('reads a border as width and colour, and nothing for what is not a plain solid line', () => {
    expect(borderOf('3px solid @accent')).toEqual({ width: 3, colour: '@accent' })
    expect(borderOf(undefined)).toBeNull()
    expect(borderOf('thin dotted red')).toBeNull()
  })

  it('sets a border on the chosen sides, and takes it away at width 0', async () => {
    const host = new FakeHost()
    host.currentId = 'quote'
    const editor = new StyleEditor(host)
    editor.setScope('every')
    await editor.setBorder(['left'], 3, '@accent')
    await editor.setBorder(SIDES, 0, '@accent')
    expect(host.sent).toEqual([
      ['change', 'quote', { set: { 'border-left': '3px solid @accent' } }],
      ['change', 'quote', { unset: ['border-top', 'border-right', 'border-bottom', 'border-left'] }],
    ])
  })

  it('opens the border controls on the side that has one, or on all four when they agree', () => {
    // Found in a browser: Quote's rule on the left showed as "all sides: 0, none".
    const host = new FakeHost()
    host.styles = [view('body', {}), view('quote', { 'border-left': '3px solid @accent' }, 'body')]
    const editor = new StyleEditor(host)
    expect(editor.borderSide()).toBe('all')
    editor.pick('quote')
    expect(editor.borderSide()).toBe('left')
  })

  it('sets the same padding on all four sides, never below 0', async () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host)
    editor.setScope('every')
    await editor.setPadding(-4)
    expect(host.sent[0]).toEqual(['change', 'body', { set: { 'padding-top': '0px', 'padding-right': '0px', 'padding-bottom': '0px', 'padding-left': '0px' } }])
  })
})

describe('the All styles editor (D302)', () => {
  it('sends every change to every use, even of the caret’s own style', async () => {
    const host = new FakeHost()
    const editor = new StyleEditor(host, true)
    editor.pick('body')
    expect(editor.scope).toBe('every')
    editor.setScope('new')
    expect(editor.scope).toBe('every')
    await editor.set('color', '#123456')
    expect(host.sent).toEqual([['change', 'body', { set: { color: '#123456' } }]])
  })
})
