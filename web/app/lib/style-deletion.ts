// Deleting and hiding a style, as the All styles dialog does it (E1.10, D226, D780–D785, `style-delete-and-hide.svg`).
//
// The server decides what a deletion does and says so beforehand (`style_deletion`); this file is what the page
// makes of that answer: the sentences the dialog shows before anything happens, which choices are on offer and which
// one is preselected, the access keys of the row actions, and the host that passes the three wire calls to the
// dialog. The wording is here and not in the component so that it is tested, and so that every sentence is a plain
// `t('…')` call the catalog extraction finds (a noun is never slotted into a sentence, see `noun-phrases.ts`).
import { translate as t } from './i18n'
import { usesCount } from './noun-phrases'
import type { Css, StyleView } from './style-css'

/** The two ways to delete a style, in the order the dialog offers them (D785). */
export type DeleteHow = 'assign' | 'rebase'
export const DELETE_HOWS: readonly DeleteHow[] = ['assign', 'rebase']

/** A style that could take the deleted one's place. */
export interface DeletionTarget {
  id: string
  name: string
  /** Whether assigning it changes how something looks. */
  changes_look: boolean
  /** Whether re-basing on it can keep every look; `reason` then says why not, in a sentence. */
  holds: boolean
  reason: string | null
}

/** What `style_deletion` answers. */
export interface StyleDeletion {
  style: string
  name: string
  /** A built-in or template style: it can only be hidden. */
  protected: boolean
  hidden: boolean
  /** How many places have the style itself. */
  uses: number
  /** The styles based on it. */
  children: { id: string; name: string }[]
  /** The plain style of its kind, which a dialog preselects: what "no style" means where everything has one. */
  suggested: { id: string; name: string } | null
  targets: DeletionTarget[]
}

/** What came of a deletion: the style (waiting for its name) that holds the look of what had the deleted one itself,
 * or null when none was needed; or the server's sentence for why it was refused (somebody began to use the style
 * meanwhile, a look could not be kept), which the dialog shows where the person is looking. Nothing changed then. */
export type Deleted = { standIn: string | null } | { refused: string }

/** The three wire calls of the All styles dialog, as a host offers them. A host that has none (read-only previews)
 * leaves `deletion` out of its `StyleHost`, and the dialog shows no Delete… and Hide. */
export interface StyleDeletionHost {
  preview(style: string): Promise<StyleDeletion | null>
  remove(style: string, how: DeleteHow, target: string | null): Promise<Deleted | null>
  hide(style: string, hidden: boolean): Promise<boolean>
  /** Take the last step back: what Undo beside the announcement does. */
  undo(): Promise<boolean>
}

/** The part of a session the dialog's host needs; every app's session has it (`BaseSession`). */
export interface StyleDeletionSession {
  styleDeletion(style: string): Promise<StyleDeletion | null>
  deleteStyle(style: string, how: DeleteHow, target: string | null): Promise<Deleted | false>
  hideStyle(style: string, hidden: boolean): Promise<boolean>
  undo(): Promise<boolean>
}

export function wasRefused(done: Deleted): done is { refused: string } {
  return 'refused' in done
}

/** The host's `deletion`: undefined for a session that cannot (a test double, an older one), so that the dialog then
 * offers no Delete… and Hide. */
export function deletionHost(session: Partial<StyleDeletionSession>): StyleDeletionHost | undefined {
  if (!session.styleDeletion || !session.deleteStyle || !session.hideStyle || !session.undo) return undefined
  const full = session as StyleDeletionSession
  return {
    preview: (style) => full.styleDeletion(style),
    remove: async (style, how, target) => (await full.deleteStyle(style, how, target)) || null,
    hide: (style, hidden) => full.hideStyle(style, hidden),
    undo: () => full.undo(),
  }
}

// ------------------------------------------------------------------------------------------------ the choice
/** What the person has picked in the Delete… dialog: a way, and for each way the style that takes the place. */
export class DeletionChoice {
  how: DeleteHow = 'assign'
  /** The style picked for each way; assigning starts on the plain style, re-basing on nothing (there is no default
   * base that would be right for everybody). */
  private picked: Record<DeleteHow, string | null>

  constructor(readonly deletion: StyleDeletion) {
    const suggested = deletion.suggested?.id
    this.picked = { assign: deletion.targets.some((x) => x.id === suggested) ? (suggested ?? null) : null, rebase: null }
  }

  /** Whether anything needs another style at all: a style nothing has and nothing is based on just goes. */
  get needsTarget(): boolean {
    return this.deletion.uses > 0 || this.deletion.children.length > 0
  }

  /** Whether a style can be picked for the way: any can for assigning, only those that keep the look for re-basing
   * (the others are shown, greyed, with their reason). */
  isOffered(target: DeletionTarget, how: DeleteHow = this.how): boolean {
    return how === 'assign' || target.holds
  }

  target(how: DeleteHow = this.how): DeletionTarget | undefined {
    const id = this.picked[how]
    return id ? this.deletion.targets.find((x) => x.id === id) : undefined
  }

  pick(how: DeleteHow, id: string | null) {
    this.picked[how] = id && this.deletion.targets.some((x) => x.id === id && this.isOffered(x, how)) ? id : null
    this.how = how
  }

  /** Ready to go: with something to move, a style that takes its place has to be chosen. */
  get ready(): boolean {
    return !this.needsTarget || this.target() !== undefined
  }

  /** What goes to the server. */
  get request(): { how: DeleteHow; target: string | null } {
    return { how: this.how, target: this.needsTarget ? (this.target()?.id ?? null) : null }
  }

  /** Whether the way chosen changes how something looks: only assigning can, and only when it does. */
  get looksChange(): boolean {
    return this.how === 'assign' && !!this.target()?.changes_look
  }
}

// ------------------------------------------------------------------------------------------------ sentences
/** "14 paragraphs have this style. 1 style is based on it: Small quote." — one line each, no noun slotted into a
 * sentence, so a translator can write each for its own grammar. */
export function usedByLine(noun: string, deletion: StyleDeletion): string {
  return deletion.uses === 0 ? t('Nothing has this style.') : t('Used by: {uses}', { uses: usesCount(noun, deletion.uses) })
}

export function basedOnLine(deletion: StyleDeletion): string {
  const names = deletion.children.map((c) => c.name).join(', ')
  if (!deletion.children.length) return ''
  return deletion.children.length === 1 ? t('Based on it: 1 style ({names})', { names }) : t('Based on it: {count} styles ({names})', { count: deletion.children.length, names })
}

/** The sentence that says what will look different, counting first: "Will look different: 14 paragraphs, 1 style". */
export function lookDifferentLine(noun: string, deletion: StyleDeletion): string {
  const parts: string[] = []
  if (deletion.uses) parts.push(usesCount(noun, deletion.uses))
  if (deletion.children.length) parts.push(deletion.children.length === 1 ? t('1 style') : t('{count} styles', { count: deletion.children.length }))
  return parts.length ? t('Will look different: {what}', { what: parts.join(', ') }) : ''
}

// What a style says, in words, for "what is lost"; a property the list does not know is called "other settings".
const LABELS: [match: (property: string) => boolean, label: () => string][] = [
  [(p) => p === 'font-style', () => t('italic')],
  [(p) => p === 'font-weight', () => t('bold')],
  [(p) => p === 'text-decoration', () => t('underline')],
  [(p) => p === 'font-family', () => t('font')],
  [(p) => p === 'font-size', () => t('size')],
  [(p) => p === 'color', () => t('colour')],
  [(p) => p === 'background-color' || p === 'fill', () => t('background')],
  [(p) => p.startsWith('margin') || p.startsWith('padding'), () => t('spacing')],
  [(p) => p.startsWith('border') || p === 'stroke' || p === 'stroke-width', () => t('border')],
  [(p) => p === 'text-align', () => t('alignment')],
  [(p) => p === 'line-height', () => t('line height')],
]

/** In what the two looks differ, as a short list of words: "italic, spacing". Empty when they do not. */
export function lookDifference(from: Css, to: Css): string[] {
  const found: string[] = []
  let other = false
  for (const property of new Set([...Object.keys(from), ...Object.keys(to)])) {
    if (from[property] === to[property]) continue
    const label = LABELS.find(([match]) => match(property))?.[1]()
    if (!label) other = true
    else if (!found.includes(label)) found.push(label)
  }
  if (other) found.push(t('other settings'))
  return found
}

/** The line under the picked style when assigning: what the new style would not have of the old one's look. */
export function lookLostLine(from: StyleView | undefined, to: StyleView | undefined): string {
  if (!from || !to) return ''
  const words = lookDifference(from.resolved, to.resolved)
  return words.length ? t('What differs: {what}', { what: words.join(', ') }) : ''
}

/** The announcement after a deletion (`style-delete-and-hide.svg`, D): what went, and where what had it is now. */
export function deletedLine(name: string, how: DeleteHow, standIn: string | null, target: string | undefined): string {
  if (how === 'rebase' && standIn) return t('“{name}” deleted. What had it now has “{standIn}”, built on “{target}”.', { name, standIn, target: target ?? '' })
  return target ? t('“{name}” deleted. What had it now has “{target}”.', { name, target }) : t('“{name}” deleted.', { name })
}

// ------------------------------------------------------------------------------------------------ hidden styles
/** The styles a person picks from (a gallery, the apply menu): the hidden ones are left out, unless the selection has
 * one — a style that is applied must not vanish from where it is chosen (D780). */
export function pickable(styles: StyleView[], current?: string): StyleView[] {
  return styles.filter((s) => !s.hidden || s.id === current)
}

// ------------------------------------------------------------------------------------------------ access keys
/** What a row of the All styles list can do, by the order they appear in. */
export type RowAction = 'edit' | 'rename' | 'delete' | 'hide' | 'show'

/** The access key of a label: its first letter, lower case, so that translated labels bring their own keys (Alt+D
 * for “Delete…”, Alt+L for “Löschen…”). The labels of one row never share a first letter in English or German. */
export function accessKeyOf(label: string): string {
  return (label.match(/\p{L}/u)?.[0] ?? '').toLocaleLowerCase()
}

/** The action of a row that a key press means: `key` with Alt held, among the labels the row has. */
export function actionForKey(key: string, labels: Partial<Record<RowAction, string>>): RowAction | undefined {
  const wanted = key.toLocaleLowerCase()
  if (wanted.length !== 1) return undefined
  return (Object.keys(labels) as RowAction[]).find((action) => accessKeyOf(labels[action] ?? '') === wanted)
}

/** A label split around its access key, for the letter to be underlined: “Delete…” is `{ head: '', key: 'D', tail:
 * 'elete…' }`. A label with no letter has no key. */
export function mnemonic(label: string): { head: string; key: string; tail: string } {
  const at = label.search(/\p{L}/u)
  if (at < 0) return { head: label, key: '', tail: '' }
  const key = String.fromCodePoint(label.codePointAt(at) ?? 0)
  return { head: label.slice(0, at), key, tail: label.slice(at + key.length) }
}
