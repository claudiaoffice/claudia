import { describe, expect, it } from 'vitest'
import type { Css, CssCheck, CssEdit, StyleView } from '~/lib/style-css'
import { StyleEditor, type StyleHost } from '~/lib/style-host'

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
