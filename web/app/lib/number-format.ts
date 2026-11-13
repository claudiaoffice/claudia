// Number formats as the grid shows them (E6.14, D348): a value seen through Excel's format code, in the reader's locale.
//
// The value of a cell never changes; its format code (`#,##0.00 "MWh"`, `dd.mm.yyyy`, `0.0%`) says how it looks, and
// the reader's locale says with which decimal sign, thousands separator and month names. This is the twin of
// `claudia_computes.numformats.render` on the server (which `TEXT()` uses): both are checked against the same list of
// cases, `packages/claudia-computes/tests/number_format_cases.json`, so a cell looks the same however it is shown.
//
// `General` and Excel's built-in short date (`m/d/yyyy`, its format 14) are shown the reader's way.

export interface NumberSymbols {
  decimal: string
  group: string
  months: readonly string[]
  monthsShort: readonly string[]
  days: readonly string[]
  daysShort: readonly string[]
  shortDate: string
}

export const ENGLISH: NumberSymbols = {
  decimal: '.',
  group: ',',
  months: ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'],
  monthsShort: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  days: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'],
  daysShort: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
  shortDate: 'm/d/yyyy',
}

export const GERMAN: NumberSymbols = {
  decimal: ',',
  group: '.',
  months: ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'],
  monthsShort: ['Jan', 'Feb', 'Mrz', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'],
  days: ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'],
  daysShort: ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'],
  shortDate: 'dd.mm.yyyy',
}

/** The Windows locale ids a code can ask for (`[$-407]`), for the names of months and days. */
const LCID: Record<string, NumberSymbols> = { '407': GERMAN, '807': GERMAN, C07: GERMAN, '409': ENGLISH, '809': ENGLISH }

/** How a locale writes numbers and dates: English and German from tables (as Excel names months), any other locale
 * from the browser's `Intl`. */
export function symbolsFor(locale: string): NumberSymbols {
  const language = locale.toLowerCase().split('-')[0]
  if (language === 'de') return locale.toLowerCase() === 'de-ch' ? { ...GERMAN, group: '’' } : GERMAN
  if (language === 'en') return locale.toLowerCase() === 'en-gb' ? { ...ENGLISH, shortDate: 'dd/mm/yyyy' } : ENGLISH
  try {
    const parts = new Intl.NumberFormat(locale).formatToParts(12345.6)
    const month = (style: 'long' | 'short', m: number) => new Intl.DateTimeFormat(locale, { month: style, timeZone: 'UTC' }).format(Date.UTC(2021, m, 1))
    const day = (style: 'long' | 'short', d: number) => new Intl.DateTimeFormat(locale, { weekday: style, timeZone: 'UTC' }).format(Date.UTC(2021, 0, 3 + d))
    return {
      decimal: parts.find((p) => p.type === 'decimal')?.value ?? '.',
      group: parts.find((p) => p.type === 'group')?.value ?? ',',
      months: Array.from({ length: 12 }, (_, m) => month('long', m)),
      monthsShort: Array.from({ length: 12 }, (_, m) => month('short', m)),
      days: Array.from({ length: 7 }, (_, d) => day('long', d)),
      daysShort: Array.from({ length: 7 }, (_, d) => day('short', d)),
      shortDate: ENGLISH.shortDate,
    }
  } catch {
    return ENGLISH
  }
}

export const SHORT_DATE = 'm/d/yyyy'

/** The colour a format's `[Red]` asks for, as a colour that reads on the grid's paper (never pure red: contrast,
 * BITV); `null` for none. Excel's `[Color12]` numbered palette is not kept. */
export function inkOf(colour: string | null): string | null {
  const INKS: Record<string, string> = { red: '#B42318', blue: '#1D4ED8', green: '#0F7D6E', magenta: '#A21CAF', cyan: '#0E7490', black: '#1F1A33' }
  return colour === null ? null : (INKS[colour] ?? null)
}

/** A named format of the workbook, as the server's `number_formats` sends it. */
export interface NumberFormatDef {
  id: string
  name: string
  code: string
  /** It still has the provisional name the import gave it (D348). */
  to_name: boolean
}

interface FormatStyle {
  based_on: string | null
  number_format?: string | null
}

/** The format code a style shows numbers with: its own format's, else the nearest parent's; `null` for General. */
export function formatCodeOf(styles: Record<string, FormatStyle>, formats: Record<string, NumberFormatDef>, id: string): string | null {
  const seen = new Set<string>()
  for (let at: string | null = id; at !== null && !seen.has(at); at = styles[at]?.based_on ?? null) {
    seen.add(at)
    const own = styles[at]?.number_format
    if (own) return formats[own]?.code ?? null
  }
  return null
}

type Kind = 'digit' | 'point' | 'group' | 'percent' | 'exp' | 'slash' | 'literal' | 'text' | 'date' | 'ampm' | 'general'
interface Token {
  kind: Kind
  text: string
}
interface Section {
  tokens: Token[]
  colour: string | null
  condition: [string, number] | null
  locale: string | null
}

/** What a cell shows: its text, and the colour the code asks for (`[Red]`), if any. */
export interface Rendered {
  text: string
  colour: string | null
}

const COLOURS = new Set(['black', 'blue', 'cyan', 'green', 'magenta', 'red', 'white', 'yellow'])
const CONDITION = /^(<=|>=|<>|<|>|=)\s*(-?\d+(?:\.\d+)?)$/
const DATE_RUN = /^(yyyy|yy|y|mmmmm|mmmm|mmm|mm|m|dddd|ddd|dd|d|hh|h|ss|s|e|g{1,3}|b{2,4})/i
const DAY_WORDS = new Set(['d', 'dd', 'ddd', 'dddd', 'm', 'mm', 'mmm', 'mmmm', 'mmmmm', 'y', 'yy', 'yyyy', 'e'])
const SINGLE: Record<string, Kind> = { '0': 'digit', '#': 'digit', '?': 'digit', '.': 'point', ',': 'group', '%': 'percent', '/': 'slash', '@': 'text' }
const WORDS: [string, Kind][] = [['general', 'general'], ['am/pm', 'ampm'], ['a/p', 'ampm']]
const PAD: Record<string, string> = { '0': '0', '?': ' ', '#': '' }

/** The sections of a code, split at the semicolons that are not quoted, escaped or in brackets. */
export function splitSections(code: string): string[] {
  const sections: string[] = []
  let current = ''
  let quoted = false
  let bracket = false
  for (let i = 0; i < code.length; i++) {
    const ch = code[i]!
    if (ch === '\\' && !quoted && i + 1 < code.length) {
      current += code.slice(i, i + 2)
      i++
      continue
    }
    if (ch === '"' && !bracket) quoted = !quoted
    else if (ch === '[' && !quoted) bracket = true
    else if (ch === ']' && !quoted) bracket = false
    if (ch === ';' && !quoted && !bracket) {
      sections.push(current)
      current = ''
    } else current += ch
  }
  sections.push(current)
  return sections
}

function bracket(inside: string, section: Section): void {
  const low = inside.toLowerCase()
  const condition = CONDITION.exec(inside.replace(/ /g, ''))
  if (COLOURS.has(low) || /^color\d{1,2}$/.test(low)) section.colour = low
  else if (condition) section.condition = [condition[1]!, Number(condition[2])]
  else if (inside.startsWith('$')) {
    const dash = inside.indexOf('-')
    const symbol = dash < 0 ? inside.slice(1) : inside.slice(1, dash)
    if (symbol) section.tokens.push({ kind: 'literal', text: symbol })
    section.locale = dash < 0 ? null : inside.slice(dash + 1).toUpperCase() || null
  } else if (/^[hms]+$/.test(low)) section.tokens.push({ kind: 'date', text: `[${low}]` })
}

/** One section read into tokens, as `parse_section` reads it. */
export function parseSection(text: string): Section {
  const section: Section = { tokens: [], colour: null, condition: null, locale: null }
  const push = (kind: Kind, t: string) => section.tokens.push({ kind, text: t })
  let i = 0
  while (i < text.length) {
    const ch = text[i]!
    if (ch === '[') {
      const end = text.indexOf(']', i)
      if (end < 0) {
        push('literal', text.slice(i))
        break
      }
      bracket(text.slice(i + 1, end), section)
      i = end + 1
      continue
    }
    if (ch === '"') {
      let end = text.indexOf('"', i + 1)
      if (end < 0) end = text.length
      push('literal', text.slice(i + 1, end))
      i = end + 1
      continue
    }
    if ('\\_*'.includes(ch) && i + 1 < text.length) {
      if (ch !== '*') push('literal', ch === '_' ? ' ' : text[i + 1]!)
      i += 2
      continue
    }
    const word = WORDS.find(([w]) => text.slice(i, i + w.length).toLowerCase() === w)
    if (word) {
      push(word[1], text.slice(i, i + word[0].length))
      i += word[0].length
      continue
    }
    if ('Ee'.includes(ch) && i + 1 < text.length && '+-'.includes(text[i + 1]!)) {
      push('exp', text.slice(i, i + 2))
      i += 2
      continue
    }
    if ('ymdhsegb'.includes(ch.toLowerCase())) {
      const run = DATE_RUN.exec(text.slice(i))
      if (run) {
        push('date', run[0])
        i += run[0].length
        continue
      }
    }
    push(SINGLE[ch] ?? 'literal', ch)
    i++
  }
  section.tokens = minutes(dateSlashes(section.tokens))
  return section
}

function dateSlashes(tokens: Token[]): Token[] {
  if (!tokens.some((t) => t.kind === 'date')) return tokens
  return tokens.map((t) => (t.kind === 'slash' ? { kind: 'literal', text: '/' } : t))
}

function minutes(tokens: Token[]): Token[] {
  const dated = tokens.flatMap((t, i) => (t.kind === 'date' ? [i] : []))
  const out = [...tokens]
  dated.forEach((index, place) => {
    const word = tokens[index]!.text.toLowerCase()
    if (word !== 'm' && word !== 'mm') return
    const before = place > 0 ? tokens[dated[place - 1]!]!.text.toLowerCase() : ''
    const after = place + 1 < dated.length ? tokens[dated[place + 1]!]!.text.toLowerCase() : ''
    if (before.startsWith('h') || before.startsWith('[h') || after.startsWith('s') || after.startsWith('[s'))
      out[index] = { kind: 'date', text: word === 'm' ? 'mi' : 'mmi' }
  })
  return out
}

const isDate = (s: Section) => s.tokens.some((t) => t.kind === 'date' || t.kind === 'ampm')

/** What a code shows: `general`, `date`, `time`, `percent`, `scientific`, `fraction`, `text` or `number`. */
export function kindOf(code: string): string {
  const first = parseSection(splitSections(code)[0]!)
  const kinds = new Set(first.tokens.map((t) => t.kind))
  if (code.trim().toLowerCase() === 'general' || (kinds.size === 1 && kinds.has('general'))) return 'general'
  if (isDate(first)) return first.tokens.some((t) => t.kind === 'date' && DAY_WORDS.has(t.text.toLowerCase())) ? 'date' : 'time'
  if (kinds.has('percent')) return 'percent'
  if (kinds.has('exp')) return 'scientific'
  if (kinds.has('slash')) return 'fraction'
  if ([...kinds].every((k) => k === 'text' || k === 'literal')) return 'text'
  return 'number'
}

/** A number the General way: up to 10 decimals, no thousands separator, the reader's decimal sign. */
export function general(n: number, symbols: NumberSymbols = ENGLISH): string {
  let text: string
  if (Number.isInteger(n) && Math.abs(n) < 1e15) text = String(n)
  else if (Math.abs(n) >= 1e15 || (n !== 0 && Math.abs(n) < 1e-9)) text = n.toExponential(5).toUpperCase().replace(/E([+-])/, 'E$1')
  else text = n.toFixed(10).replace(/0+$/, '').replace(/\.$/, '')
  return text.replace('.', symbols.decimal)
}

/** `value` with exactly `decimals` decimals, halves away from zero (from the shortest text of the number, as the
 * server rounds with `Decimal(repr(x))`). */
export function rounded(value: number, decimals: number): string {
  const [mantissa, exp = '0'] = String(value).toLowerCase().split('e')
  const [whole = '0', frac = ''] = mantissa!.split('.')
  let digits = whole + frac
  let point = whole.length + Number(exp)
  if (point < 0) {
    digits = '0'.repeat(-point) + digits
    point = 0
  }
  if (digits.length < point) digits = digits.padEnd(point, '0')
  const keep = point + decimals
  if (keep < 0) return decimals ? `0.${'0'.repeat(decimals)}` : '0'
  let kept = digits.slice(0, keep).padEnd(keep, '0')
  if ((digits[keep] ?? '0') >= '5') {
    kept = (BigInt(kept || '0') + 1n).toString().padStart(kept.length, '0')
  }
  const intPart = kept.slice(0, kept.length - decimals).replace(/^0+(?=\d)/, '') || '0'
  return decimals ? `${intPart}.${kept.slice(kept.length - decimals)}` : intPart
}

function matches([op, limit]: [string, number], n: number): boolean {
  return { '<': n < limit, '<=': n <= limit, '>': n > limit, '>=': n >= limit, '=': n === limit, '<>': n !== limit }[op] ?? false
}

function pick(n: number, sections: Section[]): [Section, boolean] {
  const numeric = sections.slice(0, 3)
  if (numeric.some((s) => s.condition)) {
    for (let i = 0; i < numeric.length; i++) {
      const s = numeric[i]!
      if (!s.condition || matches(s.condition, n)) return [s, i > 0 && n < 0]
    }
    return [numeric[numeric.length - 1]!, n < 0]
  }
  if (numeric.length >= 3 && n === 0) return [numeric[2]!, false]
  if (numeric.length >= 2 && n < 0) return [numeric[1]!, true]
  return [numeric[0]!, false]
}

function fillInteger(whole: string, places: string[], group: string): string {
  if (!places.length) return ''
  let digits = whole === '0' ? '' : whole
  if (digits.length < places.length) digits = places.slice(0, places.length - digits.length).map((k) => PAD[k]).join('') + digits
  if (!group) return digits
  const body = digits.trimStart()
  const lead = digits.length - body.length
  const parts: string[] = []
  let rest = body
  while (rest.length > 3) {
    parts.unshift(rest.slice(-3))
    rest = rest.slice(0, -3)
  }
  if (rest) parts.unshift(rest)
  return ' '.repeat(lead) + parts.join(group)
}

function spreadInteger(whole: string, places: string[]): string[] {
  if (!places.length) return []
  const digits = whole === '0' ? '' : whole
  const out = places.map((kind, i) => {
    const back = places.length - i
    return back <= digits.length ? digits[digits.length - back]! : PAD[kind]!
  })
  if (digits.length > places.length) out[0] = digits.slice(0, digits.length - places.length + 1)
  return out
}

function fillFraction(fraction: string, places: string[]): string[] {
  const chars = fraction.padEnd(places.length, '0').slice(0, places.length).split('')
  for (let i = places.length - 1; i >= 0; i--) {
    if (chars[i] !== '0' || places[i] === '0') break
    chars[i] = places[i] === '#' ? '' : ' '
  }
  return chars
}

function renderNumber(n: number, section: Section, symbols: NumberSymbols, keepSign: boolean): string {
  const tokens = section.tokens
  const kinds = tokens.map((t) => t.kind)
  if (kinds.includes('exp')) return renderScientific(n, tokens, symbols, keepSign)
  if (kinds.includes('slash')) return renderFraction(n, tokens, keepSign)
  const point = kinds.indexOf('point')
  const digitsAt = kinds.flatMap((k, i) => (k === 'digit' ? [i] : []))
  const intPlaces = digitsAt.filter((i) => point < 0 || i < point)
  const fracPlaces = digitsAt.filter((i) => point >= 0 && i > point)
  const lastDigit = digitsAt.length ? digitsAt[digitsAt.length - 1]! : -1
  const scale = kinds.filter((k, i) => k === 'group' && i > lastDigit && (point < 0 || i > point)).length
  const end = point >= 0 ? point : lastDigit + 1
  const grouped = kinds.some((k, i) => k === 'group' && intPlaces.length > 0 && intPlaces[0]! < i && i < end)
  const value = (n * 100 ** kinds.filter((k) => k === 'percent').length) / 1000 ** scale
  const text = rounded(Math.abs(value), fracPlaces.length)
  const [whole = '0', fraction = ''] = text.split('.')
  const negative = value < 0 && keepSign && digitsAt.length > 0 && /[1-9]/.test(text)
  const places = intPlaces.map((i) => tokens[i]!.text)
  const intParts = grouped ? [fillInteger(whole, places, symbols.group), ...places.slice(1).map(() => '')] : spreadInteger(whole, places)
  const fracText = fillFraction(fraction, fracPlaces.map((i) => tokens[i]!.text))
  let out = ''
  let intIndex = 0
  let fracIndex = 0
  tokens.forEach((token, i) => {
    if (intPlaces.includes(i)) out += intParts[intIndex++]
    else if (fracPlaces.includes(i)) out += fracText[fracIndex++]
    else if (token.kind === 'point') out += symbols.decimal
    else if (token.kind === 'literal' || token.kind === 'percent') out += token.text
  })
  return negative ? `-${out}` : out
}

function renderScientific(n: number, tokens: Token[], symbols: NumberSymbols, keepSign: boolean): string {
  const kinds = tokens.map((t) => t.kind)
  const expAt = kinds.indexOf('exp')
  const pointAt = kinds.slice(0, expAt).indexOf('point')
  const point = pointAt < 0 ? expAt : pointAt
  const intDigits = Math.max(1, kinds.slice(0, point).filter((k) => k === 'digit').length)
  const decimals = kinds.slice(point, expAt).filter((k) => k === 'digit').length
  const expDigits = kinds.slice(expAt + 1).filter((k) => k === 'digit').length
  let exponent = n === 0 ? 0 : Math.floor(Math.log10(Math.abs(n)))
  if (intDigits > 1) exponent -= ((exponent % intDigits) + intDigits) % intDigits
  let text = rounded(n ? Math.abs(n) / 10 ** exponent : 0, decimals)
  if (Number(text) >= 10 ** (intDigits > 1 ? intDigits : 1)) {
    exponent += intDigits
    text = rounded(Math.abs(n) / 10 ** exponent, decimals)
  }
  const mark = tokens[expAt]!.text
  const sign = exponent < 0 ? '-' : mark.endsWith('+') ? '+' : ''
  const shown = text.replace('.', symbols.decimal) + mark[0] + sign + String(Math.abs(exponent)).padStart(expDigits, '0')
  return n < 0 && keepSign ? `-${shown}` : shown
}

function limitDenominator(x: number, max: number): [number, number] {
  let best: [number, number] = [Math.round(x), 1]
  let error = Math.abs(x - best[0])
  for (let d = 1; d <= max; d++) {
    const num = Math.round(x * d)
    const e = Math.abs(x - num / d)
    if (e < error - 1e-12) {
      best = [num, d]
      error = e
    }
  }
  return best
}

function renderFraction(n: number, tokens: Token[], keepSign: boolean): string {
  const kinds = tokens.map((t) => t.kind)
  const slash = kinds.indexOf('slash')
  const after = tokens.slice(slash + 1).filter((t) => t.kind === 'digit')
  const fixed = after.map((t) => t.text).join('')
  const wholePart = tokens.slice(0, slash).some((t) => t.kind === 'literal' && t.text === ' ')
  const value = Math.abs(n)
  let whole = wholePart ? Math.floor(value) : 0
  const rest = value - whole
  let numerator: number
  let denominator: number
  if (/^\d+$/.test(fixed)) {
    denominator = Number(fixed)
    numerator = Math.round(rest * denominator)
  } else [numerator, denominator] = limitDenominator(rest, 10 ** after.length - 1)
  if (numerator === denominator && denominator) {
    whole += 1
    numerator = 0
  }
  const text = numerator === 0 ? (wholePart ? String(whole) : '0') : `${wholePart && whole ? `${whole} ` : ''}${numerator}/${denominator}`
  return n < 0 && keepSign ? `-${text}` : text
}

// -- dates
function partsOf(day: number): [number, number, number] {
  if (day === 0) return [1900, 1, 0]
  if (day === 60) return [1900, 2, 29]
  const d = new Date(Date.UTC(1899, 11, 31 + (day < 61 ? day : day - 1)))
  return [d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate()]
}

function secondDecimals(tokens: Token[]): number {
  for (let i = 1; i < tokens.length; i++) {
    const before = tokens[i - 1]!
    if (tokens[i]!.kind === 'point' && before.kind === 'date' && ['s', 'ss'].includes(before.text.toLowerCase()))
      return tokens.slice(i + 1).filter((t) => t.kind === 'digit').length
  }
  return 0
}

function renderDate(n: number, section: Section, symbols: NumberSymbols): string {
  const tokens = section.tokens
  const decimals = secondDecimals(tokens)
  let day = Math.floor(n)
  let seconds = Math.round((n - day) * 86400 * 1000) / 1000
  if (!decimals) seconds = Math.round(seconds)
  if (seconds >= 86400) {
    day += 1
    seconds -= 86400
  }
  const [year, month, date] = day >= 0 ? partsOf(day) : [1900, 1, 0]
  const hour = Math.floor(seconds / 3600)
  const minute = Math.floor((seconds % 3600) / 60)
  const second = Math.floor(seconds % 60)
  const twelve = tokens.some((t) => t.kind === 'ampm')
  const shownHour = twelve ? hour % 12 || 12 : hour
  const weekday = (((Math.floor(n) + 6) % 7) + 7) % 7
  const total = Math.round(n * 86400)
  const two = (x: number) => String(x).padStart(2, '0')
  const part = (word: string): string => {
    const low = word.toLowerCase()
    if (low.startsWith('[')) return String({ h: Math.floor(total / 3600), m: Math.floor(total / 60), s: total }[low[1] as 'h' | 'm' | 's']).padStart(low.length - 2, '0')
    const table: Record<string, string> = {
      yyyy: String(year), yyy: String(year), e: String(year), yy: two(year % 100), y: two(year % 100),
      mmmmm: symbols.months[month - 1]![0]!, mmmm: symbols.months[month - 1]!, mmm: symbols.monthsShort[month - 1]!,
      mm: two(month), m: String(month), dddd: symbols.days[weekday]!, ddd: symbols.daysShort[weekday]!,
      dd: two(date), d: String(date), hh: two(shownHour), h: String(shownHour), mmi: two(minute), mi: String(minute),
      ss: two(second), s: String(second),
    }
    return table[low] ?? word
  }
  let out = ''
  let afterPoint = false
  for (const token of tokens) {
    if (token.kind === 'date') out += part(token.text)
    else if (token.kind === 'ampm') {
      const am = hour < 12
      const shown = token.text.toUpperCase() === 'AM/PM' ? (am ? 'AM' : 'PM') : am ? 'A' : 'P'
      out += token.text[0] === token.text[0]!.toLowerCase() ? shown.toLowerCase() : shown
    } else if (token.kind === 'point' && decimals) {
      out += symbols.decimal + String(Math.round((seconds - Math.floor(seconds)) * 10 ** decimals)).padStart(decimals, '0')
      afterPoint = true
    } else if (token.kind !== 'digit') out += token.text
    else if (!afterPoint) out += ''
  }
  return out
}

/** `value` shown through `code` the way `symbols` writes it, with the colour the code asks for. */
export function render(value: number | string | boolean | null | undefined, code: string, symbols: NumberSymbols = ENGLISH): Rendered {
  if (value === null || value === undefined) return { text: '', colour: null }
  if (typeof value === 'boolean') return { text: value ? 'TRUE' : 'FALSE', colour: null }
  const sections = splitSections(code).map(parseSection)
  if (typeof value === 'string') {
    const section = sections.length >= 4 ? sections[3]! : sections.find((s) => s.tokens.some((t) => t.kind === 'text'))
    if (!section) return { text: value, colour: null }
    const text = section.tokens.map((t) => (t.kind === 'text' ? value : t.kind === 'literal' ? t.text : '')).join('')
    return { text, colour: section.colour }
  }
  const [picked, negate] = pick(value, sections)
  let section = picked
  if (section.tokens.length === 1 && section.tokens[0]!.kind === 'general') return { text: general(negate ? -value : value, symbols), colour: section.colour }
  if (code === SHORT_DATE) section = parseSection(symbols.shortDate)
  if (isDate(section)) {
    const names = LCID[section.locale ?? ''] ?? symbols
    const withNames = { ...symbols, months: names.months, monthsShort: names.monthsShort, days: names.days, daysShort: names.daysShort }
    return { text: renderDate(negate ? Math.abs(value) : value, section, withNames), colour: section.colour }
  }
  return { text: renderNumber(negate ? Math.abs(value) : value, section, symbols, !negate), colour: section.colour }
}
