// One person's view of one workbook: the replica the screen draws, kept up to date from the server's events.
// The connection, history, chat and the rest that every app has live in BaseSession.
import { BaseSession, type BaseState, type SessionOptions } from './base-session'
import { translate as t } from './i18n'
import { ProtocolError, type LinkLike, type Region, type WireData } from './protocol'
import { holderOf, firstFocus } from './replay'
import type { Thing } from './tags'
import { MAX_COLS, MAX_ROWS, type Content } from './cells'
import type { CellRange } from './cell-styles'
import type { NumberFormatDef } from './number-format'
import type { ImageAsset } from './images'
import type { CellAnchor, ObjectsEvent, PaletteEvent, StyleDef, StyleModel, StyleTarget, VisualObject } from './objects'
import type { Frame } from './geometry'
import type { Shown } from './references'
import type { ShapeDef, SlideObject } from './slide-session'
import { onSlide, othersOn, type Other, type PictureImport, type SlideHost } from './slide-host'
import type { CssEdit } from './style-css'
import { type Axis, lineSize } from './line-sizes'
import type { Chart, ChartDraft, ChartFigure, ChartSpec } from './charts'
import { rangeTouchedBy } from './charts'
import type { NameDraft, NameInfo, NameRegion } from './names'
import type { PivotDefinition, PivotInfo, PivotLabels } from './pivots'
import type { OutcomeTable } from './outcomes'
import type { Reach, Trace, Window } from './follow'
import type { PageSetupData } from '@claudia/layout'
import type { SheetPrintData } from './print/sheet'

export { DEFAULT_COL_WIDTH, DEFAULT_ROW_HEIGHT } from './line-sizes'

export type {
  BaseState,
  ChatMessage,
  CheckpointInfo,
  Step,
  Notice,
  Person,
  SessionOptions,
} from './base-session'
export { BaseSession } from './base-session'
export type { ImageAsset, ImageImport } from './images'
export type { Chart, ChartDraft, ChartFigure, ChartRange, ChartSpec } from './charts'
export { chartRange } from './charts'

export const CHUNK_ROWS = 64
export const CHUNK_COLS = 16
const COL_STRIDE = 16_384

export interface SheetInfo {
  id: string
  name: string
  rows: number
  cols: number
}
/** One tab below the workbook (E6.31, D1471): a sheet or a slide, in their one order, as `tabs` sends them. */
export interface TabInfo {
  kind: 'sheet' | 'slide'
  id: string
  name: string
}
/** A `functions` search result: name, signature and a one-line tooltip (E13.5/E13.6). Fetch the full help text,
 * with its worked example, through `functionHelp`. */
export interface FunctionSummary {
  name: string
  signature: string
  tooltip: string
}
export interface FunctionHelp extends FunctionSummary {
  help: string
}
/** A floating object anchored to a cell of a sheet (E6.17, E10.16): the shared `ObjectBody` plus a
 * `CellAnchor` — the only part of it that is this app's own (D177). `anchor.row`/`anchor.col` pin its top left
 * corner; `w`/`h` are its pixel size. Neither the anchor nor the size ever changes because of a structural edit
 * (a row/column insert, delete or resize) elsewhere on the sheet; only `moveObject` (dragging it) moves it and
 * `resizeObject` resizes it. Mirrors `claudia_computes.SheetObject`. */
export type SheetObject = VisualObject<CellAnchor>
/** An object of a workbook: on a sheet, hanging at a cell, or on a slide, at a point of it (E6.31). */
export type WorkbookObject = SheetObject | SlideObject
/** What `sql_preview` answers: the table a query gives (at most the asked rows of it), or the `#SQL!` it would show. */
export type SqlPreview =
  | { ok: true; columns: string[]; rows: (string | number | boolean | null)[][]; row_count: number; ms: number }
  | { ok: false; error: { code: string; detail: string } }
export interface State extends BaseState {
  sheets: SheetInfo[]
  activeSheet: string
  /** The sheets and slides in their one order (E6.31, D1471); the chart tabs are apart (`charts`). */
  tabs: TabInfo[]
  /** The slide on show, or `''` while a sheet or a chart tab is. */
  activeSlide: string
  /** The object selected on the slide on show (an object on a sheet is selected in the grid). */
  selected: string | null
  /** The outlines the server offers for a slide's shapes, and the ones the document has taken in. */
  library: ShapeDef[]
  shapes: Record<string, ShapeDef>
  /** What references read as, by object: a workbook's words have none (the slide view asks). */
  referenced: Record<string, Shown[]>
  cells: Record<string, Map<number, Content>>
  /** Rows (by `sheets[].id`) that were given a height away from `DEFAULT_ROW_HEIGHT` (D135). Sparse: a row not in
   * here shows at the default. */
  rowHeights: Record<string, Map<number, number>>
  /** Same as `rowHeights`, for column widths away from `DEFAULT_COL_WIDTH`. */
  colWidths: Record<string, Map<number, number>>
  generation: number
  objects: Record<string, WorkbookObject>
  diagrams: Record<string, ChartSpec> // chart definitions this document knows, by id (E6.6)
  charts: Chart[] // chart tabs, in tab order
  /** The workbook's names: named ranges, tables and the results of `SQL()` cells (E6.5), as `names` sends them. */
  names: NameInfo[]
  /** The workbook's pivot tables (E6.30), as `pivots` sends them: what each is made from, and the cells it fills now. Asked
   * for again whenever something that could change them did (`reloadPivots`). */
  pivots: PivotInfo[]
  /** A diagram's Plotly figure, read live off its sheet, cached by diagram id until something that could
   * change it happens — its own definition changing, or a `cells` event touching its range (`ensureFigure`,
   * `onAppEvent`'s `'cells'`/`'diagram'` cases). Never persisted across a reload: `loadApp` starts it empty. */
  figures: Record<string, ChartFigure>
  /** The document's styles: what a floating object and a cell look like (E6.13). */
  styles: Record<string, StyleDef>
  /** What a style property means and where a style can go: the server's `style_model` (D303, D304). */
  styleModel: StyleModel | null
  /** The style ranges of each sheet that has been looked at (E6.13, D307), least specific layer first, as the
   * server's `cell_styles` sends them. A sheet's ranges are few — a whole column is one — so a sheet is loaded whole,
   * as its sizes are. */
  cellStyles: Record<string, CellRange[]>
  /** How many things use each style — cells counted by range, objects by slot (`style_uses`). */
  styleUses: Record<string, number>
  /** What every random number of the workbook is a function of (E6.22, D291): the seed and the draw number. */
  random: { seed: number; draw: number }
  /** The workbook's named number formats by id (D378): a cell shows its number through the one its words' style
   * names, as `number_formats` sends them. */
  numberFormats: Record<string, NumberFormatDef>
  /** The cells that light up while a computation is followed (E6.23, D297), or `null`. A view of this person's own:
   * nobody else sees it. */
  trace: Trace | null
  /** The page the workbook prints on (E6.19, D1004), the same for all sheets; `null` for a server from before printing. */
  printPage: PageSetupData | null
  /** How each sheet and chart tab prints, by id, with the defaults filled in; empty for an old server. */
  sheetPrint: Record<string, SheetPrintData>
}

/** What `random_preview` answers: what to type, what an Excel file would hold, and the distribution's own values. */
export interface RandomPreview {
  formula: string
  excel: string | null
  continuous: boolean
  draws: number[]
}
export interface RandomPreviewRequest {
  distribution: string
  params: number[]
  low?: number | null
  high?: number | null
  draws?: number
}

interface Followed {
  sheet: string
  row: number
  col: number
  reach: Reach
  window: Window
}

const key = (row: number, col: number) => row * COL_STRIDE + col

/** Where a search looks: every sheet, one sheet, or a block of cells on it (first row, first column, last row, last column). */
export interface SearchScope {
  sheet?: string
  range?: [number, number, number, number]
}

/** A match, or with `match: null` everything at a place, that a replacement leaves alone (`lib/search.ts`). */
export type { SearchLeave } from './search'

export class Session extends BaseSession<State> implements SlideHost {
  /** A range like `A1:B5` (or one cell) on the sheet on show, as the part of an imported workbook to blank (D723). */
  override redactionRangePart(range: string): string | null {
    const text = range.trim().toUpperCase().replace(/\$/g, '')
    if (!this.state.activeSheet || !/^[A-Z]{1,3}[1-9]\d*(:[A-Z]{1,3}[1-9]\d*)?$/.test(text)) return null
    return `${this.state.activeSheet}!${text}`
  }

  private loaded = new Set<string>()
  private inflight = new Map<string, Promise<void>>()
  private sizesLoaded = new Set<string>()
  private sizesInflight = new Map<string, Promise<void>>()
  private figuresInflight = new Map<string, Promise<void>>()
  private stylesInflight = new Map<string, Promise<void>>()
  private followed: Followed | null = null
  private refollowing = false

  constructor(makeLink: () => LinkLike, options: SessionOptions = {}) {
    super(makeLink, options, {
      sheets: [],
      activeSheet: '',
      tabs: [],
      activeSlide: '',
      selected: null,
      library: [],
      referenced: {},
      cells: {},
      rowHeights: {},
      colWidths: {},
      generation: 0,
      diagrams: {},
      charts: [],
      names: [],
      pivots: [],
      figures: {},
      styleModel: null,
      cellStyles: {},
      styleUses: {},
      random: { seed: 0, draw: 0 },
      numberFormats: {},
      trace: null,
      printPage: null,
      sheetPrint: {},
    })
  }

  // ------------------------------------------------------------------------------ loading
  /** The sheets, their floating objects and the pictures behind them; the cells themselves are loaded as they
   * come into view. */
  protected async loadApp() {
    const link = this.need()
    const s = this.state
    const [sheets, images, diagrams, charts, names, styles, palette, styleModel, random, formats, printing, language, pivots] = await Promise.all([
      link.request<SheetInfo[]>('sheets'),
      link.request<ImageAsset[]>('images'),
      link.request<ChartSpec[]>('diagrams'),
      link.request<Chart[]>('charts'),
      link.request<{ names: NameInfo[] }>('names'),
      link.request<StyleDef[]>('styles'),
      link.request<PaletteEvent>('palette'),
      link.request<StyleModel>('style_model'),
      // a server from before random numbers has none: the draw is 0 and nothing asks for it
      link.request<{ seed: number; draw: number }>('random_state').catch(() => ({ seed: 0, draw: 0 })),
      // a server from before number formats has none: every number shows the General way
      link.request<NumberFormatDef[]>('number_formats').catch(() => [] as NumberFormatDef[]),
      // a server from before printing has neither: the preview then starts from A4 and cannot store a change
      link.request<{ page: PageSetupData; sheets: Record<string, SheetPrintData> }>('print_setup').catch(() => null),
      link.request<{ language: string | null }>('language').then((a) => a.language, () => undefined),
      // a server from before pivot tables has none: there are no pivots to draw
      link.request<{ pivots: PivotInfo[] }>('pivots').then((a) => a.pivots, () => [] as PivotInfo[]),
    ])
    // a server from before slides (E6.31) has neither: its tabs are its sheets, and there is nothing to draw on a slide
    const [tabs, shapes] = await Promise.all([
      link.request<TabInfo[]>('tabs').catch(() => sheets.map((x): TabInfo => ({ kind: 'sheet', id: x.id, name: x.name }))),
      link.request<{ library: ShapeDef[]; document: ShapeDef[] }>('shapes').catch(() => ({ library: [], document: [] })),
    ])
    this.forgetCells()
    const loaded = await Promise.all(
      tabs.map((tab) =>
        tab.kind === 'slide'
          ? link.request<{ objects: WorkbookObject[] }>('slide', { slide: tab.id })
          : link.request<{ objects: WorkbookObject[] }>('objects', { sheet: tab.id }),
      ),
    )
    s.objects = {}
    s.order = {}
    tabs.forEach((tab, i) => {
      s.order[tab.id] = loaded[i]!.objects.map((o) => o.id)
      for (const o of loaded[i]!.objects) s.objects[o.id] = o
    })
    s.sheets = sheets
    s.tabs = tabs
    s.library = shapes.library
    s.shapes = Object.fromEntries(shapes.document.map((d) => [d.id, d]))
    s.images = Object.fromEntries(images.map((x) => [x.id, x]))
    s.diagrams = Object.fromEntries(diagrams.map((x) => [x.id, x]))
    s.charts = charts
    s.names = names.names
    s.pivots = pivots
    s.figures = {}
    this.figuresInflight.clear()
    s.styles = Object.fromEntries(styles.map((x) => [x.id, x]))
    s.palette = palette
    s.styleModel = styleModel
    s.random = { seed: random.seed, draw: random.draw }
    s.numberFormats = Object.fromEntries(formats.map((x) => [x.id, x]))
    s.printPage = printing?.page ?? null
    s.sheetPrint = printing?.sheets ?? {}
    s.language = language
    this.track(this.refreshUses())
    if (!sheets.some((x) => x.id === s.activeSheet)) s.activeSheet = sheets[0]?.id ?? ''
    if (!tabs.some((tab) => tab.kind === 'slide' && tab.id === s.activeSlide)) s.activeSlide = ''
    if (s.selected && !s.objects[s.selected]) s.selected = null
  }

  // -- styles and the palette (E9.7, D200, D203): the same methods creates' session has, so that one style menu
  // can talk to either app through a `StyleHost`.
  /** Put a style into one slot of these targets — the one style API every app has (`apply_style`, D304). Without a
   * slot, into every slot of them the style fits: both slots of a cell (D311). */
  async applyStyle(targets: StyleTarget[], style: string, slot?: string): Promise<boolean> {
    return (await this.write('apply_style', { targets, style, slot })) !== false
  }

  /** Change these targets only, in one slot or (without) in every slot that held `parent`: a new style from
   * `parent`, named later (`deviate`, D75, D309). */
  async deviateStyle(parent: string, targets: StyleTarget[], slot: string | undefined, edit: CssEdit): Promise<boolean> {
    return (await this.write('deviate', { parent, targets, slot, ...edit })) !== false
  }

  /** "Clear cell style" (D317): take the cells' own style away, in one slot or both, so what lies beneath shows. */
  async clearCellStyle(sheet: string, range: [number, number, number, number], slot?: string): Promise<boolean> {
    return (await this.write('clear_cell_style', { sheet, range, slot })) !== false
  }

  /** The style ranges of a sheet that are loaded; none until `ensureCellStyles` has run for it. */
  cellStyles(sheet: string): CellRange[] {
    return this.state.cellStyles[sheet] ?? []
  }

  /** Load a sheet's style ranges, all of them, unless they are here already. */
  async ensureCellStyles(sheet: string): Promise<void> {
    if (sheet in this.state.cellStyles) return
    return this.loadCellStyles(sheet)
  }

  private loadCellStyles(sheet: string): Promise<void> {
    const running = this.stylesInflight.get(sheet)
    if (running) return running
    const generation = this.state.generation
    const job = this.need()
      .request<{ revision: string; ranges: CellRange[] }>('cell_styles', { sheet, row0: 0, row1: MAX_ROWS - 1, col0: 0, col1: MAX_COLS - 1 })
      .then((answer) => {
        if (generation === this.state.generation) this.state.cellStyles[sheet] = answer.ranges
      })
      .finally(() => this.stylesInflight.delete(sheet))
    this.stylesInflight.set(sheet, job)
    return job
  }

  /** Ask the server again how often each style is used. Quietly keeps the old counts if it cannot say. */
  async refreshUses(): Promise<void> {
    try {
      this.state.styleUses = (await this.need().request<{ uses: Record<string, number> }>('style_uses')).uses
    } catch {
      /* a server without the counts: the gallery shows none */
    }
  }

  /** The objects of a sheet, the one in front last. */
  objectsOn(sheet: string): SheetObject[] {
    return this.onHolder(sheet).filter((o): o is SheetObject => o.anchor.kind === 'cell')
  }

  /** The object `id` if it hangs on a sheet; `undefined` else (an object on a slide is the slide view's). */
  sheetObject(id: string | null | undefined): SheetObject | undefined {
    const o = id ? this.state.objects[id] : undefined
    return o?.anchor.kind === 'cell' ? (o as SheetObject) : undefined
  }

  /** The objects of a slide, the one in front last (E6.31): what the slide view draws, as creates' does. */
  slideObjects(slide: string): SlideObject[] {
    return this.onHolder(slide).flatMap((o) => onSlide(o) ?? [])
  }

  private onHolder(holder: string): WorkbookObject[] {
    return (this.state.order[holder] ?? []).map((id) => this.state.objects[id]).filter((o): o is WorkbookObject => o !== undefined)
  }

  // -- a slide among the sheets (E6.31, D1473): shown with the slide view of creates, its objects placed the same way
  /** Show a slide (`''`: none, a sheet or a chart tab is shown), with nothing selected on it. */
  async showSlide(slide: string): Promise<void> {
    if (slide === this.state.activeSlide) return
    await this.select(null)
    this.state.activeSlide = slide
  }

  /** The objects of a slide that colleagues have selected, and whether they hold them. */
  selectedByOthers(slide: string): Other[] {
    return othersOn(this.state, slide)
  }

  /** Select an object on the slide on show (`null`: nothing). Selecting holds it; a colleague who holds it first keeps
   * it. */
  async select(id: string | null): Promise<void> {
    const s = this.state
    if (id === s.selected) return
    s.selected = id
    if (id === null) return this.letGoOfObject()
    if (!(await this.holdObject(id, s.objects[id]?.anchor.holder ?? s.activeSlide)) && s.selected === id) s.selected = null
  }

  async move(id: string, x: number, y: number): Promise<boolean> {
    return (await this.write('move_object', { id, x, y })) !== false
  }

  async resize(id: string, frame: Frame): Promise<boolean> {
    return (await this.write('resize_object', { id, ...frame })) !== false
  }

  /** Put a text box on the slide on show; its id, or `null` after telling the person why not. */
  addText(frame: Frame): Promise<string | null> {
    return this.insertOnSlide({ kind: 'text' }, frame)
  }

  /** Put a shape from the library (or the document) on the slide on show. */
  addShape(shape: string, frame: Frame): Promise<string | null> {
    return this.insertOnSlide({ kind: 'shape', shape }, frame)
  }

  private async insertOnSlide(params: Record<string, unknown>, frame: Frame): Promise<string | null> {
    const done = await this.write('add_object', { slide: this.state.activeSlide, ...params, ...frame })
    if (done === false) return null
    await this.select(done.object)
    return done.object
  }

  // -- charts (E6.6): a diagram definition, shown as a floating object, a tab, or both at once
  /** The already-cached figure for a diagram, or `null` while it has not been asked for yet (call
   * `ensureFigure` to start that, typically from the component that is about to draw it). */
  figureOf(diagramId: string): ChartFigure | null {
    return this.state.figures[diagramId] ?? null
  }

  /** Load (or reload, with `force`) a diagram's figure. Safe to call on every render of a chart view: a figure
   * already cached and not invalidated resolves at once and does nothing. */
  async ensureFigure(diagramId: string, force = false): Promise<void> {
    if (!force && this.state.figures[diagramId]) return
    const running = this.figuresInflight.get(diagramId)
    if (!force && running) return running
    const job = this.need()
      .request<{ figure: ChartFigure }>('chart_figure', { diagram: diagramId })
      .then((answer) => {
        this.state.figures[diagramId] = answer.figure
      })
      .catch(() => {
        /* the diagram may have just been forgotten under us; the next relevant event resolves it one way or
         * the other, so a chart view that asked simply keeps showing its last good figure (if any) */
      })
      .finally(() => this.figuresInflight.delete(diagramId))
    this.figuresInflight.set(diagramId, job)
    return job
  }

  /** Re-fetch `charts` (the tab strip) without reloading the whole document — the `charts` push event carries
   * no payload of its own (`claudia_computes.events.ChartsChanged`), unlike `objects`/`cells`. */
  private async reloadCharts() {
    this.state.charts = await this.need().request<Chart[]>('charts')
  }

  /** Re-fetch the names; the `names` push event carries no payload of its own (`claudia_computes.events.NamesChanged`).
   * What a chart that reads a name shows may have changed with them, so those figures are asked for again. */
  private async reloadNames() {
    const answer = await this.need().request<{ names: NameInfo[] }>('names')
    this.state.names = answer.names
    for (const spec of Object.values(this.state.diagrams)) if (spec.source !== undefined) delete this.state.figures[spec.id]
  }

  private pivotsAsked = false
  private pivotsAgain = false

  /** Re-fetch the pivot tables: the `pivots` push event carries no payload of its own (`claudia_computes.events.PivotsChanged`),
   * and the cells a pivot fills grow and shrink with its source, so a change of cells or rows asks too. Asks that come
   * while one is out are one more ask afterwards, not each their own. A server from before pivot tables leaves them be. */
  private async reloadPivots() {
    if (this.pivotsAsked) {
      this.pivotsAgain = true
      return
    }
    this.pivotsAsked = true
    try {
      do {
        this.pivotsAgain = false
        const answer = await this.need().request<{ pivots: PivotInfo[] }>('pivots').catch(() => null)
        if (answer) this.state.pivots = answer.pivots
      } while (this.pivotsAgain)
    } finally {
      this.pivotsAsked = false
    }
  }

  /** Forgets a sheet's cells, and with them its row/column sizes — a structural edit (rows or columns inserted or
   * deleted) shifts both the same way, and the server does not echo the shifted sizes back as their own event. */
  private forgetCells(sheet?: string) {
    const s = this.state
    if (sheet === undefined) {
      s.cells = {}
      s.rowHeights = {}
      s.colWidths = {}
      s.cellStyles = {}
      this.stylesInflight.clear()
      this.loaded.clear()
      this.inflight.clear() // what was asked of a connection that is gone will never be answered
      this.sizesLoaded.clear()
      this.sizesInflight.clear()
    } else {
      delete s.cells[sheet]
      delete s.rowHeights[sheet]
      delete s.colWidths[sheet]
      delete s.cellStyles[sheet]
      this.stylesInflight.delete(sheet)
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
  protected onAppEvent(name: string, data: WireData): boolean {
    const s = this.state
    switch (name) {
      case 'cells': {
        const map = (s.cells[data.sheet] ??= new Map())
        for (const [r, c, content] of data.cells as [number, number, Content][]) {
          if (content === null) map.delete(key(r, c))
          else map.set(key(r, c), content)
        }
        this.refollow()
        if (s.pivots.length) this.track(this.reloadPivots()) // the source it reads, or the cells it fills, may be these
        // A changed cell may feed a diagram's figure even on another sheet's screen (a chart tab, say), so
        // every cached figure is checked, not only those for the active sheet.
        const positions = data.positions as [number, number][]
        for (const spec of Object.values(s.diagrams)) {
          // A chart that reads a name follows whatever the name is on, which may be a query result that moves: any
          // change of cells may touch it, so it is asked for again.
          if (spec.id in s.figures && (spec.range ? rangeTouchedBy(spec.range, data.sheet, positions) : true)) delete s.figures[spec.id]
        }
        return true
      }
      case 'structure':
        this.forgetCells(data.sheet)
        this.refollow()
        if (s.pivots.length) this.track(this.reloadPivots())
        return true
      case 'sizes': {
        const target = (data.axis as Axis) === 'row' ? (s.rowHeights[data.sheet] ??= new Map()) : (s.colWidths[data.sheet] ??= new Map())
        for (const [i, size] of data.sizes as [number, number | null][]) {
          if (size === null) target.delete(i)
          else target.set(i, size)
        }
        return true
      }
      case 'tabs':
      case 'sheets': // (a server from before slides)
        this.track(this.reload())
        this.refollow()
        return true
      case 'diagram':
        if (data.definition) s.diagrams[data.id] = data.definition as ChartSpec
        else delete s.diagrams[data.id]
        delete s.figures[data.id] // its range or titles may have changed (DefineDiagram/UpdateDiagram alike)
        return true
      case 'charts':
        this.track(this.reloadCharts())
        return true
      case 'names':
        this.track(this.reloadNames())
        return true
      case 'pivots':
        this.track(this.reloadPivots())
        return true
      case 'cell_styles':
        // Only a sheet somebody looks at is loaded again; another is loaded when it comes into view.
        if (data.sheet in s.cellStyles) this.track(this.loadCellStyles(data.sheet).catch(() => undefined))
        this.track(this.refreshUses())
        return true
      case 'random':
        s.random = { seed: data.seed, draw: data.draw }
        return true
      case 'print_setup':
        if (data.sheet === undefined) s.printPage = data.page as PageSetupData
        else s.sheetPrint[data.sheet as string] = data.setup as SheetPrintData
        return true
    }
    return false
  }

  /** An object came, went or changed its style: the use counts beside the style names follow; a selected object on a
   * slide that went is let go of. */
  protected override objectsChanged(e: ObjectsEvent): void {
    this.track(this.refreshUses())
    if (e.removed.includes(this.state.selected ?? '')) {
      this.state.selected = null
      this.track(this.letGoOfObject())
    }
  }

  protected override stylesChanged(): void {
    this.track(this.refreshUses())
  }

  // ------------------------------------------------------------------------------ random numbers, alternatives, following
  /** Draw fresh random numbers for everybody (Tools ▸ Resample, F9, E6.22): one undoable step in the history. */
  async resample(steps = 1): Promise<boolean> {
    return (await this.write('resample', { steps })) !== false
  }

  // ------------------------------------------------------------------------------ printing (E6.19)
  /** Print the workbook on another page (D1004): one step in the history, for everybody. */
  async setPrintPage(page: PageSetupData): Promise<boolean> {
    return (await this.write('set_print_page', { page })) !== false
  }

  /** Print a sheet or chart tab another way (D1004): one step in the history, for everybody. */
  async setSheetPrint(sheet: string, setup: SheetPrintData): Promise<boolean> {
    return (await this.write('set_sheet_print', { sheet, setup })) !== false
  }

  /** Give the workbook's random numbers a seed: the same seed and draw give the same numbers on every computer. */
  async setRandomSeed(seed: number): Promise<boolean> {
    return (await this.write('set_random_seed', { seed })) !== false
  }

  /** What a distribution would give, for the Random generator. A problem with the numbers is the answer
   * (`{ error }`), not a notice: the dialog says it beside the field. */
  async randomPreview(request: RandomPreviewRequest): Promise<RandomPreview | { error: string }> {
    try {
      return await this.need().request<RandomPreview>('random_preview', { ...request })
    } catch (error) {
      return { error: error instanceof ProtocolError ? error.message : t('Something went wrong.') }
    }
  }

  /** Every outcome of a cell that depends on alternatives (E6.21), as `all` combinations or `pair`ed by position;
   * `null` for a cell that depends on none, `false` after telling the person why not. */
  async outcomeTable(sheet: string, row: number, col: number, combine: 'all' | 'pair' = 'all'): Promise<OutcomeTable | null | false> {
    const done = await this.attempt('outcome_table', { sheet, row, col, combine })
    return done === false ? false : (done.table as OutcomeTable | null)
  }

  // -- tags (E5.20, D551)
  protected override things(): Thing[] {
    const s = this.state
    const out: Thing[] = []
    for (const tab of s.tabs) out.push({ id: tab.id, name: s.renamed[tab.id] ?? tab.name, kind: tab.kind })
    for (const chart of s.charts) out.push({ id: chart.id, name: s.renamed[chart.id] ?? chart.name, kind: 'chart' })
    for (const o of Object.values(s.objects)) if (o.name) out.push({ id: o.id, name: s.renamed[o.id] ?? o.name, kind: o.kind })
    for (const n of s.names) out.push({ id: n.id, name: n.name, kind: 'range' }) // (a name is renamed with its own command, not as a thing)
    return out
  }
  /** The sheet or slide being looked at, the chart tabs beside it, the named ranges on it and what floats on it. */
  protected override async inView(): Promise<Thing[]> {
    const here = this.currentHolder()
    return this.things().filter((t) => t.kind === 'chart' || this.holderOf(t.id) === here)
  }
  override async unnamedInView(): Promise<number> {
    return this.onHolder(this.currentHolder() ?? '').filter((o) => !o.name).length
  }
  protected override tracksThings(): boolean {
    return true
  }
  protected override holderOf(id: string): string | null {
    const s = this.state
    if (s.tabs.some((x) => x.id === id)) return id
    const named = s.names.find((n) => n.id === id)
    if (named) return named.sheet
    return s.objects[id]?.anchor.holder ?? null
  }
  protected override currentHolder(): string | null {
    return this.state.activeSlide || this.state.activeSheet || null
  }
  protected override showHolder(id: string): void {
    const tab = this.state.tabs.find((x) => x.id === id)
    if (tab?.kind === 'slide') this.state.activeSlide = id
    else if (tab) {
      this.state.activeSlide = ''
      this.state.activeSheet = id
    }
  }

  /** A step of the replay is shown on the sheet it touched (D551); the grid scrolls to it from `state.replay.focus`. */
  protected override followReplay(focus: Region[]): void {
    const holder = holderOf(firstFocus(focus))
    if (holder) this.showHolder(holder)
  }

  /** Start following the computation the cell at (`row`, `col`) is part of (E6.23): the cells of `window` that are
   * connected to it light up (`state.trace`). Kept up to date as cells change, until `unfollow`. */
  async follow(sheet: string, row: number, col: number, reach: Reach, window: Window): Promise<void> {
    this.followed = { sheet, row, col, reach, window }
    await this.fetchTrace()
  }

  unfollow(): void {
    this.followed = null
    this.state.trace = null
  }

  private async fetchTrace(): Promise<void> {
    const asked = this.followed
    if (!asked) return
    try {
      const answer = await this.need().request<{ trace: Trace }>('trace', { ...asked })
      if (this.followed === asked) this.state.trace = answer.trace
    } catch {
      // The cell or its sheet is gone, or the connection: there is nothing to light up any more.
      if (this.followed === asked) this.unfollow()
    }
  }

  /** Ask again, once, for everything that changed in the same moment. */
  private refollow(): void {
    if (!this.followed || this.refollowing) return
    this.refollowing = true
    void Promise.resolve().then(() => {
      this.refollowing = false
      return this.fetchTrace()
    })
  }

  // ------------------------------------------------------------------------------ doing things
  async setCells(sheet: string, cells: { row: number; col: number; input: string }[]): Promise<boolean> {
    const done = await this.write('set_cells', { sheet, cells })
    return done !== false
  }

  async addSheet(name: string): Promise<boolean> {
    const done = await this.write('add_sheet', { name })
    if (done === false) return false
    this.state.activeSheet = done.sheet
    return true
  }

  async structure(sheet: string, axis: 'row' | 'col', insert: boolean, at: number, count = 1): Promise<boolean> {
    return (await this.write('structure', { sheet, axis, insert, at, count })) !== false
  }

  // -- floating objects (images, today): anchored to a cell, a fixed pixel size, never touched by `structure`
  // or `resizeLines`
  /** Import a picture from disk and anchor it to a cell of the sheet that is shown (E6.17); its id, or null
   * after telling the person why not. `data` is the file's bytes, base64 (`lib/images.ts`'s `fileToBase64`);
   * `sourcePath` is the file's full path if the caller could get one — a plain web browser cannot, and passes
   * `null`. `anchor` fixes the object's cell and its pixel size for good: there is no resize yet, and no
   * structural edit (row/column insert, delete or resize) ever changes either. */
  async addImage(picture: PictureImport, anchor: { row: number; col: number; w: number; h: number } | Frame): Promise<string | null> {
    if (!('x' in anchor)) return this.putPicture(picture, { sheet: this.state.activeSheet, ...anchor })
    const id = await this.putPicture(picture, { slide: this.state.activeSlide, ...anchor }) // (a slide's, E6.31)
    if (id) await this.select(id)
    return id
  }

  /** Put a container of `type` on the sheet that is shown, anchored to a cell (D560); its id, or `null` after
   * telling the person why not. */
  addContainer(type: string, anchor: { row: number; col: number; w: number; h: number }): Promise<string | null> {
    return this.addContainerAt(type, { sheet: this.state.activeSheet, row: anchor.row, col: anchor.col }, { w: anchor.w, h: anchor.h }, undefined, true)
  }

  /** Take a new chart definition into the document (E6.6); its id, or `null` after telling the person why not.
   * Show it with `addDiagramObject`, `addChart`, or both — neither is bundled into this call, since (unlike
   * `addImage`) a definition may be placed more than once from the very start. */
  async defineDiagram(draft: ChartDraft): Promise<string | null> {
    const done = await this.write('define_diagram', { definition: { kind: 'bar', ...draft } })
    return done === false ? null : done.diagram
  }

  /** Redefine a chart in place: what a tab or floating object already showing `id` updates to. */
  async updateDiagram(id: string, draft: ChartDraft): Promise<boolean> {
    return (await this.write('update_diagram', { id, definition: { kind: 'bar', ...draft } })) !== false
  }

  /** Let a chart definition go. Refused (returns `false`) while a tab or a floating object still shows it. */
  async forgetDiagram(id: string): Promise<boolean> {
    return (await this.write('forget_diagram', { id })) !== false
  }

  /** Put a chart on the sheet that is shown, as a floating object showing `diagramId`; its id, or `null` after
   * telling the person why not. `moveObject`/`resizeObject`/`removeObject` then work on it like any object. */
  async addDiagramObject(diagramId: string, anchor: { row: number; col: number; w: number; h: number }): Promise<string | null> {
    const done = await this.write('add_diagram_object', { sheet: this.state.activeSheet, diagram: diagramId, ...anchor })
    return done === false ? null : done.object
  }

  /** Add a chart tab showing `specId`; its id, or `null` after telling the person why not. */
  async addChart(name: string, specId: string, index: number | null = null): Promise<string | null> {
    const done = await this.write('add_chart', { name, spec_id: specId, index })
    return done === false ? null : done.chart
  }

  /** Remove a chart tab. The definition it showed is untouched (`forgetDiagram` is the separate step). */
  async removeChart(id: string): Promise<boolean> {
    return (await this.write('remove_chart', { id })) !== false
  }

  // -- names, tables and queries (E6.5)
  /** Give cells a name (or point an existing one, same scope, somewhere else); `false` after telling the person why not. */
  async defineName(draft: NameDraft): Promise<boolean> {
    return (await this.write('define_name', { definition: draft })) !== false
  }

  /** Name cells that have no name and describe them, one step in the history (D1317): the id they have from then on, or
   * `false` after telling the person why not. */
  async nameAndDescribeRange(range: NameRegion, name: string, description: string): Promise<string | false> {
    const done = await this.write('name_and_describe_range', { range, name, description })
    return done === false ? false : (done.id as string)
  }

  /** Call a name something else; the formulas that use it are rewritten. */
  async renameName(old: string, next: string, scope: string | null): Promise<boolean> {
    return (await this.write('rename_name', { old, new: next, scope })) !== false
  }

  /** Take a name away; the cells stay. */
  async removeName(name: string, scope: string | null): Promise<boolean> {
    return (await this.write('remove_name', { name, scope })) !== false
  }

  /** Run a query as a `SQL()` cell on `sheet` would, without changing the document (what the SQL editor previews). */
  async sqlPreview(query: string, sheet: string, limit = 20): Promise<SqlPreview> {
    return this.need().request<SqlPreview>('sql_preview', { query, sheet, limit })
  }

  /** Put a query into a cell as `=SQL("…")`, and with `name` make its result a table of that name. */
  async defineSql(sheet: string, row: number, col: number, query: string, name: string | null): Promise<boolean> {
    return (await this.write('define_sql', { sheet, row, col, query, name })) !== false
  }

  // -- pivot tables (E6.30)
  /** Make a pivot table called `name` from `definition`, starting at a cell of `sheet` or on a sheet of its own called
   * `newSheet`; the sheet it is on, or `null` after telling the person why not. The words it writes are `labels`. */
  async definePivot(
    name: string,
    definition: PivotDefinition,
    labels: PivotLabels,
    place: { sheet: string; row: number; col: number } | { newSheet: string },
  ): Promise<string | null> {
    const where = 'newSheet' in place ? { new_sheet: place.newSheet } : { sheet: place.sheet, row: place.row, col: place.col }
    const done = await this.write('define_pivot', { name, definition, labels, ...where })
    return done === false ? null : done.sheet
  }

  /** Change what a pivot table is made from; its cells follow. The words it already writes stay unless `labels` is given. */
  async updatePivot(name: string, definition: PivotDefinition, labels?: PivotLabels): Promise<boolean> {
    return (await this.write('update_pivot', { name, definition, ...(labels ? { labels } : {}) })) !== false
  }

  /** Take a pivot table away: its cells are empty, the source is untouched. */
  async deletePivot(name: string): Promise<boolean> {
    return (await this.write('delete_pivot', { name })) !== false
  }

  /** The SQL query a pivot table is, or `null` after telling the person why not. */
  async pivotSql(name: string): Promise<string | null> {
    const done = await this.attempt('pivot_sql', { name })
    return done === false ? null : done.sql
  }

  /** Turn a pivot table into a `SQL()` query of the same name; one step in the history. */
  async pivotToSql(name: string): Promise<boolean> {
    return (await this.write('pivot_to_sql', { name })) !== false
  }

  /** The members a field of `source` has, for a filter's list: at most `limit` (the preview shows 50 rows at most), in order; `null` is "nothing". */
  async pivotMembers(source: string, field: string, sheet: string, limit = 40): Promise<{ members: (string | number | null)[]; more: boolean } | null> {
    const quote = (word: string) => `"${word.replace(/"/g, '""')}"`
    const query = `SELECT DISTINCT ${quote(field)} FROM ${quote(source)} ORDER BY ${quote(field)} LIMIT ${limit + 1}`
    const answer = await this.sqlPreview(query, sheet, limit + 1).catch(() => null)
    if (!answer || !answer.ok) return null
    const members = answer.rows.map((row) => row[0] as string | number | null)
    return { members: members.slice(0, limit), more: members.length > limit }
  }

  /** Drag an object to a new anchor cell; its size never changes. */
  async moveObject(id: string, row: number, col: number): Promise<boolean> {
    return (await this.write('move_object', { id, row, col })) !== false
  }

  /** Give an object a new frame: its anchor cell and pixel size together, since dragging a corner moves the
   * corner too. An image must keep its own proportions (the server refuses otherwise); a diagram keeps none. */
  async resizeObject(id: string, frame: { row: number; col: number; w: number; h: number }): Promise<boolean> {
    return (await this.write('resize_object', { id, ...frame })) !== false
  }

  /** Set (or, with `null`, clear back to the default) the size of one or more rows or columns in one change.
   * `sizes` is `[index, size | null]` pairs. */
  async resizeLines(sheet: string, axis: Axis, sizes: [number, number | null][]): Promise<boolean> {
    return (await this.write('resize_lines', { sheet, axis, sizes })) !== false
  }

  // -- the function catalog (E13.5, E13.6: computes' "Documentation", and the formula bar's in-context help)
  /** Every cell function whose name or description mentions `query`, closest name match first; the whole
   * catalog, alphabetically, if `query` is blank. */
  async listFunctions(query = ''): Promise<FunctionSummary[] | false> {
    return await this.attempt('functions', { query })
  }

  /** One function's full help text, by the name a `listFunctions` result (or the formula bar's own parsing of
   * what is being typed) gave. */
  async functionHelp(name: string): Promise<FunctionHelp | false> {
    return await this.attempt('function_help', { name })
  }

  // -- where I am, and holding a cell while I type into it
  private region(sheet: string, r0: number, c0: number, r1: number, c1: number): Region {
    const ref = (row: number, col: number) => ({ row, col, sheet })
    return { kind: 'cells', range: { first: ref(Math.min(r0, r1), Math.min(c0, c1)), last: ref(Math.max(r0, r1), Math.max(c0, c1)) } }
  }

  async show(sheet: string, r0: number, c0: number, r1 = r0, c1 = c0): Promise<void> {
    await this.showRegions(JSON.stringify([sheet, r0, c0, r1, c1]), [this.region(sheet, r0, c0, r1, c1)])
  }

  beginEdit(sheet: string, row: number, col: number): Promise<boolean> {
    return this.holdRegions([this.region(sheet, row, col, row, col)])
  }

  endEdit(): Promise<void> {
    return this.releaseRegions()
  }
}
