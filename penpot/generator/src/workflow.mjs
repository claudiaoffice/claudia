// The designs of E16 Workflow as Penpot components and screens: the corkboard (composes, computes, creates), quiet
// mode (Focus mode) and the binder (Here, Everything by folder and by place, the docks open and hidden).
// They are the mocks agreed with the owner (decisions D1101 to D1116 in claudiaoffice-log), drawn in the language of the
// file: the workspace of the web app (top bar, menus, tab strip, the History & Chat panel) and its tokens.
//
// Built AFTER everything else: the ids of a file's shapes come from the order they are made in, and must not move.
// Every size, colour and text style is one the file already has; nothing here adds a token.
//
// The screens of composes and creates show the colours of the app that is switched on in Penpot (Config ▸ Themes ▸ App):
// a shape here carries the token (color.app), so choosing "composes" or "creates" recolours them, as for the rest of the file.
import { board, circle, component, instance, path, pick, rect, text, variantSet } from './model.mjs'
import { vector } from './library.mjs'
import { PANEL_TEXT, WHITE, W, H, footer, formulaBar, hline, insertBar, menuBar, sidePanel, topBar, withNotes } from './workspace.mjs'

const IRIS_HEX = '#5B4BC4'
const IRIS = { raw: IRIS_HEX } // --iris: the person's own marks (open points, the selected card)
const IRIS_WASH = { raw: '#5B4BC4', opacity: 0.14 }
const MIST_SOFT = { raw: '#E7E1F4', opacity: 0.55 } // the wash behind a board of cards
const BOARD = { raw: '#EFEBF7' }
const DARK_EDGE = '#4A4566'
const DOCK = 340
const BINDER = 260

// --- the library -----------------------------------------------------------------------------------------------

const kindIcon = (Kind) => {
  const k = { w: 26, h: 26, layout: 'row', align: 'center', justify: 'center', radius: 'radius.chip', fill: IRIS_WASH }
  const ink = { stroke: { color: 'color.ink', width: 1.4, align: 'center', cap: 'round' } }
  const g = {
    text: () => vector('lines', 'M2 3 H14 M2 8 H14 M2 13 H9', 1, ink),
    sketch: () => vector('squiggle', 'M1 12 C3 4 5 4 7 9 C9 14 11 14 15 4', 1, ink),
    image: () => board('image', { w: 16, h: 13 }, rect('frame', { w: 16, h: 13, radius: 2, stroke: { color: 'color.ink', width: 1.4 } }), vector('hills', 'M2 11 L6 6 L9 9 L11 7 L14 11', 1, ink)),
    source: () => vector('page', 'M3 1 H10 L13 4 V15 H3 Z M10 1 V4 H13', 1, ink),
  }
  return board('kind', k, g[Kind]())
}

const glyphSpeech = (color) => vector('open', 'M1 1 H12 V9 H6 L3 12 V9 H1 Z', 1, { fill: color })

export function buildWorkflowLibrary() {
  const f = {}

  // Workflow / Status chip: Status (a status is an icon and a word, never a colour alone: BITV)
  f.status = variantSet(
    'Status chip',
    'Workflow',
    { Status: ['none', 'draft', 'doing', 'done'] },
    ({ Status }) => {
      const icon = {
        none: () => circle('icon', { w: 14, h: 14, stroke: { color: 'color.muted', width: 1.2, style: 'dashed', dash: 2, dashGap: 2 } }),
        draft: () => circle('icon', { w: 14, h: 14, stroke: { color: 'color.text', width: 1.4 } }),
        doing: () => board('icon', { w: 14, h: 14 }, circle('ring', { w: 14, h: 14, stroke: { raw: IRIS_HEX, width: 1.4 } }), vector('half', 'M7 1 A6 6 0 0 0 7 13 Z', 1, { fill: IRIS })),
        done: () => board('icon', { w: 14, h: 14 }, circle('disc', { w: 14, h: 14, fill: 'color.teal' }), vector('check', 'M3.5 7.5 L6 10 L10.5 4.5', 1, { stroke: { raw: '#FFFFFF', width: 1.6, align: 'center', cap: 'round' } })),
      }[Status]
      const label = { none: 'No status', draft: 'Draft', doing: 'Building', done: 'Checked' }[Status]
      return board('Status chip', { layout: 'row', align: 'center', gap: 'space.6', pad: ['space.3', 'space.10'], radius: 'radius.pill', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' } }, icon(), text('label', label, { style: 'chip', color: 'color.text' }))
    },
    { w: 760 },
  )

  // Workflow / Open badge (an open point on a card or a row)
  f.open = component(board('Open badge', { layout: 'row', align: 'center', gap: 'space.4', pad: ['space.3', 'space.8'], radius: 'radius.pill', fill: IRIS_WASH }, glyphSpeech(IRIS), text('label', '2 open', { style: 'badge', color: IRIS })), { name: 'Open badge', path: 'Workflow' })

  // Workflow / Segmented: Chosen (Here | Everything, Folders | By place, By dependency | By sheet)
  f.segmented = variantSet(
    'Segmented',
    'Workflow',
    { Chosen: ['first', 'second'] },
    ({ Chosen }) => {
      const seg = (name, label, on) => board(name, { w: 'fill', h: 'auto', layout: 'row', justify: 'center', pad: ['space.5', 'space.8'], radius: 'radius.control', fill: on ? 'color.surface' : undefined, shadow: on ? 'shadow.raised' : undefined }, text(`label ${name}`, label, { style: 'switch', color: on ? 'color.ink' : 'color.muted' }))
      return board('Segmented', { w: 240, h: 'auto', layout: 'row', pad: 'space.2', radius: 'radius.control', fill: MIST_SOFT }, seg('first', 'Here', Chosen === 'first'), seg('second', 'Everything', Chosen === 'second'))
    },
    { w: 600 },
  )

  // Workflow / Binder row: Kind × State (one line: icon, first words, a ring with the number of places, a flag)
  f.row = variantSet(
    'Binder row',
    'Workflow',
    { Kind: ['text', 'sketch', 'image', 'source'], State: ['default', 'selected'] },
    ({ Kind, State }) =>
      board(
        'Binder row',
        { w: 236, h: 'auto', layout: 'row', align: 'center', gap: 'space.8', pad: ['space.3', 'space.4'], radius: 'radius.control', stroke: State === 'selected' ? { raw: IRIS_HEX, width: 'border.2' } : undefined, fill: State === 'selected' ? IRIS_WASH : undefined },
        kindIcon(Kind),
        text('title', 'First words of the item', { style: State === 'selected' ? 'control-strong' : 'control', color: 'color.ink', w: 'fill' }),
        board('places', { layout: 'row', align: 'center', gap: 'space.2', hidden: true }, circle('ring', { w: 9, h: 9, stroke: { raw: IRIS_HEX, width: 1.4 } }), text('count', '3', { style: 'mono-small', color: IRIS })),
        glyphSpeech(IRIS),
        vector('done', 'M1 1 H13 V10 H1 Z M3.5 5.5 L6 8 L10.5 3', 1, { stroke: { color: 'color.teal', width: 1.4, align: 'center', cap: 'round' }, hidden: true }),
      ),
    { w: 900 },
  )
  // the open flag is on by default in the variants; an instance hides it (edit.hidden), or shows the done mark instead

  // Workflow / Dock handle: Points (the hide/show handle on the border of a dock; the chevron points the way it goes)
  f.handle = variantSet(
    'Dock handle',
    'Workflow',
    { Points: ['left', 'right'] },
    ({ Points }) => board('Dock handle', { w: 18, h: 40, radius: 9, fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' } }, vector('chevron', Points === 'left' ? 'M6 0 L1 6 L6 12' : 'M0 0 L5 6 L0 12', 1, { x: Points === 'left' ? 6 : 7, y: 14, stroke: { color: 'color.muted', width: 1.6, align: 'center', cap: 'round' } })),
    { w: 400 },
  )

  // Workflow / Quiet pill (Focus mode: what is held back, and how to see it)
  f.pill = component(
    board(
      'Quiet pill',
      { layout: 'row', align: 'center', gap: 'space.10', pad: ['space.8', 'space.16'], radius: 'radius.pill', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' }, shadow: 'shadow.card' },
      vector('moon', 'M12 9.5 A6 6 0 1 1 6.5 4 A4.5 4.5 0 0 0 12 9.5 Z', 1, { fill: 'color.ink' }),
      text('summary', 'ai and chat are quiet · 2 suggestions, 1 mention held', { style: 'control', color: 'color.text' }),
      text('show', 'Show', { style: 'link-strong', color: IRIS }),
    ),
    { name: 'Quiet pill', path: 'Workflow' },
  )
  return f
}

// --- pieces ----------------------------------------------------------------------------------------------------

const chip = (f, Status, label) => instance(pick(f.status, { Status }), { edit: { label: { content: label } } })
const hint = (t, o = {}) => text('hint', t, { style: 'hint', color: 'color.muted', ...o })
const pill = (name, label, o = {}) => board(name, { layout: 'row', align: 'center', pad: ['space.3', 'space.10'], radius: 'radius.pill', stroke: { color: 'color.line-field', width: 'border.1' }, ...o }, text('label', label, { style: 'hint', color: 'color.text' }))
const spacer = () => board('spacer', { w: 'fill', h: 'fill' })
const noteText = (t, empty) => (empty ? text('note', 'Put your goals, summary or other notes here …', { style: 'hint', color: 'color.muted', italic: true, w: 'fill' }) : text('note', t, { style: 'hint', color: 'color.text', w: 'fill' }))
const tip = (label, x, y) => board('Hover label', { abs: true, x, y, layout: 'row', pad: ['space.5', 'space.10'], radius: 'radius.menu-item', fill: 'color.ink', shadow: 'shadow.card' }, text('label', label, { style: 'hint', color: WHITE }))
const handle = (f, Points, x, y = 190) => instance(pick(f.handle, { Points }), { abs: true, x, y })

/** The dock on the right: the History & Chat panel with a little content, as the app has it. */
function dock(items) {
  const bubble = (who, t, accent) => board('message', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.2', pad: ['space.7', 'space.10'], radius: 'radius.control', fill: accent ? { raw: '#5B4BC4', opacity: 0.38 } : { raw: '#FFFFFF', opacity: 0.08 } }, text('who', who, { style: 'panel-tab', color: PANEL_TEXT(0.7) }), text('text', t, { style: 'hint', color: PANEL_TEXT(0.95), w: 'fill' }))
  const change = (t) => text('change', t, { style: 'mono-small', color: PANEL_TEXT(0.7) })
  const input = board('field', { w: 'fill', h: 'auto', layout: 'row', pad: ['space.8', 'space.10'], radius: 'radius.control', stroke: { raw: '#FFFFFF', opacity: 0.28, width: 'border.1' } }, text('hint', '@ai or @Mara … # to reference', { style: 'hint', color: PANEL_TEXT(0.6) }))
  return sidePanel(items.history.map(([k, a, b]) => (k === 'change' ? change(a) : bubble(a, b, k === 'session'))), [...items.chat.map(([k, a, b]) => bubble(a, b, k === 'you')), spacer(), input])
}

const flag = (n, open = true) =>
  board('flag', { abs: true, x: 0, y: 0, layout: 'row', align: 'center', justify: 'center', w: 14, h: 14, radius: 'radius.mark', fill: open ? IRIS : 'color.surface', stroke: open ? undefined : { color: 'color.teal', width: 1.2 } }, text('n', n, { style: 'badge', color: open ? WHITE : 'color.teal' }))

/** A screen of the workspace with the docks as the owner drew them: left binder (or its tab), content, right dock (or its tab). */
function screen(name, { lib, f, app, doc, toolbar, left, tabLeft, content, dockItems, dockOpen = true, tabRight, over = [], footerKids }) {
  const hl = (x) => handle(f, 'left', x)
  return board(
    name,
    { w: W, h: H, layout: 'column', fill: 'color.surface', clip: true },
    topBar(lib, doc, app),
    menuBar(lib.__w),
    typeof toolbar === 'function' ? toolbar() : toolbar,
    board(
      'body',
      { w: 'fill', h: 'fill', layout: 'row' },
      left ? board('Binder', { w: BINDER, h: 'fill', layout: 'column', fill: 'color.page', gap: 'space.6', pad: ['space.10', 'space.12'] }, ...left, hline('edge', 0)) : null,
      board('content', { w: 'fill', h: 'fill', clip: true }, ...content, tabLeft ? instance(pick(f.handle, { Points: 'right' }), { abs: true, x: 0, y: 190 }) : null, ...(tabRight ?? [])),
      dockOpen ? dock(dockItems) : null,
      left ? instance(pick(f.handle, { Points: 'left' }), { abs: true, x: BINDER - 9, y: 190 }) : null,
      dockOpen ? instance(pick(f.handle, { Points: 'right' }), { abs: true, x: W - DOCK - 9, y: 190 }) : null,
      void hl,
    ),
    typeof footerKids === 'function' ? footerKids() : footerKids,
    ...over,
  )
}

const status = (items) => board('Status bar', { w: 'fill', h: 'size.foot', layout: 'row', align: 'center', gap: 'space.24', pad: [0, 'space.14'], fill: 'color.surface' }, ...items.map((t) => text('item', t, { style: 'hint', color: 'color.muted' })), hline('line', 0))

// --- the corkboard ---------------------------------------------------------------------------------------------

const progress = (parts) => board('progress', { layout: 'row', gap: 'space.2', h: 8, w: 270 }, ...parts.map(([w, fill]) => rect('part', { w, h: 8, radius: 4, fill })))

function corkHeader(f, title, meta, labels, right) {
  return board(
    'Corkboard header',
    { w: 'fill', h: 'auto', layout: 'row', align: 'center', justify: 'space-between', gap: 'space.24', pad: ['space.12', 'space.16'], fill: 'color.page' },
    board('title', { layout: 'column', gap: 'space.3' }, text('title', title, { style: 'h3', color: 'color.ink' }), hint(meta)),
    board('progress', { layout: 'column', gap: 'space.4' }, progress([[43, 'color.teal'], [88, IRIS], [88, { raw: DARK_EDGE }], [44, 'color.mist']]), board('labels', { w: 270, layout: 'row', justify: 'space-between' }, hint(labels[0]), hint(labels[1]))),
    right,
    hline('line', 0),
  )
}

const chapterCard = (f, { n, title, st, note, words, open, selected, shadow }) =>
  board(
    'Chapter card',
    { w: 208, h: 196, layout: 'column', gap: 'space.8', pad: ['space.12', 'space.14'], radius: 'radius.row', fill: 'color.surface', stroke: selected ? { raw: IRIS_HEX, width: 'border.2' } : { color: 'color.line', width: 'border.1' }, shadow: shadow ?? (selected ? 'shadow.card' : undefined) },
    board('head', { w: 'fill', layout: 'row', align: 'center', gap: 'space.6' }, text('number', String(n), { style: 'sample-display', color: 'color.muted' }), text('title', title, { style: 'sample-display', color: 'color.ink' })),
    board('meta', { w: 'fill', layout: 'row', align: 'center', justify: 'space-between' }, chip(f, st[0], st[1]), open ? instance(f.open, { edit: { label: { content: `${open} open` } } }) : null),
    noteText(note, !note),
    spacer(),
    rect('rule', { w: 'fill', h: 'border.1', fill: 'color.line' }),
    text('words', words, { style: 'count', color: 'color.muted' }),
  )

export function corkboardComposes(lib, f, bar) {
  const cards = [
    { n: 1, title: 'Summary', st: ['draft', 'Draft'], note: '', words: '540 words' },
    { n: 2, title: 'Background', st: ['done', 'Polishing'], note: 'Why schools? Keep it to one page.', words: '1 120 words' },
    { n: 3, title: 'Recommendations', st: ['draft', 'Draft'], note: '', words: '—', selected: true, shadow: 'shadow.panel' },
    { n: 4, title: 'Method', st: ['doing', 'Writing'], note: '14 pilot schools, one winter, hourly meter data.', words: '860 words', open: 1 },
    { n: 5, title: 'Findings', st: ['doing', 'Writing'], note: 'Goal: show the 11 % effect is real, not weather. Needs the chart from computes.', words: '2 304 words', open: 2 },
    { n: 6, title: 'Appendix', st: ['none', 'No status'], note: '', words: '—' },
  ]
  const [a, b, c, d, e, g] = cards.map((x) => chapterCard(f, x))
  const newCard = board('New chapter', { w: 208, h: 120, layout: 'column', align: 'center', justify: 'center', gap: 'space.4', radius: 'radius.row', stroke: { color: 'color.line-field', width: 'border.1', style: 'dashed', dash: 5, dashGap: 4 } }, text('label', '+ New chapter', { style: 'control-strong', color: 'color.muted' }), hint('or drop a binder item here'))
  const grid = board('Cards', { abs: true, x: 16, y: 80, layout: 'column', gap: 'space.16' }, board('row 1', { layout: 'row', gap: 'space.16' }, a, b, c), board('row 2', { layout: 'row', gap: 'space.16' }, d, e, g), newCard)
  const drop = [rect('insertion', { abs: true, x: 464, y: 92, w: 3, h: 144, radius: 2, fill: IRIS }), board('Becomes chapter 3', { abs: true, x: 486, y: 52, layout: 'row', pad: ['space.5', 'space.14'], radius: 'radius.control', fill: 'color.ink' }, text('label', 'Becomes chapter 3', { style: 'control-strong', color: WHITE }))]
  const area = [rect('board', { w: 'fill', h: 'fill', fill: BOARD }), board('Header', { abs: true, x: 0, y: 0, w: 'fill' }, corkHeader(f, 'Corkboard', '6 chapters · 1 polishing · 2 writing · 2 draft · 1 no status', ['Polishing', 'No status'], pill('Status filter', 'All statuses ▾'))), grid, ...drop]
  return screen('1 · Corkboard in composes', {
    lib, f, app: 'composes', doc: 'Energy savings in schools — report', toolbar: bar, tabLeft: true, content: area,
    dockItems: { history: [['session', 'SESSION · since 09:12', 'Finish the findings chapter'], ['change', 'move_section 5 → 3 (preview)']], chat: [['you', 'You', 'Move Recommendations up before Method?'], ['ai', 'ai', 'Moving a card moves the section. Chapters 3–5 renumber; references update with them.']] },
    footerKids: () => status(['Corkboard', '6 chapters', '4 open points']),
  })
}


// the named ranges of computes
const rangeCard = (f, { name, ref, purpose, st, note, open, selected, x, y }) =>
  board(
    'Range card',
    { abs: true, x, y, w: 280, h: 118, layout: 'column', gap: 'space.6', pad: ['space.10', 'space.14'], radius: 'radius.row', fill: 'color.surface', stroke: selected ? { raw: IRIS_HEX, width: 'border.2' } : { color: 'color.line', width: 'border.1' }, shadow: selected ? 'shadow.card' : 'shadow.raised' },
    board('head', { w: 'fill', layout: 'row', align: 'center', justify: 'space-between' }, text('name', name, { style: 'formula', color: 'color.ink' }), text('ref', ref, { style: 'mono-small', color: 'color.muted' })),
    board('meta', { w: 'fill', layout: 'row', align: 'center', gap: 'space.6' }, board('purpose', { layout: 'row', pad: ['space.2', 'space.8'], radius: 'radius.pill', fill: 'color.app-soft', stroke: { color: 'color.app', width: 'border.1' } }, text('label', purpose, { style: 'badge', color: 'color.app-text' })), chip(f, st[0], st[1]), open ? instance(f.open, { edit: { label: { content: `${open} open` } } }) : null),
    noteText(note, !note),
  )

const arrow = (name, d, hx, hy, dir) => [
  vector(name, d, 1, { stroke: { raw: DARK_EDGE, width: 1.4, align: 'center', cap: 'round' } }),
  vector('head', dir === 'down' ? 'M0 0 L8 0 L4 7 Z' : 'M0 0 L7 4 L0 8 Z', 1, { x: hx, y: hy, fill: { raw: DARK_EDGE } }),
]

export function corkboardComputes(lib, f, bar) {
  const lane = (title, x) => board('Lane', { abs: true, x, y: 76, w: 320, h: 440, radius: 'radius.row', fill: { raw: '#E7E1F4', opacity: 0.5 } }, text('title', title, { style: 'label', color: 'color.muted', x: 16, y: 14 }))
  const cards = [
    rangeCard(f, { name: 'Tariffs', ref: 'Inputs!B3:D11', purpose: 'input', st: ['done', 'Checked'], note: 'From Stadtwerke sheet 2025. Rises 3 %/yr (assumed).', open: 1, selected: true, x: 36, y: 118 }),
    rangeCard(f, { name: 'Consumption', ref: 'Inputs!B12:C25', purpose: 'input', st: ['doing', 'Building'], note: '', x: 36, y: 250 }),
    rangeCard(f, { name: 'Assumptions', ref: 'Inputs!F3:G9', purpose: 'input', st: ['draft', 'Draft'], note: 'Weather, occupancy, rounding.', x: 36, y: 382 }),
    rangeCard(f, { name: 'Costs', ref: 'Costs!B3:F11', purpose: 'calculation', st: ['doing', 'Building'], note: '', x: 370, y: 150 }),
    rangeCard(f, { name: 'Savings', ref: 'Costs!H3:J11', purpose: 'calculation', st: ['draft', 'Draft'], note: 'Savings against the 2023 baseline.', x: 370, y: 300 }),
    rangeCard(f, { name: 'Summary', ref: 'Summary!A1:C8', purpose: 'output', st: ['draft', 'Draft'], note: '', x: 704, y: 150 }),
    rangeCard(f, { name: 'SavingsBySchool', ref: 'Summary!E2:F16', purpose: 'output', st: ['none', 'No status'], note: '', x: 704, y: 300 }),
  ]
  const arrows = board('Arrows', { abs: true, x: 0, y: 0, w: 'fill', h: 'fill' }, ...arrow('Tariffs → Costs', 'M316 177 C345 177 345 209 366 209', 360, 205, 'right'), ...arrow('Consumption → Costs', 'M316 309 C345 309 345 232 366 232', 360, 228, 'right'), ...arrow('Assumptions → Savings', 'M316 441 C345 441 345 359 366 359', 360, 355, 'right'), ...arrow('Costs → Savings', 'M510 268 V290', 506, 289, 'down'), ...arrow('Savings → Summary', 'M654 359 C680 359 680 209 700 209', 694, 205, 'right'), ...arrow('Savings → SavingsBySchool', 'M654 359 C676 359 676 359 700 359', 694, 355, 'right'))
  const area = [
    rect('board', { w: 'fill', h: 'fill', fill: BOARD }),
    board('Header', { abs: true, x: 0, y: 0, w: 'fill' }, corkHeader(f, 'Corkboard · named ranges', '7 ranges · 1 checked · 2 building · 3 draft · 1 no status', ['Checked', 'No status'], instance(pick(f.segmented, { Chosen: 'first' }), { w: 240, edit: { 'label first': { content: 'By dependency' }, 'label second': { content: 'By sheet' } } }))),
    lane('INPUTS', 16), lane('CALCULATIONS', 350), lane('OUTPUTS', 684), arrows, ...cards,
    hint('Arranged by what depends on what, read from the formulas. Click a card to jump to its range; cards are not dragged.', { abs: true, x: 24, y: 530 }),
  ]
  return screen('2 · Corkboard in computes', {
    lib, f, app: 'computes', doc: 'School energy model', toolbar: bar, tabLeft: true, content: area,
    dockItems: { history: [['session', 'SESSION · since 09:12', 'Check the tariff inputs']], chat: [['you', 'You', '@ai which ranges have no check yet?'], ['ai', 'ai', 'Consumption, Costs, Savings, Summary. Savings depends on both Costs and Assumptions, so check those first.']] },
    footerKids: () => status(['Corkboard', '7 named ranges', '1 open point']),
  })
}

const slideCard = (f, { n, title, mins, st, note, open, selected, chart, lines = 3 }) => {
  const thumb = board('thumb', { w: 'fill', h: 105, radius: 'radius.field', fill: WHITE, stroke: { color: 'color.line', width: 'border.1' }, clip: true }, rect('bar', { x: 0, y: 0, w: 5, h: 105, fill: 'color.app' }), text('title', title, { style: 'pick-display', color: 'color.ink', x: 16, y: 12, w: 150 }), ...(chart ? [0, 1, 2, 3, 4, 5].map((i) => rect('bar', { x: 18 + i * 22, y: 74 - [30, 20, 38, 16, 26, 10][i], w: 14, h: [30, 20, 38, 16, 26, 10][i] + 6, fill: { raw: '#BBB1EA' } })) : Array.from({ length: lines }, (_, i) => rect('line', { x: 18, y: 42 + i * 18, w: 120 - i * 18, h: 5, radius: 2, fill: { raw: '#CFC8EC' } }))))
  return board(
    'Slide card',
    { w: 214, h: 'auto', layout: 'column', gap: 'space.6', pad: 'space.12', radius: 'radius.row', fill: 'color.surface', stroke: selected ? { raw: IRIS_HEX, width: 'border.2' } : { color: 'color.line', width: 'border.1' }, shadow: selected ? 'shadow.card' : undefined },
    thumb,
    board('head', { w: 'fill', layout: 'row', align: 'center', justify: 'space-between' }, board('name', { layout: 'row', gap: 'space.5' }, text('number', String(n), { style: 'sample-display', color: 'color.muted' }), text('title', title.length > 18 ? `${title.slice(0, 17)}…` : title, { style: 'control-strong', color: 'color.ink' })), text('time', `${mins} min`, { style: 'mono-small', color: 'color.muted' })),
    board('meta', { w: 'fill', layout: 'row', align: 'center', justify: 'space-between' }, chip(f, st[0], st[1]), open ? instance(f.open, { edit: { label: { content: `${open} open` } } }) : null),
    noteText(note, !note),
  )
}

export function corkboardCreates(lib, f, bar) {
  const cards = [
    { n: 1, title: 'Energy savings in schools', mins: 1, st: ['done', 'Polishing'], note: 'Opening: who we are, one sentence.', lines: 0 },
    { n: 2, title: 'Why schools?', mins: 2, st: ['doing', 'Building'], note: '' },
    { n: 3, title: 'What we measured', mins: 2, st: ['doing', 'Building'], note: '14 schools, one winter, hourly meters.' },
    { n: 4, title: '11 % less heating', mins: 3, st: ['doing', 'Building'], note: 'The key slide. Chart from computes; say it is not yet weather-corrected.', open: 2, selected: true, chart: true },
    { n: 5, title: 'What it means', mins: 2, st: ['draft', 'Draft'], note: '' },
    { n: 6, title: 'Next steps', mins: 2, st: ['draft', 'Draft'], note: 'Ask for funding for 20 more schools.' },
    { n: 7, title: 'Questions', mins: 2, st: ['none', 'No status'], note: '', lines: 0 },
  ].map((x) => slideCard(f, x))
  const newSlide = board('New slide', { w: 214, h: 200, layout: 'column', align: 'center', justify: 'center', gap: 'space.4', radius: 'radius.row', stroke: { color: 'color.line-field', width: 'border.1', style: 'dashed', dash: 5, dashGap: 4 } }, text('label', '+ New slide', { style: 'control-strong', color: 'color.muted' }), hint('or drop a binder item here'))
  const planned = board('Planned talk', { layout: 'row', align: 'center', gap: 'space.14', pad: ['space.6', 'space.14'], radius: 'radius.field', fill: 'color.surface', stroke: { color: 'color.line', width: 'border.1' } }, board('t', { layout: 'column' }, hint('Planned talk'), text('minutes', '14 min', { style: 'formula', color: 'color.ink' })), hint('of 15'))
  const area = [
    rect('board', { w: 'fill', h: 'fill', fill: BOARD }),
    board('Header', { abs: true, x: 0, y: 0, w: 'fill' }, corkHeader(f, 'Corkboard · slides', '7 slides · 1 polishing · 3 building · 2 draft · 1 no status', ['Polishing', 'No status'], planned)),
    board('Cards', { abs: true, x: 16, y: 80, w: 984, layout: 'row', wrap: true, gap: 'space.16' }, ...cards, newSlide),
  ]
  return screen('3 · Corkboard in creates', {
    lib, f, app: 'creates', doc: 'Energy savings in schools — talk', toolbar: bar, tabLeft: true, content: area,
    dockItems: { history: [['session', 'SESSION · since 09:12', 'Build the key slide']], chat: [['you', 'You', 'How long is the talk if I keep all seven slides?'], ['ai', 'ai', '14 minutes planned, of the 15 you set. Slide 4 is the longest at 3.']] },
    footerKids: () => status(['Corkboard', '7 slides', '2 open points']),
  })
}

// --- quiet mode ------------------------------------------------------------------------------------------------

export function quietMode(f) {
  const col = 520
  return board(
    '1 · Focus mode: ai and chat are quiet',
    { w: W, h: H, fill: 'color.paper', clip: true },
    rect('top edge', { x: 640, y: 0, w: 80, h: 4, radius: 2, fill: { raw: DARK_EDGE } }),
    text('intent', 'Session: Finish the findings chapter', { style: 'hint', color: 'color.muted', x: 520, y: 18, w: 320, align: 'center' }),
    text('number', '4', { style: 'dialog-title', color: 'color.muted', x: 340, y: 112 }),
    text('heading', 'Findings', { style: 'dialog-title', color: 'color.ink', x: 376, y: 112 }),
    text('p1', 'Across the 14 pilot schools, heating demand fell by 11 % in the first winter. The effect was largest in buildings with older boilers, where the new controls replaced manual scheduling. Newer buildings saw a smaller change, as expected.', { style: 'slide-body', color: 'color.text', x: 340, y: 176, w: col }),
    text('p2', 'The comparison is not yet weather-corrected. Degree days in the pilot winter were below the long-term average, so part of the saving may come from a mild season. We therefore treat the 11 % as an upper bound until the correction is done.', { style: 'slide-body', color: 'color.text', x: 340, y: 316, w: col }),
    rect('caret', { x: 746, y: 408, w: 2, h: 20, fill: IRIS }),
    circle('flag', { x: 958, y: 186, w: 9, h: 9, stroke: { raw: '#BBB1EA', width: 1.4 } }),
    instance(f.pill, { abs: true, x: 410, y: 700 }),
    text('words', '2 304 words', { style: 'hint', color: 'color.muted', x: 24, y: 766 }),
    text('leave', 'Leave focus', { style: 'hint', color: 'color.muted', x: 1236, y: 766 }),
  )
}

// --- the binder ------------------------------------------------------------------------------------------------

const inboxRow = (n) => board('Inbox', { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.8', pad: ['space.5', 'space.8'], radius: 'radius.control', fill: { raw: '#E7E1F4', opacity: 0.7 } }, kindIcon('text'), text('label', `Inbox · ${n} not placed yet`, { style: 'control', color: 'color.ink', w: 'fill' }), text('chevron', '›', { style: 'sign', color: 'color.muted' }))

const brow = (f, Kind, title, o = {}) => instance(pick(f.row, { Kind, State: o.selected ? 'selected' : 'default' }), { w: 'fill', edit: { title: { content: title }, ...(o.places ? { places: { hidden: false }, count: { content: String(o.places) } } : {}), ...(o.flag === 'none' ? { open: { hidden: true } } : {}) } })

const jot = () => board('Jot', { w: 'fill', h: 'auto', layout: 'row', pad: ['space.8', 'space.10'], radius: 'radius.control', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' } }, hint('Jot something …', { color: 'color.faint' }))

const place = (label, here) => board('place', { w: 'fill', layout: 'row', align: 'center', gap: 'space.6' }, circle('ring', { w: 9, h: 9, stroke: { raw: IRIS_HEX, width: 1.4 } }), text('label', label, { style: here ? 'link-strong' : 'link', color: here ? IRIS : 'color.text', w: 'fill' }), here ? text('here', 'you are here', { style: 'hint', color: 'color.muted', italic: true }) : text('go', 'Go', { style: 'link-strong', color: IRIS }))

function detail(f, { title, kind = 'text', body, meta, places }) {
  return board(
    'Binder item',
    { w: 'fill', h: 'auto', layout: 'column', gap: 'space.8', pad: ['space.10', 'space.12'], radius: 'radius.row', fill: 'color.surface', stroke: { raw: IRIS_HEX, width: 'border.2' } },
    board('title', { w: 'fill', layout: 'row', align: 'center', gap: 'space.8' }, kindIcon(kind), text('title', title, { style: 'control-strong', color: 'color.ink', w: 'fill' }), glyphSpeech(IRIS)),
    text('body', body, { style: 'hint', color: 'color.text', w: 'fill' }),
    hint(meta, { color: 'color.faint' }),
    rect('rule', { w: 'fill', h: 'border.1', fill: 'color.line' }),
    board('places title', { layout: 'row', gap: 'space.6' }, text('label', 'PLACES', { style: 'facet', color: 'color.muted' }), text('count', String(places.length), { style: 'facet', color: IRIS })),
    ...places.map(([l, here]) => place(l, here)),
    rect('rule', { w: 'fill', h: 'border.1', fill: 'color.line' }),
    board('actions', { layout: 'row', gap: 'space.6' }, pill('place', '+ Place'), pill('open point', 'Open point'), pill('ask', '@ai')),
  )
}

const head = (label) => text('title', label, { style: 'h3', color: 'color.ink' })
const seg = (f, Chosen, w = 'fill', labels) => instance(pick(f.segmented, { Chosen }), { w, ...(labels ? { edit: { 'label first': { content: labels[0] }, 'label second': { content: labels[1] } } } : {}) })
const byKind = ['Folders', 'By place']
const more = (t) => board('more', { w: 'fill', layout: 'row', justify: 'space-between' }, hint(t.split('|')[0]), text('link', 'Everything ›', { style: 'link-strong', color: IRIS }))

/** Here, in composes. */
export const binderHereComposes = (f) => [head('Binder'), seg(f, 'first'), inboxRow(3), board('context', { w: 'fill', layout: 'row', align: 'center', justify: 'space-between' }, text('chapter', '4 Findings', { style: 'control-strong', color: 'color.ink' }), hint('5 items')), detail(f, { title: 'Is 11 % weather-corrected?', body: 'Need degree-day data for the pilot winter. @ai can you find a source?', meta: 'Today 09:12 · You', places: [['4 Findings, ¶1', true], ['2 Background, ¶3'], ['5 Recommendations, ¶2']] }), brow(f, 'text', 'Confirm: 14 schools, not 15', { flag: 'none' }), brow(f, 'sketch', 'Savings logic (scribble)', { flag: 'none' }), brow(f, 'image', 'Boiler room, school 7', { flag: 'none' }), brow(f, 'source', 'Stadtwerke tariff sheet 2025', { flag: 'none' }), more('4 more elsewhere|'), spacer(), jot()]

const search = () => board('Search', { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.6', pad: ['space.6', 'space.10'], radius: 'radius.control', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' } }, circle('lens', { w: 11, h: 11, stroke: { color: 'color.muted', width: 1.4 } }), text('label', 'Search the binder …', { style: 'search', color: 'color.faint' }))

const folder = (name, n, auto, open) => board('folder', { w: 'fill', layout: 'row', align: 'center', gap: 'space.6' }, text('chevron', open ? '▾' : '▸', { style: 'glyph-small', color: 'color.muted' }), rect('icon', { w: 16, h: 12, radius: 3, stroke: { color: 'color.ink', width: 1.2, ...(auto ? { style: 'dashed', dash: 2, dashGap: 2 } : {}) } }), text('name', name, { style: 'control-strong', color: 'color.ink' }), auto ? text('auto', 'auto', { style: 'hint', color: 'color.muted', italic: true }) : null, board('fill', { w: 'fill', h: 1 }), text('count', String(n), { style: 'count', color: 'color.muted' }))
const indent = (n) => board('indent', { w: 'fill', layout: 'row', pad: [0, 0, 0, 'space.14'] }, n)

/** Everything ▸ Folders, in composes. */
export const binderFolders = (f) => [head('Binder'), seg(f, 'second'), search(), seg(f, 'first', 170, byKind), folder('Inbox', 3, true, true), indent(brow(f, 'text', 'Ask Mara: figures?', { flag: 'none' })), indent(brow(f, 'image', 'Boiler room, school 7', { flag: 'none' })), indent(brow(f, 'source', 'Tariff sheet 2025', { flag: 'none' })), folder('Open points', 2, true, true), indent(brow(f, 'text', 'Weather-corrected?', { places: 3 })), indent(brow(f, 'text', 'Add sample caveat')), folder('Sources', 2, true, false), folder('Media', 1, true, false), folder('Interviews', 2, false, true), indent(brow(f, 'text', 'Janitor, school 7', { flag: 'none' })), indent(brow(f, 'text', 'Head teacher', { places: 2, flag: 'none' })), text('new', '+ New folder', { style: 'link', color: 'color.muted' }), spacer(), jot()]

const chapter = (n, name, count, open) => board('chapter', { w: 'fill', layout: 'row', align: 'center', gap: 'space.6' }, text('chevron', open ? '▾' : '▸', { style: 'glyph-small', color: 'color.muted' }), text('number', String(n), { style: 'pick-display', color: 'color.muted' }), text('name', name, { style: 'control-strong', color: 'color.ink' }), board('fill', { w: 'fill', h: 1 }), text('count', String(count), { style: 'count', color: 'color.muted' }))

/** Everything ▸ By place, in composes. */
export const binderByPlace = (f) => [head('Binder'), seg(f, 'second'), search(), seg(f, 'second', 170, byKind), inboxRow(3), chapter(2, 'Background', 1, true), indent(brow(f, 'text', 'Weather-corrected?', { places: 3 })), chapter(3, 'Method', 2, true), indent(brow(f, 'text', 'Add sample caveat')), chapter(4, 'Findings', 5, true), indent(brow(f, 'text', 'Weather-corrected?', { places: 3, selected: true })), indent(brow(f, 'text', 'Confirm: 14 schools, not 15', { flag: 'none' })), indent(brow(f, 'sketch', 'Savings logic (scribble)', { flag: 'none' })), indent(brow(f, 'image', 'Boiler room, school 7', { flag: 'none' })), chapter(5, 'Recommendations', 1, false), spacer(), jot()]

export const binderHereComputes = (f) => [head('Binder'), seg(f, 'first'), inboxRow(2), board('context', { w: 'fill', layout: 'row', align: 'center', justify: 'space-between' }, text('chapter', 'Tariffs · Inputs!B3:D11', { style: 'control-strong', color: 'color.ink' }), hint('3 items')), detail(f, { title: 'Tariff rises 3 %/yr: source?', body: 'The 2025 tariff sheet shows 2.8 %. @ai please check and tell me which to use.', meta: 'Today 09:12 · You', places: [['Inputs!D2:D9', true], ['Costs!E3']] }), brow(f, 'source', 'Stadtwerke tariff sheet 2025', { flag: 'none' }), brow(f, 'text', 'Rounding: 2 decimals', { flag: 'none' }), more('3 more elsewhere|'), spacer(), jot()]

export const binderHereCreates = (f) => [board('tabs', { w: 'fill', layout: 'row', gap: 'space.14' }, text('slides', 'Slides', { style: 'body', color: 'color.muted' }), board('on', { layout: 'row', pad: [0, 0, 'space.4', 0], stroke: undefined }, text('binder', 'Binder', { style: 'tab-on', color: 'color.ink' }), rect('underline', { abs: true, x: 0, y: 22, w: 'fill', h: 'border.2', fill: 'color.app' }))), seg(f, 'first'), inboxRow(2), board('context', { w: 'fill', layout: 'row', align: 'center', justify: 'space-between' }, text('chapter', 'Slide 4 · 11 % less heating', { style: 'control-strong', color: 'color.ink' }), hint('3 items')), detail(f, { title: 'Caveat: not weather-corre…', body: 'Say it out loud before the chart, not after. Repeat on the recommendation slide.', meta: 'Today 09:12 · You', places: [['Slide 4, chart', true], ['Slide 5, text']] }), brow(f, 'image', 'Boiler room, school 7', { flag: 'none' }), brow(f, 'sketch', 'Story arc (scribble)', { flag: 'none' }), more('5 more elsewhere|'), spacer(), jot()]

// the page of composes, with the flags in the margin
function pageOfComposes(contentW, { selection = false } = {}) {
  const pw = 520
  const x = Math.round((contentW - pw) / 2)
  const para = (t, y) => text('paragraph', t, { style: 'slide-body', color: 'color.text', x: 44, y, w: pw - 88 })
  return [
    rect('mist', { w: 'fill', h: 'fill', fill: BOARD }),
    board('Page', { abs: true, x, y: 24, w: pw, h: 560, fill: WHITE, shadow: 'shadow.card', radius: 4 },
      text('number', '4', { style: 'dialog-title', color: 'color.muted', x: 44, y: 34 }), text('heading', 'Findings', { style: 'dialog-title', color: 'color.ink', x: 78, y: 34 }),
      para('Across the 14 pilot schools, heating demand fell by 11 % in the first winter. The effect was largest in buildings with older boilers, where the new controls replaced manual scheduling.', 84),
      para('The comparison is not yet weather-corrected. Degree days in the pilot winter were below the long-term average, so part of the saving may come from a mild season.', 196),
      text('sub number', '4.1', { style: 'pick-display', color: 'color.muted', x: 44, y: 300 }), text('sub heading', 'Heating', { style: 'pick-display', color: 'color.ink', x: 76, y: 300 }),
      para('Heating demand dropped most in the three schools with the oldest boilers (7, 9 and 12), as the sketch in the binder shows.', 332),
      board('Chart', { abs: true, x: 44, y: 414, w: pw - 88, h: 110, radius: 'radius.field', stroke: { color: 'color.line-field', width: 'border.1', style: 'dashed', dash: 5, dashGap: 4 } }, text('title', 'Chart · Savings by school', { style: 'control-strong', color: 'color.ink', x: 160, y: 20 }), text('source', 'from computes ▸ Summary, rev 12', { style: 'hint', color: 'color.muted', x: 160, y: 42 }), text('changed', 'Source changed — ask before updating', { style: 'hint', color: IRIS, x: 160, y: 62 }), ...[0, 1, 2, 3, 4, 5].map((i) => rect('bar', { x: 18 + i * 20, y: 80 - [50, 34, 60, 24, 42, 18][i], w: 14, h: [50, 34, 60, 24, 42, 18][i], fill: { raw: '#BBB1EA' } }))),
      ...(selection ? [rect('selected text', { x: 270, y: 84, w: 74, h: 20, fill: { raw: '#5B4BC4', opacity: 0.22 } })] : []),
    ),
    board('flags', { abs: true, x: x + pw + 14, y: 100, w: 40, h: 60 }, board('flag', { x: 0, y: 0, w: 14, h: 14, radius: 'radius.mark', fill: IRIS }, text('n', '1', { style: 'badge', color: WHITE, x: 4, y: 0 })), text('places', '3 places', { style: 'badge', color: IRIS, x: -6, y: 20 })),
    circle('ring a', { abs: true, x: x + pw + 18, y: 210, w: 9, h: 9, stroke: { raw: '#BBB1EA', width: 1.4 } }),
    circle('ring b', { abs: true, x: x + pw + 18, y: 304, w: 9, h: 9, stroke: { raw: '#BBB1EA', width: 1.4 } }),
  ]
}

const dockComposes = { history: [['session', 'SESSION · since 09:12', 'Finish the findings chapter'], ['change', 'pin item#4 → ¶1'], ['change', 'open item#4'], ['change', 'status 4 → writing']], chat: [['ai', 'Mara', '@ai can you draft a short note for the Findings card?'], ['ai', 'ai', 'Suggestion ready: note for card 4. Review it on the corkboard.']] }

export function binderScreens(lib, f, bar) {
  const base = { lib, f, toolbar: bar, dockItems: dockComposes, app: 'composes', doc: 'Energy savings in schools — report' }
  const footer1 = () => status(['4 Findings', '2 304 words', '4 open points'])
  const one = screen('1 · Binder: Here (composes)', { ...base, left: binderHereComposes(f), content: pageOfComposes(1360 - BINDER - DOCK, { selection: true }), footerKids: footer1 })
  const two = screen('2 · Binder: Everything, by folder', { ...base, left: binderFolders(f), content: pageOfComposes(1360 - BINDER - DOCK), footerKids: footer1 })
  const three = screen('3 · Binder: Everything, by place', { ...base, left: binderByPlace(f), content: pageOfComposes(1360 - BINDER - DOCK, { selection: true }), footerKids: footer1 })
  return { one, two, three }
}

/** computes: Here follows the named range under the cell. */
export function binderComputes(lib, f, w) {
  const heads = ['School', 'Boiler', 'kWh 2024', '€/kWh', 'Cost €', 'Saving %']
  const rows = [['School 1', 'Gas', '182 400', '0.092', '16 781', '12 %'], ['School 2', 'Oil', '143 900', '0.104', '14 966', '17 %'], ['School 3', 'Gas', '201 700', '0.092', '18 556', '9 %'], ['School 4', 'District', '98 500', '0.081', '7 978', '11 %'], ['School 5', 'Oil', '167 300', '0.104', '17 399', '19 %'], ['School 6', 'Gas', '120 800', '0.092', '11 114', '8 %'], ['School 7', 'Oil', '155 600', '0.104', '16 182', '21 %'], ['School 8', 'District', '110 200', '0.081', '8 926', '7 %']]
  const cw = 110
  const kids = [rect('cells', { w: 'fill', h: 'fill', fill: 'color.surface' }), rect('column heads', { x: 0, y: 0, w: 'fill', h: 26, fill: 'color.page' }), rect('row heads', { x: 0, y: 0, w: 52, h: 'fill', fill: 'color.page' })]
  for (let r = 0; r < 14; r++) kids.push(rect('row line', { x: 0, y: 26 + r * 26, w: 'fill', h: 1, fill: 'color.line' }))
  for (let c = 0; c < 6; c++) kids.push(rect('column line', { x: 52 + c * cw, y: 0, w: 1, h: 'fill', fill: 'color.line' }), text('col', 'ABCDEF'[c], { style: 'hint', color: 'color.muted', x: 52 + c * cw, y: 4, w: cw, align: 'center' }))
  for (let r = 0; r < 14; r++) kids.push(text('row', String(r + 1), { style: 'hint', color: 'color.muted', x: 0, y: 26 + r * 26 + 4, w: 52, align: 'center' }))
  heads.forEach((t, c) => kids.push(text('head', t, { style: 'cell', color: 'color.ink', x: 52 + c * cw + 8, y: 30, w: cw - 16, align: c > 1 ? 'right' : 'left' })))
  rows.forEach((r, i) => r.forEach((t, c) => kids.push(text('cell', t, { style: c > 1 ? 'formula' : 'cell', color: 'color.text', x: 52 + c * cw + 8, y: 56 + i * 26, w: cw - 16, align: c > 1 ? 'right' : 'left' }))))
  kids.push(rect('named range', { x: 52 + 3 * cw, y: 52, w: cw, h: 208, stroke: { raw: IRIS_HEX, width: 'border.2', style: 'dashed', dash: 5, dashGap: 4 } }), board('flag', { x: 52 + 3 * cw + cw - 14, y: 52, w: 14, h: 14, fill: IRIS }, text('n', '1', { style: 'badge', color: WHITE, x: 4, y: 0 })), text('places', '2 places', { style: 'badge', color: IRIS, x: 52 + 3 * cw + 24, y: 262 }))
  return screen('4 · Binder: Here in computes', {
    lib, f, app: 'computes', doc: 'School energy model', toolbar: () => formulaBar('Tariffs', '=C4*D4'), left: binderHereComputes(f), content: [board('Sheet', { abs: true, x: 0, y: 0, w: 'fill', h: 'fill' }, ...kids)],
    dockItems: { history: [['session', 'SESSION · since 09:12', 'Check the tariff inputs']], chat: [['you', 'You', '@ai please check the tariff assumption in the binder.'], ['ai', 'ai', 'The 2025 sheet shows +2.8 %, not 3 %. I replied on the item; the cell is unchanged (suggest mode).']] },
    footerKids: () => footer(w, [['sheet', 'on', 'Inputs'], ['sheet', 'default', 'Costs'], ['sheet', 'default', 'Summary'], ['sheet', 'default', 'Chart']]),
  })
}

/** creates: the binder is the second tab of the left panel, next to the slide strip. */
export function binderCreates(lib, f, bar) {
  const slide = board('Slide', { abs: true, x: 60, y: 24, w: 640, h: 360, fill: WHITE, shadow: 'shadow.card', clip: true }, rect('bar', { x: 0, y: 0, w: 8, h: 360, fill: 'color.app' }), text('title', '11 % less heating', { style: 'dialog-title', color: 'color.ink', x: 44, y: 38 }), text('subtitle', 'in the first winter, across 14 schools', { style: 'body', color: 'color.muted', x: 44, y: 78 }), ...[0, 1, 2, 3, 4, 5].map((i) => rect('bar', { x: 54 + i * 40, y: 300 - [100, 70, 130, 56, 100, 40][i], w: 28, h: [100, 70, 130, 56, 100, 40][i], fill: { raw: '#BBB1EA' } })), rect('image', { x: 360, y: 130, w: 230, h: 160, radius: 4, fill: { raw: '#D4E1E6' } }), text('caption', 'Savings by school (computes ▸ Summary)', { style: 'hint', color: 'color.muted', x: 44, y: 326 }), rect('linked', { x: 44, y: 118, w: 270, h: 186, stroke: { raw: IRIS_HEX, width: 'border.2', style: 'dashed', dash: 5, dashGap: 4 } }), board('flag', { x: 300, y: 112, w: 14, h: 14, fill: IRIS }, text('n', '1', { style: 'badge', color: WHITE, x: 4, y: 0 })))
  const notes = board('Speaker notes', { abs: true, x: 60, y: 404, w: 640, h: 120, layout: 'column', gap: 'space.4', pad: 'space.14', radius: 'radius.row', fill: WHITE, stroke: { color: 'color.line', width: 'border.1' } }, text('title', 'Speaker notes (Markdown)', { style: 'control-strong', color: 'color.ink' }), text('body', 'Say plainly: the 11 % is not yet weather-corrected. Then show the three oldest boilers.', { style: 'hint', color: 'color.text', w: 'fill' }))
  return screen('5 · Binder: Here in creates', { lib, f, app: 'creates', doc: 'Energy savings in schools — talk', toolbar: bar, left: binderHereCreates(f), content: [rect('mist', { w: 'fill', h: 'fill', fill: BOARD }), slide, notes], dockItems: { history: [['session', 'SESSION · since 09:12', 'Build the key slide']], chat: [['ai', 'Mara', 'Use the boiler photo on slide 4?'], ['you', 'You', 'Already there. Check the caveat.']] }, footerKids: () => status(['Slide 4 of 7', 'Planned 3 min', 'Here = this slide']) })
}

/** The docks, hidden and shown. */
export function binderDocks(lib, f, bar) {
  const base = { lib, f, toolbar: bar, app: 'composes', doc: 'Energy savings in schools — report', footerKids: () => status(['4 Findings', '2 304 words', '4 open points']) }
  const hiddenChat = screen('6 · Binder open, History & Chat hidden', {
    ...base, left: binderHereComposes(f), content: pageOfComposes(1360 - BINDER, { selection: true }), dockOpen: false,
    tabRight: [instance(pick(f.handle, { Points: 'left' }), { abs: true, x: 1360 - BINDER - 18, y: 190 }), board('unread', { abs: true, x: 1360 - BINDER - 30, y: 176, w: 18, h: 18, layout: 'row', align: 'center', justify: 'center', radius: 'radius.pill', fill: IRIS, stroke: { raw: '#FFFFFF', width: 'border.2' } }, text('n', '1', { style: 'badge', color: WHITE })), tip('Show History & Chat', 1360 - BINDER - 190, 232)],
  })
  const hiddenBinder = screen('7 · History & Chat open, binder hidden', {
    ...base, tabLeft: true, content: [...pageOfComposes(1360 - DOCK, { selection: true }), tip('Show Binder', 26, 232)], dockItems: dockComposes,
  })
  return { hiddenChat, hiddenBinder }
}

// --- the pages -------------------------------------------------------------------------------------------------

export function workflowPages(lib, f, w) {
  const bar = () => insertBar(w)
  lib.__w = w
  const cork = [
    withNotes(w, corkboardComposes(lib, f, bar), [
      'Overview and progress: the header counts chapters by status. It is a count, not a score. Filter by status to see what is still draft.',
      'A card is a view of the text: number and title come from the heading (read-only). Status and note are yours: one free note with grey priming text when empty. Open points show as a badge.',
      'Moving a card moves the chapter: the drop is a logged move_section command, numbers and references update. A card can exist before there is text: add one, or drop a binder item on the board.',
      'Status words are editable per document; the defaults are Draft, Writing, Polishing in composes. A status is an icon and a word, never a colour alone.',
    ]),
    withNotes(w, corkboardComputes(lib, f, bar), [
      'Same board, different unit: the cards are named ranges (a range with a header row is a table). Dragging would mean nothing here, so the board is laid out by dependency, or by sheet.',
      'Same card as in composes: name and reference come from the model (read-only); purpose, status and one free note are yours. The defaults are Draft, Building, Checked.',
      'The arrows read the formulas: they show what feeds what, so you see which ranges are upstream of a result and still unchecked. Experimental.',
    ]),
    withNotes(w, corkboardCreates(lib, f, bar), [
      'Planned time, summed: each slide carries a planned time (as in presenter mode) and the corkboard adds it up. It informs, it does not stop you.',
      'Same card, same attributes: number and title come from the slide; status, free note and time are yours. Open points from the binder show as a badge.',
      'This is the slide sorter: the slide strip stays in the editor. Dragging a card moves the slide; page numbers follow because they come from the template.',
    ]),
  ]
  const quiet = [
    withNotes(w, quietMode(f), [
      'Quiet means queued, not lost: suggestions and @mentions are held. The pill says what is waiting; "Show" opens them, and leaving focus releases them. Tools ▸ Quiet ai and chat does the same without hiding the panels.',
      'Everything else steps back: the top bar, menus, panels, toolbar and tab strip are hidden. Flags shrink to rings. No timers, no word goals, no streaks.',
      'The session intent stays in view as one faint line. Mouse to the top edge shows the bars again. (D1102)',
    ]),
  ]
  const b = binderScreens(lib, f, bar)
  const d = binderDocks(lib, f, bar)
  const binder = [
    withNotes(w, b.one, [
      'Opens on Here: only what is linked to the chapter you are in, one line per item. Everything else is one click away, so the panel stays calm.',
      'The selected item opens into a card with its full text and all its places. Each place is a flag in the text; the ring and number on a row say how many.',
      'The inbox is just a count: unplaced items wait behind one slim row. "+ Place" pins the item to the text you have selected. (D1107, D1108)',
      'The hide arrow sits on the binder\'s edge like History & Chat\'s: both docks can be hidden to their own side. The binder is a private drawer in the document (D1110).',
    ]),
    withNotes(w, b.two, ['Folders without filing: Inbox, Open points, Sources and Media are generated (dashed folder, "auto"), so they are never out of date. Your own folders are manual: an item lives in one of them.', 'The same one-line row: icon, first words, a flag if open, and a ring with the number of places.', 'Search covers text, source names and place labels. "By place" regroups the same items by chapter.']),
    withNotes(w, b.three, ['The document is the folder tree: by place groups items by chapter, in document order. Pinning an item is what puts it in a chapter, so the list cannot drift from the text.', 'One item, several places: the weather question is linked to chapters 2, 4 and 5, so it shows under each. Selecting it highlights its place in the text.', 'Collapsed means quiet: chapters without a pending item stay folded.']),
    withNotes(w, binderComputes(lib, f, w), ['Here follows the cell: in computes it means the named range under the cursor (or the sheet, if there is none).', 'Several places, one item: the tariff question lives on Inputs!D2:D9 and on Costs!E3. "Go" jumps there and Shift+F8 cycles through them.', 'The place is outlined: the selected item\'s range gets a dashed iris outline and a corner flag in the grid, like a comment.']),
    withNotes(w, binderCreates(lib, f, bar), ['Same panel, one tab over: the left panel is the slide strip in creates, so the binder is its second tab. Here means the slide you are on.', 'Places can be slides or objects: the caveat is linked to the chart on slide 4 and to the text on slide 5.', 'Visible in the editor only: the dashed outline and flag never appear in the show or in exports.']),
    withNotes(w, d.hiddenChat, ['The page takes the room: with History & Chat tucked away it re-centres in the space that is left; nothing floats over it.', 'A quiet tab remains: the small number only counts things addressed to you (@mentions, an ai reply to you). No popup, no sound.', 'Hidden is not off: a mention waits behind the tab, and jotting still lands in the inbox.']),
    withNotes(w, d.hiddenBinder, ['The binder leaves a tab, not a hole: the same handle on the left edge, chevron pointing in. The hover label says what it is.', 'The place flags stay: they belong to the document view, not to the dock.', 'Both docks open (screen 1) is the full view; Focus mode hides both at once.']),
  ]
  return { cork, quiet, binder }
}
