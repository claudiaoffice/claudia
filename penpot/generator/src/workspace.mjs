// The document workspace of claudia as Penpot components (menus, tabs, tools, radio buttons, design notes) and the
// screens of E6.31 "Slides in computes", built from them, from the front page's library and from the dialogs'.
// Sizes and colours are tokens (src/tokens.mjs says where each comes from in web/app); what a stylesheet writes as a
// literal (the panel's light text, the scrim behind a dialog) is written the same way here.
//
// Built AFTER the dialogs: the ids of a file's shapes come from the order they are made in, and must not move.
import { board, circle, component, instance, pick, rect, text, variantSet } from './model.mjs'
import { vector } from './library.mjs'
import { dialogShell } from './dialogs.mjs'

export const WHITE = { raw: '#FFFFFF' }
export const PANEL_TEXT = (opacity) => ({ raw: '#E6E0F5', opacity }) // SidePanel.vue: color #e6e0f5, rgb(230 224 245 / n%)
const SCRIM = { raw: '#1F1A33', opacity: 0.38 } // Modal.vue ::backdrop rgb(31 26 51 / 38%)
const NOTE = { raw: '#FFF6D6' } // a design note: not part of the app
const NOTE_EDGE = '#E0B84A'

export const W = 1360 // the window the browser scripts use (web/e2e/*.cjs)
export const H = 800

// --- the library -----------------------------------------------------------------------------------------------

/** The workspace's own components (the front page's and the dialogs' are used as they are). */
export function buildWorkspaceLibrary() {
  const w = {}
  // Workspace / Menu entry: State (MenuBar.vue .drop button, ContextMenu.vue .menu button)
  w.menuEntry = variantSet(
    'Menu entry',
    'Workspace',
    { State: ['default', 'active', 'disabled'] },
    ({ State }) =>
      board(
        'Menu entry',
        { w: 'size.menu-min', h: 'auto', layout: 'row', align: 'center', justify: 'space-between', gap: 'space.24', pad: ['space.6', 'space.10'], radius: 'radius.menu-item', fill: State === 'active' ? 'color.mist' : undefined },
        text('label', 'Entry', { style: 'body', color: State === 'disabled' ? 'color.muted' : 'color.text' }),
        text('key', 'Ctrl+K', { style: 'menu-key', color: 'color.muted' }),
      ),
    { w: 900 },
  )
  // Workspace / Menu separator (.sep: 1px, margin 5px 4px)
  w.menuSep = component(board('Menu separator', { w: 'size.menu-min', h: 'auto', layout: 'column', pad: ['space.5', 'space.4'] }, rect('line', { w: 'fill', h: 'border.1', fill: 'color.line' })), { name: 'Menu separator', path: 'Workspace' })

  // Workspace / Menu title (MenuBar.vue .title)
  w.menuTitle = component(board('Menu title', { h: 'size.menu-title', layout: 'row', align: 'center', pad: ['space.4', 'space.10'], radius: 'radius.menu-item' }, text('label', 'File', { style: 'body', color: 'color.text' })), { name: 'Menu title', path: 'Workspace' })

  // Workspace / Tab: Kind × State (FooterBar.vue .tabs button; a slide is marked by a small frame, new in E6.31)
  w.tab = variantSet(
    'Tab',
    'Workspace',
    { Kind: ['sheet', 'slide'], State: ['default', 'on'] },
    ({ Kind, State }) => {
      const on = State === 'on'
      const ink = on ? 'color.app-dark' : 'color.text'
      return board(
        'Tab',
        { h: 'auto', layout: 'row', align: 'center', gap: 'space.6', pad: ['space.4', 'space.14'], radius: on ? ['radius.tab', 'radius.tab', 0, 0] : 'radius.tab', fill: on ? 'color.app-soft' : undefined },
        Kind === 'slide' ? rect('frame', { w: 13, h: 9, radius: 2, stroke: { color: ink, width: 'border.1' }, opacity: 0.75 }) : null,
        text('label', Kind === 'slide' ? 'Slide' : 'Sheet1', { style: on ? 'tab-on' : 'body', color: ink }),
        // FooterBar.vue .tabs button.on: box-shadow inset 0 -2px 0 var(--app); the tab is 4 + 21 + 4 px high
        on ? rect('underline', { abs: true, x: 0, y: 27, w: 'fill', h: 'border.2', fill: 'color.app' }) : null,
      )
    },
    { w: 760 },
  )

  // Workspace / Tool: Glyph (InsertBar.vue .tool: an icon and a word)
  const glyph = {
    text: () => text('glyph', 'T', { style: 'app-name', color: 'color.ink' }),
    image: () => board('glyph', { w: 15, h: 13 }, rect('frame', { w: 15, h: 13, radius: 2, stroke: { color: 'color.ink', width: 'border.1' } }), vector('hills', 'M2 11 L6 6 L9 9 L11 7 L13 11', 1, { stroke: { color: 'color.ink', width: 1.2, align: 'center', cap: 'round' } })),
    circle: () => circle('glyph', { w: 15, h: 15, stroke: { color: 'color.ink', width: 1.4 } }),
    rectangle: () => rect('glyph', { w: 15, h: 15, stroke: { color: 'color.ink', width: 1.4 } }),
    triangle: () => vector('glyph', 'M8 1 L15 14 L1 14 Z', 1, { stroke: { color: 'color.ink', width: 1.4, align: 'center' } }),
  }
  const label = { text: 'Text', image: 'Image', circle: 'Circle', rectangle: 'Rectangle', triangle: 'Triangle' }
  w.tool = variantSet(
    'Tool',
    'Workspace',
    { Glyph: Object.keys(glyph) },
    ({ Glyph }) => board('Tool', { h: 'size.tool', layout: 'row', align: 'center', gap: 'space.6', pad: [0, 'space.10'], radius: 'radius.tab' }, glyph[Glyph](), text('label', label[Glyph], { style: 'body', color: 'color.ink' })),
    { w: 760 },
  )

  // Workspace / Radio: Checked (SheetChartInsertDialog.vue .radio; as big as the dialogs' check box)
  w.radio = variantSet(
    'Radio',
    'Workspace',
    { Checked: ['yes', 'no'] },
    ({ Checked }) =>
      board(
        'Radio',
        { layout: 'row', align: 'center', gap: 'space.7' },
        board('dot', { w: 'size.check', h: 'size.check' }, circle('ring', { w: 'size.check', h: 'size.check', fill: 'color.surface', stroke: { color: Checked === 'yes' ? 'color.app' : 'color.line-field', width: 'border.1' } }), Checked === 'yes' ? circle('mark', { x: 4, y: 4, w: 8, h: 8, fill: 'color.app' }) : null),
        text('label', 'Choice', { style: 'control', color: 'color.text' }),
      ),
    { w: 400 },
  )
  // Workspace / Chart kind: State (SheetChartInsertDialog.vue .kind, .kind.on, .kind.soon)
  w.chartKind = variantSet(
    'Chart kind',
    'Workspace',
    { State: ['on', 'soon'] },
    ({ State }) =>
      board(
        'Chart kind',
        { layout: 'row', pad: ['space.4', 'space.12'], radius: 'radius.pill', stroke: { color: State === 'on' ? 'color.app' : 'color.line-field', width: State === 'on' ? 'border.2' : 'border.1', ...(State === 'soon' ? { style: 'dashed', dash: 3, dashGap: 3 } : {}) } },
        text('label', State === 'on' ? 'Bar' : 'Line · soon', { style: 'chip', color: State === 'on' ? 'color.text' : 'color.muted' }),
      ),
    { w: 400 },
  )

  // Notes / Note: a design note beside a screen (not part of the app)
  w.note = component(
    board('Note', { w: 300, h: 'auto', layout: 'row', gap: 'space.8', pad: ['space.10', 'space.12'], radius: 'radius.field', fill: NOTE, stroke: { raw: NOTE_EDGE, width: 'border.1' } }, board('number', { w: 20, h: 20, layout: 'row', align: 'center', justify: 'center', radius: 'radius.pill', fill: { raw: NOTE_EDGE } }, text('n', '1', { style: 'hint', color: 'color.ink' })), text('text', 'What the screen shows, and why.', { style: 'hint', color: 'color.ink', w: 'fill' })),
    { name: 'Note', path: 'Notes' },
  )
  return w
}

// --- pieces of a screen ----------------------------------------------------------------------------------------

export const hline = (name, y, w = 'fill', color = 'color.line') => rect(name, { abs: true, x: 0, y, w, h: 'border.1', fill: color })

export function topBar(lib, doc, app = 'computes') {
  const person = (letter, fill) => board('person', { w: 'size.avatar', h: 'size.avatar', layout: 'row', align: 'center', justify: 'center', radius: 'radius.pill', fill, stroke: { color: 'color.surface', width: 'border.2' } }, text('letter', letter, { style: 'hint', color: 'color.paper' }))
  return board(
    'Top bar',
    { w: 'fill', h: 'size.top-bar', layout: 'row', align: 'center', gap: 'space.24', pad: [0, 'space.16'], fill: 'color.surface' },
    board('brand', { layout: 'row', align: 'center', gap: 'space.14' }, instance(lib.wordmark, {}), board('app', { layout: 'row', align: 'center', gap: 'space.7', pad: [0, 0, 0, 'space.14'] }, rect('divider', { abs: true, x: 0, y: 2, w: 'border.1', h: 24, fill: 'color.line' }), instance(pick(lib.appIcon, { App: app, Size: '22' }), { nested: true }), text('name', app, { style: 'app-name', color: 'color.text' }))),
    text('document', doc, { style: 'doc-title', color: 'color.text', w: 'fill' }),
    board('right', { layout: 'row', align: 'center', gap: 'space.14' }, board('people', { layout: 'row', align: 'center' }, person('A', 'color.rose'), person('ai', 'color.iris')), board('History & chat', { layout: 'row', pad: ['space.7', 'space.17'], radius: 'radius.pill', fill: 'color.mist' }, text('label', 'History & chat', { style: 'body', color: 'color.ink' }))),
    hline('line', 51),
  )
}

export function menuBar(w) {
  const titles = ['File', 'Edit', 'Insert', 'Format', 'View', 'Tools', 'Config', 'Help'] // as the code has them today (owner, 2026-11-22)
  return board('Menu bar', { w: 'fill', h: 'size.menu-bar', layout: 'row', align: 'center', gap: 'space.2', pad: ['space.2', 'space.10'], fill: 'color.surface' }, ...titles.map((t) => instance(w.menuTitle, { edit: { label: { content: t } } })), hline('line', 31))
}

export function insertBar(w) {
  return board('Insert bar', { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.2', pad: ['space.6', 'space.10'], fill: 'color.surface' }, ...['text', 'image', 'circle', 'rectangle', 'triangle'].map((Glyph) => instance(pick(w.tool, { Glyph }), {})), hline('line', 41))
}

export function formulaBar(ref, formula) {
  return board(
    'Formula bar',
    { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.8', pad: ['space.6', 'space.10'], fill: 'color.surface' },
    board('name box', { w: 'size.name-box', h: 'size.tool', layout: 'row', align: 'center', justify: 'center', radius: 'radius.field', fill: 'color.page', stroke: { color: 'color.line-field', width: 'border.1' } }, text('ref', ref, { style: 'formula', color: 'color.text' })),
    board('eq', { h: 'size.tool', layout: 'row', align: 'center', pad: [0, 'space.2', 0, 'space.8'] }, text('=', '=', { style: 'equals', color: 'color.app-text' })),
    text('formula', formula, { style: 'formula', color: 'color.text', w: 'fill' }),
    hline('line', 41),
  )
}

export function sidePanel(historyKids = [], chatKids = []) {
  const label = (name, t, o = {}) => text(name, t, { style: 'panel-label', color: PANEL_TEXT(0.62), ...o })
  return board(
    'History & Chat',
    { w: 'size.dock', h: 'fill', layout: 'column', fill: 'color.ink' },
    board('ai mode', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.5', pad: ['space.10', 'space.14', 'space.4', 'space.14'] }, label('label', 'When I ask the AI, in this document:'), board('segmented', { w: 'fill', h: 'auto', layout: 'row', radius: 'radius.control', clip: true, stroke: { raw: '#E7E1F4', width: 'border.1' } }, board('act', { w: 'fill', h: 'auto', layout: 'row', justify: 'center', pad: ['space.6', 'space.4'] }, text('label', 'Act at once', { style: 'body', color: PANEL_TEXT(0.85) })), board('suggest', { w: 'fill', h: 'auto', layout: 'row', justify: 'center', pad: ['space.6', 'space.4'], fill: 'color.iris' }, text('label', 'Suggest first', { style: 'body', color: WHITE })))),
    board('tabs', { w: 'fill', h: 'auto', layout: 'row', gap: 'space.2', pad: ['space.8', 'space.10', 0, 'space.10'] }, board('History & Chat', { w: 'fill', h: 'auto', layout: 'row', justify: 'center', pad: ['space.7', 'space.4'], radius: ['radius.tab', 'radius.tab', 0, 0], fill: { raw: '#FFFFFF', opacity: 0.07 } }, text('label', 'History & Chat', { style: 'panel-tab', color: WHITE })), board('Help', { w: 'fill', h: 'auto', layout: 'row', justify: 'center', pad: ['space.7', 'space.4'] }, text('label', 'Help', { style: 'panel-tab', color: PANEL_TEXT(0.6) }))),
    board('history', { w: 'fill', h: 'fill', layout: 'column', gap: historyKids.length ? 'space.6' : undefined, pad: ['space.12', 'space.14'] }, label('title', 'HISTORY'), ...historyKids),
    board('chat', { w: 'fill', h: 'fill', layout: 'column', gap: chatKids.length ? 'space.6' : undefined, pad: ['space.12', 'space.14'] }, label('title', 'CHAT'), ...chatKids),
  )
}

export function footer(w, tabs) {
  return board(
    'Tab strip',
    { w: 'fill', h: 'size.foot', layout: 'row', align: 'center', gap: 'space.4', pad: [0, 'space.10'], fill: 'color.surface' },
    ...tabs.map(([Kind, State, name]) => instance(pick(w.tab, { Kind, State }), { edit: { label: { content: name } } })),
    board('add', { layout: 'row', pad: ['space.3', 'space.11'], radius: 'radius.tab' }, text('+', '+', { style: 'tab-add', color: 'color.muted' })),
    hline('line', 0),
  )
}

/** A selected object's frame: the outline and its eight handles (ObjectFrame.vue), around a w×h box at x, y. */
export function selection(x, y, w, h) {
  const at = [
    [0, 0], [w / 2, 0], [w, 0], [0, h / 2], [w, h / 2], [0, h], [w / 2, h], [w, h],
  ]
  return board(
    'selection',
    { abs: true, x, y, w, h },
    rect('outline', { w, h, stroke: { color: 'color.iris', width: 'border.1' } }),
    ...at.map(([hx, hy]) => rect('handle', { x: hx - 5.5, y: hy - 5.5, w: 'size.handle', h: 'size.handle', radius: 'radius.handle', fill: WHITE, stroke: { color: 'color.iris', width: 'border.2' } })),
  )
}

/** A bar chart as Plotly draws it in ChartView.vue: the first of BAR_COLORS (charts.py) is the teal of the palette. */
export function barChart(x, y, w, h, title) {
  const top = title ? 36 : 14
  const base = h - 30
  const left = 44
  const right = w - 12
  const data = [
    ['East', 300],
    ['West', 120],
    ['North', 70],
  ]
  const kids = [rect('paper', { w, h, fill: WHITE })]
  if (title) kids.push(text('title', title, { style: 'chart-title', color: 'color.text', x: w / 2 - 54, y: 10 }))
  for (const v of [0, 100, 200, 300]) {
    const gy = base - ((base - top) * v) / 300
    kids.push(rect(`grid ${v}`, { x: left, y: gy, w: right - left, h: 1, fill: v ? 'color.line' : 'color.ink' }))
    kids.push(text(`tick ${v}`, String(v), { style: 'chart-label', color: 'color.muted', x: left - 30, y: gy - 7, w: 24, align: 'right' }))
  }
  const span = (right - left) / data.length
  data.forEach(([name, v], i) => {
    const bh = ((base - top) * v) / 300
    kids.push(rect(`bar ${name}`, { x: left + i * span + span * 0.12, y: base - bh, w: span * 0.76, h: bh, fill: 'color.teal' }))
    kids.push(text(`label ${name}`, name, { style: 'chart-label', color: 'color.muted', x: left + i * span + span / 2 - 16, y: base + 6, w: 32, align: 'center' }))
  })
  return board('Chart', { abs: true, x, y, w, h }, ...kids)
}

/** A screen of the workspace: bars on top, the content on the left, History & Chat on the right, tabs below. */
function screen(name, { lib, w, toolbar, content, tabs, over = [] }) {
  return board(
    name,
    { w: W, h: H, layout: 'column', fill: 'color.surface', clip: true },
    topBar(lib, 'sales-2027'),
    menuBar(w),
    toolbar,
    board('body', { w: 'fill', h: 'fill', layout: 'row' }, board('content', { w: 'fill', h: 'fill', clip: true }, ...content), sidePanel()),
    footer(w, tabs),
    ...over, // what lies over the whole window: a dialog and its backdrop (Modal.vue)
  )
}

export function sheetGrid(rows) {
  const kids = [rect('cells', { w: 'fill', h: 'fill', fill: 'color.surface' })]
  for (let r = 0; r < 24; r++) kids.push(rect(`row line ${r}`, { x: 0, y: 26 + r * 26, w: 'fill', h: 1, fill: 'color.line' }))
  for (let c = 0; c < 10; c++) kids.push(rect(`column line ${c}`, { x: 52 + c * 96, y: 0, w: 1, h: 'fill', fill: 'color.line' }))
  kids.push(rect('column heads', { x: 0, y: 0, w: 'fill', h: 'size.grid-row', fill: 'color.page' }))
  kids.push(rect('row heads', { x: 0, y: 0, w: 'size.grid-header', h: 'fill', fill: 'color.page' }))
  for (let c = 0; c < 10; c++) kids.push(text(`col ${c}`, 'ABCDEFGHIJ'[c], { style: 'hint', color: 'color.muted', x: 52 + c * 96, y: 4, w: 96, align: 'center' }))
  for (let r = 0; r < 23; r++) kids.push(text(`row ${r + 1}`, String(r + 1), { style: 'hint', color: 'color.muted', x: 0, y: 26 + r * 26 + 4, w: 52, align: 'center' }))
  rows.forEach(([a, b], r) => {
    kids.push(text(`A${r + 1}`, a, { style: 'cell', color: 'color.text', x: 52 + 8, y: 26 + r * 26 + 4 }))
    kids.push(text(`B${r + 1}`, b, { style: 'cell', color: 'color.text', x: 52 + 96, y: 26 + r * 26 + 4, w: 88, align: 'right' }))
  })
  return board('Sheet', { abs: true, x: 0, y: 0, w: 'fill', h: 'fill' }, ...kids)
}

const DATA = [
  ['Region', 'Amount'],
  ['East', '300'],
  ['West', '120'],
  ['North', '70'],
]

/** A screen and the notes that go with it, side by side on the page. */
export const withNotes = (w, scr, notes) =>
  board(`${scr.name} (with notes)`, { layout: 'row', gap: 'space.24' }, scr, board('Notes', { w: 320, h: 'auto', layout: 'column', gap: 'space.12', pad: ['space.24', 0] }, ...notes.map((t, i) => instance(w.note, { w: 'fill', edit: { n: { content: String(i + 1) }, text: { content: t } } }))))

// --- the screens of E6.31 --------------------------------------------------------------------------------------

export function slidesInComputes(w, d, lib) {
  // 1. a slide among the sheets
  const SW = 880
  const SH = (SW * 9) / 16
  const slideArea = board(
    'Slide area',
    { abs: true, x: 0, y: 0, w: 'fill', h: 'fill', fill: { raw: '#E9E5E0' } }, // SlideCanvas.vue .area: color-mix(--ink 6%, --paper)
    board(
      'Slide',
      { abs: true, x: 50, y: 40, w: SW, h: SH, fill: WHITE, shadow: 'shadow.card', clip: true },
      ...Array.from({ length: 31 }, (_, i) => rect(`grid v ${i + 1}`, { x: ((i + 1) * SW) / 32, y: 0, w: 1, h: SH, fill: 'color.grid' })),
      ...Array.from({ length: 17 }, (_, j) => rect(`grid h ${j + 1}`, { x: 0, y: ((j + 1) * SH) / 18, w: SW, h: 1, fill: 'color.grid' })),
      text('title', 'Q1 review', { style: 'slide-title', color: 'color.text', x: 40, y: 26 }),
      barChart(40, 80, 520, 330, 'Sales by region'),
      selection(40, 80, 520, 330),
      text('text box', 'East leads with 300, more than West and North together.', { style: 'slide-body', color: 'color.text', x: 600, y: 110, w: 230 }),
    ),
  )
  const one = withNotes(
    w,
    screen('1 · A slide among the sheets', { lib, w, toolbar: insertBar(w), content: [slideArea], tabs: [['sheet', 'default', 'Sheet1'], ['slide', 'on', 'Sales chart'], ['sheet', 'default', 'Costs']] }),
    [
      'A slide sits among the sheets, in one tab order; a small frame marks it. Its tab is named after its chart.',
      "A slide has no cells: creates' object toolbar takes the place of the formula bar. Text boxes, shapes and images can be added beside the chart.",
      'The same 16:9 frame and grid as a slide in creates; no speaker notes and no Present in computes.',
      'A slide comes only from a chart: Insert chart "Show as: A slide", or "Move to Slide" on a chart on a sheet. "+" adds sheets only, as today.',
      'A slide goes with its last object, in the same undo step.',
    ],
  )

  // 2. Edit ▸ Chart… with "Show as: A slide"
  const legend = (t) => text('legend', t, { style: 'legend', color: 'color.text' })
  const radio = (Checked, t) => instance(pick(w.radio, { Checked }), { edit: { label: { content: t } } })
  const check = (t) => instance(pick(d.check, { Checked: 'yes' }), { edit: { label: { content: t } } })
  const field = (label, value) => instance(pick(lib.field, { Value: 'filled', Trailing: 'none' }), { w: 'fill', edit: { label: { content: label }, value: { content: value } } })
  const button = (Kind, t) => instance(pick(lib.button, { Kind, Size: 'regular', State: 'default' }), { edit: { label: { content: t } } })
  const dialog = dialogShell(
    'Insert chart',
    'size.dialog-chart',
    instance(d.dialogHeader, { edit: { title: { content: 'Insert chart' } } }),
    board('Chart', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.6' }, legend('Chart'), board('kinds', { layout: 'row', gap: 'space.8' }, instance(pick(w.chartKind, { State: 'on' }), {}), instance(pick(w.chartKind, { State: 'soon' }), {}), instance(pick(w.chartKind, { State: 'soon' }), { edit: { label: { content: 'Scatter · soon' } } }))),
    board('Data from', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.6' }, legend('Data from'), board('source', { w: 'fill', h: 'auto', layout: 'row', pad: ['space.5', 'space.8'], radius: 'radius.field', stroke: { color: 'color.app', width: 'border.2' } }, text('selection', 'The selection, as it is now: A1:B4', { style: 'hint', color: 'color.muted' }))),
    board('Show as', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.6' }, legend('Show as'), radio('yes', 'A slide'), radio('no', 'A floating object on the sheet')),
    field('Name (the slide it opens as)', 'Sales chart'),
    board('series', { w: 'fill', h: 'auto', layout: 'row', gap: 'space.14' }, board('Series are in', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.6' }, legend('Series are in'), radio('yes', 'Columns'), radio('no', 'Rows')), board('header', { w: 'fill', h: 'auto', layout: 'column', pad: ['space.24', 0, 0, 0] }, check('First row is a header'))),
    field('Title (optional)', 'Sales by region'),
    board('axes', { w: 'fill', h: 'auto', layout: 'row', gap: 'space.14' }, field('X axis (optional)', 'Region'), field('Y axis (optional)', 'Amount')),
    board('checks', { w: 'fill', h: 'auto', layout: 'row', gap: 'space.14' }, board('legend', { w: 'fill', h: 'auto', layout: 'row' }, check('Legend')), board('gridlines', { w: 'fill', h: 'auto', layout: 'row' }, check('Gridlines'))),
    board('buttons', { layout: 'row', gap: 'space.10' }, button('primary', 'Insert'), button('default', 'Cancel')),
  )
  Object.assign(dialog, { abs: true, x: (W - 520) / 2, y: 38 }) // as the browser places it in a 1360×800 window
  const two = withNotes(
    w,
    screen('2 · Insert chart: Show as a slide', { lib, w, toolbar: formulaBar('A1:B4', 'Region'), content: [sheetGrid(DATA)], tabs: [['sheet', 'on', 'Sheet1']], over: [rect('backdrop', { abs: true, x: 0, y: 0, w: W, h: H, fill: SCRIM }), dialog] }),
    [
      '"Show as: A tab" becomes "A slide", and stays the default. Insert makes a slide named as the field says, right after the current tab, with the chart filling its frame.',
      'The rest of the dialog is as today (E6.6): the kind, the data, the series, the titles.',
      'Menus and keys stay as they are today (Edit ▸ Chart…, Ctrl+Alt+C); the menu rework against claudia-menus.xlsx comes later.',
    ],
  )

  // 3. "Move to Slide" in the object menu of a chart on a sheet
  const entry = (State, label, key = '') => instance(pick(w.menuEntry, { State }), { w: 280, edit: { label: { content: label }, key: { content: key } } })
  const menu = board(
    'Object menu',
    { abs: true, x: 690, y: 70, w: 'auto', h: 'auto', layout: 'column', pad: 'space.6', radius: 'radius.row', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' }, shadow: 'shadow.card' },
    entry('default', 'Name & describe…', 'Ctrl+Alt+D'),
    entry('default', 'Style…', 'Ctrl+Alt+A'),
    instance(w.menuSep, { w: 280 }),
    entry('active', 'Move to Slide'),
    instance(w.menuSep, { w: 280 }),
    entry('default', 'Delete', 'Del'),
  )
  const three = withNotes(
    w,
    screen('3 · Move a chart to a slide', { lib, w, toolbar: formulaBar('A1:B4', 'Region'), content: [sheetGrid(DATA), barChart(260, 60, 410, 270, 'Sales by region'), selection(260, 60, 410, 270), menu], tabs: [['sheet', 'on', 'Sheet1'], ['sheet', 'default', 'Costs']] }),
    [
      'New in a chart\'s object menu: "Move to Slide". It makes a slide named after the chart, right after this sheet, and moves the chart onto it: one step, undone as one. On the slide the chart first fills the frame.',
      'It stays the same chart (its data, kind and titles); nothing is left behind on the sheet.',
      'The other entries are a chart\'s today: Name & describe…, Style…, Delete. "Move to Slide" has no key yet: the menus are reworked later.',
    ],
  )
  return [one, two, three]
}
