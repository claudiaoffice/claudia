// One person's view of one workbook: the replica the screen draws, kept up to date from the server's events.
// The connection, history, chat and the rest that every app has live in BaseSession.
import { BaseSession, type BaseState, type SessionOptions } from './base-session'
import { type LinkLike, type Region } from './protocol'
import { type Content } from './cells'
import { type Axis, lineSize } from './line-sizes'

export { DEFAULT_COL_WIDTH, DEFAULT_ROW_HEIGHT } from './line-sizes'

export type {
  BaseState,
  ChatMessage,
  CheckpointInfo,
  Entry,
  Notice,
  Person,
  SessionOptions,
} from './base-session'
export { BaseSession } from './base-session'

export const CHUNK_ROWS = 64
export const CHUNK_COLS = 16
const COL_STRIDE = 16_384

export interface SheetInfo {
  id: string
  name: string
  rows: number
  cols: number
}
export interface State extends BaseState {
  sheets: SheetInfo[]
  activeSheet: string
  cells: Record<string, Map<number, Content>>
  /** Rows (by `sheets[].id`) that were given a height away from `DEFAULT_ROW_HEIGHT` (D135). Sparse: a row not in
   * here shows at the default. */
  rowHeights: Record<string, Map<number, number>>
  /** Same as `rowHeights`, for column widths away from `DEFAULT_COL_WIDTH`. */
  colWidths: Record<string, Map<number, number>>
  generation: number
}

const key = (row: number, col: number) => row * COL_STRIDE + col

export class Session extends BaseSession<State> {
  private loaded = new Set<string>()
  private inflight = new Map<string, Promise<void>>()
  private sizesLoaded = new Set<string>()
  private sizesInflight = new Map<string, Promise<void>>()
  private editing = false
  private shown = ''

  constructor(makeLink: () => LinkLike, options: SessionOptions = {}) {
    super(makeLink, options, { sheets: [], activeSheet: '', cells: {}, rowHeights: {}, colWidths: {}, generation: 0 })
  }

  // ------------------------------------------------------------------------------ loading
  /** The sheets; the cells themselves are loaded as they come into view. */
  protected async loadApp() {
    const s = this.state
    const sheets = await this.need().request<SheetInfo[]>('sheets')
    this.forgetCells()
    s.sheets = sheets
    if (!sheets.some((x) => x.id === s.activeSheet)) s.activeSheet = sheets[0]?.id ?? ''
  }

  /** Forgets a sheet's cells, and with them its row/column sizes — a structural edit (rows or columns inserted or
   * deleted) shifts both the same way, and the server does not echo the shifted sizes back as their own event. */
  private forgetCells(sheet?: string) {
    const s = this.state
    if (sheet === undefined) {
      s.cells = {}
      s.rowHeights = {}
      s.colWidths = {}
      this.loaded.clear()
      this.inflight.clear() // what was asked of a connection that is gone will never be answered
      this.sizesLoaded.clear()
      this.sizesInflight.clear()
    } else {
      delete s.cells[sheet]
      delete s.rowHeights[sheet]
      delete s.colWidths[sheet]
      for (const k of [...this.loaded]) if (k.startsWith(`${sheet}:`)) this.loaded.delete(k)
      this.sizesLoaded.delete(sheet)
      this.sizesInflight.delete(sheet)
    }
    s.generation++
  }

  cell(sheet: string, row: number, col: number): Content {
    return this.state.cells[sheet]?.get(key(row, col)) ?? null
  }

  rowHeight(sheet: string, row: number): number {
    return lineSize(this.state.rowHeights[sheet], row, 'row')
  }

  colWidth(sheet: string, col: number): number {
    return lineSize(this.state.colWidths[sheet], col, 'col')
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

  /** Load a sheet's row and column sizes, unless they are here already (they are sparse, so this is the whole
   * sheet at once rather than chunked like cells). */
  async ensureSizes(sheet: string): Promise<void> {
    if (this.sizesLoaded.has(sheet)) return
    const running = this.sizesInflight.get(sheet)
    if (running) return running
    const job = this.need()
      .request<{ revision: string; rows: [number, number][]; cols: [number, number][] }>('sizes', { sheet })
      .then((answer) => {
        this.state.rowHeights[sheet] = new Map(answer.rows)
        this.state.colWidths[sheet] = new Map(answer.cols)
        this.sizesLoaded.add(sheet)
      })
      .finally(() => this.sizesInflight.delete(sheet))
    this.sizesInflight.set(sheet, job)
    return job
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
  protected onAppEvent(name: string, data: any): boolean {
    const s = this.state
    switch (name) {
      case 'cells': {
        const map = (s.cells[data.sheet] ??= new Map())
        for (const [r, c, content] of data.cells as [number, number, Content][]) {
          if (content === null) map.delete(key(r, c))
          else map.set(key(r, c), content)
        }
        return true
      }
      case 'structure':
        this.forgetCells(data.sheet)
        return true
      case 'sizes': {
        const target = (data.axis as Axis) === 'row' ? (s.rowHeights[data.sheet] ??= new Map()) : (s.colWidths[data.sheet] ??= new Map())
        for (const [i, size] of data.sizes as [number, number | null][]) {
          if (size === null) target.delete(i)
          else target.set(i, size)
        }
        return true
      }
      case 'sheets':
        this.track(this.reload())
        return true
    }
    return false
  }

  // ------------------------------------------------------------------------------ doing things
  async setCells(sheet: string, cells: { row: number; col: number; input: string }[]): Promise<boolean> {
    const done = await this.attempt('set_cells', { sheet, cells, base: this.state.revision })
    return done !== false
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

  /** Set (or, with `null`, clear back to the default) the size of one or more rows or columns in one change.
   * `sizes` is `[index, size | null]` pairs. */
  async resizeLines(sheet: string, axis: Axis, sizes: [number, number | null][]): Promise<boolean> {
    return (await this.attempt('resize_lines', { sheet, axis, sizes, base: this.state.revision })) !== false
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
