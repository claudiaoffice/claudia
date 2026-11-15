// What the search panel needs from a presentation (E10.19, D281): the `SearchHost` of creates. A place in a presentation
// is the words, the label or the description of an object, `{ slide, object, source }` (`source` is `box`, `label` or
// `description`), or the speaker notes of a slide, `{ slide, source: 'notes' }` (CODE-18): only this file reads it. The
// slide draws what was found in the words of its objects (`SlideCanvas.vue`); a match anywhere else takes the person to
// the slide (and to the notes, which are shown for it).
import type { SlideSession } from './slide-session'
import type { Kinds, SearchHost, SearchMatch, SearchPlace, SearchSwitch } from './search'
import { lookOnly } from './replay'

type Translate = (msgid: string, vars?: Record<string, string | number>) => string

export type SlideScopeId = 'all' | 'slide'

/** What creates can be searched in: the words on the slides, the labels of shapes, speaker notes and descriptions. */
const SWITCHES: SearchSwitch[] = ['text', 'label', 'notes', 'description'].map((key) => ({
  key,
  matchKind: key,
  replaceable: true,
  whileReplacing: true,
}))
const ALL_KINDS = SWITCHES.map((s) => s.key)
const chosen = (kinds: Kinds) => ALL_KINDS.filter((k) => kinds[k])

/** The slide a place is on. */
export function slideOf(at: SearchPlace): string {
  if (typeof at.slide !== 'string') throw new Error(`not a place in a presentation: ${JSON.stringify(at)}`)
  return at.slide
}

const isNotes = (at: SearchPlace) => at.source === 'notes'

/** What the slide draws for a search: a stretch of the words of an object, and whether it is the match being looked at. */
export interface SlideMark {
  object: string
  start: number
  end: number
  current: boolean
}

/** The stretches of the words of the objects on `slide` that the matches are in (descriptions and notes are not drawn
 *  on the slide); `current` is the index in `matches` of the match being looked at. */
export function marksFor(matches: SearchMatch[], current: number | null, slide: string): SlideMark[] {
  const marks: SlideMark[] = []
  matches.forEach((m, index) => {
    if (m.at.slide !== slide || typeof m.at.object !== 'string' || m.at.source === 'description') return
    marks.push({ object: m.at.object, start: m.start, end: m.end, current: index === current })
  })
  return marks
}

export function slideSearchHost(from: {
  session: SlideSession
  /** Show the speaker notes (they may be hidden) for a match in them. */
  showNotes: () => void
  t: Translate
}): SearchHost<Record<string, unknown>> {
  const { session, t } = from
  const state = session.state
  const number = (slide: string) => state.slides.findIndex((s) => s.id === slide) + 1
  return {
    get readonly() {
      return lookOnly(state)
    },
    unit: 'text',
    switches: SWITCHES,
    scopes: ['all', 'slide'] satisfies SlideScopeId[],
    helpTopic: 'creates.searching-and-replacing',
    extraParts: ['word'],
    scopeLabel: (scope) => (scope === 'all' ? t('All slides') : t('This slide')),
    scopeOf: (scope) => (scope === 'slide' && state.activeSlide ? { slide: state.activeSlide } : {}),
    find: (query, scope) => session.searchFind(query, ALL_KINDS, scope),
    preview: (query, kinds, scope, leave) => session.searchPreview(query, chosen(kinds), scope, leave),
    replace: (query, kinds, scope, leave) => session.searchReplace(query, chosen(kinds), scope, leave),
    keyOf: (at) => (isNotes(at) ? `${slideOf(at)}/notes` : `${slideOf(at)}/${at.object}/${at.source}`),
    where(at) {
      const n = number(slideOf(at))
      if (isNotes(at)) return t('Speaker notes of slide {n}', { n })
      return at.source === 'description' ? t('Description of an object on slide {n}', { n }) : t('Object on slide {n}', { n })
    },
    jump(at) {
      void session.showSlide(slideOf(at)).then(() => {
        if (isNotes(at)) from.showNotes()
      })
    },
    revision: () => state.revision,
  }
}

/** A piece of the words of an object, and how a search marks it. */
export interface Piece {
  text: string
  found: 'match' | 'current' | null
}

/** The words cut where the marks begin and end: the pieces joined are the words again. Marks that overlap or lie outside
 *  the words are fitted to them (a stale mark must not break the slide). */
export function piecesOf(words: string, marks: readonly Pick<SlideMark, 'start' | 'end' | 'current'>[]): Piece[] {
  const pieces: Piece[] = []
  let at = 0
  for (const m of [...marks].sort((a, b) => a.start - b.start)) {
    const start = Math.max(at, Math.min(m.start, words.length))
    const end = Math.max(start, Math.min(m.end, words.length))
    if (end === start) continue
    if (start > at) pieces.push({ text: words.slice(at, start), found: null })
    pieces.push({ text: words.slice(start, end), found: m.current ? 'current' : 'match' })
    at = end
  }
  if (at < words.length || pieces.length === 0) pieces.push({ text: words.slice(at), found: null })
  return pieces
}
