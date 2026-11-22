// The dialogs of the text app, as Penpot components and pages: the Styles dialog (StylesDialog.vue with the editor of
// StyleSpec.vue) and the Search & replace panel (SearchPanel.vue). Everything is built from the tokens, and the parts
// that more than one dialog uses (fields, selects, check boxes, buttons, links, flags) are components of their own.
//
// This file is built AFTER the front page's library and page: the ids of a file's shapes come from the order they are
// made in, and the ids of what was there must not move.
import { board, circle, component, instance, pick, rect, text, variantSet } from './model.mjs'
import { line, vector } from './library.mjs'

/** The shell of a modal dialog (Modal.vue): a title bar, what the dialog says, a row of buttons. */
const dialogShell = (name, width, ...children) =>
  board(name, { w: width, h: 'auto', layout: 'column', gap: 'space.14', pad: ['space.24', 'space.26'], radius: 'radius.dialog', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' }, shadow: 'shadow.card' }, ...children)

// --- the parts -------------------------------------------------------------------------------------------------

export function buildDialogLibrary(lib) {
  const d = {}

  // Dialogs / Grip: the six dots that say a dialog can be moved (UX-39)
  const dots = []
  for (const [i, x] of [1.1, 6.1].entries()) for (const [j, y] of [1.6, 6.6, 11.6].entries()) dots.push(circle(`dot ${j * 2 + i + 1}`, { x, y, w: 2.8, h: 2.8, fill: 'color.muted' }))
  d.grip = component(board('Grip', { w: 10, h: 16 }, ...dots), { name: 'Grip', path: 'Dialogs' })

  // Dialogs / Icon button: a glyph in a small square (.icon)
  const GLYPH = { more: '⋯', close: '✕', up: '▲', down: '▼' }
  d.iconButton = variantSet(
    'Icon button',
    'Dialogs',
    { Glyph: Object.keys(GLYPH), Size: ['regular', 'small'] },
    ({ Glyph, Size }) => {
      const small = Size === 'small'
      const side = small ? 'size.icon-button-s' : 'size.icon-button'
      return board('Icon button', { w: side, h: side, layout: 'row', align: 'center', justify: 'center', radius: 'radius.chip' }, text('glyph', GLYPH[Glyph], { style: small ? 'glyph-small' : 'glyph', color: 'color.muted' }))
    },
    { w: 760 },
  )

  // Dialogs / Check box (the box alone) and Check (the box with its label)
  const tick = () => vector('tick', 'M3.5 8.4l3 3 6-6.6', 1, { stroke: line(null, 2, { raw: '#FFFFFF' }) })
  d.checkbox = variantSet(
    'Check box',
    'Dialogs',
    { Checked: ['no', 'yes'] },
    ({ Checked }) => {
      const on = Checked === 'yes'
      return board('Check box', { w: 'size.check', h: 'size.check', radius: 'radius.mark', fill: on ? 'color.app' : 'color.surface', stroke: { color: on ? 'color.app' : 'color.line-field', width: 'border.1' } }, ...(on ? [tick()] : []))
    },
    { w: 400 },
  )
  d.check = variantSet(
    'Check',
    'Dialogs',
    { Checked: ['no', 'yes'] },
    ({ Checked }) => board('Check', { layout: 'row', align: 'center', gap: 'space.7' }, instance(pick(d.checkbox, { Checked }), { nested: true }), text('label', 'Match case', { style: 'control', color: 'color.text' })),
    { w: 400 },
  )

  // Dialogs / Select: a choice shown in a box with a caret (.field select, .font-btn); the native one is what the
  // heading level and the numbering use today, kept apart so that it can be replaced
  const caret = () => text('caret', '▾', { style: 'glyph-small', color: 'color.muted' })
  d.select = variantSet(
    'Select',
    'Dialogs',
    { Kind: ['panel', 'labelled', 'tool', 'native'] },
    ({ Kind }) => {
      const box = { w: Kind === 'native' ? 200 : 160, h: 'auto', layout: 'row', align: 'center', gap: 'space.4', pad: ['space.6', 'space.8'], radius: 'radius.field', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' } }
      if (Kind === 'labelled') return board('Select', { ...box, gap: 'space.6' }, board('said', { w: 'fill', h: 'auto', layout: 'row', gap: 'space.4' }, text('label', 'Look in:', { style: 'control', color: 'color.text' }), text('value', 'Everything (5)', { style: 'control-strong', color: 'color.text' })), caret())
      if (Kind === 'tool') return board('Select', { ...box, h: 'size.control', pad: [0, 'space.10'], gap: 'space.8' }, text('value', 'Inter', { style: 'body', color: 'color.text', w: 'fill' }), caret())
      if (Kind === 'native') return board('Select', { ...box, h: 21, pad: ['space.2', 'space.4'], radius: 'radius.mark' }, text('value', 'No heading (no parent)', { style: 'control', color: 'color.text', w: 'fill' }), caret())
      return board('Select', box, text('value', 'The whole text', { style: 'control', color: 'color.text', w: 'fill' }), caret())
    },
    { w: 760 },
  )

  // Dialogs / Input: a text box of the search panel (.field), with the focus ring the app colour
  d.input = variantSet(
    'Input',
    'Dialogs',
    { State: ['default', 'focus'] },
    ({ State }) => {
      const focus = State === 'focus'
      return board('Input', { w: 300, h: 'auto', layout: 'row', align: 'center', gap: 'space.4', pad: focus ? ['space.5', 'space.7'] : ['space.6', 'space.8'], radius: 'radius.field', fill: 'color.surface', stroke: { color: focus ? 'color.app' : 'color.line-field', width: focus ? 'border.2' : 'border.1' } }, text('value', 'paragraph', { style: 'control', color: 'color.text', w: 'fill' }))
    },
    { w: 760 },
  )

  // Dialogs / Panel button: the button of the search panel (.btn at 13px)
  d.button = variantSet(
    'Panel button',
    'Dialogs',
    { Kind: ['default', 'primary', 'accent'] },
    ({ Kind }) => {
      const primary = Kind === 'primary'
      const accent = Kind === 'accent'
      return board(
        'Panel button',
        { w: 170, h: 'auto', layout: 'row', align: 'center', justify: 'center', pad: ['space.6', 'space.16'], radius: 'radius.pill', fill: primary ? 'color.ink' : undefined, stroke: { color: primary ? 'color.ink' : accent ? 'color.app' : 'color.line-field', width: 'border.1' } },
        text('label', 'Replace this one', { style: 'button-panel', color: primary ? 'color.paper' : accent ? 'color.app-text' : 'color.text' }),
      )
    },
    { w: 760 },
  )

  // Dialogs / Flag: a small pill (what kind of match it is, what a style is waiting for)
  d.flag = variantSet(
    'Flag',
    'Dialogs',
    { Kind: ['kind', 'to-name', 'hidden'] },
    ({ Kind }) => {
      const fill = { kind: 'color.faint', 'to-name': 'color.purpose-input', hidden: 'color.mist' }[Kind]
      const ink = { kind: 'color.muted', 'to-name': 'color.apricot-dark', hidden: 'color.text' }[Kind]
      return board('Flag', { layout: 'row', align: 'center', pad: Kind === 'kind' ? ['space.1', 'space.7'] : ['space.1', 'space.6'], radius: 'radius.pill', fill }, text('label', { kind: 'text', 'to-name': 'to name', hidden: 'hidden' }[Kind], { style: Kind === 'kind' ? 'badge' : 'link', color: ink }))
    },
    { w: 760 },
  )

  // Dialogs / Link: text in the app colour; the letter that Alt + it acts on is underlined (D783)
  d.link = variantSet(
    'Link',
    'Dialogs',
    { Weight: ['regular', 'strong'], Mnemonic: ['no', 'yes'] },
    ({ Weight, Mnemonic }) => {
      const style = Weight === 'strong' ? 'link-strong' : 'link'
      return board('Link', { layout: 'row' }, ...(Mnemonic === 'yes' ? [text('mn', 'E', { style, color: 'color.app-text', underline: true })] : []), text('tail', Mnemonic === 'yes' ? 'dit' : 'Rename', { style, color: 'color.app-text' }))
    },
    { w: 760 },
  )

  // Dialogs / Switch: Controls | CSS, one segment chosen
  d.switch = variantSet(
    'Switch',
    'Dialogs',
    { Chosen: ['Controls', 'CSS'] },
    ({ Chosen }) => {
      const seg = (label) => board(label, { w: 'auto', h: 22, layout: 'row', align: 'center', pad: [0, 'space.10'], radius: 'radius.chip', fill: Chosen === label ? 'color.surface' : undefined, shadow: Chosen === label ? 'shadow.raised' : undefined }, text('label', label, { style: 'switch', color: Chosen === label ? 'color.text' : 'color.muted' }))
      return board('Switch', { layout: 'row', pad: 'space.2', radius: 'radius.field', fill: 'color.mist' }, seg('Controls'), seg('CSS'))
    },
    { w: 400 },
  )

  // Dialogs / Stepper: − value +, with the unit when there is one
  d.stepper = variantSet(
    'Stepper',
    'Dialogs',
    { Unit: ['none', 'pt'] },
    ({ Unit }) => {
      const pt = Unit === 'pt'
      const sign = (name, glyph, w) => board(name, { w, h: 28, layout: 'row', align: 'center', justify: 'center' }, text('sign', glyph, { style: 'sign', color: 'color.text' }))
      return board(
        'Stepper',
        { w: pt ? 115 : 92, h: 'size.control', layout: 'row', align: 'center', radius: 'radius.field', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' } },
        sign('minus', '−', pt ? 26 : 28),
        board('value', { w: pt ? 42 : 34, h: 28, layout: 'row', align: 'center', justify: pt ? 'end' : 'center', pad: [0, pt ? 'space.2' : 'space.4'] }, text('number', pt ? '12' : '0', { style: 'mono-value', color: 'color.text' })),
        ...(pt ? [board('unit', { w: 'auto', h: 28, layout: 'row', align: 'center', pad: [0, 'space.4', 0, 'space.2'] }, text('unit', 'pt', { style: 'kbd', color: 'color.muted' }))] : []),
        sign('plus', '+', pt ? 26 : 28),
      )
    },
    { w: 400 },
  )

  // Dialogs / Colour button: the colour of a part of a style, picked by its meaning
  d.colour = variantSet(
    'Colour button',
    'Dialogs',
    { Swatch: ['colour', 'none'] },
    ({ Swatch }) => {
      const none = Swatch === 'none'
      const swatch = none
        ? board('swatch', { w: 16, h: 16, radius: 'radius.swatch', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' }, clip: true }, vector('hatch', 'M-2 18 L18 -2 M2 22 L22 2 M-6 14 L14 -6', 1, { stroke: line('color.line', 1) }))
        : board('swatch', { w: 16, h: 16, radius: 'radius.swatch', fill: 'color.text', stroke: { color: 'color.line-field', width: 'border.1' } })
      return board('Colour button', { w: 'auto', h: 'size.control', layout: 'row', align: 'center', gap: 'space.7', pad: [0, 'space.9'], radius: 'radius.field', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' } }, swatch, text('what', 'Text', { style: 'control', color: 'color.text' }), text('is', none ? 'None' : 'Text', { style: 'hint', color: 'color.muted' }))
    },
    { w: 400 },
  )

  // Dialogs / Mark: one button of a group (bold, italic, align, which side a border is on)
  const ALIGN = { left: 'M2 3h12M2 6.5h8M2 10h12M2 13.5h8', center: 'M2 3h12M4 6.5h8M2 10h12M4 13.5h8', right: 'M2 3h12M6 6.5h8M2 10h12M6 13.5h8', justify: 'M2 3h12M2 6.5h12M2 10h12M2 13.5h12' }
  const FACE = { bold: 'B', italic: 'I', underline: 'U', strike: 'S', all: '▢', top: '▔', 'side right': '▕', bottom: '▁', 'side left': '▏', 'align left': 0, 'align center': 0, 'align right': 0, 'align justify': 0 }
  d.mark = variantSet(
    'Mark',
    'Dialogs',
    { Face: Object.keys(FACE), On: ['no', 'yes'] },
    ({ Face, On }) => {
      const on = On === 'yes'
      const ink = on ? 'color.app-text' : 'color.text'
      let face
      if (Face.startsWith('align ')) face = vector('glyph', ALIGN[Face.slice(6)], 14 / 16, { stroke: line(ink, 1.5 * (14 / 16)) })
      else if (Face === 'bold') face = text('glyph', 'B', { style: 'mark-bold', color: ink })
      else if (Face === 'italic') face = text('glyph', 'I', { style: 'mark-italic', color: ink })
      else if (Face === 'underline') face = text('glyph', 'U', { style: 'glyph', color: ink, underline: true })
      else if (Face === 'strike') face = text('glyph', 'S', { style: 'glyph', color: ink, strike: true })
      else face = text('glyph', FACE[Face], { style: 'glyph', color: ink })
      return board('Mark', { w: 'size.segment', h: 28, layout: 'row', align: 'center', justify: 'center', fill: on ? 'color.app-selected' : 'color.surface' }, face)
    },
    { w: 1000 },
  )

  // Dialogs / Notice: what a change in the editor does (it goes to every use)
  d.notice = component(board('Notice', { w: 454, h: 'auto', layout: 'row', pad: ['space.7', 'space.9'], radius: 'radius.field', fill: 'color.app-wash' }, text('text', 'A change here changes every use of “Body text” (3).', { style: 'summary', color: 'color.text', w: 'fill' })), { name: 'Notice', path: 'Dialogs' })

  // Dialogs / Sentence: what a pattern finds, in words
  d.sentence = component(board('Sentence', { w: 346, h: 'auto', layout: 'row', pad: ['space.10', 'space.12'], radius: 'radius.row', fill: 'color.mist' }, text('text', 'Finds the text “paragraph”.', { style: 'sentence', color: 'color.text', w: 'fill' })), { name: 'Sentence', path: 'Dialogs' })

  // Dialogs / Dialog header and Panel header
  d.dialogHeader = component(board('Dialog header', { w: 'auto', h: 'auto', layout: 'row', align: 'center', gap: 'space.10' }, instance(d.grip, { nested: true }), text('title', 'Styles', { style: 'dialog-title', color: 'color.text' })), { name: 'Dialog header', path: 'Dialogs' })
  d.panelHeader = component(
    board(
      'Panel header',
      { w: 378, h: 'auto', layout: 'column' },
      board('bar', { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.4', pad: ['space.10', 'space.12', 'space.8', 'space.14'] }, instance(d.grip, { nested: true }), text('title', 'Search & replace', { style: 'panel-title', color: 'color.text', w: 'fill' }), instance(pick(d.iconButton, { Glyph: 'more', Size: 'regular' }), { nested: true }), instance(pick(d.iconButton, { Glyph: 'close', Size: 'regular' }), { nested: true })),
      rect('divider', { w: 'fill', h: 'border.1', fill: 'color.line' }),
    ),
    { name: 'Panel header', path: 'Dialogs' },
  )

  // Dialogs / Style row: a style in the list while one is being edited (.pick), in its own look
  d.styleRow = variantSet(
    'Style row',
    'Dialogs',
    { Look: ['body', 'display', 'bold', 'italic'], State: ['default', 'current'] },
    ({ Look, State }) =>
      board(
        'Style row',
        { w: 240, h: 'auto', layout: 'row', align: 'center', gap: 'space.8', pad: ['space.6', 'space.10'], radius: 'radius.field', fill: State === 'current' ? 'color.app-selected' : undefined },
        text('name', 'Body text', { style: { body: 'pick-body', display: 'pick-display', bold: 'pick-bold', italic: 'pick-italic' }[Look], color: 'color.text', w: 'fill' }),
        text('count', '0', { style: 'mono-small', color: 'color.muted' }),
      ),
    { w: 1000 },
  )

  // Dialogs / Style entry: a style in the list of all styles, with what it is for and what can be done to it
  d.styleEntry = variantSet(
    'Style entry',
    'Dialogs',
    { Look: ['body', 'display'] },
    ({ Look }) =>
      board(
        'Style entry',
        { w: 466, h: 'auto', layout: 'column', gap: 'space.2', pad: ['space.8', 'space.10'], radius: 'radius.field' },
        text('name', 'Body text', { style: Look === 'body' ? 'sample-body' : 'sample-display', color: 'color.text', w: 'fill' }),
        board(
          'meta',
          { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.10' },
          text('purpose', 'running text', { style: 'hint', color: 'color.muted' }),
          text('count', '3 paragraphs', { style: 'mono-small', color: 'color.muted' }),
          board('spacer', { w: 'fill', h: 1 }),
          board(
            'links',
            { layout: 'row', gap: 'space.12' },
            instance(pick(d.link, { Weight: 'regular', Mnemonic: 'no' }), { nested: true }),
            instance(pick(d.link, { Weight: 'strong', Mnemonic: 'yes' }), { nested: true }),
            instance(pick(d.link, { Weight: 'regular', Mnemonic: 'yes' }), { nested: true, edit: { mn: { content: 'H' }, tail: { content: 'ide' } } }),
          ),
        ),
      ),
    { w: 1000 },
  )

  // Dialogs / Match row: one found place (.list li): where, the text around it with the hit marked, and what it is
  d.match = variantSet(
    'Match row',
    'Dialogs',
    { Replacing: ['no', 'yes'] },
    ({ Replacing }) => {
      const yes = Replacing === 'yes'
      const hit = board('mark', { layout: 'row', align: 'center', pad: [0, 'space.2'], radius: 'radius.mark', fill: 'color.purpose-input' }, text('hit', 'paragraph', { style: 'control', color: 'color.text', underline: true }))
      return board(
        'Match row',
        { w: 346, h: 'auto', layout: 'row', align: 'center', gap: 'space.6', radius: 'radius.field' },
        ...(yes ? [board('tick', { w: 20, h: 'auto', layout: 'row', align: 'center', justify: 'center' }, instance(pick(d.checkbox, { Checked: 'yes' }), { nested: true }))] : []),
        board(
          'row',
          { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.6', pad: ['space.5', 'space.6'] },
          text('where', 'Paragraph 2', { style: 'mono-small', color: 'color.muted' }),
          board('excerpt', { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.2', clip: true }, text('before', 'A ', { style: 'control', color: 'color.text' }), hit, ...(yes ? [text('arrow', ' →', { style: 'control', color: 'color.text' }), text('after', 'passage', { style: 'button-panel', color: 'color.app-text' })] : [text('tail', ' that gets a style of its own.', { style: 'control', color: 'color.text' })])),
          instance(pick(d.flag, { Kind: 'kind' }), { nested: true }),
        ),
      )
    },
    { w: 760 },
  )

  return d
}

// --- the Styles dialog -----------------------------------------------------------------------------------------

/** A group of marks (.marks): a bordered row of the buttons that belong together. */
const marks = (d, name, faces, chosen) => board(name, { layout: 'row', pad: 'space.1', radius: 'radius.field', stroke: { color: 'color.line-field', width: 'border.1' }, clip: true }, ...faces.map((Face) => instance(pick(d.mark, { Face, On: Face === chosen ? 'yes' : 'no' }), {})))

const heading = (name, content, style = 'facet') => text(name, content, { style, color: 'color.muted' })
const hr = () => rect('divider', { w: 'fill', h: 'border.1', fill: 'color.line' })

export function stylesPages(d, lib) {
  const row = (children, o = {}) => board('row', { w: 'fill', h: 'auto', layout: 'row', gap: 'space.8', ...o }, ...children)
  const check = (Checked, label) => instance(pick(d.check, { Checked }), { edit: { label: { content: label } } })
  const colour = (Swatch, what, is) => instance(pick(d.colour, { Swatch }), { edit: { what: { content: what }, is: { content: is } } })
  const stepper = (Unit, value) => instance(pick(d.stepper, { Unit }), { edit: { number: { content: value } } })
  const link = (content, o = {}) => text('link', content, { style: 'link', color: 'color.app-text', ...o })

  const sample = (Look, State, name, count) => instance(pick(d.styleRow, { Look, State }), { w: 'fill', edit: { name: { content: name }, count: { content: count } } })
  const SAMPLES = [
    ['body', 'Body text', 3],
    ['display', 'Title', 0],
    ['display', 'Heading 1', 0],
    ['display', 'Heading 2', 0],
    ['display', 'Heading 3', 0],
    ['bold', 'Heading 4', 0],
    ['bold', 'Heading 5', 0],
    ['italic', 'Heading 6', 0],
    ['italic', 'Quote', 0],
    ['body', 'Remark', 0],
    ['body', 'Contents Title', 0],
    ['bold', 'Contents 1', 0],
    ['body', 'Contents 2', 0],
    ['body', 'Contents 3', 0],
  ]

  // 1. the list of all styles, nothing being edited
  const PURPOSE = { 'Body text': 'running text', Title: 'names the document', 'Heading 1': 'a section', 'Heading 2': 'a subsection', 'Heading 3': 'a part of a subsection' }
  const entry = (name, Look, count) => instance(pick(d.styleEntry, { Look }), { w: 'fill', edit: { name: { content: name }, purpose: { content: PURPOSE[name] }, count: { content: `${count} paragraphs` } } })
  const list = dialogShell(
    'Styles - all styles',
    520,
    instance(d.dialogHeader, {}),
    board('list', { w: 'fill', h: 330, layout: 'column', gap: 'space.2', clip: true }, entry('Body text', 'body', 3), entry('Title', 'display', 0), entry('Heading 1', 'display', 0), entry('Heading 2', 'display', 0), entry('Heading 3', 'display', 0), entry('Heading 4', 'display', 0)),
    text('keys', 'Alt + the underlined letter acts on the style the focus is on.', { style: 'hint', color: 'color.muted', w: 'fill' }),
    board('buttons', { w: 'fill', h: 'auto', layout: 'row', justify: 'end', m: ['space.12', 0, 0, 0] }, instance(pick(lib.button, { Kind: 'default', Size: 'regular', State: 'default' }), { edit: { label: { content: 'Close' } } })),
  )

  // 2. one style being edited: the list on the left, what the style is made of on the right
  const textFacet = board(
    'Text facet',
    { w: 'fill', h: 'auto', layout: 'column', gap: 'space.8' },
    heading('title', 'Text'),
    row([instance(pick(d.select, { Kind: 'tool' }), { w: 'fill' }), instance(pick(d.stepper, { Unit: 'pt' }), {})], { align: 'start' }),
    row([marks(d, 'Font properties', ['bold', 'italic', 'underline', 'strike']), colour('colour', 'Text', 'Text')], { align: 'start' }),
  )
  const paragraphFacet = board(
    'Paragraph facet',
    { w: 'fill', h: 'auto', layout: 'column', gap: 'space.8' },
    hr(),
    heading('title', 'Paragraph'),
    marks(d, 'Alignment', ['align left', 'align center', 'align right', 'align justify'], 'align left'),
    check('yes', 'Hyphenate'),
    row([text('label', 'Heading', { style: 'hint', color: 'color.muted' }), instance(pick(d.select, { Kind: 'native' }), { w: 176 })], { align: 'center' }),
  )
  const boxFacet = board(
    'Box facet',
    { w: 'fill', h: 'auto', layout: 'column', gap: 'space.8' },
    hr(),
    heading('title', 'Box'),
    row([colour('none', 'Background', 'None')], { align: 'start' }),
    row([marks(d, 'Sides', ['all', 'top', 'side right', 'bottom', 'side left'], 'all'), stepper('none', '0'), colour('none', 'Border', 'None')], { align: 'start' }),
    row([text('label', 'Padding', { style: 'control', color: 'color.text' }), stepper('none', '0'), text('unit', 'px', { style: 'control', color: 'color.muted' })], { align: 'center' }),
  )
  const spec = board(
    'spec',
    { w: 'fill', h: 'auto', layout: 'column' },
    hr(),
    board(
      'spec body',
      { w: 'fill', h: 'auto', layout: 'column', gap: 'space.10', pad: ['space.10', 'space.8', 'space.8', 'space.8'] },
      row([heading('title', 'Look', 'spec-head'), instance(pick(d.switch, { Chosen: 'Controls' }), {})], { align: 'center', justify: 'space-between' }),
      instance(d.notice, { w: 'fill' }),
      board('controls', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.10' }, textFacet, paragraphFacet, boxFacet),
    ),
  )
  const editorPane = board(
    'editor pane',
    { w: 'fill', h: 'auto', layout: 'column', gap: 'space.10' },
    row(
      [board('names', { w: 'auto', h: 'auto', layout: 'column', gap: 'space.2' }, text('name', 'Body text', { style: 'editor-title', color: 'color.text' }), text('purpose', 'running text', { style: 'hint', color: 'color.muted' })), instance(pick(d.link, { Weight: 'regular', Mnemonic: 'no' }), {})],
      { align: 'start', justify: 'space-between', gap: 'space.12' },
    ),
    spec,
  )
  const editing = dialogShell(
    'Styles - editing a style',
    780,
    instance(d.dialogHeader, {}),
    board('panes', { w: 'fill', h: 'auto', layout: 'row', gap: 'space.16' }, board('list', { w: 240, h: 520, layout: 'column', gap: 'space.2', clip: true }, ...SAMPLES.map(([Look, name, count], i) => sample(Look, i === 0 ? 'current' : 'default', name, String(count)))), editorPane),
    board('buttons', { w: 'fill', h: 'auto', layout: 'row', justify: 'end', m: ['space.12', 0, 0, 0] }, instance(pick(lib.button, { Kind: 'default', Size: 'regular', State: 'default' }), { edit: { label: { content: 'Close' } } })),
  )

  return [list, editing]
}

// --- the Search & replace panel --------------------------------------------------------------------------------

export function searchPages(d) {
  const body = (...children) => board('body', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.8', pad: ['space.12', 'space.16', 'space.18', 'space.16'] }, ...children)
  const row = (children, o = {}) => board('row', { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.6', ...o }, ...children)
  const label = (content) => text('label', content, { style: 'label', color: 'color.muted', m: ['space.6', 0, 'space.2', 0] })
  const link = (content) => text('link', content, { style: 'control', color: 'color.app-text' })
  const select = (Kind, w, value, extra = {}) => instance(pick(d.select, { Kind }), { w, edit: { value: { content: value }, ...extra } })
  const button = (Kind, content, w = 'fill') => instance(pick(d.button, { Kind }), { w, edit: { label: { content } } })
  const tiny = (Glyph) => instance(pick(d.iconButton, { Glyph, Size: 'small' }), {})
  const options = (rowsBelow = []) =>
    board(
      'options',
      { w: 'fill', h: 'auto', layout: 'column', gap: 'space.10' },
      row([select('labelled', 211, 'Everything (5)'), select('panel', 'fill', 'The whole text')]),
      row([instance(pick(d.check, { Checked: 'no' }), { edit: { label: { content: 'Match case' } } }), instance(pick(d.check, { Checked: 'no' }), { edit: { label: { content: 'Whole text' } } })], { gap: 'space.18' }),
      ...rowsBelow,
    )
  const results = (summary, sub, rows, tail) =>
    board(
      'results',
      { w: 'fill', h: 'fill', layout: 'column', gap: 'space.6', pad: ['space.10', 'space.16'] },
      board('head', { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.6' }, text('summary', summary, { style: 'control-strong', color: 'color.text' }), ...(sub ? [text('sub', sub, { style: 'hint', color: 'color.muted' })] : [])),
      board('list', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.2' }, ...rows),
      ...(tail ?? []),
    )
  const footer = (...children) => board('footer', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.8', pad: ['space.10', 'space.16', 'space.12', 'space.16'] }, hr(), ...children)
  const panel = (name, ...children) =>
    board(name, { w: 380, h: 664, layout: 'column', radius: 'radius.panel', fill: 'color.surface', stroke: { color: 'color.line', width: 'border.1' }, shadow: 'shadow.panel', clip: true }, instance(d.panelHeader, { w: 'fill' }), ...children)
  const match = (Replacing, where, before, tail) => instance(pick(d.match, { Replacing }), { w: 'fill', edit: { where: { content: where }, before: { content: before }, ...(Replacing === 'yes' ? {} : { tail: { content: tail } }) } })
  const replaceSection = (content, State = 'default', w = 206) =>
    board('replace', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.2' }, label('Replace with'), instance(pick(d.input, { State }), { w, edit: { value: { content } } }), link('Close Replace'))

  // 1. finding: the quick field, and what else decides what is found
  const quick = () => row([instance(pick(d.input, { State: 'focus' }), { w: 'fill' }), tiny('up'), tiny('down')], { gap: 'space.4' })
  const finding = panel(
    'Search & replace - find',
    body(quick(), options([row([button('accent', 'Replace with… ›', 'fill'), button('accent', 'Build a pattern…', 'fill')], { gap: 'space.10', m: ['space.6', 0, 0, 0] })])),
    results('2 matches', null, [match('no', 'Paragraph 2', 'A ', ' that gets a style of its own.'), match('no', 'Paragraph 3', 'A ', ' of plain body text.')]),
    board('keys', { w: 'fill', h: 'auto', layout: 'column', pad: ['space.10', 'space.16', 'space.12', 'space.16'] }, hr(), text('hint', 'Enter: next match · Shift+Enter: previous · Esc: close', { style: 'hint', color: 'color.muted', w: 'fill' })),
  )

  // 2. finding and replacing
  const replacing = panel(
    'Search & replace - replace',
    body(quick(), options([row([button('accent', 'Build a pattern…', 'fill')], { m: ['space.6', 0, 0, 0] })]), replaceSection('passage')),
    results('2 matches', '· 2 will change, 0 skipped', [match('yes', 'Paragraph 2', 'A '), match('yes', 'Paragraph 3', 'A ')]),
    footer(row([button('default', 'Replace this one'), button('primary', 'Replace all 2')], { gap: 'space.8' }), text('hint', 'One step in the history. Undo brings it back.', { style: 'hint', color: 'color.muted', w: 'fill' })),
  )

  // 3. the builder: a pattern put together from parts, said in a sentence
  const part = board(
    'part',
    { w: 'fill', h: 'auto', layout: 'row', wrap: true, align: 'center', gap: 'space.6' },
    select('panel', 168, 'the text'),
    instance(pick(d.input, { State: 'default' }), { w: 53, edit: { value: { content: 'parag' } } }),
    select('panel', 113, 'once'),
    link('Keep'),
    tiny('close'),
  )
  const builder = board(
    'builder',
    { w: 'fill', h: 'auto', layout: 'column', gap: 'space.8' },
    label('Find'),
    part,
    link('+ Add a part'),
    label('Only in texts that…'),
    link('+ Add a condition'),
    instance(d.sentence, { w: 'fill', m: ['space.4', 0, 0, 0] }),
  )
  const building = panel(
    'Search & replace - builder',
    body(builder, options(), replaceSection('\u00a0', 'focus', 'fill')),
    results('2 matches', '· 2 will change, 0 skipped', [match('yes', 'Paragraph 2', 'A '), match('yes', 'Paragraph 3', 'A ')]),
    footer(row([button('default', 'Replace this one'), button('primary', 'Replace all 2')], { gap: 'space.8' }), text('hint', 'One step in the history. Undo brings it back.', { style: 'hint', color: 'color.muted', w: 'fill' })),
  )

  return [finding, replacing, building]
}
