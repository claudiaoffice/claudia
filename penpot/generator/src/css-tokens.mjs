// Reads claudia's web/app/assets/tokens.css and evaluates its custom properties the way a browser would, for each
// combination of colour scheme (light/dark) and app (computes/composes/creates).
//
// Only what tokens.css uses is understood: var(), hex colours, rgb(), `transparent`, `white` and
// `color-mix(in srgb, A p%, B)`. Anything else throws, so a new kind of value in the stylesheet cannot be dropped
// silently.
import { readFileSync } from 'node:fs'

export const APPS = ['computes', 'composes', 'creates']

/** @returns {{root: Record<string,string>, apps: Record<string,Record<string,string>>, dark: Record<string,string>, darkApps: Record<string,Record<string,string>>}} */
export function parseTokensCss(file) {
  const css = readFileSync(file, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '')
  const out = { root: {}, apps: {}, dark: {}, darkApps: {} }
  for (const [, selector, body] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const sel = selector.trim().replace(/\s+/g, '')
    let target
    let m
    if (sel === ':root') target = out.root
    else if ((m = sel.match(/^:root\[data-app='(\w+)'\]$/))) target = out.apps[m[1]] ??= {}
    else if (sel === ":root[data-theme='dark']") target = out.dark
    else if ((m = sel.match(/^:root\[data-theme='dark'\]\[data-app='(\w+)'\]$/))) target = out.darkApps[m[1]] ??= {}
    else continue
    for (const decl of body.split(';')) {
      const d = decl.match(/^\s*--([\w-]+)\s*:\s*([\s\S]+?)\s*$/)
      if (d) target[d[1]] = d[2].replace(/\s+/g, ' ')
    }
  }
  return out
}

/** The custom properties as they apply to one scheme and app (the cascade order of tokens.css). */
export function cascade(parsed, { dark, app }) {
  return {
    ...parsed.root,
    ...(parsed.apps[app] ?? {}),
    ...(dark ? parsed.dark : {}),
    ...(dark ? parsed.darkApps[app] ?? {} : {}),
  }
}

// --- colours ---------------------------------------------------------------------------------------------------

const NAMED = { white: [255, 255, 255, 1], transparent: [0, 0, 0, 0] }

export function parseColor(text) {
  const t = text.trim().toLowerCase()
  if (NAMED[t]) return [...NAMED[t]]
  let m = t.match(/^#([0-9a-f]{3}|[0-9a-f]{6})$/)
  if (m) {
    const h = m[1].length === 3 ? [...m[1]].map((c) => c + c).join('') : m[1]
    return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)).concat(1)
  }
  m = t.match(/^rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)(?:\s*[/,]\s*([\d.]+)(%?))?\s*\)$/)
  if (m) return [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : m[5] ? +m[4] / 100 : +m[4]]
  return null
}

/** Splits `a, b(c, d), e` at the commas outside brackets. */
function splitTop(s) {
  const parts = []
  let depth = 0
  let cur = ''
  for (const ch of s) {
    if (ch === '(') depth++
    if (ch === ')') depth--
    if (ch === ',' && depth === 0) {
      parts.push(cur.trim())
      cur = ''
    } else cur += ch
  }
  parts.push(cur.trim())
  return parts
}

/**
 * Evaluates a colour value. Returns `{ rgba, ref }`: `ref` is the custom property it is a plain `var()` of (so the
 * token can stay a reference), `rgba` is the colour either way.
 */
export function evalColor(value, vars, seen = []) {
  const v = value.trim()
  const ref = v.match(/^var\(--([\w-]+)\)$/)
  if (ref) {
    if (seen.includes(ref[1])) throw new Error(`tokens.css: circular var(--${ref[1]})`)
    if (!(ref[1] in vars)) throw new Error(`tokens.css: var(--${ref[1]}) is not defined`)
    return { rgba: evalColor(vars[ref[1]], vars, [...seen, ref[1]]).rgba, ref: ref[1] }
  }
  const mix = v.match(/^color-mix\(in srgb, (.+)\)$/)
  if (mix) {
    const [a, b] = splitTop(mix[1])
    const side = (s) => {
      const m = s.match(/^(.*?)(?:\s+([\d.]+)%)?$/)
      return { color: evalColor(m[1], vars, seen).rgba, pct: m[2] === undefined ? null : +m[2] / 100 }
    }
    const A = side(a)
    const B = side(b)
    const pa = A.pct ?? (B.pct === null ? 0.5 : 1 - B.pct)
    const pb = B.pct ?? 1 - pa
    // premultiplied mixing, as CSS does it
    const alpha = A.color[3] * pa + B.color[3] * pb
    const ch = (i) => (alpha === 0 ? 0 : (A.color[i] * A.color[3] * pa + B.color[i] * B.color[3] * pb) / alpha)
    return { rgba: [ch(0), ch(1), ch(2), alpha] }
  }
  const c = parseColor(v)
  if (!c) throw new Error(`tokens.css: cannot read the colour "${value}"`)
  return { rgba: c }
}

export const hex2 = (n) => Math.round(Math.min(255, Math.max(0, n))).toString(16).padStart(2, '0').toUpperCase()
export function toHex([r, g, b, a]) {
  return `#${hex2(r)}${hex2(g)}${hex2(b)}${a < 1 ? hex2(a * 255) : ''}`
}
/** CSS colour text, for a token whose colour is translucent. */
export function toRgbaText([r, g, b, a]) {
  return `rgba(${Math.round(r)}, ${Math.round(g)}, ${Math.round(b)}, ${Math.round(a * 1000) / 1000})`
}
export const isColorValue = (value) => {
  try {
    evalColor(value, {})
    return true
  } catch {
    return /^var\(--[\w-]+\)$/.test(value.trim()) || value.trim().startsWith('color-mix(')
  }
}
