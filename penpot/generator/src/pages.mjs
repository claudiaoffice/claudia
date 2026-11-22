// The pages of the file: Foundations (the tokens, shown), Icons and Components (the library), Front page (the
// design itself, made of instances of the library and of the tokens).
import { board, circle, instance, measureBox, pick, rect, text } from './model.mjs'
import { FONT_FAMILIES, LATER, TYPE } from './tokens.mjs'

const section = (title, ...children) => board(title, { w: 1200, h: 'auto', layout: 'column', gap: 'space.16' }, text('title', title, { style: 'h3', color: 'color.text' }), ...children)

// --- Foundations -----------------------------------------------------------------------------------------------

export function foundations(T) {
  return foundationSections(T, { type: (name) => !LATER.type.has(name), radius: (name) => !LATER.radius.has(name) })
}

/** The text styles and radii added for the workspace, on a page of their own (see LATER in tokens.mjs). */
export function laterFoundations(T) {
  return foundationSections(T, { type: (name) => LATER.type.has(name), radius: (name) => LATER.radius.has(name), only: true })
}

function foundationSections(T, { type, radius: radiusShown, only = false }) {
  const hex = (name) => {
    const v = T.resolver().value(name)
    return String(v)
  }
  const swatch = (name) =>
    board(name, { w: 128, h: 'auto', layout: 'column', gap: 'space.6' }, rect('colour', { w: 128, h: 64, radius: 'radius.control', fill: name, stroke: { color: 'color.line', width: 'border.1' } }), text('name', name.replace('color.', ''), { style: 'connect', color: 'color.text' }), text('value', hex(name), { style: 'server-host', color: 'color.muted' }))
  const row = (name, ...kids) => board(name, { w: 'fill', h: 'auto', layout: 'row', wrap: true, gap: 'space.16' }, ...kids)

  const core = T.names('core').filter((n) => n.startsWith('color.'))
  const scheme = T.names('scheme/light')
  const app = T.names('app/computes')

  const types = Object.keys(TYPE).filter(type).map((name) =>
    board(`type.${name}`, { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.24' }, text('token', `type.${name}`, { style: 'server-host', color: 'color.muted', w: 200 }), text('sample', name === 'wordmark' ? 'claudia' : "Tables, texts and slides on this place", { style: name, color: name === 'wordmark' ? 'color.wordmark' : 'color.text' })),
  )

  const spaces = T.names('core').filter((n) => n.startsWith('space.'))
  const space = (name) => {
    const v = parseFloat(T.resolver().value(name))
    return board(name, { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.12' }, text('token', name, { style: 'server-host', color: 'color.muted', w: 120 }), rect('bar', { w: name, h: 12, fill: 'color.app' }), text('px', `${v}px`, { style: 'hint', color: 'color.muted' }))
  }
  const radii = T.names('core').filter((n) => n.startsWith('radius.') && radiusShown(n))
  const radius = (name) => board(name, { layout: 'column', gap: 'space.6' }, rect('shape', { w: 96, h: 64, radius: name, fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' } }), text('token', name, { style: 'server-host', color: 'color.muted' }))
  const fonts = Object.entries(FONT_FAMILIES).map(([key, f]) =>
    board(`font.${key}`, { w: 280, h: 'auto', layout: 'column', gap: 'space.6' }, text('specimen', 'Aa', { style: key === 'display' ? 'h1' : key === 'hand' ? 'wordmark' : key === 'mono' ? 'kbd' : 'body', color: 'color.text' }), text('family', f.family, { style: 'connect', color: 'color.text' }), text('token', `font.${key}: ${f.note}`, { style: 'hint', color: 'color.muted', w: 260 })),
  )

  if (only) return [section('Type', board('styles', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.12' }, ...types)), section('Radius', row('radii', ...radii.map(radius)))]
  return [
    section('Colour: the palette (set core)', row('palette', ...core.map(swatch))),
    section('Colour: the scheme (set scheme/light or scheme/dark)', row('scheme', ...scheme.map((n) => swatch(n)))),
    section('Colour: the app (set app/computes, composes or creates)', row('app', ...app.map((n) => swatch(n)))),
    section('Type', board('styles', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.12' }, ...types)),
    section('Fonts', row('fonts', ...fonts)),
    section('Space', board('scale', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.6' }, ...spaces.map(space))),
    section('Radius', row('radii', ...radii.map(radius))),
    section('Shadow', row('shadow', board('card', { w: 200, h: 96, fill: 'color.surface', radius: 'radius.card', shadow: 'shadow.card' }), text('token', 'shadow.card', { style: 'server-host', color: 'color.muted' }))),
  ]
}

// --- Icons and Components --------------------------------------------------------------------------------------

export const librarySheets = (lib) => [lib.appIcon, lib.glyph, lib.button, lib.rowAction, lib.field, lib.place, lib.docRow, lib.kind].concat([lib.search, lib.dashed, lib.filter, lib.wordmark, lib.summary])

// --- the front page --------------------------------------------------------------------------------------------

/** The page background: paper to mist at 160deg (a CSS gradient, which Penpot has no tokens for). */
function pageGradient(tokens) {
  const a = tokens.value('color.paper')
  const b = tokens.value('color.mist')
  return {
    lazy: ({ w, h }) => {
      const angle = (160 * Math.PI) / 180
      const dx = Math.sin(angle)
      const dy = -Math.cos(angle)
      const len = Math.abs(w * dx) + Math.abs(h * dy)
      const cx = w / 2
      const cy = h / 2
      const p = (t) => [(cx + dx * len * (t - 0.5)) / w, (cy + dy * len * (t - 0.5)) / h]
      const [sx, sy] = p(0)
      const [ex, ey] = p(1)
      return {
        type: 'linear',
        startX: sx,
        startY: sy,
        endX: ex,
        endY: ey,
        width: 1,
        stops: [
          { color: a, opacity: 1, offset: 0 },
          { color: a, opacity: 1, offset: 0.55 },
          { color: b, opacity: 1, offset: 1 },
        ],
      }
    },
  }
}

export async function frontPage(lib, env) {
  const { tokens, ch52 } = env
  const act = (Glyph) => instance(pick(lib.rowAction, { Glyph, State: 'default' }), {})
  const place = (State, name, host, w = 165) => instance(pick(lib.place, { State }), { w, edit: { name: { content: name }, host: { content: host } } })

  const sidebar = board(
    'Places',
    { w: 'size.sidebar', h: 'fill', layout: 'column', pad: ['space.14', 'space.11', 'space.14', 'space.10'], fill: 'color.mist' },
    board('title', { w: 'fill', h: 'auto', layout: 'row', pad: ['space.4', 'space.8', 'space.8', 'space.8'] }, text('title', 'My places', { style: 'sidebar-title', color: 'color.muted' })),
    board('places', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.3' }, board('place', { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.1' }, place('current', "admin's server", '127.0.0.1:8765'), act('pencil'), act('gear'))),
    instance(lib.dashed, { w: 'fill', m: ['space.8', 0, 0, 0], edit: { label: { content: '+ Connect to a server…' } } }),
    board('collections title', { w: 'fill', h: 'auto', layout: 'row', m: ['space.18', 0, 0, 0], pad: ['space.4', 'space.8', 'space.8', 'space.8'] }, text('title', 'Collections', { style: 'sidebar-title', color: 'color.muted' })),
    instance(lib.dashed, { w: 'fill', m: ['space.8', 0, 0, 0], edit: { label: { content: '+ New collection' } } }),
    board('spacer', { w: 'fill', h: 'fill' }),
    board('kept', { w: 'fill', h: 'auto', layout: 'row', pad: ['space.16', 'space.8', 'space.4', 'space.8'] }, text('hint', 'Mine and the collections are kept in this browser.', { style: 'hint', color: 'color.muted', w: 'fill' })),
    rect('divider', { abs: true, x: 239, y: 0, w: 1, h: 'fill', fill: 'color.line' }),
  )

  const docRow = (App, name, kind, when) =>
    board(
      'document',
      { w: 'fill', h: 'auto', layout: 'column', gap: 'space.2' },
      board('line', { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.2' }, instance(pick(lib.docRow, { App, State: 'default' }), { edit: { name: { content: name }, meta: { content: `${kind} · ${when}` } } }), board('actions', { layout: 'row', align: 'center' }, act('info'), act('bookmark'))),
      instance(lib.summary, { w: 'fill' }),
    )

  const heading = (name, content, o = {}) => text(name, content, { style: 'h2', color: 'color.muted', ...o })

  const left = board(
    'documents',
    { w: 360, h: 'auto', layout: 'column' },
    board('mine', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.10', m: [0, 0, 'space.18', 0] }, heading('title', 'Mine · opened before'), text('hint', 'Nothing opened yet from this browser.', { style: 'hint', color: 'color.muted', w: 'fill' })),
    board(
      'list',
      { w: 'fill', h: 'auto', layout: 'column', gap: 'space.10' },
      board('head', { w: 'fill', h: 'auto', layout: 'row', align: 'center', justify: 'space-between' }, heading('title', "On admin's server · 35"), instance(lib.filter, {})),
      board(
        'rows',
        { w: 'fill', h: 300, layout: 'column', gap: 'space.6', clip: true },
        docRow('creates', 'creates-d-4805', 'Slides', 'just now'),
        docRow('composes', 'composes-d-8526', 'Text', '1 min ago'),
        docRow('computes', 'computes-d-2219', 'Table', '1 min ago'),
        docRow('creates', 'talk-7321', 'Slides', '2 min ago'),
      ),
    ),
  )

  const field = (Value, Trailing, label, value) => instance(pick(lib.field, { Value, Trailing }), { w: 'fill', edit: { label: { content: label }, value: { content: value } } })
  const kind = (App) => instance(pick(lib.kind, { App, Chosen: 'no' }), { w: 'fill' })
  const button = (Kind, content, w) => instance(pick(lib.button, { Kind, Size: 'regular', State: 'default' }), { ...(w ? { w } : {}), edit: { label: { content } } })

  const form = board(
    'form',
    { w: 288, h: 'auto', layout: 'column', gap: 'space.12' },
    field('placeholder', 'none', 'Document', 'budget-2027'),
    field('placeholder', 'none', 'Your name', 'ann'),
    field('placeholder', 'eye', 'Password', '\u00a0'),
    board('buttons', { w: 'fill', h: 'auto', layout: 'row', gap: 'space.10', m: ['space.4', 0, 0, 0] }, button('primary', 'Open')),
    text('forgot', 'I forgot my password', { style: 'hint', color: 'color.app-text', underline: true }),
    board(
      'new',
      { w: 'fill', h: 'auto', layout: 'column', m: ['space.8', 0, 0, 0] },
      rect('divider', { w: 'fill', h: 'border.1', fill: 'color.line' }),
      board(
        'start',
        { w: 'fill', h: 'auto', layout: 'column', gap: 'space.10', pad: ['space.14', 0, 0, 0] },
        text('title', 'Or start a new one', { style: 'h3', color: 'color.text' }),
        board('kinds', { w: 'fill', h: 'auto', layout: 'row', gap: 'space.6' }, kind('computes'), kind('composes'), kind('creates')),
        button('default', 'Create document', 'fill'),
        text('hint', 'A new document belongs to whoever creates it first. The password protects this document only (at least 8 characters, with a capital letter, a small letter and a digit).', { style: 'hint', color: 'color.muted', w: 'fill' }),
      ),
    ),
  )

  const main = board(
    'Main',
    { w: 'fill', h: 'auto', layout: 'column', pad: ['space.36', 'space.40', 'space.32', 'space.40'] },
    text('title', "admin's server", { style: 'h1', color: 'color.text', m: [0, 0, 'space.8', 0] }),
    text('sub', 'Tables, texts and slides on this place, and the documents you opened before.', { style: 'body', color: 'color.muted', w: ch52, m: [0, 0, 'space.24', 0] }),
    board('tools', { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.12' }, instance(lib.search, { w: 'fill', edit: { placeholder: { content: "Search Mine and admin's server" } } }), button('default', 'Open a File…')),
    text('drop', 'Word, Excel, PowerPoint, OpenDocument or Claudia, or drop one anywhere on this page.', { style: 'hint', color: 'color.muted', w: 'fill', align: 'right', m: ['space.6', 0, 'space.18', 0] }),
    board('columns', { w: 'fill', h: 'auto', layout: 'row', gap: 'space.32' }, left, form),
  )

  // Penpot gives a hugging board nothing for a child that fills its height (the card was 0px high): the card's height
  // is the main part's, written down, and both parts then fill it.
  const cardH = Math.ceil((await measureBox(main, 760, null)).h)
  main.h = 'fill'
  const card = board('Card', { w: 'size.card', h: cardH, layout: 'row', fill: 'color.surface', radius: 'radius.card', shadow: 'shadow.card', clip: true }, sidebar, main)

  return board(
    'Front page',
    { w: 1360, h: 'auto', layout: 'column', align: 'center', fill: pageGradient(tokens), clip: true },
    board('header', { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.18', pad: ['space.6', 'space.28'] }, instance(lib.wordmark, {})),
    board('stage', { w: 'fill', h: 'auto', layout: 'column', align: 'center', pad: [0, 0, 'space.32', 0] }, card),
  )
}
