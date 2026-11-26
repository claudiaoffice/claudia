// A workspace's menus, live (D1644): its handlers and what is true now, assembled from the definition of its app each
// time either changes. The trial's policy is read from the page's address once (D1647).
import { computed, type ComputedRef } from 'vue'
import type { Facts, Thing } from '../fits/facts'
import { DEFAULT_POLICY, policyFromAddress } from '../fits/policy'
import { useI18n } from '../i18n'
import { roleNow } from '../replay'
import type { BaseState } from '../base-session'
import { DEFINITIONS, type AppName } from '../menus.generated'
import { assembleMenus, handlerGaps, type AssembledMenus, type Handlers } from './assemble'

export interface MenuSource {
  handlers: () => Handlers
  facts: () => Facts
  notice: (why: string) => void
}

export function useMenus(app: AppName, source: MenuSource): ComputedRef<AssembledMenus> {
  const { t, locale } = useI18n()
  const policy = typeof window === 'undefined' ? DEFAULT_POLICY : policyFromAddress(window.location.search)
  let checked = false
  return computed(() => {
    const handlers = source.handlers()
    if (!checked) {
      checked = true
      sayGaps(app, handlers)
    }
    return assembleMenus({ definition: DEFINITIONS[app], handlers, facts: source.facts, policy, t, notice: source.notice, locale: locale.value })
  })
}

/** An action of the definition this workspace does not do, or a handler for one there is not, is a mistake: said on the
 * console, where the browser tests look for errors, as the unit test of `handlerGaps` cannot mount a workspace. */
function sayGaps(app: AppName, handlers: Handlers): void {
  const { missing, unknown } = handlerGaps(DEFINITIONS[app], handlers)
  if (missing.length) console.error(`menus of ${app}: no handler for ${missing.join(', ')}`)
  if (unknown.length) console.error(`menus of ${app}: a handler for no action: ${unknown.join(', ')}`)
}

/** What the document's app adds to what every window knows (`windowFacts`). */
export interface AppFacts {
  selection: readonly Thing[]
  references?: boolean
  randomNumbers?: boolean
  slides?: number
  /** In one of the desktop apps (the shell is there), not a browser tab. */
  desktop?: boolean
}

/** What is true now: who I am, what the server and the ai can do, and what this document has (D1601, D1615). Looking at
 * the past (Replay) or at a redaction being previewed is looking only (`roleNow`). */
export function windowFacts(state: BaseState, own: AppFacts): Facts {
  const role = roleNow(state)
  const answering = state.consent?.answering
  return {
    role: role === 'owner' || role === 'editor' ? role : 'viewer',
    client: own.desktop ? 'desktop' : 'web',
    ai: !!answering && answering.provider !== 'stand-in',
    tools: new Set(state.containerTypes.map((k) => k.type)),
    document: {
      undo: state.canUndo,
      redo: state.canRedo,
      references: own.references ?? false,
      randomNumbers: own.randomNumbers ?? false,
      backPlace: !!state.wayBack,
      slides: own.slides ?? 0,
    },
    selection: own.selection,
  }
}
