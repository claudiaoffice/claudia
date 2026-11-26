// The web's menus and context menus, assembled from the one definition (D1644): its entries × the workspace's handlers ×
// the verdicts of `fits/`. What does not fit is left out or greyed as the trial says (D1606); separators and submenus
// with nothing left collapse, and a menu with nothing left is one greyed line saying why (D1603). An entry is judged
// again when it runs, so an open menu that went stale, a shell's action and a key all get the notice of D1604 instead.
// Plain data and functions, no Vue: `use-menus.ts` gives it the live facts.
import type { Menu, MenuItem } from '../../components/MenuBar.vue'
import type { Translate } from '../fits/conditions'
import { REASONS, type Facts, type Reason } from '../fits/facts'
import { judge } from '../fits/judge'
import type { FitPolicy } from '../fits/policy'
import { describeRule, parseRule } from '../fits/rule'
import { hintOf } from '../shortcuts'
import type { AppDef, EntryDef, MenuDef } from '../menus.generated'
import type { ActionState } from '../shell-bridge'

/** What a workspace keeps of an entry: what it does, and what only it can say about it. */
export interface Handler {
  /** Does it; for a switch (`checkable`), turns it over. */
  run: () => void
  /** Words that change with the document ("Undo Add Container"), or that are never translated (a language's own name). */
  label?: () => string
  checked?: () => boolean
  /** Choices the entry opens on the web, where the workbook asks for a submenu the definition cannot hold (Wrap Text…
   * ▸ the four modes); its key, and the shells' entry, still `run`. */
  items?: () => MenuItem[]
  /** The entry's own sentence for a reason, said instead of the condition's (D1650). */
  why?: Partial<Record<Reason, string>>
  /** A sentence when the workspace cannot run it now for a reason the workbook has no condition for: the entry is
   * greyed, never left out. Each use is listed for the owner (implementation note of slice 4). */
  notNow?: () => string | null
}

export type Handlers = Readonly<Record<string, Handler>>

/** What a workspace hands the part of it that opens a context menu (the grid, the canvas): the menu with that id. */
export type ContextMenuOf = (id: string, own?: Handlers) => MenuItem[]

export interface MenuInput {
  definition: AppDef
  handlers: Handlers
  /** What is true now: read when the menus are assembled and again when an entry runs. */
  facts: () => Facts
  policy: FitPolicy
  t: Translate
  /** Says why something did not run (the window's notice, `role=status`). */
  notice: (why: string) => void
  /** The language of the words: decides how a sentence goes on after a colon. */
  locale: string
}

export interface AssembledMenus {
  bar: Menu[]
  /** The context menu with that id in the definition; empty for one the app has not. `own`: what the place that opens
   * it does instead of the workspace's handlers (the style popover at the pointer, the object under it). */
  context: (id: string, own?: Handlers) => MenuItem[]
  /** Every action's state, for a native shell's menus: one left out is not enabled. */
  states: Record<string, ActionState>
  /** The menus of the bar with nothing left, by their word in the definition ("insert"), and the line that says why. */
  empty: Record<string, string>
  /** Every action the page runs, once, in the person's words: what has a key, and what Preferences ▸ Shortcuts lists. */
  actions: { id: string; label: string }[]
  /** Every action for Preferences ▸ Shortcuts (D1604): the menu bar's by menu, then what only a context menu has. */
  listing: () => ShortcutGroup[]
  /** Runs an action by its id, as a shell or a key asks: judged now, by the rule of its first place. `target` is what
   * a shell asks of a switch. False for an id the definition or the handlers have not. */
  run: (id: string, target?: 'on' | 'off') => boolean
}

/** One row of Preferences ▸ Shortcuts: where the action is, its key, when it fits, and whether it fits now (D1642). */
export interface ShortcutRow {
  id: string
  /** Its place in the menu: "Paste As ▸ Plain Text". */
  label: string
  keys: string | null
  /** The rule in plain words: "editors and owners, when something is selected". */
  when: string
  fits: boolean
  /** Why not, in a few words: "not for you" (role), "not now" (document, selection), "not here" (server, client, ai). */
  tag: string | null
}

export interface ShortcutGroup {
  title: string
  rows: ShortcutRow[]
}

type Judged = { shown: boolean; enabled: true } | { shown: boolean; enabled: false; reason: Reason | null; why: string }

/** What a workspace has to give: a handler for every action the page runs, and none for an action there is not. */
export function handlerGaps(definition: AppDef, handlers: Handlers): { missing: string[]; unknown: string[] } {
  const ids = new Set<string>()
  const needed = new Set<string>()
  for (const entry of entriesOf(definition)) {
    ids.add(entry.id)
    if (entry.kind !== 'shell') needed.add(entry.id)
  }
  return {
    missing: [...needed].filter((id) => !handlers[id]).sort(),
    unknown: Object.keys(handlers).filter((id) => !ids.has(id)).sort(),
  }
}

export function assembleMenus(input: MenuInput): AssembledMenus {
  const { definition, handlers, t } = input
  /** The definition's words in the person's language: `scripts/extract_i18n.py` takes them from the definition itself. */
  const word = (english: string) => input.t(english)
  const facts = input.facts()

  function judged(entry: EntryDef, now: Facts, from: Handlers = handlers): Judged {
    const handler = from[entry.id]
    const verdict = judge(parseRule(entry.fits), now, input.policy, entry.id, t, handler?.why)
    if (!verdict.enabled) return verdict
    const notNow = handler?.notNow?.()
    if (notNow) return { shown: true, enabled: false, reason: null, why: notNow }
    if (!handler) return { shown: entry.kind !== 'shell', enabled: false, reason: null, why: '' }
    return verdict
  }

  /** Runs the entry if it fits now; says why if not. */
  function attempt(entry: EntryDef, target?: 'on' | 'off', from: Handlers = handlers): boolean {
    const handler = from[entry.id]
    if (!handler) return false
    const now = judged(entry, input.facts(), from)
    if (!now.enabled) {
      if (now.why) input.notice(now.why)
      return true
    }
    if (target === undefined || !handler.checked || (target === 'on') !== handler.checked()) handler.run()
    return true
  }

  function item(entry: EntryDef, from: Handlers): MenuItem | null {
    const verdict = judged(entry, facts, from)
    if (!verdict.shown) return null
    const handler = from[entry.id]
    const made: MenuItem = {
      id: entry.id,
      label: handler?.label?.() ?? word(entry.label),
      action: (target) => void attempt(entry, target, from),
    }
    if (!verdict.enabled) made.disabled = true
    else if (handler?.items) made.items = handler.items()
    if (entry.checkable) made.checked = handler?.checked?.() ?? false
    return made
  }

  /** The items of a menu, lines between the groups that kept something, and the why of what was left out. */
  function items(menu: MenuDef, from: Handlers = handlers): { items: MenuItem[]; why: Judged | null } {
    const out: MenuItem[] = []
    let why: Judged | null = null
    const missed = (entry: EntryDef) => {
      const verdict = judged(entry, facts, from)
      if (!verdict.shown && !verdict.enabled && verdict.why && rank(verdict) < (why ? rank(why) : Infinity)) why = verdict
    }
    for (const section of menu.sections) {
      const kept: MenuItem[] = []
      for (const placed of section) {
        if ('items' in placed) {
          const subs = placed.items.map((entry) => item(entry, from) ?? (missed(entry), null)).filter((x): x is MenuItem => !!x)
          // a submenu whose entries are all greyed is greyed itself, so that it does not open onto nothing to choose
          if (subs.length) kept.push({ label: word(placed.label), items: subs, ...(subs.every((x) => x.disabled) ? { disabled: true } : {}) })
        } else {
          const made = item(placed, from)
          if (made) kept.push(made)
          else missed(placed)
        }
      }
      if (kept.length) out.push(...(out.length ? [{ label: '', separator: true }] : []), ...kept)
    }
    return { items: out, why }
  }

  /** The menus of the bar with nothing left, by their word in the definition ("insert"), with the line that says why:
   *  what a shell draws in them (D1603, contract `action_state.empty`). */
  const empty: Record<string, string> = {}
  const bar = definition.menus.map((menu): Menu => {
    const made = items(menu)
    const why = made.why as Judged | null
    if (made.items.length || !why || why.enabled) return { label: word(menu.label), items: made.items }
    const line = emptyLine(menu.label, why.why, t, input.locale)
    empty[menu.id] = line
    return { label: word(menu.label), items: [{ label: line, disabled: true }] }
  })

  function context(id: string, own: Handlers = {}): MenuItem[] {
    const menu = definition.contexts.find((c) => c.id === id)
    if (!menu) return []
    // the place's own handler, keeping what the workspace's says that the place's does not (Copy's sentence)
    const merged = { ...handlers, ...Object.fromEntries(Object.entries(own).map(([id, h]) => [id, { ...handlers[id], ...h }])) }
    const made = items(menu, merged)
    const why = made.why as Judged | null
    if (made.items.length || !why || why.enabled) return made.items
    return [{ label: why.why, disabled: true }]
  }

  const first = new Map<string, EntryDef>()
  for (const entry of entriesOf(definition)) if (!first.has(entry.id)) first.set(entry.id, entry)
  const inTheBar = new Set([...entriesOf({ ...definition, contexts: [], keysOnly: [] })].map((entry) => entry.id))

  const states: Record<string, ActionState> = {}
  const actions: { id: string; label: string }[] = []
  for (const [id, entry] of first) {
    if (handlers[id]) actions.push({ id, label: handlers[id].label?.() ?? word(entry.label) })
    // the shells draw the bar only (D1645); a key of anything else reaches the page, which judges it when pressed
    if (!inTheBar.has(id) || (entry.kind === 'shell' && !handlers[id])) continue
    const verdict = judged(entry, facts)
    const state: ActionState = { enabled: verdict.enabled, visible: verdict.shown }
    if (entry.checkable) state.checked = handlers[id]?.checked?.() ?? false
    states[id] = state
  }

  /** "not for you", "not now" or "not here" (D1642). */
  function tagOf(verdict: Judged): string | null {
    if (verdict.enabled) return null
    if (verdict.reason === 'role') return t('not for you')
    if (verdict.reason === 'server' || verdict.reason === 'client' || verdict.reason === 'ai') return t('not here')
    return t('not now')
  }

  function listing(): ShortcutGroup[] {
    const listed = new Set<string>()
    const rows = (menu: MenuDef): ShortcutRow[] =>
      menu.sections.flat().flatMap((placed) =>
        ('items' in placed ? placed.items.map((entry) => [entry, `${word(placed.label)} ▸ `] as const) : [[placed, ''] as const])
          .filter(([entry]) => !listed.has(entry.id) && (entry.kind !== 'shell' || handlers[entry.id]))
          .map(([entry, path]): ShortcutRow => {
            listed.add(entry.id)
            const verdict = judged(entry, facts)
            const label = handlers[entry.id]?.label?.() ?? word(entry.label)
            return { id: entry.id, label: path + label, keys: hintOf(entry.id) ?? null, when: describeRule(parseRule(entry.fits), t), fits: verdict.enabled, tag: tagOf(verdict) }
          }),
      )
    const groups = definition.menus.map((menu) => ({ title: word(menu.label), rows: rows(menu) }))
    for (const menu of definition.contexts) groups.push({ title: t('Context menu: {menu}', { menu: word(menu.label) }), rows: rows(menu) })
    groups.push({ title: t('Keys without an entry'), rows: rows({ id: 'keys-only', label: '', sections: [definition.keysOnly] }) })
    return groups.filter((group) => group.rows.length)
  }

  return {
    bar,
    context,
    states,
    empty,
    actions,
    listing,
    run: (id, target) => {
      const entry = first.get(id)
      return entry ? attempt(entry, target) : false
    },
  }
}

/** Every entry of the menus, then of the context menus, then the keys without entry, in the definition's order. */
function* entriesOf(definition: AppDef): Generator<EntryDef> {
  for (const menu of [...definition.menus, ...definition.contexts]) {
    for (const section of menu.sections) {
      for (const placed of section) {
        if ('items' in placed) yield* placed.items
        else yield placed
      }
    }
  }
  yield* definition.keysOnly
}

/** The order of D1642: who you are first. A workspace's own sentence comes after every reason. */
function rank(verdict: Judged): number {
  return verdict.enabled || verdict.reason === null ? REASONS.length : REASONS.indexOf(verdict.reason)
}

/** The one line of a menu with nothing left (D1603): "Nothing to insert: you can only look at this document." English
 * goes on after a colon in small letters; German, among others, with a capital, so the sentence stays as it is. */
function emptyLine(menu: string, why: string, t: Translate, locale: string): string {
  const after = locale.startsWith('en') ? why.charAt(0).toLowerCase() + why.slice(1) : why
  switch (menu) {
    case 'File':
      return t('Nothing to do with the file: {why}', { why: after })
    case 'Edit':
      return t('Nothing to edit: {why}', { why: after })
    case 'Insert':
      return t('Nothing to insert: {why}', { why: after })
    case 'Format':
      return t('Nothing to format: {why}', { why: after })
    case 'View':
      return t('Nothing to show: {why}', { why: after })
    case 'Tools':
      return t('No tools here: {why}', { why: after })
    default:
      return t('Nothing here: {why}', { why: after })
  }
}
