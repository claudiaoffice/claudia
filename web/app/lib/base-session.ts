// What every app's session has in common: the connection with its reconnecting, who is here, the history, the chat,
// checkpoints, undo/redo. The replica of the document itself belongs to the app (Session: cells, TextSession: text).
// All changes go to the server as requests; nothing is believed until the server's events say it happened.
import { reactive } from 'vue'
import { closeMessage, ProtocolError, type LineInfo, type LinkLike, type Region, type RestoreProposal, type RestoreResolution, type Welcome, type WireData } from './protocol'

export const LOG_LIMIT = 500
const FINAL_CLOSES = new Set([4400, 4401, 4403, 4404, 4408, 1013])

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
export interface BaseState {
  /** Which app the document belongs to (`computes`, `composes`): the server says so when it welcomes us. */
  app: string
  /** The server's own address (`host` or `host:port`, as `location.host`/`socketUrl` use it) — whichever one this
   *  session actually opened a socket to, not necessarily the page's own (E3.11, "knowing which server you're on";
   *  the Open dialog can connect to a bookmarked server other than the one the page was loaded from). Blank only
   *  before the first connection has told us. */
  host: string
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
}

export interface SessionOptions {
  retryDelays?: number[]
  /** The server this session is to connect to (same shape as `BaseState.host`) — carried into `state.host` so the
   *  connection indicator can show it without reaching back into whatever built the link. */
  host?: string
}

export const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

function initialState(): BaseState {
  return {
    app: '',
    host: '',
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
  }
}

export abstract class BaseSession<S extends BaseState = BaseState> {
  readonly state: S
  /** Was this document made by the very opening that led here? Then its owner is shown the recovery key. */
  justCreated = false

  protected link: LinkLike | null = null
  private tasks = new Set<Promise<unknown>>()
  private noticeCount = 0
  private closing = false
  private retryDelays: number[]

  /** `app` is the app's own part of the state (it becomes reactive together with the common part). */
  constructor(
    private makeLink: () => LinkLike,
    options: SessionOptions,
    app: Omit<S, keyof BaseState>,
  ) {
    this.retryDelays = options.retryDelays ?? [1000, 2000, 4000, 8000]
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
    this.applyWelcome(welcome)
    await this.reload()
    this.state.status = 'open'
    this.state.error = ''
  }

  private applyWelcome(w: Welcome) {
    const s = this.state
    s.me = { user: w.user, role: w.role, color: w.color }
    s.doc = w.doc
    s.app = w.app
    s.line = w.line
    s.revision = w.revision
    s.people = w.people.map((p) => ({ ...p }))
    s.presence = {}
    for (const p of w.presence) s.presence[p.user] = { regions: this.adoptRegions(p.regions), locked: p.locked }
    s.typing = []
    s.proposal = w.proposal
    if (w.returned) this.notice(this.returnedText(w.returned))
    this.onWelcome()
  }

  /** The one-time notice of what happened, while this person was away, to the line they were on (E3.7). */
  private returnedText(r: RestoreResolution): string {
    const verb = r.kind === 'restore' ? 'restored' : 'switched'
    return `While you were away, ${r.by} ${verb} to ${r.label} (agreed: ${r.agreed.join(', ')}).`
  }

  /** What became of the suggestion that was open, for the notice everybody sees once it resolves (E3.7). */
  private resolvedText(p: RestoreProposal, outcome: string): string {
    if (outcome === 'agreed') return `Everybody agreed: now at ${p.label}.`
    if (outcome === 'declined') return `The suggestion to go to ${p.label} was declined.`
    return `The suggestion to go to ${p.label} was withdrawn.`
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
    const link = this.need()
    const s = this.state
    const [entries, chat, checkpoints, history, lines, restorePolicy] = await Promise.all([
      link.request<Entry[]>('log', { limit: LOG_LIMIT }),
      link.request<ChatMessage[]>('chat_log', { limit: LOG_LIMIT }),
      link.request<CheckpointInfo[]>('checkpoints'),
      link.request<{ can_undo: boolean; can_redo: boolean; undo_label: string; redo_label: string }>('history'),
      link.request<LineInfo[]>('lines'),
      link.request<{ policy: 'consensus' | 'veto' }>('restore_policy'),
      this.loadApp(),
    ]).then(([e, c, k, h, l, p]) => [e, c, k, h, l, p] as const)
    s.entries = entries
    s.chat = chat
    s.checkpoints = checkpoints
    s.canUndo = history.can_undo
    s.canRedo = history.can_redo
    s.undoLabel = history.undo_label
    s.redoLabel = history.redo_label
    s.lines = lines
    s.restorePolicy = restorePolicy.policy
    const last = entries.at(-1)
    if (last) s.revision = last.revision
  }

  // ------------------------------------------------------------------------------ events
  private onEvent(name: string, data: WireData) {
    if (this.onAppEvent(name, data)) return
    const s = this.state
    switch (name) {
      case 'command':
        s.revision = data.revision
        if (!s.entries.some((e) => e.revision === data.revision)) {
          s.entries.push(data)
          if (s.entries.length > LOG_LIMIT) s.entries.shift()
        }
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
        this.notice('The document changed under you (it went back to a checkpoint or was rebuilt). It was reloaded.', 'warning')
        this.track(this.reload())
        break
    }
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
      this.notice(`${message.data.user} left this document.`)
    } else if (message.kind === 'owner_changed') {
      this.notice(`${message.data.owner} is now the owner of this document.`)
      this.track(this.reconnectNow())  // our own role may have just changed (we may have been the old owner)
    } else if (message.kind === 'document_deleted') {
      this.notice('This document was deleted by its owner.', 'warning')
      this.close()
    }
  }

  // ------------------------------------------------------------------------------ doing things
  notice(text: string, kind: Notice['kind'] = 'info') {
    this.state.notice = { id: ++this.noticeCount, kind, text }
  }

  protected need(): LinkLike {
    if (!this.link) throw new ProtocolError('closed', 'not connected')
    return this.link
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
    if (!(error instanceof ProtocolError)) return this.notice('Something went wrong.', 'error')
    switch (error.code) {
      case 'locked':
      case 'conflict':
        return this.notice(error.message, 'warning')
      case 'stale':
        this.notice('Your change was not applied: the document changed under you. It was reloaded.', 'warning')
        return void this.track(this.reload())
      case 'forbidden':
        return this.notice('You can only look at this document.', 'warning')
      case 'closed':
        return this.notice('Not connected to the server.', 'error')
      default:
        return this.notice(error.message, 'error')
    }
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
    if (done !== false && !done.saved) this.notice('Nothing has changed since the last checkpoint.')
    return done !== false && done.saved
  }

  async say(text: string): Promise<boolean> {
    return (await this.attempt('chat', { text })) !== false
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

  /** The document's current content as bytes of a Word, Excel or PowerPoint file (`format` is one of what the
   * app supports: "docx", "xlsx" or "pptx"), as `{format, content_type, data}` with `data` base64 — no tracked
   * changes, no history, no chat; just the document as it stands now. */
  async exportOffice(format: string): Promise<{ format: string; content_type: string; data: string } | false> {
    return await this.attempt('export_office', { format })
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
