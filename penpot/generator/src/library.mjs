// The design system of claudia's front page, as Penpot components: every one is built from the tokens (colours,
// spacing, radii, type), every variant is a real variant of one component, and what is inside another component
// (an icon in a row action, an app icon in a document row) is an instance of it.
import { board, circle, component, instance, path, pick, rect, text, variantSet } from './model.mjs'
import { boundsOf, circlePath, mapPath, parsePath } from './svgpath.mjs'

const WHITE = { raw: '#FFFFFF' }

// --- vectors ---------------------------------------------------------------------------------------------------

/** Exact bounds of a path: the curves are sampled, as a control point is not on the curve. */
function exactBounds(segs) {
  let x1 = Infinity
  let y1 = Infinity
  let x2 = -Infinity
  let y2 = -Infinity
  const see = (x, y) => {
    x1 = Math.min(x1, x)
    x2 = Math.max(x2, x)
    y1 = Math.min(y1, y)
    y2 = Math.max(y2, y)
  }
  let cx = 0
  let cy = 0
  let sx = 0
  let sy = 0
  for (const s of segs) {
    if (s[0] === 'M') [cx, cy] = [sx, sy] = [s[1], s[2]]
    else if (s[0] === 'L') [cx, cy] = [s[1], s[2]]
    else if (s[0] === 'C') {
      for (let i = 0; i <= 32; i++) {
        const t = i / 32
        const u = 1 - t
        see(u * u * u * cx + 3 * u * u * t * s[1] + 3 * u * t * t * s[3] + t * t * t * s[5], u * u * u * cy + 3 * u * u * t * s[2] + 3 * u * t * t * s[4] + t * t * t * s[6])
      }
      ;[cx, cy] = [s[5], s[6]]
    } else [cx, cy] = [sx, sy]
    if (s[0] !== 'Z') see(cx, cy)
  }
  return { x1, y1, x2, y2 }
}

/** A path layer from SVG path data in a `box`-sized viewBox, drawn at `scale`; its own box is the path's bounds. */
function vector(name, d, scale, o = {}) {
  const segs = typeof d === 'string' ? parsePath(d) : d
  const scaled = mapPath(segs, (x, y) => [x * scale, y * scale])
  const b = exactBounds(scaled)
  const shifted = mapPath(scaled, (x, y) => [x - b.x1, y - b.y1])
  return path(name, shifted, { x: b.x1, y: b.y1, w: b.x2 - b.x1, h: b.y2 - b.y1, ...o })
}

const line = (colorToken, width, extra = {}) => ({ color: colorToken, width, align: 'center', cap: 'round', ...extra })

// --- icons -----------------------------------------------------------------------------------------------------

const APP_COLOR = { computes: 'color.teal', composes: 'color.rose', creates: 'color.apricot' }

/** An app icon (AppIcon.vue, 64×64 design) at `size`. */
function appIconBoard(app, size) {
  const k = size / 64
  const kids = [rect('plate', { x: 2 * k, y: 2 * k, w: 60 * k, h: 60 * k, radius: 15 * k, fill: APP_COLOR[app] })]
  if (app === 'computes') {
    kids.push(vector('equals', 'M16 24 H48', k, { stroke: line(null, 5 * k, { raw: '#FFFFFF' }) }))
    kids.push(vector('wave', 'M16 41 C24 33 30 49 38 41 C42 37 45 38 48 40', k, { stroke: line(null, 5 * k, { raw: '#FFFFFF' }) }))
  } else if (app === 'composes') {
    kids.push(vector('nib', 'M32 11 L42 32 L32 46 L22 32 Z', k, { fill: WHITE }))
    kids.push(circle('hole', { x: (32 - 2.6) * k, y: (29 - 2.6) * k, w: 5.2 * k, h: 5.2 * k, fill: 'color.rose' }))
    kids.push(vector('slit', 'M32 31.5 L32 46', k, { stroke: line('color.rose', 1.8 * k) }))
    kids.push(vector('baseline', 'M16 52 H48', k, { stroke: line(null, 3 * k, { raw: '#FFFFFF' }), opacity: 'opacity.baseline' }))
  } else {
    kids.push(vector('slide', 'M14 18 H50 V46 H14 Z M32 22 A8 8 0 1 0 32 38 A8 8 0 1 0 32 22 Z', k, { fill: WHITE }))
  }
  return board('App icon', { w: size, h: size }, ...kids)
}

const ICONS = {
  // glyph: [width, height, viewBox scale, stroke width in viewBox units, paths]
  pencil: [13, 13, 13 / 24, 1.8, [['stroke', 'M12 20h9'], ['stroke', 'M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z']]],
  gear: [
    13,
    13,
    13 / 24,
    1.8,
    [
      ['stroke', circlePath(12, 12, 3)],
      [
        'stroke',
        'M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z',
      ],
    ],
  ],
  eye: [20, 14, 1, 1.5, [['stroke', 'M1 7c3.6-6.6 14.4-6.6 18 0-3.6 6.6-14.4 6.6-18 0z'], ['stroke', circlePath(10, 7, 2.6)]]],
  'eye-off': [20, 14, 1, 1.5, [['stroke', 'M1 7c3.6-6.6 14.4-6.6 18 0-3.6 6.6-14.4 6.6-18 0z'], ['stroke', circlePath(10, 7, 2.6)], ['stroke', 'M3 13 17 1']]],
  bookmark: [12, 15, 1, 1.4, [['stroke', 'M1 1h10v13l-5-4-5 4z']]],
  chevron: [10, 6, 1, 1.4, [['stroke', 'M1 1l4 4 4-4']]],
}

function iconBoard(glyph, colorToken = 'color.muted') {
  const [w, h, k, sw, paths] = ICONS[glyph]
  const kids = paths.map(([, d], i) => vector(i === 0 ? 'outline' : `outline ${i + 1}`, d, k, { stroke: line(colorToken, sw * k) }))
  return board('Icon', { w, h }, ...kids)
}

// --- the library -----------------------------------------------------------------------------------------------

export function buildLibrary() {
  const lib = {}

  // Icons / App icon: App × Size
  lib.appIcon = variantSet('App icon', 'Icons', { App: ['computes', 'composes', 'creates'], Size: ['20', '22', '64'] }, ({ App, Size }) => appIconBoard(App, +Size), { w: 760 })
  // Icons / Glyph: the line icons, in the colour of their surroundings (muted by default)
  lib.glyph = variantSet('Icon', 'Icons', { Glyph: Object.keys(ICONS) }, ({ Glyph }) => iconBoard(Glyph), { w: 760 })

  // Atoms / Button: Kind × Size × State (.btn in app.css)
  lib.button = variantSet(
    'Button',
    'Atoms',
    { Kind: ['default', 'primary'], Size: ['regular', 'small'], State: ['default', 'hover', 'disabled'] },
    ({ Kind, Size, State }) => {
      const primary = Kind === 'primary'
      const small = Size === 'small'
      const hover = State === 'hover'
      const fill = primary ? (hover ? 'color.iris' : 'color.ink') : hover ? 'color.faint' : undefined
      return board(
        'Button',
        {
          layout: 'row',
          align: 'center',
          justify: 'center',
          pad: small ? ['space.6', 'space.11'] : ['space.7', 'space.17'],
          radius: 'radius.pill',
          fill,
          stroke: { color: primary ? (hover ? 'color.iris' : 'color.ink') : 'color.line-field', width: 'border.1' },
          opacity: State === 'disabled' ? 'opacity.disabled' : undefined,
        },
        text('label', 'Button', { style: small ? 'button-small' : 'button', color: primary ? 'color.paper' : 'color.text' }),
      )
    },
    { w: 960 },
  )

  // Atoms / Row action: Glyph × State (.server-action, 26×26)
  lib.rowAction = variantSet(
    'Row action',
    'Atoms',
    { Glyph: ['pencil', 'gear', 'bookmark', 'info', 'remove'], State: ['default', 'hover'] },
    ({ Glyph, State }) => {
      const hover = State === 'hover'
      const content =
        Glyph === 'info' || Glyph === 'remove'
          ? text('glyph', Glyph === 'info' ? 'i' : '×', { style: 'body', color: hover ? 'color.text' : 'color.muted' })
          : instance(pick(lib.glyph, { Glyph }), { nested: true, edit: {} })
      return board('Row action', { w: 'size.row-action', h: 'size.row-action', layout: 'row', align: 'center', justify: 'center', radius: 'radius.input-small', fill: hover ? 'color.faint' : undefined }, content)
    },
    { w: 760 },
  )

  // Atoms / Field: Value × Trailing (label above an input; .field in app.css, PasswordInput.vue)
  lib.field = variantSet(
    'Field',
    'Atoms',
    { Value: ['placeholder', 'filled'], Trailing: ['none', 'eye'] },
    ({ Value, Trailing }) => {
      const eye = Trailing === 'eye'
      return board(
        'Field',
        { w: 288, h: 'auto', layout: 'column', gap: 'space.4' },
        text('label', 'Label', { style: 'hint', color: 'color.muted' }),
        board(
          'input',
          { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.4', pad: eye ? ['space.9', 'space.10', 'space.9', 'space.11'] : ['space.9', 'space.11'], radius: 'radius.field', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' } },
          text('value', Value === 'filled' ? 'Value' : 'Placeholder', { style: 'input', color: Value === 'filled' ? 'color.text' : 'color.muted', w: 'fill' }),
          eye ? instance(pick(lib.glyph, { Glyph: 'eye' }), { nested: true }) : null,
        ),
      )
    },
    { w: 760 },
  )

  // Atoms / Search field (.search with its Ctrl+F key name)
  lib.search = component(
    board(
      'Search field',
      { w: 'fill', h: 'auto', layout: 'row', align: 'center', gap: 'space.8', pad: ['space.10', 'space.11', 'space.10', 'space.13'], radius: 'radius.control', fill: 'color.surface', stroke: { color: 'color.line-field', width: 'border.1' } },
      text('placeholder', 'Search', { style: 'search', color: 'color.muted', w: 'fill' }),
      text('shortcut', 'Ctrl+F', { style: 'kbd', color: 'color.muted' }),
    ),
    { name: 'Search field', path: 'Atoms' },
  )
  lib.search.w = 400

  // Atoms / Dashed button (.connect-start: "+ Connect to a server…")
  lib.dashed = component(
    board('Dashed button', { w: 220, h: 'auto', layout: 'row', align: 'center', pad: ['space.9', 'space.11'], radius: 'radius.control', stroke: { color: 'color.line-field', width: 'border.1', style: 'dashed', dash: 4, dashGap: 4 } }, text('label', '+ Add', { style: 'connect', color: 'color.muted', w: 'fill' })),
    { name: 'Dashed button', path: 'Atoms' },
  )

  // Atoms / Filter (.filter: a list filter, in the app colour)
  lib.filter = component(board('Filter', { layout: 'row', align: 'center', gap: 'space.4' }, text('label', 'all apps', { style: 'filter', color: 'color.app-text' }), instance(pick(lib.glyph, { Glyph: 'chevron' }), { nested: true })), { name: 'Filter', path: 'Atoms' })

  // Atoms / Wordmark
  lib.wordmark = component(board('Wordmark', { layout: 'row' }, text('claudia', 'claudia', { style: 'wordmark', color: 'color.wordmark' })), { name: 'Wordmark', path: 'Atoms' })

  // Molecules / Place: a server in the sidebar (.server)
  lib.place = variantSet(
    'Place',
    'Molecules',
    { State: ['default', 'current'] },
    ({ State }) =>
      board(
        'Place',
        { w: 165, h: 'auto', layout: 'row', align: 'center', gap: 'space.9', pad: ['space.8', 'space.9'], radius: 'radius.control', fill: State === 'current' ? 'color.app-soft' : undefined },
        circle('dot', { w: 'size.dot', h: 'size.dot', fill: State === 'current' ? 'color.teal' : 'color.faint' }),
        board('text', { w: 'fill', h: 'auto', layout: 'column' }, text('name', "admin's server", { style: 'server-name', color: 'color.text' }), text('host', '127.0.0.1:8765', { style: 'server-host', color: 'color.muted' })),
      ),
    { w: 760 },
  )

  // Molecules / Document row: App × State (.doc: icon, name, where and when)
  lib.docRow = variantSet(
    'Document row',
    'Molecules',
    { App: ['computes', 'composes', 'creates'], State: ['default', 'chosen'] },
    ({ App, State }) =>
      board(
        'Document row',
        {
          w: 306,
          h: 'auto',
          layout: 'row',
          align: 'center',
          gap: 'space.10',
          pad: ['space.9', 'space.13'],
          radius: 'radius.row',
          fill: State === 'chosen' ? 'color.app-soft' : undefined,
          stroke: { color: State === 'chosen' ? 'color.app' : 'color.line-field', width: 'border.1' },
        },
        instance(pick(lib.appIcon, { App, Size: '22' }), { nested: true }),
        board('text', { w: 'fill', h: 'auto', layout: 'column', gap: 'space.1' }, text('name', 'document-name', { style: 'body', color: 'color.text', w: 'fill' }), text('meta', 'Kind · just now', { style: 'hint', color: 'color.muted', w: 'fill' })),
      ),
    { w: 1000 },
  )

  // Molecules / Document summary (.summary: "No description yet")
  lib.summary = component(board('Document summary', { w: 306, h: 'auto', layout: 'row', pad: ['space.2', 'space.12', 'space.6', 'space.12'] }, text('summary', 'No description yet', { style: 'summary', color: 'color.muted', italic: true, w: 'fill' })), { name: 'Document summary', path: 'Molecules' })

  // Molecules / Kind: App × Chosen (.kind: a kind of new document)
  lib.kind = variantSet(
    'Kind',
    'Molecules',
    { App: ['computes', 'composes', 'creates'], Chosen: ['no', 'yes'] },
    ({ App, Chosen }) => {
      const yes = Chosen === 'yes'
      return board(
        'Kind',
        { w: 92, h: 'auto', layout: 'row', align: 'center', gap: 'space.6', pad: yes ? 'space.10' : 'space.9', radius: 'radius.control', fill: 'color.surface', stroke: { color: yes ? 'color.text' : 'color.line-field', width: yes ? 'border.2' : 'border.1' } },
        instance(pick(lib.appIcon, { App, Size: '20' }), { nested: true }),
        text('label', { computes: 'Table', composes: 'Text', creates: 'Slides' }[App], { style: yes ? 'kind-chosen' : 'kind', color: 'color.text' }),
      )
    },
    { w: 760 },
  )

  return lib
}

export { appIconBoard, iconBoard, line, vector }
