// What an object says to someone who cannot see it (BITV 1.1.1): its description, or the mark that it is only
// decoration. Mirrors `claudia_core.ObjectBody.description`/`decorative` and the `describe_object` method; the same in
// all three apps, so the accessible names, the dialog's checks and the alt text of a picture are written once.

import { translate as t } from './i18n'
import type { ImageImport } from './images'
import type { ShortcutDef } from './shortcuts'

/** `claudia_core.MAX_ALT_CHARS`: a description is at most this long. */
export const MAX_DESCRIPTION = 300

/** The part of an object these functions read (an object of any app has it). */
export interface Describable {
  kind: 'text' | 'shape' | 'image' | 'diagram'
  description: string
  decorative: boolean
  imported: Pick<ImageImport, 'alt'> | null
}

/** What the dialog finds wrong with a description, as a code it puts into words (`null`: nothing). */
export type DescriptionProblem = 'empty' | 'too-long' | 'decorative-with-words'

/** The picture's alt text: its description, nothing for a decoration (so that a screen reader skips it), and what it was
 * imported with if the server sent no description (one that predates them). */
export function pictureAlt(o: Describable): string {
  if (o.decorative) return ''
  return o.description ?? o.imported?.alt ?? ''
}

/** Has the object been described, or marked as decoration? (What an accessibility check will look for.) */
export function isDescribed(o: Describable): boolean {
  return o.decorative || (pictureAlt(o).trim() !== '')
}

/** What a screen reader says for an object: its kind, then its description, or its words if it has no description;
 * a decoration says so, and a picture or a chart that is not described says that, instead of an empty name. */
export function objectName(o: Describable, parts: { shape?: string; words?: string } = {}): string {
  const kind = o.kind === 'image' ? t('Picture') : o.kind === 'diagram' ? t('Chart') : o.kind === 'text' ? t('Text box') : (parts.shape ?? t('Shape'))
  if (o.decorative) return t('{kind} (decorative)', { kind })
  const said = pictureAlt(o).trim() || (o.kind === 'image' || o.kind === 'diagram' ? '' : (parts.words ?? '').trim())
  if (said) return t('{kind}: {words}', { kind, words: said })
  return o.kind === 'image' || o.kind === 'diagram' ? t('{kind} (no description)', { kind }) : kind
}

/** What is wrong with this description for an object of `kind`: a picture needs words or the decorative mark, any other
 * object may go without; a description is short; a decoration has none. */
export function descriptionProblem(kind: Describable['kind'], text: string, decorative: boolean): DescriptionProblem | null {
  if (decorative) return text.trim() === '' ? null : 'decorative-with-words'
  if (text.length > MAX_DESCRIPTION) return 'too-long'
  return kind === 'image' && text.trim() === '' ? 'empty' : null
}

/** The parameters of `describe_object`: a decoration is sent with no words, whatever was typed before it was ticked. */
export function describeParams(text: string, decorative: boolean): { description: string; decorative: boolean } {
  return { description: decorative ? '' : text.trim(), decorative }
}

/** Format ▸ Describe Object…, Ctrl+Alt+D, the same key in every app (and the shells' `format.describe`). */
export function describeShortcut(run: () => void, enabled: () => boolean): ShortcutDef {
  return { id: 'format.describe', get label() { return t('Describe Object…') }, chord: { key: 'd', code: 'KeyD', ctrl: true, alt: true }, run, enabled }
}

/** The object a keyboard user reaches by stepping through the floating objects (Ctrl+Alt+PageDown / PageUp), in the
 * order given and wrapping round: objects are otherwise reached only by the mouse. `null` where there are none. */
export function cycleObject(ids: string[], current: string | null, step: 1 | -1): string | null {
  if (ids.length === 0) return null
  const at = current === null ? -1 : ids.indexOf(current)
  if (at < 0) return step === 1 ? ids[0]! : ids[ids.length - 1]!
  return ids[(at + step + ids.length) % ids.length]!
}
