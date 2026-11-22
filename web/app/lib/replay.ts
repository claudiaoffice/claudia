// Replaying the history (D551): which rows the wheel visits, where the playhead goes, and where a view looks. The
// views themselves draw the past from the same read requests they always make, answered "as of" a step
// (`BaseSession.replayAt`); this module is only the logic of the playhead, so it is tested without a window.
import type { ChatMessage, Step } from './base-session'
import { ProtocolError, type CloseHandler, type EventHandler, type LinkLike, type Region, type WireData } from './protocol'

/** Which rows the history shows, and so which the wheel visits: the changes, the conversation, or both. */
export type Filter = 'all' | 'chat' | 'steps'

/** One row of the history: a change, or a chat message in the place of the change it was written after. `state` is the
 * revision of the document that row stands for (the last change at or before it), `null` before the first change. */
export type Item =
  | (Step & { kind: 'change'; state: string })
  | (ChatMessage & { kind: 'chat'; state: string | null })

/** The revision a row shows the document at, `null` when there is nothing yet. */
export function stateOf(item: Item): string | null {
  return item.state
}

/** The rows of the history in order, for a filter. A chat message is placed after the change whose revision it carries
 * (`at`); one written before any change, or before the history shown, comes first. */
export function timeline(entries: readonly Step[], chat: readonly ChatMessage[], filter: Filter): Item[] {
  const shown = new Set(entries.map((e) => e.revision))
  const after = new Map<string, ChatMessage[]>()
  const first: ChatMessage[] = []
  for (const message of chat) {
    // written when the document had no change yet (`at` is empty), or at one older than the history shown: at the start
    if (message.at === null || !shown.has(message.at)) first.push(message)
    else after.set(message.at, [...(after.get(message.at) ?? []), message])
  }
  const items: Item[] = first.map((message) => ({ ...message, kind: 'chat' as const, state: null }))
  for (const e of entries) {
    items.push({ ...e, kind: 'change', state: e.revision })
    for (const message of after.get(e.revision) ?? []) items.push({ ...message, kind: 'chat', state: e.revision })
  }
  return filter === 'all' ? items : items.filter((i) => (filter === 'steps' ? i.kind === 'change' : i.kind === 'chat'))
}

/** The row `by` rows from `at`, stopping at the ends; with `unit` "author", the start of the next (or previous) run of
 * rows by one author. */
export function step(items: readonly Item[], at: number, by: 1 | -1, unit: 'row' | 'author' = 'row'): number {
  const last = items.length - 1
  if (last < 0) return -1
  const here = Math.min(Math.max(at, 0), last)
  if (unit === 'row') return Math.min(Math.max(here + by, 0), last)
  if (by > 0) {
    const who = authorOf(items[here]!)
    let i = here
    while (i < last && authorOf(items[i]!) === who) i++
    return i
  }
  const start = groupStart(items, here)
  return start < here ? start : groupStart(items, Math.max(here - 1, 0))
}

/** Where the run of rows by one author that row `at` belongs to starts. */
export function groupStart(items: readonly Item[], at: number): number {
  const who = authorOf(items[at]!)
  let i = at
  while (i > 0 && authorOf(items[i - 1]!) === who) i--
  return i
}

const authorOf = (item: Item): string => item.author ?? ''

/** The row that shows a revision: its own, else the nearest row before it (`-1` with no rows). */
export function nearest(items: readonly Item[], revision: string): number {
  const own = items.findIndex((i) => i.kind === 'change' && i.revision === revision)
  if (own >= 0) return own
  const seq = (r: string) => Number(r.slice(r.lastIndexOf(':') + 1))
  let found = -1
  items.forEach((item, i) => {
    if (item.kind === 'change' && seq(item.revision) <= seq(revision)) found = i
  })
  return found < 0 ? (items.length ? items.length - 1 : -1) : found
}

/** One wheel event's `deltaY`, as the steps it makes. A notch of a mouse wheel (100 or 120, by system) is one step; the
 * small deltas of a trackpad add up until they make one; a turn the other way forgets what was gathered. */
export class WheelStepper {
  private gathered = 0
  private static readonly NOTCH = 100
  private static readonly STEP = 60

  feed(delta: number): number {
    if (delta === 0) return 0
    if (Math.abs(delta) >= WheelStepper.NOTCH) {
      this.gathered = 0
      return Math.sign(delta)
    }
    if (Math.sign(delta) !== Math.sign(this.gathered)) this.gathered = 0
    this.gathered += delta
    const steps = Math.trunc(this.gathered / WheelStepper.STEP) || 0
    this.gathered -= steps * WheelStepper.STEP
    return steps
  }

  reset(): void {
    this.gathered = 0
  }
}

/** What a key does to the playhead, `null` for a key that is not one of its keys: Alt+PageUp / Alt+PageDown a step,
 * Alt+Home the start, End and Escape back to now. */
export function keyStep(event: { key: string; altKey?: boolean }): { by: 1 | -1 } | { to: 'start' | 'now' } | null {
  if (event.key === 'Escape' || (event.key === 'End' && !event.altKey)) return { to: 'now' }
  if (!event.altKey) return null
  if (event.key === 'PageUp') return { by: -1 }
  if (event.key === 'PageDown') return { by: 1 }
  if (event.key === 'Home') return { to: 'start' }
  return null
}

/** The first place a step touched: where a view looks. */
export function firstFocus(focus: readonly Region[]): Region | null {
  return focus[0] ?? null
}

/** The slide, sheet or paragraph a place lies in; `null` for no place. */
export function holderOf(region: Region | null): string | null {
  if (region === null) return null
  if (region.kind === 'objects') return region.holder
  if (region.kind === 'cells') return region.range.first.sheet ?? null
  return region.paragraph
}

/** What a replay may still ask the server live: the panel's own reading, the conversation and the suggestions to go
 * back, which go on in the present. */
export const LIVE_REQUESTS: ReadonlySet<string> = new Set([
  'log',
  'chat_log',
  'chat',
  'checkpoints',
  'history',
  'branches',
  'restore_policy',
  'language',
  'ping',
  'peek_revision',
  'thing_last_seen',
  // working a redaction out changes nothing (D721)
  'redaction_plan',
  'changes_since',
  // a suggestion changes nothing until everybody has agreed: it may be made, answered and taken back from the past
  'propose_restore_step',
  'answer_restore',
  'withdraw_restore',
])

/** What a view reads the document with; asked "as of" a step while replaying. The same list the server answers (`VIEW_READS`). */
export const VIEW_READS: ReadonlySet<string> = new Set([
  'snapshot',
  'palette',
  'styles',
  'style_model',
  'style_uses',
  'images',
  'containers',
  'container_types',
  'shapes',
  'print_setup',
  'slides',
  'slide',
  'sheets',
  'cells',
  'sizes',
  'charts',
  'diagrams',
  'chart_figure',
  'names',
  'number_formats',
  'cell_styles',
  'cell_style_at',
  'outcome_table',
  'random_state',
  'objects',
  'paragraphs',
  'page',
  'look',
  'suggestions',
])

/** A link whose reads of the document are answered for a document other than the live one, while the conversation
 * stays live and anything that would change the document is refused before it leaves the page. */
abstract class LookingLink implements LinkLike {
  constructor(private inner: LinkLike) {}

  /** The request a view's read becomes. */
  protected abstract looked(method: string, params: Record<string, unknown>): [string, Record<string, unknown>]

  connect() {
    return this.inner.connect()
  }
  async request<T = WireData>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (LIVE_REQUESTS.has(method)) return this.inner.request<T>(method, params)
    if (VIEW_READS.has(method)) return this.inner.request<T>(...this.looked(method, params))
    throw new ProtocolError('forbidden', method)
  }
  onEvent(handler: EventHandler) {
    this.inner.onEvent(handler)
  }
  onClose(handler: CloseHandler) {
    this.inner.onClose(handler)
  }
  close() {
    this.inner.close()
  }
}

/** The link of a session that is looking at the past: reads are answered as of one step (`as_of`). */
export class PastLink extends LookingLink {
  constructor(
    inner: LinkLike,
    private revision: () => string,
  ) {
    super(inner)
  }
  protected looked(method: string, params: Record<string, unknown>): [string, Record<string, unknown>] {
    return ['as_of', { revision: this.revision(), method, params }]
  }
}

/** The link of a session that is previewing a redaction (D721): reads are answered from the state the redaction would
 * leave (`as_planned`), by the token of its plan. */
export class PlannedLink extends LookingLink {
  constructor(
    inner: LinkLike,
    private plan: () => string,
  ) {
    super(inner)
  }
  protected looked(method: string, params: Record<string, unknown>): [string, Record<string, unknown>] {
    return ['as_planned', { plan: this.plan(), method, params }]
  }
}

/** Can this person only look at the document right now: they are a viewer, or they are looking at the past or at
 * the preview of a redaction. */
export function lookOnly(state: { me: { role: string }; replay?: unknown; preview?: unknown }): boolean {
  return state.me.role === 'viewer' || state.replay != null || state.preview != null
}

/** The role the menus go by: while looking at the past or at a preview, nothing can be changed, as for a viewer. */
export function roleNow(state: { me: { role: string }; replay?: unknown; preview?: unknown }): string {
  return state.replay != null || state.preview != null ? 'viewer' : state.me.role
}

/** What a wheel event moved, in pixels whatever the unit it was reported in (lines and pages count as 40 and 800). */
export function wheelDelta(event: { deltaY: number; deltaX?: number; deltaMode?: number; shiftKey?: boolean }): number {
  const raw = event.shiftKey && !event.deltaY ? (event.deltaX ?? 0) : event.deltaY
  return event.deltaMode === 1 ? raw * 40 : event.deltaMode === 2 ? raw * 800 : raw
}
