// What the search panel needs from a text (E9.28, D282): the `SearchHost` of composes. A place in a text is a paragraph,
// `{ block }` (with `offset` when only the part of it from there on was searched, a selection's first or last paragraph),
// or an object that hangs from one, `{ block, object, source }` (CODE-18): only this file reads it. The text draws what
// was found in the paragraphs (`TextEditor.vue`); an object is not drawn in the editor, so a match in one takes the
// person to the paragraph it hangs from.
import type { TextSession } from './text-session'
import type { Kinds, SearchHost, SearchMatch, SearchPlace, SearchSwitch } from './search'

type Translate = (msgid: string, vars?: Record<string, string | number>) => string

export type TextScopeId = 'all' | 'section' | 'selection'

/** What composes can be searched in: paragraphs by their style, and what objects floating over the text say. */
const SWITCHES: SearchSwitch[] = ['text', 'heading', 'remark', 'object', 'description'].map((key) => ({
  key,
  matchKind: key,
  replaceable: true,
  whileReplacing: true,
}))
const ALL_KINDS = SWITCHES.map((s) => s.key)
const chosen = (kinds: Kinds) => ALL_KINDS.filter((k) => kinds[k])

/** The paragraph a place is in, and where in it if the place says (`offset`). */
export function blockOf(at: SearchPlace): { block: string; offset: number } {
  if (typeof at.block !== 'string') throw new Error(`not a place in a text: ${JSON.stringify(at)}`)
  return { block: at.block, offset: typeof at.offset === 'number' ? at.offset : 0 }
}

const isObject = (at: SearchPlace) => typeof at.object === 'string'

/** What the editor draws for a search: a stretch of a paragraph, and whether it is the match being looked at. */
export interface TextMark {
  block: string
  start: number
  end: number
  current: boolean
}

/** The stretches of paragraphs the matches are in (an object's words are not in the editor); `current` is the index in
 *  `matches` of the match being looked at. */
export function marksFor(matches: SearchMatch[], current: number | null): TextMark[] {
  const marks: TextMark[] = []
  matches.forEach((m, index) => {
    if (isObject(m.at)) return
    const { block, offset } = blockOf(m.at)
    marks.push({ block, start: offset + m.start, end: offset + m.end, current: index === current })
  })
  return marks
}

export function textSearchHost(from: {
  session: TextSession
  /** Show a paragraph (and so the matches in it). */
  goTo: (block: string) => void
  t: Translate
}): SearchHost<Record<string, unknown>> {
  const { session, t } = from
  const state = session.state
  const number = (block: string) => state.blocks.findIndex((b) => b.id === block) + 1
  /** The selection as the server reads it: from the earlier end to the later one; `null` when it is only a caret. */
  const selection = () => {
    const sel = state.selection
    if (!sel) return null
    const order = (p: { block: string; offset: number }) => [state.blocks.findIndex((b) => b.id === p.block), p.offset]
    const [a, b] = [order(sel.anchor), order(sel.focus)]
    const forward = a[0]! < b[0]! || (a[0] === b[0] && a[1]! <= b[1]!)
    const [from_, to] = forward ? [sel.anchor, sel.focus] : [sel.focus, sel.anchor]
    return from_.block === to.block && from_.offset === to.offset ? null : { from: { ...from_ }, to: { ...to } }
  }
  return {
    get readonly() {
      return state.me.role === 'viewer'
    },
    unit: 'text',
    switches: SWITCHES,
    scopes: ['all', 'section', 'selection'] satisfies TextScopeId[],
    extraParts: ['word'],
    scopeLabel: (scope) => (scope === 'all' ? t('The whole text') : scope === 'section' ? t('This section') : t('Selection')),
    scopeOf(scope) {
      if (scope === 'section') {
        const here = state.selection?.focus.block ?? state.blocks[0]?.id
        return here ? { section: here } : {}
      }
      const range = scope === 'selection' ? selection() : null
      return range ? { range } : {}
    },
    find: (query, scope) => session.searchFind(query, ALL_KINDS, scope),
    preview: (query, kinds, scope, leave) => session.searchPreview(query, chosen(kinds), scope, leave),
    replace: (query, kinds, scope, leave) => session.searchReplace(query, chosen(kinds), scope, leave),
    keyOf: (at) => (isObject(at) ? `${at.block}/${at.object}/${at.source}` : `${blockOf(at).block}:${blockOf(at).offset}`),
    where(at) {
      const n = number(blockOf(at).block)
      if (!isObject(at)) return t('Paragraph {n}', { n })
      return at.source === 'description' ? t('Description of an object in paragraph {n}', { n }) : t('Object in paragraph {n}', { n })
    },
    jump: (at) => from.goTo(blockOf(at).block),
    revision: () => state.revision,
  }
}
