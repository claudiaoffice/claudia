// What every app's session has in common: the connection with its reconnecting, who is here, the history, the chat,
// checkpoints, undo/redo. The replica of the document itself belongs to the app (Session: cells, TextSession: text).
// All changes go to the server as requests; nothing is believed until the server's events say it happened.
import { reactive } from 'vue'
import { DEFAULT_AI_MODE, readAiMode, safeStorage, storeAiMode, type AiMode, type ModeStorage } from './ai-mode'
import type { PreviewAnswer, ReplaceAnswer, SearchAnswer, SearchLeave, SearchQuery } from './search'
import type { RenderingDef, RenderOutcome, RenderType } from './rendering'
import { closeMessage, ProtocolError, type LineInfo, type LinkLike, type Region, type RestoreProposal, type RestoreResolution, type Welcome, type WireData } from './protocol'

import { languageNow, onLanguageChange, translate as t } from './i18n'
import type { Thing } from './tags'
import { nearest, PastLink, step as stepRow, timeline, type Filter, type Item } from './replay'
export const LOG_LIMIT = 500
const FINAL_CLOSES = new Set([4400, 4401, 4403, 4404, 4408, 1013])

/** One thing an export could not put into the file, as a code for the interface to put into words (E12.6). */
export interface ExportLoss {
  kind: string
  detail: string
  count: number
}

/** What `export_office` answers: the file as base64, and for formats that can tell, what it could not hold. */
export interface ExportedFile {
  format: string
  content_type: string
  data: string
  losses?: ExportLoss[]
}

export interface Person {
  id: number
  user: string
  color: string
}
export interface Entry {
  revision: string
  author: string | null
  origin: 'do' | 'undo' | 'redo'
  time: string
  label: string
  summary: string
  of?: string | null
}
export interface ChatMessage {
  number: number
  author: string
  to: string
  text: string
  time: string
  at: string | null
}
export interface CheckpointInfo {
  number: number
  label: string
  author: string | null
  marks: string
  time?: string
}
export interface Notice {
  id: number
  kind: 'info' | 'warning' | 'error'
  text: string
}
/** A `help_search` result: everything but the body (E13.1, E13.3). */
export interface HelpTopicSummary {
  id: string
  title: string
  apps: string[]
  tags: string[]
}
/** A `help_topic` result: the whole topic, its `body` Markdown shown as plain text for now (D30 is not wired up
 * for help yet — this iteration's own scope decision, not a property of the topic format). */
export interface HelpTopic extends HelpTopicSummary {
  language: string
  explains: string[]
  body: string
}
/** Looking at the document as it was (D551): where the playhead stands, and what the views are showing. */
export interface ReplayState {
  /** Which rows the history shows, and the wheel visits. */
  filter: Filter
  /** The row the playhead is on: `c:<revision>` for a change, `m:<number>` for a chat message. */
  row: string
  /** The step the views show: the document after this revision. */
  revision: string
  /** Do the views go to what the step touched? */
  follow: boolean
  /** How many changes others made since the replay began, which the views do not show. */
  newer: number
  /** Is a step still being loaded? */
  loading: boolean
  /** What the step touched, for the views to point at. */
  focus: Region[]
  /** Does the view also mark what changed after this step ("Show differences from now", D553)? */
  differences: boolean
  /** Where the document changed after this step, while `differences` is on; empty otherwise. */
  changed: Region[]
  /** Were there more places than `changed` lists? */
  changedMore: boolean
}

/** What a tag has just taken the view to (E5.20, D551): the thing, the slide, sheet or paragraph it is on, and where to
 * go back to (`null` when the view did not move). The view marks the thing for a moment. */
export interface Pointed {
  id: string
  container: string | null
  from: string | null
}
export const POINT_MS = 3000

export const rowKey = (item: Item): string => (item.kind === 'change' ? `c:${item.revision}` : `m:${item.number}`)

export interface BaseState {
  /** Which app the document belongs to (`computes`, `composes`): the server says so when it welcomes us. */
  app: string
  /** The server's own address (`host` or `host:port`, as `location.host`/`socketUrl` use it) — whichever one this
   *  session actually opened a socket to, not necessarily the page's own (E3.11, "knowing which server you're on";
   *  the Open dialog can connect to a bookmarked server other than the one the page was loaded from). Blank only
   *  before the first connection has told us. */
  host: string
  /** How the AI treats this person's requests in this document (D262): the person's own choice, kept in this browser. */
  aiMode: AiMode
  status: 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed'
  error: string
  me: { user: string; role: string; color: string }
  doc: string
  line: string
  revision: string | null
  people: Person[]
  presence: Record<string, { regions: Region[]; locked: boolean }>
  typing: string[]
  entries: Entry[]
  chat: ChatMessage[]
  checkpoints: CheckpointInfo[]
  canUndo: boolean
  canRedo: boolean
  undoLabel: string
  redoLabel: string
  notice: Notice | null
  /** Every line of the document's history: the active one, and the side lines a restore left behind (E3.8). */
  lines: LineInfo[]
  /** A restore/switch suggestion waiting for everybody's answer, if one is open right now (E3.7). */
  proposal: RestoreProposal | null
  /** How silence at a suggestion's deadline is read: `consensus` (must actively agree) or `veto` (must object). */
  restorePolicy: 'consensus' | 'veto'
  /** The playhead, while the person looks at the document as it was; `null` in the present. */
  replay: ReplayState | null
  /** The names things were given since the document was loaded (`thing_renamed`), by id: a tag shows the name now. */
  renamed: Record<string, string>
  /** The thing a tag in the chat just took the view to, for the view to mark. */
  pointed: Pointed | null
  /** What the server can make as a rendered container (`rendering_types`); empty for a server that makes none (D560). */
  renderTypes: RenderType[]
  /** The definitions of the rendered containers the document holds, by id; the text is the truth (D390). */
  renderings: Record<string, RenderingDef>
  /** What the server last said of making a container's picture, by id; gone when its text changes. */
  renderOutcomes: Record<string, RenderOutcome>
}

export interface SessionOptions {
  retryDelays?: number[]
  /** The server this session is to connect to (same shape as `BaseState.host`) — carried into `state.host` so the
   *  connection indicator can show it without reaching back into whatever built the link. */
  host?: string
  /** Where the person's choices about this document are kept (the browser's local storage; tests hand in a map). */
  storage?: ModeStorage
}

export const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

function initialState(): BaseState {
  return {
    app: '',
    host: '',
    aiMode: DEFAULT_AI_MODE,
    status: 'idle',
    error: '',
    me: { user: '', role: '', color: '' },
    doc: '',
    line: 'main',
    revision: null,
    people: [],
    presence: {},
    typing: [],
    entries: [],
    chat: [],
    checkpoints: [],
    canUndo: false,
    canRedo: false,
    undoLabel: '',
    redoLabel: '',
    notice: null,
    lines: [],
    proposal: null,
    restorePolicy: 'consensus',
    replay: null,
    renamed: {},
    pointed: null,
    renderTypes: [],
    renderings: {},
    renderOutcomes: {},
  }
}

export abstract class BaseSession<S extends BaseState = BaseState> {
  readonly state: S
  /** Was this document made by the very opening that led here? Then its owner is shown the recovery key. */
  justCreated = false
  /** The file this document was just made from, as the welcome said (D438); only right after the import. */
  imported: { name: string; format: string; kept: boolean; losses: { kind: string; count: number }[] } | null = null

  protected link: LinkLike | null = null
  private tasks = new Set<Promise<unknown>>()
  private noticeCount = 0
  private closing = false
  private retryDelays: number[]
  private storage: ModeStorage

  private stopLanguage: (() => void) | null = null
  private replayLink: PastLink | null = null
  private replayWanted: string | null = null
  private replayPump: Promise<void> | null = null

  /** `app` is the app's own part of the state (it becomes reactive together with the common part). */
  constructor(
    private makeLink: () => LinkLike,
    options: SessionOptions,
    app: Omit<S, keyof BaseState>,
  ) {
    this.retryDelays = options.retryDelays ?? [1000, 2000, 4000, 8000]
    this.storage = options.storage ?? safeStorage()
    this.state = reactive({ ...initialState(), ...app, host: options.host ?? '' }) as unknown as S
  }

  /** Load what the app shows of the document (called with every (re)load, next to the common parts). */
  protected abstract loadApp(): Promise<void>
  /** Handle an event that only the app knows; `true` if it was one. */
  protected abstract onAppEvent(name: string, data: WireData): boolean

  // ------------------------------------------------------------------------------ connecting
  async open(): Promise<void> {
    this.state.status = 'connecting'
    try {
      await this.start()
    } catch (error) {
      this.state.status = 'closed'
      this.state.error = error instanceof ProtocolError ? error.message : closeMessage(0)
      throw error
    }
  }

  close() {
    this.closing = true
    this.stopLanguage?.()
    this.stopLanguage = null
    this.link?.close()
    this.state.status = 'closed'
  }

  /** Resolves when everything that was started in the background (reloads, reconnects) is done. */
  async settled(): Promise<void> {
    while (this.tasks.size > 0) await Promise.allSettled([...this.tasks])
  }

  private async start() {
    const link = this.makeLink()
    link.onEvent((name, data) => this.onEvent(name, data))
    link.onClose((code, requested) => this.onClose(link, code, requested))
    const welcome = await link.connect()
    this.link = link
    this.stopLanguage ??= onLanguageChange((tag) => void this.tellLanguage(tag))
    this.applyWelcome(welcome)
    await this.reload()
    this.state.status = 'open'
    this.state.error = ''
  }

  private applyWelcome(w: Welcome) {
    const s = this.state
    s.me = { user: w.user, role: w.role, color: w.color }
    s.doc = w.doc
    s.aiMode = readAiMode(s.host, w.doc, this.storage)
    s.app = w.app
    s.line = w.line
    s.revision = w.revision
    s.people = w.people.map((p) => ({ ...p }))
    s.presence = {}
    for (const p of w.presence) s.presence[p.user] = { regions: this.adoptRegions(p.regions), locked: p.locked }
    s.typing = []
    s.proposal = w.proposal
    if (w.returned) this.notice(this.returnedText(w.returned))
    if (w.locale && w.locale !== languageNow()) void this.tellLanguage(languageNow()) // chosen since this link began
    this.onWelcome()
  }

  /** The person chose another App Language: the server speaks it to this window from now on (D323). A server that
   * does not know the request, or no answer, changes nothing the person would notice, so it is not reported. */
  private async tellLanguage(tag: string): Promise<void> {
    try {
      await this.link?.request('set_locale', { locale: tag })
    } catch {
      // the interface is already in the new language; only the server's own messages stay in the old one
    }
  }

  /** The one-time notice of what happened, while this person was away, to the line they were on (E3.7). */
  private returnedText(r: RestoreResolution): string {
    const vars = { by: r.by, label: r.label, agreed: r.agreed.join(', ') }
    return r.kind === 'restore'
      ? t('While you were away, {by} restored to {label} (agreed: {agreed}).', vars)
      : t('While you were away, {by} switched to {label} (agreed: {agreed}).', vars)
  }

  /** What became of the suggestion that was open, for the notice everybody sees once it resolves (E3.7). */
  private resolvedText(p: RestoreProposal, outcome: string): string {
    if (outcome === 'agreed') return t('Everybody agreed: now at {label}.', { label: p.label })
    if (outcome === 'declined') return t('The suggestion to go to {label} was declined.', { label: p.label })
    return t('The suggestion to go to {label} was withdrawn.', { label: p.label })
  }

  /** Where the app counts differently from the server it converts the regions people send (default: as they are). */
  protected adoptRegions(regions: Region[]): Region[] {
    return regions
  }

  /** A connection (a new or a renewed one) was welcomed: the app forgets what it knew of the document. */
  protected onWelcome(): void {}

  private onClose(link: LinkLike, code: number, requested: boolean) {
    if (link !== this.link) return
    if (requested || this.closing) {
      this.state.status = 'closed'
      return
    }
    if (FINAL_CLOSES.has(code)) {
      this.state.status = 'closed'
      this.state.error = closeMessage(code)
      return
    }
    this.state.status = 'reconnecting'
    this.track(this.reconnect())
  }

  private async reconnect() {
    for (let attempt = 0; this.state.status === 'reconnecting'; attempt++) {
      await sleep(this.retryDelays[Math.min(attempt, this.retryDelays.length - 1)] ?? 1000)
      if (this.state.status !== 'reconnecting') return
      try {
        await this.start()
        return
      } catch (error) {
        if (error instanceof ProtocolError && error.code !== 'closed' && error.code !== 'sealed') {
          this.state.status = 'closed'
          this.state.error = error.message
          return
        }
      }
    }
  }

  protected track<T>(task: Promise<T>): Promise<T> {
    this.tasks.add(task)
    const done = () => this.tasks.delete(task)
    task.then(done, done)
    return task
  }

  // ------------------------------------------------------------------------------ loading
  /** Everything the screen shows: the common parts and the app's. */
  protected async reload() {
    await this.stopReplay() // the present is what a reload is for
    this.state.renamed = {}
    const link = this.need()
    const s = this.state
    const [entries, chat, checkpoints, history, lines, restorePolicy, renderTypes, renderings] = await Promise.all([
      link.request<Entry[]>('log', { limit: LOG_LIMIT }),
      link.request<ChatMessage[]>('chat_log', { limit: LOG_LIMIT }),
      link.request<CheckpointInfo[]>('checkpoints'),
      link.request<{ can_undo: boolean; can_redo: boolean; undo_label: string; redo_label: string }>('history'),
      link.request<LineInfo[]>('lines'),
      link.request<{ policy: 'consensus' | 'veto' }>('restore_policy'),
      this.optional<{ types: RenderType[] }>('rendering_types'),
      this.optional<RenderingDef[]>('renderings'),
      this.loadApp(),
    ]).then(([e, c, k, h, l, p, rt, rd]) => [e, c, k, h, l, p, rt, rd] as const)
    s.entries = entries
    s.chat = chat
    s.checkpoints = checkpoints
    s.canUndo = history.can_undo
    s.canRedo = history.can_redo
    s.undoLabel = history.undo_label
    s.redoLabel = history.redo_label
    s.lines = lines
    s.restorePolicy = restorePolicy.policy
    s.renderTypes = renderTypes?.types ?? []
    s.renderings = Object.fromEntries((renderings ?? []).map((d) => [d.id, d]))
    s.renderOutcomes = {}
    const last = entries.at(-1)
    if (last) s.revision = last.revision
  }

  /** What a request answers, or `null` where this server does not know it (an older server, an app without it). */
  private async optional<T>(method: string): Promise<T | null> {
    try {
      return await this.need().request<T>(method)
    } catch (error) {
      if (error instanceof ProtocolError && error.code !== 'closed') return null
      throw error
    }
  }

  // ------------------------------------------------------------------------------ events
  private onEvent(name: string, data: WireData) {
    const s = this.state
    if (!s.replay && this.onAppEvent(name, data)) return // while looking at the past, the present does not disturb it
    switch (name) {
      case 'command':
        s.revision = data.revision
        if (!s.entries.some((e) => e.revision === data.revision)) {
          if (s.replay) s.replay.newer++
          s.entries.push(data)
          if (s.entries.length > LOG_LIMIT) s.entries.shift()
        }
        break
      case 'thing_renamed':
        s.renamed[data.id] = data.name
        break
      case 'rendering':
        this.onRendering(data.id, data.definition)
        break
      case 'render_result':
        s.renderOutcomes[data.id] = { ok: data.ok, diagnostics: data.diagnostics ?? [], message: data.message ?? '', unavailable: data.unavailable ?? null }
        break
      case 'history':
        s.canUndo = data.can_undo
        s.canRedo = data.can_redo
        s.undoLabel = data.undo_label
        s.redoLabel = data.redo_label
        break
      case 'chat':
        if (!s.chat.some((m) => m.number === data.number)) s.chat.push(data)
        break
      case 'checkpoint':
        s.checkpoints.push({ number: data.number, label: data.label, author: data.author, marks: data.marks })
        break
      case 'joined':
        if (!s.people.some((p) => p.id === data.id)) s.people.push({ id: data.id, user: data.user, color: data.color })
        break
      case 'left':
        s.people = s.people.filter((p) => p.id !== data.id)
        break
      case 'ephemeral':
        this.onEphemeral(data)
        break
      case 'restore_proposed':
        s.proposal = data
        break
      case 'restore_resolved': {
        const open = s.proposal
        s.proposal = null
        if (open) this.notice(this.resolvedText(open, data.outcome), data.outcome === 'declined' ? 'warning' : 'info')
        break
      }
      case 'branch':
      case 'rebuilt':
      case 'redacted':
        this.notice(t('The document changed under you (it went back to a checkpoint or was rebuilt). It was reloaded.'), 'warning')
        this.track(this.reload())
        break
    }
  }

  private onRendering(id: string, definition: RenderingDef | null) {
    const s = this.state
    if (!definition) {
      delete s.renderings[id]
      delete s.renderOutcomes[id]
      return
    }
    const before = s.renderings[id]
    if (before && (before.source !== definition.source || JSON.stringify(before.params) !== JSON.stringify(definition.params))) delete s.renderOutcomes[id]
    s.renderings[id] = definition
  }

  private onEphemeral(message: { kind: string; sender: string | null; data: WireData }) {
    const s = this.state
    const who = message.sender ?? ''
    if (message.kind === 'presence') {
      if (message.data.gone || !message.data.regions?.length) delete s.presence[who]
      else s.presence[who] = { regions: this.adoptRegions(message.data.regions), locked: message.data.locked === true }
    } else if (message.kind === 'typing') {
      const others = s.typing.filter((u) => u !== who)
      s.typing = message.data.on ? [...others, who] : others
    } else if (message.kind === 'person_left') {
      this.notice(t('{user} left this document.', { user: message.data.user }))
    } else if (message.kind === 'owner_changed') {
      this.notice(t('{owner} is now the owner of this document.', { owner: message.data.owner }))
      this.track(this.reconnectNow())  // our own role may have just changed (we may have been the old owner)
    } else if (message.kind === 'document_deleted') {
      this.notice(t('This document was deleted by its owner.'), 'warning')
      this.close()
    }
  }

  // ------------------------------------------------------------------------------ doing things
  notice(text: string, kind: Notice['kind'] = 'info') {
    this.state.notice = { id: ++this.noticeCount, kind, text }
  }

  protected need(): LinkLike {
    if (!this.link) throw new ProtocolError('closed', 'not connected')
    if (this.state.replay) return (this.replayLink ??= new PastLink(this.link, () => this.replayShown))
    return this.link
  }

  /** The step the views are being loaded for (the playhead's own moves on as soon as the person steps again). */
  private replayShown = ''

  // ------------------------------------------------------------------------------ replaying (D551)
  /** The rows of the history as the replay's filter shows them. */
  replayItems(): Item[] {
    const s = this.state
    return timeline(s.entries, s.chat, s.replay?.filter ?? 'all')
  }

  /** Which row the playhead is on, `-1` when it is on none. */
  replayIndex(): number {
    const row = this.state.replay?.row
    return this.replayItems().findIndex((i) => rowKey(i) === row)
  }

  /** Start looking at the document as it was, at `revision` or at its latest change. */
  async startReplay(revision?: string): Promise<void> {
    const s = this.state
    if (s.replay || s.status !== 'open' || s.entries.length === 0) return
    const items = timeline(s.entries, s.chat, 'all')
    const at = revision ? nearest(items, revision) : items.findLastIndex((i) => i.kind === 'change')
    const latest = s.entries.at(-1)!.revision
    s.replay = { filter: 'all', row: rowKey(items[at]!), revision: latest, follow: true, newer: 0, loading: false, focus: [], differences: false, changed: [], changedMore: false }
    this.replayLink = null
    this.replayShown = latest
    await this.replayGo(at)
  }

  /** Move the playhead `by` rows (or, with `unit: 'author'`, runs of rows by one person). */
  async replayStep(by: 1 | -1, unit: 'row' | 'author' = 'row'): Promise<void> {
    if (!this.state.replay) return
    const items = this.replayItems()
    const here = this.replayIndex()
    await this.replayGo(stepRow(items, here < 0 ? items.length - 1 : here, by, unit))
  }

  /** Move the playhead to row `index`; the views catch up with the last place it was told to go to. */
  async replayGo(index: number): Promise<void> {
    const s = this.state
    const items = this.replayItems()
    if (!s.replay || items.length === 0) return
    const item = items[Math.min(Math.max(index, 0), items.length - 1)]!
    s.replay.row = rowKey(item)
    this.replayWanted = item.state ?? s.entries[0]!.revision
    await this.catchUp()
  }

  /** Visit only the changes, only the conversation, or both; the playhead stays where it is, or at the nearest change. */
  setReplayFilter(filter: Filter): void {
    const r = this.state.replay
    if (!r) return
    r.filter = filter
    const items = this.replayItems()
    if (items.some((i) => rowKey(i) === r.row)) return
    const at = nearest(items, r.revision)
    if (at >= 0) r.row = rowKey(items[at]!)
  }

  /** Should the views go to what each step touched? Turning it on goes to what this one touched. */
  setReplayFollow(follow: boolean): void {
    const r = this.state.replay
    if (!r) return
    r.follow = follow
    if (follow) this.followReplay(r.focus)
  }

  /** Mark, besides what the step changed, every place that changed after it (D553), or stop doing so. */
  async setReplayDifferences(on: boolean): Promise<void> {
    const r = this.state.replay
    if (!r) return
    r.differences = on
    r.changed = []
    r.changedMore = false
    if (on) await this.loadDifferences(r.revision)
  }

  /** Suggest going back to the document as it is at the step on show (D553): the same agreement as for a checkpoint,
   * from everybody connected as an owner or editor; what came after stays on a side line. */
  async proposeRestoreStep(): Promise<boolean> {
    const r = this.state.replay
    if (!r) return false
    return (await this.attempt('propose_restore_step', { revision: r.revision })) !== false
  }

  /** Back to the present. */
  async endReplay(): Promise<void> {
    if (!this.state.replay) return
    await this.stopReplay()
    this.state.renamed = {}
    await this.track(this.loadApp())
  }

  // ------------------------------------------------------------------------------ tags (E5.20, D551)
  /** Everything with a name that this view knows of, from its own replica. An app that has none returns nothing and
   * answers `locate` and `inView` from the server. */
  protected things(): Thing[] {
    return []
  }
  /** The named things in sight: what `#` in the chat offers. */
  protected async inView(): Promise<Thing[]> {
    return this.things()
  }
  /** How many things in sight have no name yet (a document from before names): `#` offers to name them. */
  async unnamedInView(): Promise<number> {
    return 0
  }
  /** The slide, sheet or paragraph a thing is on (itself, for a slide or sheet); `null` where there is none. */
  protected containerOf(_id: string): string | null {
    return null
  }
  /** Where the view is now, in the same terms as `containerOf`. */
  protected currentContainer(): string | null {
    return null
  }
  /** Take the view to a slide, sheet or paragraph. */
  protected showContainer(_id: string): void {}
  /** Where a thing is, if it is in this view's document as it is shown. */
  protected async locate(id: string): Promise<{ container: string | null } | null> {
    return this.things().some((t) => t.id === id) ? { container: this.containerOf(id) } : null
  }

  /** The things a `#` in the chat may offer: those with a name, in sight. */
  taggableThings(): Promise<Thing[]> {
    return this.inView()
  }

  /** The current name of a thing: what it was renamed to, else what it has, `undefined` for one this view does not know. */
  nameOf(id: string): string | undefined {
    return this.things().find((t) => t.id === id)?.name ?? this.state.renamed[id]
  }

  /** The thing to write a tag for: named already, or named now if it had no name (the first tag to it names it). */
  async thingToReference(id: string): Promise<Thing | null> {
    const find = () => this.things().find((t) => t.id === id) ?? null
    const known = find()
    if (known) return known
    await this.nameUnnamed()
    return find()
  }

  /** Does this view keep a replica of the document's things, so that one it does not hold is gone? */
  protected tracksThings(): boolean {
    return false
  }
  /** Is this thing known to be gone from the document as shown (a tag to it then says so)? */
  isGone(id: string): boolean {
    return this.tracksThings() && this.nameOf(id) === undefined
  }

  /** Give a thing (a sheet, a slide, a chart tab, an object) another name, as one step of the history. The server
   * refuses a name somebody else has, a named range included, with a sentence that is shown here. */
  async renameThing(id: string, name: string): Promise<boolean> {
    return (await this.attempt('rename_thing', { id, name, base: this.state.revision })) !== false
  }

  /** Name everything that has no name (a document from before names) in one step of the history; how many were named. */
  async nameUnnamed(): Promise<number> {
    const done = await this.attempt('name_unnamed', { base: this.state.revision })
    return done === false ? 0 : done.named
  }

  /** What a click on a tag does: take the view to the thing and mark it. For a thing that is gone, a replay at the last
   * moment it was there. */
  async goToThing(id: string, retry = true): Promise<void> {
    const s = this.state
    const found = await this.locate(id)
    if (!found) return this.goToMissing(id, retry)
    const from = this.currentContainer()
    const moved = found.container !== null && found.container !== from
    if (moved) this.showContainer(found.container!)
    const pointed: Pointed = { id, container: found.container, from: moved ? from : null }
    s.pointed = pointed
    setTimeout(() => {
      if (s.pointed === pointed) s.pointed = null
    }, POINT_MS)
  }

  /** The way back after a tag took the view elsewhere. */
  goBack(): void {
    const p = this.state.pointed
    if (p?.from) this.showContainer(p.from)
    this.state.pointed = null
  }

  private async goToMissing(id: string, retry: boolean): Promise<void> {
    const seen = await this.attempt('thing_last_seen', { id })
    if (seen === false) return
    if (seen.present) {
      // it is there now, but not in the past that is being shown: leave the replay and go
      if (this.state.replay && retry) {
        await this.endReplay()
        return this.goToThing(id, false)
      }
      return
    }
    if (!seen.revision) return this.notice(t('There is nothing like that in this document.'), 'warning')
    if (this.state.replay) await this.replayGo(nearest(this.replayItems(), seen.revision))
    else await this.startReplay(seen.revision)
    this.notice(t('That was deleted. This is the last moment it was there.'))
  }

  /** The views' own part of following a step: go to what it touched. */
  protected followReplay(_focus: Region[]): void {}

  private async stopReplay(): Promise<void> {
    const r = this.state.replay
    if (!r) return
    this.replayWanted = r.revision // the step being loaded is the last
    await this.replayPump
    this.state.replay = null
    this.replayLink = null
    this.replayWanted = null
  }

  private catchUp(): Promise<void> {
    this.replayPump ??= this.loadWanted().finally(() => {
      this.replayPump = null
    })
    return this.replayPump
  }

  private async loadWanted(): Promise<void> {
    const s = this.state
    while (s.replay && this.replayWanted !== null && this.replayWanted !== s.replay.revision) {
      const revision = this.replayWanted
      s.replay.loading = true
      this.replayShown = revision
      try {
        const [looked] = await Promise.all([this.need().request<{ focus: Region[] }>('peek_revision', { revision, state: false }), this.loadApp()])
        if (!s.replay) return
        s.replay.revision = revision
        s.replay.focus = looked.focus
        if (s.replay.follow) this.followReplay(looked.focus)
        if (s.replay.differences) await this.loadDifferences(revision)
      } catch (error) {
        if (s.replay) this.replayWanted = s.replay.revision // stay where the views are
        this.explain(error)
      }
    }
    if (s.replay) s.replay.loading = false
  }

  /** Ask where the document changed after `revision`, unless the playhead has moved on or the marking was turned off. */
  private async loadDifferences(revision: string): Promise<void> {
    const r = this.state.replay
    if (!r) return
    try {
      const found = await this.need().request<{ regions: Region[]; truncated: boolean }>('changes_since', { revision })
      if (this.state.replay !== r || !r.differences || r.revision !== revision) return
      r.changed = found.regions
      r.changedMore = found.truncated
    } catch (error) {
      if (this.state.replay === r) this.explain(error)
    }
  }

  /** Run a request; `false` after telling the person why it did not work. */
  protected async attempt(method: string, params: Record<string, unknown> = {}): Promise<WireData | false> {
    try {
      return await this.need().request(method, params)
    } catch (error) {
      this.explain(error)
      return false
    }
  }

  protected explain(error: unknown) {
    if (!(error instanceof ProtocolError)) return this.notice(t('Something went wrong.'), 'error')
    switch (error.code) {
      case 'locked':
      case 'conflict':
        return this.notice(error.message, 'warning')
      case 'stale':
        this.notice(t('Your change was not applied: the document changed under you. It was reloaded.'), 'warning')
        return void this.track(this.reload())
      case 'forbidden':
        return this.notice(t('You can only look at this document.'), 'warning')
      case 'closed':
        return this.notice(t('Not connected to the server.'), 'error')
      default:
        return this.notice(error.message, 'error')
    }
  }

  // ------------------------------------------------------------------------------ search and replace (E5.15)
  /** What a search finds on `scope` (the app's own: computes `{}`, `{sheet}`, `{sheet, range}`; composes `{}`, `{section}`,
   *  `{range}`; creates `{}`, `{slide}`), in the kinds of text asked for.
   *  `null` when it could not be asked: a search runs while she types, so a failure makes no noise. */
  async searchFind(query: SearchQuery, kinds: string[], scope: object): Promise<SearchAnswer | null> {
    try {
      return await this.need().request<SearchAnswer>('search_find', { query, kinds, scope })
    } catch {
      return null
    }
  }

  /** What a replacement would change and what it would skip (and why); nothing is changed. */
  async searchPreview(query: SearchQuery, kinds: string[], scope: object, leave: SearchLeave[]): Promise<PreviewAnswer | null> {
    try {
      return await this.need().request<PreviewAnswer>('search_preview', { query, kinds, scope, leave })
    } catch {
      return null
    }
  }

  /** Replaces, in one step of the history; `false` after telling the person why it did not work. */
  async searchReplace(query: SearchQuery, kinds: string[], scope: object, leave: SearchLeave[]): Promise<ReplaceAnswer | false> {
    const done = await this.attempt('search_replace', { query, kinds, scope, leave, base: this.state.revision })
    return done === false ? false : (done as unknown as ReplaceAnswer)
  }

  // ------------------------------------------------------------------------------ rendered containers (D560)
  /** Puts a container of `type` at `where` (the app's own place: `{slide, x, y}`, …), its first text the type's example.
   *  Returns the new object's id, or `null` — after telling why — if it was not made. */
  async addRendering(type: string, where: Record<string, unknown>, size = { w: 480, h: 270 }, source?: string): Promise<string | null> {
    const kind = this.state.renderTypes.find((k) => k.type === type)
    if (!kind) return null
    const done = await this.attempt('add_rendering', { ...where, ...size, type, source: source ?? kind.example ?? '', params: {}, alt: null, base: this.state.revision })
    return done === false ? null : (done.object as string)
  }

  /** Changes the text of a container; a text that is the same as it is is not sent. `false` after saying why not. */
  async setRenderingSource(id: string, source: string, params: Record<string, unknown> | null = null): Promise<boolean> {
    if (this.state.renderings[id]?.source === source && !params) return true
    return (await this.attempt('set_rendering_source', { id, source, params, base: this.state.revision })) !== false
  }

  async undo(): Promise<boolean> {
    const done = await this.attempt('undo')
    return done !== false && done.applied
  }

  async redo(): Promise<boolean> {
    const done = await this.attempt('redo')
    return done !== false && done.applied
  }

  /** Send whatever is still waiting to be sent, before something that must see all of it (a checkpoint, an
   *  export). Nothing waits in an app that sends every change as it is made; composes overrides this for the
   *  words it collects while someone types (`TextSession.flush`). */
  async flush(): Promise<void> {}

  async saveCheckpoint(label: string | null): Promise<boolean> {
    const done = await this.attempt('save_checkpoint', { label })
    if (done !== false && !done.saved) this.notice(t('Nothing has changed since the last checkpoint.'))
    return done !== false && done.saved
  }

  /** Says `text` in the chat, with how the person wants the AI to treat it if it is for the AI (D262). Always sent:
   *  a message without a mode means a client without the switch, which the server answers as *act* (UNSAID_MODE). */
  async say(text: string): Promise<boolean> {
    return (await this.attempt('chat', { text, ai_mode: this.state.aiMode })) !== false
  }

  /** The person's choice of how the AI treats their requests in this document; kept for next time. */
  setAiMode(mode: AiMode): void {
    this.state.aiMode = mode
    storeAiMode(this.state.host, this.state.doc, mode, this.storage)
  }

  async addUser(name: string, password: string, role: 'editor' | 'viewer'): Promise<boolean> {
    return (await this.attempt('add_user', { name, password, role })) !== false
  }

  /** Reopen the connection with the same name and password, so a role the server just changed takes effect. */
  async reconnectNow(): Promise<void> {
    this.close()
    this.closing = false
    await this.open()
  }

  /** Everybody who may log in to this document, not just who is connected now, in the order they were added. */
  async roster(): Promise<{ user: string; role: string }[] | false> {
    return await this.attempt('roster')
  }

  /** Remove yourself, confirming it with your own current password. `false` after telling the person why not
   * (a wrong password, or being the document's only owner). */
  /** Choose a new password for this document, confirming it with the current one (D448). Only your own: everybody
   * else keeps theirs. `true`, or what went wrong in words fit for the dialog that asked (it says it there, not in a
   * notice behind it). */
  async changePassword(oldPassword: string, newPassword: string): Promise<true | string> {
    try {
      await this.need().request('change_password', { old_password: oldPassword, new_password: newPassword })
      return true
    } catch (error) {
      return error instanceof ProtocolError ? error.message : t('Something went wrong.')
    }
  }

  async leave(password: string): Promise<boolean> {
    return (await this.attempt('leave', { password })) !== false
  }

  /** Owners: ask `name` (who must already be an editor) to become the owner instead, confirming it with your own
   * current password. They accept with `acceptOwner`. */
  async proposeOwner(name: string, password: string): Promise<boolean> {
    return (await this.attempt('propose_owner', { name, password })) !== false
  }

  /** Accept an ownership proposed to you, confirming it with your own current password. Reconnects on success, so
   * the server recognises you as the owner for the rest of this session. */
  async acceptOwner(password: string): Promise<boolean> {
    const done = await this.attempt('accept_owner', { password })
    if (done !== false) await this.reconnectNow()
    return done !== false
  }

  /** Remove this document from the server for good, confirming it with your own current password. There is no
   * way back from this. */
  async deleteDocument(password: string): Promise<boolean> {
    const done = await this.attempt('delete_document', { password })
    if (done !== false) this.close()
    return done !== false
  }

  /** The document's current content as Claudia's own format (not Word, Excel or PowerPoint, and not the history
   * or the chat): `{format, app, exported_at, state_schema, state}`, ready to be saved to a file. */
  async exportContent(): Promise<Record<string, unknown> | false> {
    return await this.attempt('export_content')
  }

  /** The document's current content as bytes of a Word, Excel, PowerPoint or OpenDocument file (`format` is one of
   * what the app supports: "docx", "odt", "xlsx", "ods", "pptx" or "odp"), as `{format, content_type, data}` with
   * `data` base64 — no history, no chat; just the document as it stands now. With `trackedChanges` the text app also writes its
   * open suggestions as tracked changes, dated and signed (D411); the parameter is only sent when asked for, because
   * the other apps do not know it. An OpenDocument answer also has `losses`: what the file could not hold, as
   * `{kind, detail, count}` codes (nothing shows them yet: the screen for that is designed first). */
  async exportOffice(format: string, options: { trackedChanges?: boolean } = {}): Promise<ExportedFile | false> {
    return await this.attempt('export_office', options.trackedChanges ? { format, tracked_changes: true } : { format })
  }

  // ------------------------------------------------------------------------------ help (E13.1, E13.3, E13.5)
  /** Help topics whose title, tags or what-they-explain mention `query`; every topic, by title, if `query` is
   * blank. The same for every app — a topic names the apps it is for itself. */
  async helpSearch(query = ''): Promise<HelpTopicSummary[] | false> {
    return await this.attempt('help_search', { query })
  }

  /** One help topic in full, by the id a `helpSearch` result gave. */
  async helpTopic(id: string): Promise<HelpTopic | false> {
    return await this.attempt('help_topic', { id })
  }

  // ------------------------------------------------------------------------------ lines, and restoring with consent (E3.7, E3.8)
  /** A read-only look at any line (active or hidden), without switching to it: for previewing before suggesting. */
  async peekLine(line: string): Promise<{ line: string; revision: string | null; app: string; state_schema: string; state: unknown } | false> {
    return await this.attempt('peek_line', { line })
  }

  /**
   * Suggest going back to a checkpoint. Carried out at once if you are the only owner or editor connected right
   * now; otherwise everybody in that group must agree (`state.proposal`, `answerRestore`) — unless somebody
   * declines, which ends it right away.
   */
  async proposeRestore(checkpoint: number): Promise<boolean> {
    return (await this.attempt('propose_restore', { checkpoint })) !== false
  }

  /** Suggest making another line active again (the way back after a restore). Same consent as `proposeRestore`. */
  async proposeSwitch(line: string): Promise<boolean> {
    return (await this.attempt('propose_switch', { line })) !== false
  }

  /** Agree or decline the open suggestion (`state.proposal`). */
  async answerRestore(agree: boolean): Promise<boolean> {
    return (await this.attempt('answer_restore', { agree })) !== false
  }

  /** Take back the open suggestion: only the person who made it, or an owner. */
  async withdrawRestore(): Promise<boolean> {
    return (await this.attempt('withdraw_restore')) !== false
  }

  /** Owners only: permanently forget every hidden line (everything a restore ever left behind). */
  async discardSideHistory(): Promise<boolean> {
    const done = await this.attempt('discard_side_history')
    if (done !== false) this.track(this.reload())
    return done !== false
  }

  /** Owners only: choose how silence at a suggestion's deadline is read (`state.restorePolicy`). */
  async setRestorePolicy(policy: 'consensus' | 'veto'): Promise<boolean> {
    const done = await this.attempt('set_restore_policy', { policy })
    if (done !== false) this.state.restorePolicy = done.policy
    return done !== false
  }

  /**
   * Owners: make a new recovery key (the old one stops working). It is shown once and the server keeps nothing of it,
   * so whoever calls this must show it to the person at once. `null` if there is none; unless `quiet`, the person is
   * told why (a server may simply keep no recovery keys).
   */
  async newRecoveryKey(options: { quiet?: boolean } = {}): Promise<string | null> {
    try {
      return (await this.need().request<{ recovery_key: string }>('new_recovery_key')).recovery_key
    } catch (error) {
      if (!options.quiet) this.explain(error)
      return null
    }
  }

  /** Round-trip time to the server right now, in milliseconds — `null` if there is no connection or the request
   *  failed. For the connection indicator's latency reading (E3.11); `ping` is a cheap no-op on the server. */
  async ping(): Promise<number | null> {
    if (!this.link) return null
    const started = performance.now()
    try {
      await this.need().request('ping')
      return Math.round(performance.now() - started)
    } catch {
      return null
    }
  }
}
