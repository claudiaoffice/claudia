// What the search panel needs from a workbook (E5.15, D282): the `SearchHost` of computes. The panel is one component
// for all three apps; each app gives it a host that says what can be searched, where, how to name a match and how to
// get to it. Everything else — the builder, the sentence, the lists — is shared (`lib/search.ts`, `SearchPanel.vue`).
import { bounds, type Sel } from './selection'
import type { Session, SearchLeave, SearchScope } from './session'
import { whereLabel, type Kinds, type PartWhat, type PreviewAnswer, type ReplaceAnswer, type SearchAnswer, type SearchQuery } from './search'

export type ScopeId = 'sheet' | 'all' | 'selection'

export interface SearchHost {
  /** Can only look: Replace is off. */
  readonly readonly: boolean
  /** What can be looked in, and where. */
  readonly kinds: (keyof Kinds)[]
  readonly scopes: ScopeId[]
  /** Parts of the builder that only this app has (a cell reference). */
  readonly extraParts: PartWhat[]
  /** The scope as the server wants it. */
  scopeOf(scope: ScopeId): SearchScope
  /** Looks in every kind; which are shown is the panel's choice. `null`: no answer. */
  find(query: SearchQuery, scope: SearchScope): Promise<SearchAnswer | null>
  preview(query: SearchQuery, kinds: Kinds, scope: SearchScope, leave: SearchLeave[]): Promise<PreviewAnswer | null>
  replace(query: SearchQuery, kinds: Kinds, scope: SearchScope, leave: SearchLeave[]): Promise<ReplaceAnswer | false>
  /** `Costs!B2`. */
  where(match: { sheet: string; row: number; col: number }): string
  /** Show the match in the document. */
  jump(match: { sheet: string; row: number; col: number }): void
  /** Changes when the document does, so that a search that is showing can run again. */
  revision(): string | null
}

const ALL_KINDS: (keyof Kinds)[] = ['text', 'formulas', 'values']
const chosen = (kinds: Kinds) => ALL_KINDS.filter((k) => kinds[k])

export function sheetSearchHost(from: {
  session: Session
  selection: () => Sel
  goTo: (sheet: string, row: number, col: number) => void
}): SearchHost {
  const { session } = from
  const state = session.state
  return {
    get readonly() {
      return state.me.role === 'viewer'
    },
    kinds: ALL_KINDS,
    scopes: ['sheet', 'all', 'selection'],
    extraParts: ['cellref'],
    scopeOf(scope) {
      if (scope === 'all') return {}
      if (scope === 'sheet') return { sheet: state.activeSheet }
      const b = bounds(from.selection())
      return { sheet: state.activeSheet, range: [b.r0, b.c0, b.r1, b.c1] }
    },
    find: (query, scope) => session.searchFind(query, ALL_KINDS, scope),
    preview: (query, kinds, scope, leave) => session.searchPreview(query, chosen(kinds), scope, leave),
    replace: (query, kinds, scope, leave) => session.searchReplace(query, chosen(kinds), scope, leave),
    where: (match) => whereLabel(match, (id) => state.sheets.find((s) => s.id === id)?.name ?? id),
    jump: (match) => from.goTo(match.sheet, match.row, match.col),
    revision: () => state.revision,
  }
}
