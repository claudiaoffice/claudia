// The document's colour roles, on the client (D200–D202).
//
// A style names a colour by what it *means* — `@accent`, or `@accent/55` for that role at 55% opacity — and the
// server turns those into colours before any CSS reaches a browser. What a client still needs is the vocabulary:
// to read a value back as the role it names, to show a person the role's name instead of a hex, and to say in
// plain words what a contrast reading means for them.
//
// Not to be confused with `palette.ts`, which is the *app's* own brand swatches in the colour picker. This file is
// about the palette a document carries.
import type { ColourRole, Reading } from './objects'

export type { ColourRole, Reading } from './objects'

/** A value that names a role: its id, and the opacity if it was given one. */
export interface RoleRef {
  role: string
  opacity: number | null
}

const ROLE = /^@([a-z0-9][a-z0-9-]{0,39})(?:\/([1-9][0-9]?|100))?$/

/** The role a value names, or `null` for a literal colour. The same grammar the server accepts. */
export function roleIn(value: string | undefined): RoleRef | null {
  const match = ROLE.exec((value ?? '').trim())
  if (!match) return null
  return { role: match[1]!, opacity: match[2] === undefined ? null : Number(match[2]) }
}

/** The value a style stores for a role, with an opacity when one is wanted: `@accent`, `@accent/55`. */
export function roleValue(role: string, opacity: number | null = null): string {
  return opacity === null || opacity >= 100 ? `@${role}` : `@${role}/${opacity}`
}

/** What to call a value in the interface: the role's name, or the colour itself when it is off the palette. */
export function nameOf(value: string | undefined, roles: ColourRole[]): string {
  const named = roleIn(value)
  if (!named) return (value ?? '').trim() || 'None'
  const role = roles.find((r) => r.id === named.role)
  const label = role?.name ?? named.role
  return named.opacity === null ? label : `${label} at ${named.opacity}%`
}

/** The colour to paint a swatch with: a role resolved from the palette, or the literal as given. */
export function swatchFor(value: string | undefined, roles: ColourRole[]): string {
  const named = roleIn(value)
  if (!named) return (value ?? '').trim()
  const role = roles.find((r) => r.id === named.role)
  if (!role) return 'transparent'
  if (named.opacity === null) return role.colour
  // `color-mix` rather than an alpha, so a swatch on any background shows what the wash will really look like.
  return `color-mix(in srgb, ${role.colour} ${named.opacity}%, transparent)`
}

/**
 * Is this value off the palette: a colour of its own, where the document has roles to choose from?
 *
 * This is the deviation the mock warns about — not an error, and never blocked (D202). It simply means a palette
 * change will leave this one colour behind.
 */
export function offPalette(value: string | undefined, roles: ColourRole[]): boolean {
  const text = (value ?? '').trim()
  if (!text || text === 'none' || text === 'transparent') return false
  return roles.length > 0 && roleIn(text) === null
}

/** The role whose colour is nearest this literal, for the one click that adopts it. */
export function nearestRole(value: string | undefined, roles: ColourRole[]): ColourRole | null {
  const mine = rgbOf(value)
  if (!mine || roles.length === 0) return null
  let best: ColourRole | null = null
  let bestDistance = Infinity
  for (const role of roles) {
    const theirs = rgbOf(role.colour)
    if (!theirs) continue
    const distance = Math.hypot(mine[0] - theirs[0], mine[1] - theirs[1], mine[2] - theirs[2])
    if (distance < bestDistance) [best, bestDistance] = [role, distance]
  }
  return best
}

/**
 * A colour as red, green, blue and opacity: `#rgb`, `#rrggbb`, `rgb(...)` or `rgba(...)`.
 *
 * The opacity matters for contrast. A shape's fill is `@accent/14`, which resolves to `rgba(91, 75, 196, 0.14)`;
 * reading that as full-strength iris and checking the words against *it* said they would be hard to read on a
 * background that is in fact almost the colour of the page. A warning that fires on a brand-new shape is how a
 * warning teaches people to ignore warnings.
 */
export function colourOf(value: string | undefined): [number, number, number, number] | null {
  const text = (value ?? '').trim()
  const plain = rgbOf(text)
  if (plain) return [...plain, 1]
  const func = /rgba?\(([^)]*)\)/i.exec(text)
  if (!func) return null
  const parts = func[1]!.split(',').map((p) => Number(p.trim()))
  if (parts.length < 3 || parts.slice(0, 3).some((n) => !Number.isFinite(n))) return null
  const alpha = parts.length > 3 && Number.isFinite(parts[3]!) ? Math.min(1, Math.max(0, parts[3]!)) : 1
  return [parts[0]!, parts[1]!, parts[2]!, alpha]
}

/** `value` laid over `behind`, as `#rrggbb`: what a translucent colour really looks like where it sits. */
export function flatten(value: string | undefined, behind: string | undefined): string | null {
  const near = colourOf(value)
  if (!near) return null
  const [red, green, blue, alpha] = near
  if (alpha >= 1) return hex(red, green, blue)
  const far = colourOf(behind) ?? [255, 255, 255, 1]
  const mixed = [red, green, blue].map((channel, i) => alpha * channel + (1 - alpha) * far[i]!)
  return hex(mixed[0]!, mixed[1]!, mixed[2]!)
}

function hex(red: number, green: number, blue: number): string {
  const two = (n: number) =>
    Math.round(Math.min(255, Math.max(0, n)))
      .toString(16)
      .padStart(2, '0')
  return `#${two(red)}${two(green)}${two(blue)}`
}

/** `#rgb` or `#rrggbb` as red, green and blue; `null` for anything else. */
export function rgbOf(value: string | undefined): [number, number, number] | null {
  const text = (value ?? '').trim().replace(/^#/, '')
  const full = text.length === 3 ? [...text].map((c) => c + c).join('') : text
  if (!/^[0-9a-f]{6}$/i.test(full)) return null
  return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16)) as [number, number, number]
}

/** WCAG relative luminance of a hexadecimal colour. */
export function luminance(value: string): number {
  const rgb = rgbOf(value) ?? [0, 0, 0]
  const linear = rgb.map((channel) => {
    const unit = channel / 255
    return unit <= 0.03928 ? unit / 12.92 : Math.pow((unit + 0.055) / 1.055, 2.4)
  })
  return 0.2126 * linear[0]! + 0.7152 * linear[1]! + 0.0722 * linear[2]!
}

/** The contrast ratio between two hexadecimal colours: 1 for the same colour, 21 at most. */
export function contrast(one: string, other: string): number {
  const [a, b] = [luminance(one), luminance(other)]
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

/** Can words in `ink` be read on `behind`? The real WCAG floor; what is *said* about it is below. */
export function readable(ink: string, behind: string): boolean {
  return contrast(ink, behind) >= 4.5
}

/**
 * What a failing reading means, in words a person can act on — never the ratio (D202).
 *
 * A figure tells a reader nothing about whether they can read the page, which is the whole point: the server sends
 * the numbers so that a client can decide *whether* to warn, and each client says what it means in its own words.
 */
export function troubleWith(reading: Reading, roles: ColourRole[]): string | null {
  if (reading.ok) return null
  const fore = roles.find((r) => r.id === reading.foreground)?.name ?? reading.foreground
  const back = roles.find((r) => r.id === reading.background)?.name ?? reading.background
  return reading.words
    ? `${fore} on ${back} will be hard to read.`
    : `${fore} will be hard to make out against ${back}.`
}

/** Every reading that fails, worst first — what a palette dialog shows after a change. */
export function troubles(readings: Reading[]): Reading[] {
  return readings.filter((r) => !r.ok).sort((a, b) => a.ratio - b.ratio)
}
