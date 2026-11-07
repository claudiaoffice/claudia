// Who is who on screen: a colour for every participant, and text that is readable on it.
import type { BaseState } from './base-session'
import { currentLocale } from './locale'

export const IRIS = '#5b4bc4'
const GREY = '#8a8697'

export function colorOf(state: Pick<BaseState, 'me' | 'people'>, user: string): string {
  if (user.toLowerCase() === 'ai') return IRIS
  if (user === state.me.user) return state.me.color || GREY
  return state.people.find((p) => p.user === user)?.color ?? GREY
}

/** White on dark colours, ink on light ones (apricot is light). */
export function inkOn(hex: string): string {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex)
  if (!m) return '#ffffff'
  const [r, g, b] = [m[1]!, m[2]!, m[3]!].map((x) => parseInt(x, 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  const luminance = 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
  return luminance > 0.4 ? '#1f1a33' : '#ffffff'
}

export function initial(name: string): string {
  return (name.trim()[0] ?? '?').toUpperCase()
}

/** `14:03:12` in the person's own clock, from the server's UTC time.
 *
 * `locale` defaults to the app's own negotiated locale (E5.7), not the runtime's implicit default: with no argument,
 * `toLocaleTimeString` follows whatever the *browser* is set to, which can silently disagree with what the person
 * picked in Claudia itself. */
export function clock(iso: string, locale: string = currentLocale()): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}

/** `just now`, `5 min ago`, `yesterday`, or the date. `locale` — see `clock` above for why it is not left implicit. */
export function ago(iso: string, now = Date.now(), locale: string = currentLocale()): string {
  const seconds = Math.round((now - new Date(iso).getTime()) / 1000)
  if (Number.isNaN(seconds)) return ''
  if (seconds < 45) return 'just now'
  if (seconds < 3600) return `${Math.round(seconds / 60)} min ago`
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h ago`
  if (seconds < 172800) return 'yesterday'
  return new Date(iso).toLocaleDateString(locale)
}
