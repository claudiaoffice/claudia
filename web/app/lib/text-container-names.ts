// What a screen reader says for a container floating in a text (BITV 1.1.1): its description, or what it is made of.
import { pictureAlt, type Describable } from './descriptions'

type Translate = (msgid: string, vars?: Record<string, string | number>) => string

/** The name of a container: "LaTeX container: <description>", or without a description the type alone. */
export function descriptionOf(object: Partial<Pick<Describable, 'description' | 'decorative' | 'imported'>>, type: string, t: Translate): string {
  const said = pictureAlt({ kind: 'container', description: '', decorative: false, imported: null, ...object }).trim()
  return said ? t('{type} container: {words}', { type, words: said }) : t('{type} container (no description)', { type })
}
