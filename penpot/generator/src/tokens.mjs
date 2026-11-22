// The design tokens of claudia as a Penpot token library (sets and themes), plus a resolver for the shapes.
//
// Colours are not retyped here: they come out of web/app/assets/tokens.css (src/css-tokens.mjs). The scale (spacing,
// radii, type sizes, ...) is what the front page's components actually use (web/app/components/OpenDialog.vue and
// assets/app.css); every entry says where it comes from, so a change in the code is a change here.
import { APPS, cascade, evalColor, parseTokensCss, toHex, toRgbaText } from './css-tokens.mjs'

// --- the scale -------------------------------------------------------------------------------------------------

export const FONT_FAMILIES = {
  // css custom property -> the family claudia loads for it (@fontsource, nuxt.config.ts) and Penpot's font id
  ui: { family: 'Inter', id: 'gfont-inter', note: 'interface and body, app names in lowercase' },
  display: { family: 'Fraunces', id: 'gfont-fraunces', note: 'headlines and numerals' },
  mono: { family: 'JetBrains Mono', id: 'gfont-jetbrains-mono', note: 'code, formulas, hosts, key names' },
  hand: { family: 'Sacramento', id: 'gfont-sacramento', note: 'the wordmark "claudia" only' },
}

const WEIGHTS = { regular: 400, medium: 500, semibold: 600 }

// Sizes in px; the name is the size, a hyphen stands for the decimal point (token names have no dot but groups).
const sizeName = (n) => String(n).replace('.', '-')
const FONT_SIZES = [11, 11.5, 12, 12.5, 13, 13.5, 14, 34, 40]
const SPACE = [1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 24, 28, 32, 36, 40]
const RADIUS = {
  'input-small': [7, 'inputs in the sidebar, row actions'],
  field: [8, 'a labelled field (.field input)'],
  control: [9, 'server rows, the search field, kind buttons, notices'],
  row: [10, 'a document row, a menu; --radius in tokens.css'],
  card: [18, 'the front page card'],
  pill: [999, 'buttons (.btn)'],
}
const BORDER = { 1: 'every outline', 2: 'the chosen kind of a new document' }
const SIZING = {
  sidebar: [240, 'width of the places sidebar (.servers)'],
  card: [1000, 'width of the front page card (.card)'],
  'row-action': [26, 'a row action button (.server-action)'],
  dot: [8, 'the dot before a place (.server-dot)'],
  'app-icon-s': [20, 'an app icon next to a kind (AppIcon :size 20)'],
  'app-icon-m': [22, 'an app icon in a document row (AppIcon :size 22)'],
  'app-icon-l': [64, 'an app icon at its design size'],
}
const OPACITY = { disabled: [0.45, 'a disabled button (.btn:disabled)'], baseline: [0.55, 'the baseline in the composes icon'] }

/** Text styles. lh: a factor, or 'normal' (resolved in a browser); ls in em; sizes name a font.size token. */
export const TYPE = {
  body: { font: 'ui', size: 14, weight: 'regular', lh: 1.45, note: 'body and form text (body in app.css)' },
  button: { font: 'ui', size: 14, weight: 'medium', lh: 1.45, note: 'buttons (.btn)' },
  'button-small': { font: 'ui', size: 12.5, weight: 'medium', lh: 1.45, note: '.btn.small' },
  h1: { font: 'display', size: 40, weight: 'regular', lh: 1.1, note: 'page title (h1)' },
  h2: { font: 'ui', size: 12, weight: 'medium', lh: 1, ls: 0.06, transform: 'uppercase', note: 'section heading (h2)' },
  h3: { font: 'ui', size: 13, weight: 'semibold', lh: 'normal', note: 'block heading (h3; the font shorthand resets the line height)' },
  'sidebar-title': { font: 'ui', size: 12, weight: 'semibold', lh: 'normal', note: 'sidebar section title (.servers-title)' },
  'server-name': { font: 'ui', size: 13.5, weight: 'medium', lh: 'normal', note: '.server-name' },
  'server-host': { font: 'mono', size: 11.5, weight: 'regular', lh: 'normal', note: '.server-host' },
  connect: { font: 'ui', size: 13, weight: 'medium', lh: 'normal', note: '.connect-start' },
  count: { font: 'ui', size: 11.5, weight: 'regular', lh: 'normal', note: 'a count (.count)' },
  hint: { font: 'ui', size: 12, weight: 'regular', lh: 1.45, note: 'hints, field labels, meta (.hint, .field, .meta)' },
  summary: { font: 'ui', size: 12.5, weight: 'regular', lh: 1.45, note: "a document's description (.summary)" },
  input: { font: 'ui', size: 14, weight: 'regular', lh: 1.45, note: 'text in a field (.field input; line-height is inherited, font: inherit)' },
  search: { font: 'ui', size: 13.5, weight: 'regular', lh: 'normal', note: 'text in the search field' },
  kind: { font: 'ui', size: 12.5, weight: 'medium', lh: 'normal', note: 'a kind of document (.kind)' },
  'kind-chosen': { font: 'ui', size: 12.5, weight: 'semibold', lh: 'normal', note: 'the chosen kind (.kind[aria-checked=true])' },
  kbd: { font: 'mono', size: 11, weight: 'regular', lh: 'normal', note: 'a key name (kbd)' },
  filter: { font: 'ui', size: 12, weight: 'regular', lh: 'normal', note: 'a list filter (.filter)' },
  wordmark: { font: 'hand', size: 34, weight: 'regular', lh: 1, note: 'the wordmark (Wordmark.vue)' },
}

// --- the colours -----------------------------------------------------------------------------------------------

/** Custom properties whose value depends on the colour scheme (they get a set per scheme), and on the app. */
const SCHEME_COLORS = ['text', 'wordmark', 'muted', 'faint', 'line', 'line-field', 'surface', 'page', 'purpose-input', 'purpose-data', 'purpose-calc', 'purpose-result', 'tint-now', 'tint-since', 'app-text']
const APP_COLORS = ['app', 'app-dark', 'app-soft']
const NOT_COLORS = ['font-ui', 'font-display', 'font-mono', 'font-hand', 'radius', 'shadow']

const colorText = (rgba) => (rgba[3] < 1 ? toRgbaText(rgba) : toHex(rgba))

export function buildTokens({ cssFile, lineHeightOf }) {
  const parsed = parseTokensCss(cssFile)
  const scenario = (dark, app) => cascade(parsed, { dark, app })
  const light = scenario(false, 'computes')

  // core colours: everything that does not move with the scheme or the app
  const coreColors = {}
  for (const [name, value] of Object.entries(light)) {
    if (NOT_COLORS.includes(name) || SCHEME_COLORS.includes(name) || APP_COLORS.includes(name)) continue
    coreColors[name] = evalColor(value, light)
  }
  // creates' darker apricot is only ever written as a literal in its app override
  coreColors['apricot-dark'] = evalColor(scenario(false, 'creates')['app-dark'], light)
  const coreByHex = new Map()
  for (const [name, c] of Object.entries(coreColors)) if (c.rgba[3] === 1 && !coreByHex.has(toHex(c.rgba))) coreByHex.set(toHex(c.rgba), name)

  /** A colour token value: a reference to a core colour where the stylesheet has one, else the colour itself. */
  const colorValue = (c) => {
    if (c.ref && c.ref in coreColors) return `{color.${c.ref}}`
    const byHex = c.rgba[3] === 1 ? coreByHex.get(toHex(c.rgba)) : undefined
    return byHex ? `{color.${byHex}}` : colorText(c.rgba)
  }
  const tok = (type, value, description = '') => ({ $type: type, $value: value, $description: description })

  const core = {}
  const put = (set, name, token) => {
    const path = name.split('.')
    let node = set
    for (const p of path.slice(0, -1)) node = node[p] ??= {}
    node[path.at(-1)] = token
  }

  for (const [name, c] of Object.entries(coreColors)) {
    put(core, `color.${name}`, tok('color', c.ref && c.ref in coreColors ? `{color.${c.ref}}` : colorText(c.rgba), `--${name} in tokens.css`))
  }
  for (const [key, f] of Object.entries(FONT_FAMILIES)) put(core, `font.${key}`, tok('fontFamilies', f.family, `--font-${key}: ${f.note}`))
  for (const [name, w] of Object.entries(WEIGHTS)) put(core, `font.weight.${name}`, tok('fontWeights', String(w)))
  for (const s of FONT_SIZES) put(core, `font.size.${sizeName(s)}`, tok('fontSizes', String(s), `${s}px`))
  for (const s of SPACE) put(core, `space.${sizeName(s)}`, tok('spacing', String(s), `${s}px: a gap or padding the front page uses (a padding includes the 1px outline of its box, as boxes here are border-box)`))
  for (const [name, [v, note]] of Object.entries(SIZING)) put(core, `size.${name}`, tok('sizing', String(v), note))
  for (const [name, [v, note]] of Object.entries(RADIUS)) put(core, `radius.${name}`, tok('borderRadius', String(v), note))
  for (const [name, note] of Object.entries(BORDER)) put(core, `border.${name}`, tok('borderWidth', String(name), note))
  for (const [name, [v, note]] of Object.entries(OPACITY)) put(core, `opacity.${name}`, tok('opacity', String(v), note))

  // --shadow: 0 1px 2px rgb(31 26 51 / 8%), 0 8px 24px rgb(31 26 51 / 8%)
  const shadows = light.shadow.split(/,(?![^(]*\))/).map((s) => {
    const m = s.trim().match(/^(-?\d+)(?:px)? (-?\d+)(?:px)? (\d+)(?:px)? (rgb\(.+\))$/)
    if (!m) throw new Error(`tokens.css: cannot read the shadow "${s}"`)
    return { offsetX: m[1], offsetY: m[2], blur: m[3], spread: '0', color: toRgbaText(evalColor(m[4], {}).rgba), inset: false }
  })
  put(core, 'shadow.card', tok('shadow', shadows, '--shadow: the front page card'))

  for (const [name, t] of Object.entries(TYPE)) {
    const value = {
      fontFamilies: `{font.${t.font}}`,
      fontSizes: `{font.size.${sizeName(t.size)}}`,
      fontWeights: `{font.weight.${t.weight}}`,
      lineHeights: String(Math.round((t.lh === 'normal' ? lineHeightOf(t) / t.size : t.lh) * 1000) / 1000),
    }
    if (t.ls) value.letterSpacing = String(Math.round(t.ls * t.size * 100) / 100)
    if (t.transform) value.textCase = t.transform
    put(core, `type.${name}`, tok('typography', value, t.note))
  }

  // the scheme sets
  const schemeSet = (dark) => {
    const set = {}
    const vars = scenario(dark, 'computes')
    for (const name of SCHEME_COLORS) {
      if (name === 'app-text') {
        put(set, 'color.app-text', tok('color', dark ? '{color.app-light}' : '{color.app-dark}', dark ? 'the app colour lightened for the dark surface' : 'the dark app colour, as text'))
        continue
      }
      put(set, `color.${name}`, tok('color', colorValue(evalColor(vars[name], vars)), `--${name} in tokens.css, ${dark ? 'dark' : 'light'} scheme`))
    }
    return set
  }

  // the app sets
  const APP_LIGHT = { computes: 'teal-light', composes: 'rose-light', creates: 'apricot-light' }
  const appSet = (app) => {
    const set = {}
    const vars = scenario(false, app)
    for (const name of APP_COLORS) put(set, `color.${name}`, tok('color', colorValue(evalColor(vars[name], vars)), `--${name} in tokens.css for ${app}`))
    put(set, 'color.app-light', tok('color', `{color.${APP_LIGHT[app]}}`, `--app-text in the dark scheme for ${app}`))
    return set
  }

  const sets = { core, 'scheme/light': schemeSet(false), 'scheme/dark': schemeSet(true) }
  for (const app of APPS) sets[`app/${app}`] = appSet(app)

  const theme = (group, name, enabled, description) => ({
    id: `${group}-${name}`.toLowerCase(),
    name,
    group,
    description,
    isSource: false,
    selectedTokenSets: Object.fromEntries(enabled.map((s) => [s, 'enabled'])),
  })
  const themes = [
    theme('Scheme', 'Light', ['core', 'scheme/light'], 'the light scheme (tokens.css :root)'),
    theme('Scheme', 'Dark', ['core', 'scheme/dark'], "the dark scheme (tokens.css :root[data-theme='dark'])"),
    ...APPS.map((a) => theme('App', a, [`app/${a}`], `the colour of ${a}`)),
  ]
  const active = { themes: ['Scheme/Light', 'App/computes'], sets: ['core', 'scheme/light', 'app/computes'] }

  const doc = {
    ...sets,
    $themes: themes,
    $metadata: { tokenSetOrder: Object.keys(sets), activeThemes: active.themes, activeSets: active.sets },
  }

  // --- the resolver ---
  const flat = (set) => {
    const out = {}
    const walk = (node, path) => {
      if ('$value' in node) out[path.join('.')] = node
      else for (const [k, v] of Object.entries(node)) walk(v, [...path, k])
    }
    walk(set, [])
    return out
  }
  const flatSets = Object.fromEntries(Object.entries(sets).map(([n, s]) => [n, flat(s)]))

  function resolver(activeSets = active.sets) {
    const lookup = (name) => {
      let found
      for (const s of activeSets) if (flatSets[s]?.[name]) found = flatSets[s][name]
      if (!found) throw new Error(`token ${name} is not defined in the active sets (${activeSets.join(', ')})`)
      return found
    }
    const resolveValue = (v) => {
      if (typeof v === 'string') {
        const m = v.match(/^\{([\w.-]+)\}$/)
        return m ? resolveValue(lookup(m[1]).$value) : v
      }
      if (Array.isArray(v)) return v.map(resolveValue)
      if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, resolveValue(x)]))
      return v
    }
    return {
      /** the value of a token under the active themes */
      value: (name) => resolveValue(lookup(name).$value),
      type: (name) => lookup(name).$type,
      has: (name) => activeSets.some((s) => flatSets[s]?.[name]),
    }
  }

  const names = (setName) => Object.keys(flatSets[setName])
  return { doc, resolver, active, themes, sets, names, coreColors: Object.fromEntries(Object.entries(coreColors).map(([k, c]) => [k, toHex(c.rgba)])) }
}

/** The CSS-ish font spec of a text style, for measuring and for the shapes. */
export function fontSpecOf(styleName, resolve) {
  const t = TYPE[styleName]
  if (!t) throw new Error(`unknown text style ${styleName}`)
  const size = t.size
  return {
    family: FONT_FAMILIES[t.font].family,
    fontId: FONT_FAMILIES[t.font].id,
    size,
    weight: WEIGHTS[t.weight],
    style: t.style ?? 'normal',
    lh: t.lh,
    ls: t.ls ? Math.round(t.ls * size * 100) / 100 : 0,
    transform: t.transform ?? 'none',
  }
}
