// What every app's session has in common: the connection with its reconnecting, who is here, the history, the chat,
// checkpoints, undo/redo. The replica of the document itself belongs to the app (Session: cells, TextSession: text).
// All changes go to the server as requests; nothing is believed until the server's events say it happened.
import type { AuditRow } from './audit'
import type { ConsentView, Via } from './ai-provider'
import { reactive } from 'vue'
import { DEFAULT_AI_MODE, readAiMode, storeAiMode, type AiMode, type ModeStorage } from './ai-mode'
import { safeStorage } from './storage'
import type { PreviewAnswer, ReplaceAnswer, SearchAnswer, SearchLeave, SearchQuery } from './search'
import { outcomesOf, toOutcome, type ContainerDef, type RenderOutcome, type RenderType } from './containers'
import { closeMessage, ProtocolError, type BranchInfo, type LinkLike, type Region, type RestoreProposal, type RestoreResolution, type Welcome, type WireData } from './protocol'

import { languageNow, onLanguageChange, translate as t } from './i18n'
import { roleName } from './people'
import type { Thing } from './tags'
import type { FontReport } from './font-report'
import type { ThingDetails } from './name-and-describe'
import type { SchemeInfo } from './numbering'
import type { Toc } from './contents'
import type { Deleted, DeleteHow, StyleDeletion } from './style-deletion'
import { lookOnly, nearest, PastLink, PlannedLink, step as stepRow, timeline, type Filter, type Item } from './replay'
import { requestOf, type Picked, type RedactionPlan } from './redaction'
import type { ImageAsset } from './images'
import { describeParams } from './descriptions'
import type { ColourRole, ObjectBody, ObjectsEvent, PaletteEvent, VisualObject } from './objects'
import type { CssCheck, CssEdit } from './style-css'
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

/** File ▸ Export… ▸ Claudia, unencrypted (D1270): the zip, base64, and the parts it holds. */
export interface UnprotectedFile {
  format: 'claudia-unencrypted'
  filename: string
  content_type: string
  data: string
  parts: string[]
}

export interface Person {
  id: number
  user: string
  color: string
}
export interface Step {
  revision: string
  author: string | null
  origin: 'do' | 'undo' | 'redo'
  time: string
  label: string
  summary: string
  of?: string | null
  /** The command's kind (`core.Redaction` for the record of a redaction); absent from an older server. */
  kind?: string
  /** Its content was taken away (D720). */
  redacted?: boolean
}
export interface ChatMessage {
  number: number
  author: string
  to: string
  text: string
  time: string
  at: string | null
  /** Its words were taken away (D724). */
  redacted?: boolean
  /** Who answered, for a message of the ai (E7.11). */
  via?: Via
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

/** What a tag has just taken the view to (E5.20, D551): the thing, and the slide, sheet or paragraph it is on. The view
 * marks the thing for a moment (`POINT_MS`); the way back (`WayBack`) lives longer. */
export interface Pointed {
  id: string
  holder: string | null
}
export const POINT_MS = 3000

/** Where the person was before a jump (D1312): the slide, sheet or paragraph in view, and the place the view said it
 * was showing at the top (a paragraph id, a cell, a slide id: the view's own words; `null` if it said none). It lasts
 * until it is used, the person types or clicks into the text, or the next jump takes its place. */
export interface WayBack {
  holder: string | null
  anchor: string | null
}

/** A request to the view to scroll to a place it reported earlier; `nonce` changes with every request, so that asking
 * for the same place twice is seen twice. */
export interface ScrollBack {
  anchor: string
  nonce: number
}

export const rowKey = (item: Item): string => (item.kind === 'change' ? `c:${item.revision}` : `m:${item.number}`)

/** What all three apps keep of the object layer, the styles, the palette and the language, the same way (D1432). An app's
 *  state narrows the types (its own anchor, its own style type). */
export interface ObjectLayerState {
  /** The objects, by id. */
  objects: Record<string, VisualObject>
  /** By holder (a sheet, a paragraph, a slide): the ids of its objects, the one in front last. */
  order: Record<string, string[]>
  /** The decoded pictures the document holds, by id. */
  images: Record<string, ImageAsset>
  /** The outlines the shapes among the objects are drawn with, by id. */
  shapes: Record<string, { id: string }>
  /** The document's styles, by id, in the order the server lists them; they carry the resolved colours (D200). */
  styles: Record<string, { id: string }>
  /** The document's colour roles and how they read against each other (D200). */
  palette: PaletteEvent | null
  /** The language the document is written in (D915), a BCP 47 tag; `null` when not set, `undefined` for a server that
   *  does not know languages. */
  language: string | null | undefined
}

export interface BaseState extends ObjectLayerState {
  /** Which app the document belongs to (`computes`, `composes`): the server says so when it welcomes us. */
  app: string
  /** The server's own address (`host` or `host:port`, as `location.host`/`socketUrl` use it) — whichever one this
   *  session actually opened a socket to, not necessarily the page's own (E3.11, "knowing which server you're on";
   *  the Open dialog can connect to a bookmarked server other than the one the page was loaded from). Blank only
   *  before the first connection has told us. */
  host: string
  /** How the AI treats this person's requests in this document (D262): the person's own choice, kept in this browser. */
  aiMode: AiMode
  status: 'idle' | 'connecting' | 'open' | 'reconnecting' | 'waiting' | 'closed'
  error: string
  me: { user: string; role: string; color: string }
  doc: string
  /** The branch of the history the document is on now. */
  branch: string
  revision: string | null
  people: Person[]
  presence: Record<string, { regions: Region[]; locked: boolean }>
  typing: string[]
  entries: Step[]
  chat: ChatMessage[]
  /** What has left the document (exports, prints, PDFs), oldest first; empty for a viewer, who is never sent it (D1271). */
  audit: AuditRow[]
  /** What the owners decided about Claude here, and who answers `@ai` now (E7.11); `null` for a server that does not know. */
  consent: ConsentView | null
  checkpoints: CheckpointInfo[]
  canUndo: boolean
  canRedo: boolean
  undoLabel: string
  redoLabel: string
  notice: Notice | null
  /** Every branch of the document's history: the active one, and the ones a restore left behind (E3.8). */
  branches: BranchInfo[]
  /** A restore/switch suggestion waiting for everybody's answer, if one is open right now (E3.7). */
  proposal: RestoreProposal | null
  /** How silence at a suggestion's deadline is read: `consensus` (must actively agree) or `veto` (must object). */
  restorePolicy: 'consensus' | 'veto'
  /** The playhead, while the person looks at the document as it was; `null` in the present. */
  replay: ReplayState | null
  /** The redaction being previewed (D721): the token the views read its state with, and the places to mark. */
  preview: { plan: string; regions: Region[] } | null
  /** The names things were given since the document was loaded (`thing_renamed`), by id: a tag shows the name now. */
  renamed: Record<string, string>
  /** The thing a tag in the chat just took the view to, for the view to mark. */
  pointed: Pointed | null
  /** The way back after a jump (D1312), `null` when there is none. */
  wayBack: WayBack | null
  /** Set by `goBack`: the place the view is asked to scroll to. */
  scrollBack: ScrollBack | null
  /** What the server can make as a container (`container_types`); empty for a server that makes none (D560). */
  containerTypes: RenderType[]
  /** The definitions of the containers the document holds, by id; the text is the truth (D390). */
  containers: Record<string, ContainerDef>
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
    branch: 'main',
    revision: null,
    people: [],
    presence: {},
    typing: [],
    entries: [],
    chat: [],
    audit: [],
    consent: null,
    checkpoints: [],
    canUndo: false,
    canRedo: false,
    undoLabel: '',
    redoLabel: '',
    notice: null,
    branches: [],
    proposal: null,
    restorePolicy: 'consensus',
    replay: null,
    preview: null,
    renamed: {},
    pointed: null,
    wayBack: null,
    scrollBack: null,
    containerTypes: [],
    containers: {},
    renderOutcomes: {},
    objects: {},
    order: {},
    images: {},
    shapes: {},
    styles: {},
    palette: null,
    language: undefined,
  }
}

/** What `download_claudia` returns: the sealed Claudia file as base64, and what it holds (`content`, and for an owner
 * or an editor `history` and `chat`). */
type UndoState = { can_undo: boolean; can_redo: boolean; undo_label: string; redo_label: string }

export interface SealedFile {
  format: 'claudia'
  filename: string
  content_type: string
  data: string
  parts: string[]
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
  private previewLink: PlannedLink | null = null
  /** A redaction was just heard of; the `rebuilt` that follows it is the same news. */
  private redactionHeard = false
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
      if (error instanceof ProtocolError && error.code === 'sealed') {
        // The server holds no key to this document yet and a viewer cannot bring it up (D101, D1262): wait for the
        // editor or owner who will, and open by ourselves as soon as one has.
        this.state.status = 'waiting'
        this.state.error = closeMessage(4423)
        this.track(this.reconnect())
        return
      }
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
    s.branch = w.branch
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
    for (let attempt = 0; this.waitingToConnect(); attempt++) {
      await sleep(this.retryDelays[Math.min(attempt, this.retryDelays.length - 1)] ?? 1000)
      if (!this.waitingToConnect()) return
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

  /** Is the session trying to get back (after a loss) or to get in (a sealed document)? */
  private waitingToConnect(): boolean {
    return this.state.status === 'reconnecting' || this.state.status === 'waiting'
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
    this.dropPreview()
    this.state.renamed = {}
    const link = this.need()
    const s = this.state
    // A viewer holds the content key only, and the server keeps the history and the chat from her (D1261).
    const reads = s.me.role !== 'viewer'
    const [entries, chat, checkpoints, history, branches, restorePolicy, containerTypes, definitions, audit, consent] = await Promise.all([
      reads ? link.request<Step[]>('log', { limit: LOG_LIMIT }) : Promise.resolve<Step[]>([]),
      reads ? link.request<ChatMessage[]>('chat_log', { limit: LOG_LIMIT }) : Promise.resolve<ChatMessage[]>([]),
      reads ? link.request<CheckpointInfo[]>('checkpoints') : Promise.resolve<CheckpointInfo[]>([]),
      reads
        ? link.request<UndoState>('history')
        : Promise.resolve<UndoState>({ can_undo: false, can_redo: false, undo_label: '', redo_label: '' }),
      reads ? link.request<BranchInfo[]>('branches') : Promise.resolve<BranchInfo[]>([]),
      reads
        ? link.request<{ policy: 'consensus' | 'veto' }>('restore_policy')
        : Promise.resolve<{ policy: 'consensus' | 'veto' }>({ policy: 'consensus' }),
      this.optional<{ types: RenderType[] }>('container_types'),
      this.optional<ContainerDef[]>('containers'),
      reads ? this.optional<AuditRow[]>('audit_log') : Promise.resolve<AuditRow[] | null>(null),
      this.optional<ConsentView>('ai_consent'),
      this.loadApp(),
    ]).then(([e, c, k, h, l, p, rt, rd, au, co]) => [e, c, k, h, l, p, rt, rd, au, co] as const)
    s.entries = entries
    s.chat = chat
    s.audit = audit ?? []
    s.consent = consent
    s.checkpoints = checkpoints
    s.canUndo = history.can_undo
    s.canRedo = history.can_redo
    s.undoLabel = history.undo_label
    s.redoLabel = history.redo_label
    s.branches = branches
    s.restorePolicy = restorePolicy.policy
    s.containerTypes = containerTypes?.types ?? []
    s.containers = Object.fromEntries((definitions ?? []).map((d) => [d.id, d]))
    s.renderOutcomes = outcomesOf(definitions ?? [])
    const last = entries.at(-1)
    if (last) s.revision = last.revision
    else if (!reads) s.revision = (await link.request<{ revision: string | null }>('ping')).revision ?? s.revision
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
    // while looking at the past or at a preview, the present does not disturb the views
    if (!s.replay && !s.preview && (this.onObjectLayerEvent(name, data) || this.onAppEvent(name, data))) return
    switch (name) {
      case 'command':
        s.revision = data.revision
        // A viewer is told the revision alone (D1261): there is no step to list.
        if (s.me.role !== 'viewer' && !s.entries.some((e) => e.revision === data.revision)) {
          if (s.replay) s.replay.newer++
          s.entries.push(data)
          if (s.entries.length > LOG_LIMIT) s.entries.shift()
        }
        break
      case 'thing_renamed':
        s.renamed[data.id] = data.name
        break
      case 'container':
        this.onContainer(data.id, data.definition)
        break
      case 'render_result':
        s.renderOutcomes[data.id] = toOutcome(data)
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
      case 'redacted':
        this.redactionHeard = true
        this.notice(t('Part of the history was redacted. The document was reloaded.'), 'info')
        this.track(this.reload())
        break
      case 'rebuilt':
        if (this.redactionHeard) {
          this.redactionHeard = false // (the reload of the redaction shows the rebuilt state already)
          break
        }
        this.notice(t('The document changed under you (it went back to a checkpoint or was rebuilt). It was reloaded.'), 'warning')
        this.track(this.reload())
        break
      case 'branch':
        this.notice(t('The document changed under you (it went back to a checkpoint or was rebuilt). It was reloaded.'), 'warning')
        this.track(this.reload())
        break
    }
  }

  private onContainer(id: string, definition: ContainerDef | null) {
    const s = this.state
    if (!definition) {
      delete s.containers[id]
      delete s.renderOutcomes[id]
      return
    }
    const before = s.containers[id]
    if (before && (before.source !== definition.source || JSON.stringify(before.params) !== JSON.stringify(definition.params))) delete s.renderOutcomes[id]
    s.containers[id] = definition
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
    } else if (message.kind === 'audit_recorded') {
      s.audit = [...s.audit, message.data as AuditRow]
    } else if (message.kind === 'ai_consent_changed') {
      this.track(this.readConsent()) // who answers now changes with it: ask, rather than work it out here
    } else if (message.kind === 'role_changed') {
      if (message.data.user === s.me.user) {
        this.notice(t('Your role in this document is now “{role}”.', { role: roleName(message.data.role) }))
        this.track(this.reconnectNow())  // the server holds fewer keys for us now, or more: start again with what we may see
      } else {
        this.notice(t('{user} may now “{role}”.', { user: message.data.user, role: roleName(message.data.role) }))
      }
    } else if (message.kind === 'person_removed') {
      if (message.data.user === s.me.user) {
        this.notice(t('You are no longer a person of this document.'), 'warning')
        this.close()
      } else {
        this.notice(t('{user} was removed from this document.', { user: message.data.user }))
      }
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

  // ------------------------------------------------------------------------------ where I am, and holding what I work on
  /** The place last shown to the others, in few characters, so that the same place is not sent twice. */
  private shownWhere = ''
  private holdingRegions = false

  /** Show the others where I am; `where` says it in few characters so that the same place is not sent twice. */
  protected async showRegions(where: string, regions: Region[]): Promise<void> {
    if (where === this.shownWhere || this.state.status !== 'open') return
    this.shownWhere = where
    try {
      await this.need().request('presence', { regions })
    } catch {
      this.shownWhere = '' // not important enough to bother the person; the next move tries again
    }
  }

  /** Hold these regions so that nobody else changes them; false after telling the person why not. */
  protected async holdRegions(regions: Region[]): Promise<boolean> {
    if ((await this.attempt('lock', { regions })) === false) return false
    this.holdingRegions = true
    this.shownWhere = ''
    return true
  }

  /** Let go of what I hold, if anything. */
  protected async releaseRegions(): Promise<void> {
    if (!this.holdingRegions) return
    this.holdingRegions = false
    this.shownWhere = ''
    try {
      await this.need().request('unlock')
    } catch {
      /* the lock runs out by itself */
    }
  }

  protected need(): LinkLike {
    if (!this.link) throw new ProtocolError('closed', 'not connected')
    if (this.state.replay) return (this.replayLink ??= new PastLink(this.link, () => this.replayShown))
    if (this.state.preview) return (this.previewLink ??= new PlannedLink(this.link, () => this.state.preview?.plan ?? ''))
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
    if (s.replay || s.preview || s.status !== 'open' || s.entries.length === 0) return
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

  // ------------------------------------------------------------------------------ redacting (E3.14, D720–D728)
  /** Work out what redacting `picked` would do (D721): nothing changes. A sentence instead of a plan when it cannot be,
   * for the dialog to show in place (a notice would sit behind it). */
  async planRedaction(picked: Picked): Promise<RedactionPlan | string> {
    try {
      return await this.need().request<RedactionPlan>('redaction_plan', { ...requestOf(picked), state: false })
    } catch (error) {
      if (error instanceof ProtocolError && error.code !== 'closed') return error.message
      this.explain(error)
      return t('Not connected to the server.')
    }
  }

  /** Show the document as `plan` would leave it, with the places it changes marked, until `endPreview`. A plan that is
   * not allowed, or changes nothing people see, shows the present. */
  async previewRedaction(plan: RedactionPlan): Promise<void> {
    const s = this.state
    await this.stopReplay()
    if (!plan.plan || !plan.changes_now) return this.endPreview()
    s.preview = { plan: plan.plan, regions: plan.regions ?? [] }
    this.previewLink = null
    await this.track(this.loadApp())
    if (s.preview?.plan === plan.plan) this.followReplay(s.preview.regions)
  }

  /** Back to the present after a preview. */
  async endPreview(): Promise<void> {
    if (!this.state.preview) return
    this.dropPreview()
    await this.track(this.loadApp())
  }

  /** For blanking part of an imported workbook (D723): the part a range the person wrote names, on the sheet on show;
   * `null` where the app has no cells, or the text is not a range. */
  redactionRangePart(_range: string): string | null {
    return null
  }

  private dropPreview(): void {
    this.state.preview = null
    this.previewLink = null
  }

  /** Carry out the redaction `plan` showed for `picked` (D229): the dependents it named are the confirmation that they
   * were shown. Afterwards `note`, if any, goes to the chat (D728). The views follow the `redacted` event. */
  async redact(picked: Picked, plan: RedactionPlan, note = ''): Promise<boolean> {
    await this.endPreview()
    const done = await this.attempt('redact', { ...requestOf(picked), dependents: plan.dependents })
    if (done === false) return false
    if (note.trim()) await this.say(note.trim())
    return true
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
  protected holderOf(_id: string): string | null {
    return null
  }
  /** Where the view is now, in the same terms as `holderOf`. */
  protected currentHolder(): string | null {
    return null
  }
  /** Take the view to a slide, sheet or paragraph. */
  protected showHolder(_id: string): void {}
  /** Where a thing is, if it is in this view's document as it is shown. */
  protected async locate(id: string): Promise<{ holder: string | null } | null> {
    return this.things().some((t) => t.id === id) ? { holder: this.holderOf(id) } : null
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
  /** Write the words of an object (a text box or a shape on a slide or in a text) as a person typed them (step G): the
   * server changes only what differs, so the words that stay keep who wrote them. One step in the history (D1232). */
  async writeWords(id: string, text: string): Promise<boolean> {
    return (await this.write('write_words', { id, text })) !== false
  }

  /** Is this thing known to be gone from the document as shown (a tag to it then says so)? */
  isGone(id: string): boolean {
    return this.tracksThings() && this.nameOf(id) === undefined
  }

  /** Give a thing (a sheet, a slide, an object) another name, as one step of the history. The server refuses a name
   * somebody else has, a named range included, with a sentence that is shown here. */
  async renameThing(id: string, name: string): Promise<boolean> {
    return (await this.write('rename_thing', { id, name })) !== false
  }

  /** The next free generic name for a thing of `kind` (an object kind or `slide`), in the language of this window:
   * "Chart 2" when "Chart 1" is taken (D1475). `null` when the server says no (an older one does not know the request);
   * a lost connection is not caught here. */
  async freeName(kind: string): Promise<string | null> {
    try {
      return (await this.need().request<{ name: string }>('free_name', { kind })).name
    } catch (error) {
      if (error instanceof ProtocolError) return null
      throw error
    }
  }

  /** The fonts this document asks for that the server does not have (D1306); an answer that says nothing when the server
   * does not know the request (an older one) or fails, because a banner is no reason to bother anybody. */
  async fontReport(): Promise<FontReport> {
    try {
      return (await this.need().request('font_report', {})) as unknown as FontReport
    } catch {
      return { checked: false, missing: [] }
    }
  }

  /** How many paragraphs have a description an export could write as a review comment (A4): none for an app that has no
   * such option, or a server that does not know the request. The export dialog shows its tick only above zero. */
  async exportDescriptions(): Promise<number> {
    try {
      return ((await this.need().request('export_choices', {})) as unknown as { descriptions: number }).descriptions ?? 0
    } catch {
      return 0
    }
  }

  /** What the Name & describe… dialog shows about a thing (D1317); `false` (with the reason shown) when it is gone. */
  async thingDetails(id: string): Promise<ThingDetails | false> {
    return (await this.attempt('thing_details', { id })) as unknown as ThingDetails | false
  }

  /** The one dialog of Name & describe… (D1317): name and description together, one step in the history, so one Undo
   * takes both back. The server refuses a name somebody else has with a sentence that is shown here. */
  async nameAndDescribe(params: { id: string; name: string; description: string; decorative: boolean }): Promise<boolean> {
    return (await this.write('name_and_describe', { ...params })) !== false
  }

  /** Name everything that has no name (a document from before names) in one step of the history; how many were named. */
  async nameUnnamed(): Promise<number> {
    const done = await this.write('name_unnamed')
    return done === false ? 0 : done.named
  }

  /** What a click on a tag does: take the view to the thing and mark it. For a thing that is gone, a replay at the last
   * moment it was there. */
  async goToThing(id: string, retry = true): Promise<void> {
    const s = this.state
    const found = await this.locate(id)
    if (!found) return this.goToMissing(id, retry)
    const before = { holder: this.currentHolder(), anchor: this.anchorProvider?.() ?? null }
    s.wayBack = before.holder === null && before.anchor === null ? null : before // nothing to go back to: no chip
    if (found.holder !== null && found.holder !== before.holder) this.showHolder(found.holder)
    s.pointed = { id, holder: found.holder }
    const pointed = s.pointed // as the reactive state hands it out: the raw object would never equal what is read back
    setTimeout(() => {
      if (s.pointed === pointed) s.pointed = null
    }, POINT_MS)
  }

  private anchorProvider: (() => string | null) | null = null
  /** The view says where it is showing the top of the document, in its own words, when asked (D1312). */
  setAnchorProvider(provider: (() => string | null) | null): void {
    this.anchorProvider = provider
  }

  /** "Back where I was" (D1312): show the holder the person was in, and ask the view for the place it was at. */
  goBack(): void {
    const s = this.state
    const back = s.wayBack
    if (!back) return
    s.wayBack = null
    s.pointed = null
    if (back.holder) this.showHolder(back.holder)
    if (back.anchor) s.scrollBack = { anchor: back.anchor, nonce: (s.scrollBack?.nonce ?? 0) + 1 }
  }

  /** The person went on from where the jump took them (typed, clicked into the text): the way back is let go. */
  clearBack(): void {
    this.state.wayBack = null
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

  /** The events every app takes in alike (D1432): the objects, their pictures and outlines, the styles, the palette and
   *  the language. `true` if it was one. */
  private onObjectLayerEvent(name: string, data: WireData): boolean {
    const s = this.state
    switch (name) {
      case 'objects': {
        const e = data as ObjectsEvent // typed, so a renamed field is a compile error and not a silent undefined
        for (const o of e.changed) s.objects[o.id] = o
        for (const id of e.removed) delete s.objects[id]
        s.order[e.holder] = e.order
        this.objectsChanged(e)
        return true
      }
      case 'image':
        if (data.asset) s.images[data.id] = data.asset as ImageAsset
        else delete s.images[data.id]
        return true
      case 'shape':
        if (data.definition) s.shapes[data.id] = data.definition as { id: string }
        else delete s.shapes[data.id]
        return true
      case 'styles':
        // A style a colleague changed, and a palette role anybody changed, both arrive here: the styles carry the
        // resolved colours a document is drawn with, and a client cannot work them out for itself (D200).
        s.styles = Object.fromEntries((data.styles as { id: string }[]).map((x) => [x.id, x]))
        this.stylesChanged()
        return true
      case 'palette':
        // Only the styles are drawn from, and they arrive with the event above; the roles are kept for the controls
        // that offer them by name (D200).
        s.palette = data as PaletteEvent
        return true
      case 'language':
        s.language = (data.language as string | null) ?? null
        return true
    }
    return false
  }

  /** What else an app does when objects of one holder changed (the event is in the state already). */
  protected objectsChanged(_event: ObjectsEvent): void {}

  /** What else an app does when the styles changed (they are in the state already). */
  protected stylesChanged(): void {}

  // ------------------------------------------------------------------------------ the object layer, the styles, the palette
  /** The styles as a style menu wants them, in the order the server lists them. */
  styleViews() {
    return Object.values(this.state.styles) as S['styles'][string][]
  }

  /** Every object of the document, for the use counts beside the style names. The client's `VisualObject` is flat
   *  (`ObjectBody & { anchor }`), so an object is already a body. */
  bodies(): ObjectBody[] {
    return Object.values(this.state.objects)
  }

  /** Put a picture from disk at `where` (the app's holder and place, as the wire has them, and the size); its id, or
   *  `null` after telling the person why not. `data` is the file's bytes, base64; `sourcePath` is the file's full path
   *  if the caller could get one (a plain web browser cannot) and `null` if not. */
  protected async putPicture(
    picture: { data: string; alt: string; sourceName: string; sourcePath: string | null; decorative?: boolean; fit?: boolean },
    where: Record<string, unknown>,
  ): Promise<string | null> {
    const done = await this.write('add_image', {
      ...where,
      data: picture.data,
      alt: picture.alt,
      source_name: picture.sourceName,
      source_path: picture.sourcePath,
      ...(picture.decorative ? { decorative: true } : {}),
      ...(picture.fit ? { fit: true } : {}), // from a file: the server sizes it (D1332)
    })
    return done === false ? null : (done.object as string)
  }

  /** Turn an object to `rotation` whole degrees clockwise about its centre (D1021): one step in the history. The server
   *  keeps it where it must be (on its slide or page, D1022) and refuses a turn that cannot fit, or a chart's. */
  async rotateObject(id: string, rotation: number): Promise<boolean> {
    return (await this.write('rotate_object', { id, rotation })) !== false
  }

  /** Say what an object is to someone who cannot see it, or that it is only decoration (BITV 1.1.1); its own step in the
   *  history. A picture needs one or the other, which the server insists on. */
  async describeObject(id: string, description: string, decorative: boolean): Promise<boolean> {
    return (await this.write('describe_object', { id, ...describeParams(description, decorative) })) !== false
  }

  async removeObject(id: string): Promise<boolean> {
    return (await this.write('remove_object', { id })) !== false
  }

  /** Change a style for everything that has it — and for the styles based on it, where they say nothing (D73). */
  async changeStyle(style: string, edit: CssEdit): Promise<boolean> {
    return (await this.write('change_style', { style, ...edit })) !== false
  }

  async renameStyle(style: string, name: string): Promise<boolean> {
    return (await this.write('rename_style', { style, name })) !== false
  }

  /** Give a colour role another colour: every style that meant it follows, and so does every object (D200). */
  async setRole(role: string, colour: string): Promise<boolean> {
    return (await this.write('set_role', { role, colour })) !== false
  }

  /** Put a whole palette in place of this document's — what "the colours it started with" does (D200). */
  async replacePalette(roles: ColourRole[]): Promise<boolean> {
    return (await this.write('replace_palette', { roles })) !== false
  }

  /** What the server makes of this CSS text, line by line. A read: viewers may ask it too. */
  async checkCss(text: string): Promise<CssCheck | null> {
    try {
      return await this.need().request<CssCheck>('check_css', { text })
    } catch {
      return null
    }
  }

  /** Say which language the document is written in (D915), or `null` for not known: one step, for everybody. */
  async setLanguage(language: string | null): Promise<boolean> {
    return (await this.write('set_language', { language })) !== false
  }

  // ------------------------------------------------------------------------------ changing the document (D1432)
  /** Whether this person may only look: a viewer, or anybody while looking at the past or at a preview. */
  get readOnly(): boolean {
    return lookOnly(this.state)
  }

  /** Refuse a change for someone who may only look, and tell her so; `true` when refused. Nothing is sent. */
  protected refused(): boolean {
    if (!this.readOnly) return false
    this.notice(t('You can only look at this document.'), 'warning')
    return true
  }

  /** Run a change. An app whose changes must wait for something (composes: the words still being typed) overrides it. */
  protected run<T>(job: () => Promise<T>): Promise<T> {
    return job()
  }

  /** The one door every change of the document goes through (D1432): refused before anything is sent for someone who
   *  may only look (CODE-75); otherwise sent through `run`, based on the revision she sees when it leaves. */
  protected async write(method: string, params: Record<string, unknown> = {}): Promise<WireData | false> {
    if (this.refused()) return false
    return this.run(() => this.attempt(method, { ...params, base: this.state.revision }))
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
    const done = await this.write('search_replace', { query, kinds, scope, leave })
    return done === false ? false : (done as unknown as ReplaceAnswer)
  }

  // ------------------------------------------------------------------------------ containers (D560)
  /** Puts a container of `type` at `where` (the app's own place: `{slide, x, y}`, …), its first text the type's example.
   *  Returns the new object's id, or `null` — after telling why — if it was not made. With `fit`, `size` is only the
   *  most it may take: its first picture is shown at its own size if that is smaller (D1229). */
  async addContainerAt(type: string, where: Record<string, unknown>, size = { w: 420, h: 240 }, source?: string, fit = false): Promise<string | null> {
    const kind = this.state.containerTypes.find((k) => k.type === type)
    if (!kind) return null
    const done = await this.write('add_container', { ...where, ...size, type, source: source ?? kind.example ?? '', params: {}, alt: null, ...(fit ? { fit: true } : {}) })
    return done === false ? null : (done.object as string)
  }

  /** Changes the text of a container; a text that is the same as it is is not sent. `false` after saying why not. */
  async setContainerSource(id: string, source: string, params: Record<string, unknown> | null = null): Promise<boolean> {
    if (this.state.containers[id]?.source === source && !params) return true
    return (await this.write('set_container_source', { id, source, params })) !== false
  }

  // ------------------------------------------------------------------------------ numbering (E9.21, E9.22)
  // The same requests in every app whose paragraphs can be numbered (`claudia_server.structure_methods`); the markers
  // come back as `labels` events, the lists as `lists` and the schemes as `schemes`.
  /** Number every heading style (in creates: every slide title), or no longer. */
  async numberHeadings(on: boolean): Promise<boolean> {
    return (await this.write('number_headings', { on })) !== false
  }

  /** A new scheme drawn as `like` is, named `name`; its id, or `null` after saying why not. */
  async newScheme(like: string, name: string): Promise<string | null> {
    const done = await this.write('new_scheme', { like, name })
    return done === false ? null : (done.scheme as string)
  }

  /** Give a scheme another definition (as the server sends it). */
  async changeScheme(scheme: SchemeInfo): Promise<boolean> {
    return (await this.write('change_scheme', { scheme })) !== false
  }

  /** Draw a built-in scheme as it was built in again. */
  async resetScheme(scheme: string): Promise<boolean> {
    return (await this.write('reset_scheme', { scheme })) !== false
  }

  /** Take a scheme no list uses out of the document. */
  async removeScheme(scheme: string): Promise<boolean> {
    return (await this.write('remove_scheme', { scheme })) !== false
  }

  /** Number a heading style in a list (`"none"`: not numbered; `null`: as its parent). */
  async setStyleNumbering(style: string, numbering: string | null): Promise<boolean> {
    return (await this.write('set_style_numbering', { style, numbering })) !== false
  }

  // ------------------------------------------------------------------------------ tables of contents (E9.31)
  /** Give a table of contents (in creates: an agenda) other options; the entries come back as a `generated` event. */
  async setContents(paragraph: string, options: Toc): Promise<boolean> {
    return (await this.write('set_contents', { paragraph, options })) !== false
  }

  // ------------------------------------------------------------------------------ deleting and hiding styles (E1.10)
  /** What deleting a style would do, so that the dialog can say it in words first (`style_deletion`, D226). A read: a
   *  server that cannot say makes no noise, and the dialog then offers no Delete…. */
  async styleDeletion(style: string): Promise<StyleDeletion | null> {
    try {
      return await this.need().request<StyleDeletion>('style_deletion', { style })
    } catch {
      return null
    }
  }

  /** Delete a style in one step (D785): `how` and the style that `target`s its place (null only for a style that
   *  nothing has). A refusal that is about this very deletion comes back as its sentence; anything else is told as a
   *  notice, and is `false`. */
  async deleteStyle(style: string, how: DeleteHow, target: string | null): Promise<Deleted | false> {
    if (this.refused()) return false
    const params: Record<string, unknown> = { style, how, base: this.state.revision }
    if (target) params.target = target
    try {
      const done = await this.need().request<{ stand_in: string | null }>('delete_style', params)
      return { standIn: done.stand_in ?? null }
    } catch (error) {
      if (error instanceof ProtocolError && error.code === 'command_error') return { refused: error.message }
      this.explain(error)
      return false
    }
  }

  /** Hide a style from the menus a style is picked from, or show it again (D780). */
  async hideStyle(style: string, hidden: boolean): Promise<boolean> {
    return (await this.write('hide_style', { style, hidden })) !== false
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

  /** Owners: allow Claude to be sent this document's content when somebody asks `@ai` (`true`), or withdraw it. What the
   *  server answers is the state; every window of the document hears of the change as it happens (E7.11, D264). */
  async setAiConsent(allowed: boolean): Promise<boolean> {
    const view = await this.attempt('set_ai_consent', { allowed })
    if (view === false) return false
    this.state.consent = view as ConsentView
    return true
  }

  private async readConsent(): Promise<void> {
    const view = await this.optional<ConsentView>('ai_consent')
    if (view) this.state.consent = view
  }

  /** The person's choice of how the AI treats their requests in this document; kept for next time. */
  setAiMode(mode: AiMode): void {
    this.state.aiMode = mode
    storeAiMode(this.state.host, this.state.doc, mode, this.storage)
  }

  async addUser(name: string, password: string, role: 'editor' | 'viewer'): Promise<boolean> {
    return (await this.attempt('add_user', { name, password, role })) !== false
  }

  /** Owners: give `name` the role `editor` or `viewer`. Lowering an editor renews the document's history and chat keys
   *  (`renewed`). `false` after telling the person why not. */
  async changeRole(name: string, role: 'editor' | 'viewer'): Promise<{ user: string; role: string; renewed: boolean } | false> {
    return await this.attempt('change_role', { name, role })
  }

  /** Owners: take `name` out of the document and renew the keys she held. `false` after telling the person why not. */
  async removePerson(name: string): Promise<boolean> {
    return (await this.attempt('remove_person', { name })) !== false
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
    return await this.recorded(await this.attempt('export_content'))
  }

  /** The document as Claudia's own sealed file, for File ▸ Download (D110): the whole file for an owner, the file
   * with only your own key slot for an editor, and for a viewer only what the content key opens. `data` is base64.
   * Confirmed with your own current password, which is also what finds your slot. `false` after saying why not. */
  async downloadClaudia(password: string): Promise<SealedFile | false> {
    return (await this.attempt('download_claudia', { password })) as SealedFile | false
  }

  /** The document's current content as bytes of a Word, Excel, PowerPoint or OpenDocument file (`format` is one of
   * what the app supports: "docx", "odt", "xlsx", "ods", "pptx" or "odp"), as `{format, content_type, data}` with
   * `data` base64 — no history, no chat; just the document as it stands now. With `trackedChanges` the text app also writes its
   * open suggestions as tracked changes, dated and signed (D411); the parameter is only sent when asked for, because
   * the other apps do not know it. An OpenDocument answer also has `losses`: what the file could not hold, as
   * `{kind, detail, count}` codes (nothing shows them yet: the screen for that is designed first). */
  async exportOffice(format: string, options: { trackedChanges?: boolean; descriptionComments?: boolean } = {}): Promise<ExportedFile | false> {
    const params: Record<string, unknown> = { format }
    if (options.trackedChanges) params.tracked_changes = true
    if (options.descriptionComments) params.description_comments = true
    return await this.recorded(await this.attempt('export_office', params))
  }

  /** File ▸ Export… ▸ Claudia, unencrypted (D1270): one zip anybody can read, with the content and, if an owner asks
   * (`includeHistory`), the history with its hidden branches and the chat. No keys, no passwords, no people. The server
   * records the export for you (D1271). `false` after saying why not (an editor or a viewer asking for the history). */
  async exportClaudia(includeHistory = false): Promise<UnprotectedFile | false> {
    return await this.recorded(await this.attempt('export_claudia', includeHistory ? { include_history: true } : {}))
  }

  /** Tell the server that this window has just printed or saved a PDF of the document (D1271), so that it is
   * recorded for you: `kind` is `print` or `pdf`. Called when the file is saved or the page sent to the printer, not
   * when the preview opens. It is a report of what Claudia's own screens did, not a guarantee. `false` after saying
   * why not (a server that does not record, or more reports than it takes in a minute). */
  async reportOutput(kind: 'print' | 'pdf', pages: number): Promise<boolean> {
    return (await this.recorded(await this.attempt('report_output', { kind, format: kind, pages }))) !== false
  }

  /** `answer` of something that leaves the document, passed on: the server has recorded it, and the other windows are
   * told (D1271) but this one, whose own request it was, is not, so it reads the record again. Owners and editors only:
   * a viewer is never sent the record (D1261). */
  private async recorded<T>(answer: T | false): Promise<T | false> {
    if (answer !== false && this.state.me.role !== 'viewer') {
      const audit = await this.optional<AuditRow[]>('audit_log')
      if (audit) this.state.audit = audit
    }
    return answer
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

  // ------------------------------------------------------------------------------ branches, and restoring with consent (E3.7, E3.8)
  /** A read-only look at any line (active or hidden), without switching to it: for previewing before suggesting. */
  async peekBranch(branch: string): Promise<{ branch: string; revision: string | null; app: string; state_schema: string; state: unknown } | false> {
    return await this.attempt('peek_branch', { branch })
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
  async proposeSwitch(branch: string): Promise<boolean> {
    return (await this.attempt('propose_switch', { branch })) !== false
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
