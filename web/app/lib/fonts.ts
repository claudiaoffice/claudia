// The fonts the style menu offers. For now this is a fixed list: the suite's own fonts (design system) and the common
// system ones. Fonts are named, never loaded from anywhere (D26); the font service (E3.3) will say what a server has.
import type { Css } from './style-css'

export interface FontChoice {
  /** What the person sees, and what `font-family` starts with. */
  name: string
  /** The value of `font-family` that is written into the style: the font and what to fall back to. */
  stack: string
  kind: 'suite' | 'serif' | 'sans' | 'mono' | 'generic'
}

export const FONTS: FontChoice[] = [
  { name: 'Inter', stack: "Inter, system-ui, 'Segoe UI', sans-serif", kind: 'suite' },
  { name: 'Fraunces', stack: 'Fraunces, Georgia, serif', kind: 'suite' },
  { name: 'JetBrains Mono', stack: "'JetBrains Mono', ui-monospace, 'Cascadia Mono', monospace", kind: 'suite' },
  { name: 'Georgia', stack: 'Georgia, serif', kind: 'serif' },
  { name: 'Times New Roman', stack: "'Times New Roman', Times, serif", kind: 'serif' },
  { name: 'Arial', stack: 'Arial, Helvetica, sans-serif', kind: 'sans' },
  { name: 'Helvetica', stack: 'Helvetica, Arial, sans-serif', kind: 'sans' },
  { name: 'Verdana', stack: 'Verdana, Geneva, sans-serif', kind: 'sans' },
  { name: 'Trebuchet MS', stack: "'Trebuchet MS', sans-serif", kind: 'sans' },
  { name: 'Courier New', stack: "'Courier New', Courier, monospace", kind: 'mono' },
  { name: 'system-ui', stack: "system-ui, -apple-system, 'Segoe UI', sans-serif", kind: 'generic' },
  { name: 'serif', stack: 'serif', kind: 'generic' },
  { name: 'sans-serif', stack: 'sans-serif', kind: 'generic' },
  { name: 'monospace', stack: 'monospace', kind: 'generic' },
]

/** The choice a `font-family` value starts with, if it is one of ours. */
export function choiceOf(css: Css): FontChoice | undefined {
  const first = (css['font-family'] ?? '').split(',')[0]?.trim().replace(/^['"]|['"]$/g, '').toLowerCase()
  return FONTS.find((f) => f.name.toLowerCase() === first)
}

/** The `font-family` value for a name the person typed: quoted if it has spaces, with a generic family to fall back on. */
export function stackFor(typed: string): string {
  const known = FONTS.find((f) => f.name.toLowerCase() === typed.trim().toLowerCase())
  if (known) return known.stack
  const name = typed.trim().replace(/['"]/g, '')
  return /\s/.test(name) ? `'${name}', sans-serif` : `${name}, sans-serif`
}
