// What every app's session has in common: the connection with its reconnecting, who is here, the history, the chat,
// checkpoints, undo/redo. The replica of the document itself belongs to the app (Session: cells, TextSession: text).
// All changes go to the server as requests; nothing is believed until the server's events say it happened.
import { reactive } from 'vue'
import { closeMessage, ProtocolError, type LinkLike, type Region, type Welcome } from './protocol'

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
export interface BaseState {
  /** Which app the document belongs to (`computes`, `composes`): the server says so when it welcomes us. */
  app: string
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
}

export interface SessionOptions {
  retryDelays?: number[]
}

export const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

function initialState(): BaseState {
  return {
    app: '',
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
  }
}

export abstract class BaseSession<S extends BaseState = BaseState> {
  readonly state: S

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
    this.state = reactive({ ...initialState(), ...app }) as unknown as S
  }

  /** Load what the app shows of the document (called with every (re)load, next to the common parts). */
  protected abstract loadApp(): Promise<void>
  /** Handle an event that only the app knows; `true` if it was one. */
  protected abstract onAppEvent(name: string, data: any): boolean

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
    this.onWelcome()
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
        if (error instanceof ProtocolError && error.code !== 'closed') {
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
    const [entries, chat, checkpoints, history] = await Promise.all([
      link.request<Entry[]>('log', { limit: LOG_LIMIT }),
      link.request<ChatMessage[]>('chat_log', { limit: LOG_LIMIT }),
      link.request<CheckpointInfo[]>('checkpoints'),
      link.request<{ can_undo: boolean; can_redo: boolean; undo_label: string; redo_label: string }>('history'),
      this.loadApp(),
    ]).then(([e, c, k, h]) => [e, c, k, h] as const)
    s.entries = entries
    s.chat = chat
    s.checkpoints = checkpoints
    s.canUndo = history.can_undo
    s.canRedo = history.can_redo
    s.undoLabel = history.undo_label
    s.redoLabel = history.redo_label
    const last = entries.at(-1)
    if (last) s.revision = last.revision
  }

  // ------------------------------------------------------------------------------ events
  private onEvent(name: string, data: any) {
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
      case 'branch':
      case 'rebuilt':
      case 'redacted':
        this.notice('The document changed under you (it went back to a checkpoint or was rebuilt). It was reloaded.', 'warning')
        this.track(this.reload())
        break
    }
  }

  private onEphemeral(message: { kind: string; sender: string | null; data: any }) {
    const s = this.state
    const who = message.sender ?? ''
    if (message.kind === 'presence') {
      if (message.data.gone || !message.data.regions?.length) delete s.presence[who]
      else s.presence[who] = { regions: this.adoptRegions(message.data.regions), locked: message.data.locked === true }
    } else if (message.kind === 'typing') {
      const others = s.typing.filter((u) => u !== who)
      s.typing = message.data.on ? [...others, who] : others
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
  protected async attempt(method: string, params: Record<string, unknown> = {}): Promise<any | false> {
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
}
