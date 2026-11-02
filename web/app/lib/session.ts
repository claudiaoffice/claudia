// One person's view of one document: the replica the screen draws, kept up to date from the server's events.
// All changes go to the server as requests; nothing is believed until the server's events say it happened.
import { reactive } from 'vue'
import { closeMessage, ProtocolError, type LinkLike, type Region, type Welcome } from './protocol'
import { type Content } from './cells'

export const CHUNK_ROWS = 64
export const CHUNK_COLS = 16
const COL_STRIDE = 16_384
const LOG_LIMIT = 500
const FINAL_CLOSES = new Set([4400, 4401, 4403, 4404, 4408, 1013])

export interface Person {
  id: number
  user: string
  color: string
}
export interface SheetInfo {
  id: string
  name: string
  rows: number
  cols: number
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
export interface State {
  status: 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed'
  error: string
  me: { user: string; role: string; color: string }
  doc: string
  line: string
  revision: string | null
  people: Person[]
  presence: Record<string, { regions: Region[]; locked: boolean }>
  typing: string[]
  sheets: SheetInfo[]
  activeSheet: string
  cells: Record<string, Map<number, Content>>
  generation: number
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

const key = (row: number, col: number) => row * COL_STRIDE + col
const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

export class Session {
  readonly state: State = reactive({
    status: 'idle',
    error: '',
    me: { user: '', role: '', color: '' },
    doc: '',
    line: 'main',
    revision: null,
    people: [],
    presence: {},
    typing: [],
    sheets: [],
    activeSheet: '',
    cells: {},
    generation: 0,
    entries: [],
    chat: [],
    checkpoints: [],
    canUndo: false,
    canRedo: false,
    undoLabel: '',
    redoLabel: '',
    notice: null,
  }) as State

  private link: LinkLike | null = null
  private loaded = new Set<string>()
  private inflight = new Map<string, Promise<void>>()
  private tasks = new Set<Promise<unknown>>()
  private noticeCount = 0
  private editing = false
  private shown = ''
  private closing = false
  private retryDelays: number[]

  constructor(
    private makeLink: () => LinkLike,
    options: SessionOptions = {},
  ) {
    this.retryDelays = options.retryDelays ?? [1000, 2000, 4000, 8000]
  }

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
    s.line = w.line
    s.revision = w.revision
    s.people = w.people.map((p) => ({ ...p }))
    s.presence = {}
    for (const p of w.presence) s.presence[p.user] = { regions: p.regions, locked: p.locked }
    s.typing = []
  }

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

  private track<T>(task: Promise<T>): Promise<T> {
    this.tasks.add(task)
    const done = () => this.tasks.delete(task)
    task.then(done, done)
    return task
  }

  // ------------------------------------------------------------------------------ loading
  /** Everything the screen shows except the cells (those are loaded as they come into view). */
  private async reload() {
    const link = this.need()
    const s = this.state
    const [sheets, entries, chat, checkpoints, history] = await Promise.all([
      link.request<SheetInfo[]>('sheets'),
      link.request<Entry[]>('log', { limit: LOG_LIMIT }),
      link.request<ChatMessage[]>('chat_log', { limit: LOG_LIMIT }),
      link.request<CheckpointInfo[]>('checkpoints'),
      link.request<{ can_undo: boolean; can_redo: boolean; undo_label: string; redo_label: string }>('history'),
    ])
    this.forgetCells()
    s.sheets = sheets
    if (!sheets.some((x) => x.id === s.activeSheet)) s.activeSheet = sheets[0]?.id ?? ''
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

  private forgetCells(sheet?: string) {
    const s = this.state
    if (sheet === undefined) {
      s.cells = {}
      this.loaded.clear()
      this.inflight.clear() // what was asked of a connection that is gone will never be answered
    } else {
      delete s.cells[sheet]
      for (const k of [...this.loaded]) if (k.startsWith(`${sheet}:`)) this.loaded.delete(k)
    }
    s.generation++
  }

  cell(sheet: string, row: number, col: number): Content {
    return this.state.cells[sheet]?.get(key(row, col)) ?? null
  }

  /** The positions of the filled cells (that are loaded) inside a rectangle. */
  filledIn(sheet: string, r0: number, c0: number, r1: number, c1: number): [number, number][] {
    const found: [number, number][] = []
    for (const k of this.state.cells[sheet]?.keys() ?? []) {
      const [row, col] = [Math.floor(k / COL_STRIDE), k % COL_STRIDE]
      if (row >= r0 && row <= r1 && col >= c0 && col <= c1) found.push([row, col])
    }
    return found
  }

  /** Load the parts of the sheet that cover this window, unless they are here already. */
  async ensure(sheet: string, row0: number, row1: number, col0: number, col1: number): Promise<void> {
    const jobs: Promise<void>[] = []
    for (let cr = Math.floor(row0 / CHUNK_ROWS); cr <= Math.floor(row1 / CHUNK_ROWS); cr++) {
      for (let cc = Math.floor(col0 / CHUNK_COLS); cc <= Math.floor(col1 / CHUNK_COLS); cc++) {
        jobs.push(this.loadChunk(sheet, cr, cc))
      }
    }
    await Promise.all(jobs)
  }

  private loadChunk(sheet: string, cr: number, cc: number): Promise<void> {
    const id = `${sheet}:${cr}:${cc}`
    if (this.loaded.has(id)) return Promise.resolve()
    const running = this.inflight.get(id)
    if (running) return running
    const generation = this.state.generation
    const [row0, col0] = [cr * CHUNK_ROWS, cc * CHUNK_COLS]
    const job = this.need()
      .request<{ cells: [number, number, Content][] }>('cells', {
        sheet,
        row0,
        row1: row0 + CHUNK_ROWS - 1,
        col0,
        col1: col0 + CHUNK_COLS - 1,
      })
      .then((answer) => {
        if (generation !== this.state.generation) return // everything was reloaded meanwhile
        const map = (this.state.cells[sheet] ??= new Map())
        for (let r = row0; r < row0 + CHUNK_ROWS; r++) for (let c = col0; c < col0 + CHUNK_COLS; c++) map.delete(key(r, c))
        for (const [r, c, content] of answer.cells) map.set(key(r, c), content)
        this.loaded.add(id)
      })
      .finally(() => this.inflight.delete(id))
    this.inflight.set(id, job)
    return job
  }

  // ------------------------------------------------------------------------------ events
  private onEvent(name: string, data: any) {
    const s = this.state
    switch (name) {
      case 'cells': {
        const map = (s.cells[data.sheet] ??= new Map())
        for (const [r, c, content] of data.cells as [number, number, Content][]) {
          if (content === null) map.delete(key(r, c))
          else map.set(key(r, c), content)
        }
        break
      }
      case 'structure':
        this.forgetCells(data.sheet)
        break
      case 'sheets':
        this.track(this.reload())
        break
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
      else s.presence[who] = { regions: message.data.regions, locked: message.data.locked === true }
    } else if (message.kind === 'typing') {
      const others = s.typing.filter((u) => u !== who)
      s.typing = message.data.on ? [...others, who] : others
    }
  }

  // ------------------------------------------------------------------------------ doing things
  notice(text: string, kind: Notice['kind'] = 'info') {
    this.state.notice = { id: ++this.noticeCount, kind, text }
  }

  private need(): LinkLike {
    if (!this.link) throw new ProtocolError('closed', 'not connected')
    return this.link
  }

  /** Run a request; `false` after telling the person why it did not work. */
  private async attempt(method: string, params: Record<string, unknown> = {}): Promise<any | false> {
    try {
      return await this.need().request(method, params)
    } catch (error) {
      this.explain(error)
      return false
    }
  }

  private explain(error: unknown) {
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

  async setCells(sheet: string, cells: { row: number; col: number; input: string }[]): Promise<boolean> {
    const done = await this.attempt('set_cells', { sheet, cells, base: this.state.revision })
    return done !== false
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

  async addSheet(name: string): Promise<boolean> {
    const done = await this.attempt('add_sheet', { name, base: this.state.revision })
    if (done === false) return false
    this.state.activeSheet = done.sheet
    return true
  }

  async structure(sheet: string, axis: 'row' | 'col', insert: boolean, at: number, count = 1): Promise<boolean> {
    return (await this.attempt('structure', { sheet, axis, insert, at, count, base: this.state.revision })) !== false
  }

  async addUser(name: string, password: string, role: 'editor' | 'viewer'): Promise<boolean> {
    return (await this.attempt('add_user', { name, password, role })) !== false
  }

  // -- where I am, and holding a cell while I type into it
  private region(sheet: string, r0: number, c0: number, r1: number, c1: number): Region {
    const ref = (row: number, col: number) => ({ row, col, sheet })
    return { kind: 'cells', range: { first: ref(Math.min(r0, r1), Math.min(c0, c1)), last: ref(Math.max(r0, r1), Math.max(c0, c1)) } }
  }

  async show(sheet: string, r0: number, c0: number, r1 = r0, c1 = c0): Promise<void> {
    const where = JSON.stringify([sheet, r0, c0, r1, c1])
    if (where === this.shown || this.state.status !== 'open') return
    this.shown = where
    try {
      await this.need().request('presence', { regions: [this.region(sheet, r0, c0, r1, c1)] })
    } catch {
      this.shown = '' // not important enough to bother the person; the next move tries again
    }
  }

  async beginEdit(sheet: string, row: number, col: number): Promise<boolean> {
    if ((await this.attempt('lock', { regions: [this.region(sheet, row, col, row, col)] })) === false) return false
    this.editing = true
    this.shown = ''
    return true
  }

  async endEdit(): Promise<void> {
    if (!this.editing) return
    this.editing = false
    this.shown = ''
    try {
      await this.need().request('unlock')
    } catch {
      /* the lock runs out by itself */
    }
  }
}
