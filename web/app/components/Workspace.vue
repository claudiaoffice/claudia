<script setup lang="ts">
// A workbook: the formula bar, the grid (or a chart tab), the sheet tabs, inside the document window every app shares
// (DocumentFrame).
import { computed, nextTick, ref, watch } from 'vue'
import { inputOf, rangeLabel, parseCell, VIEW_COLS, VIEW_ROWS } from '~/lib/cells'
import { pointTo, refOf, sheetPrefix, slotAt } from '~/lib/pointing'
import { bounds, jump, move, single, summarize, type Sel } from '~/lib/selection'
import type { Session } from '~/lib/session'
import {
  askItem,
  authorsItemUnavailable,
  clipboardItems,
  configMenu,
  darkItem,
  fileMenu,
  helpMenu,
  panelItem,
  undoRedoItems,
  type DocumentMenuContext,
} from '~/lib/document-menus'
import { currentFunctionAt } from '~/lib/formula-help'
import { useI18n } from '~/lib/i18n'
import { objectStyleHost } from '~/lib/object-style-host'
import { cellStyleHost } from '~/lib/cell-style-host'
import { sheetArea } from '~/lib/cell-styles'
import { chordLabel, type ShortcutDef } from '~/lib/shortcuts'
import { galleryFor } from '~/lib/style-host'
import { formatItems } from '~/lib/format-menu'
import { useTheme } from '~/lib/theme'
import type { Axis } from '~/lib/line-sizes'
import DocumentFrame from './DocumentFrame.vue'
import type { Menu } from './MenuBar.vue'
import type { EditState } from './SheetGrid.vue'

const props = defineProps<{ session: Session }>()
const emit = defineEmits<{ leave: [opts?: { startFresh?: boolean }] }>()

const session = props.session
const state = session.state
const { dark, toggle: toggleDark } = useTheme()
// `t` stays this bare (never `i18n.t`): `scripts/extract_i18n.py`'s own regex only recognises an unqualified
// `t(...)` call (`obj.t(...)` is deliberately excluded, the same way `format(...)` is) -- see its docstring.
const { t, locale, choose } = useI18n()
const SIZE = { rows: VIEW_ROWS, cols: VIEW_COLS }

const sel = ref<Sel>(single(0, 0))
const edit = ref<EditState | null>(null)
const pointed = ref(false) // the selection is the last cell range picked with the mouse in a formula
let original = ''
/** computes' own dialogs; the window's (save, share, export, …) are DocumentFrame's. */
const dialog = ref<null | 'sheet' | 'image' | 'chart' | 'row-size' | 'col-size' | 'styles' | 'colours'>(null)
const frame = ref<InstanceType<typeof DocumentFrame> | null>(null)

const EXPORT_FORMATS = [{ value: 'xlsx', label: 'Excel workbook (.xlsx)' }]
/** The chart tab shown instead of a sheet, or `null` for a sheet (`FooterBar.vue`'s own docstring on why this
 * is not part of `state`). Reset to `null` if its tab disappears (removed here, or by someone else). */
const activeChart = ref<string | null>(null)
const activeChartSpec = computed(() => state.charts.find((c) => c.id === activeChart.value)?.spec_id ?? null)
watch(
  () => state.charts,
  (charts) => {
    if (activeChart.value !== null && !charts.some((c) => c.id === activeChart.value)) activeChart.value = null
  },
)
const grid = ref<{
  focus: () => void
  selectObject: (id: string) => void
  openStyleMenu: (at?: { x: number; y: number }, mode?: 'edit' | 'apply') => void
  selectedObject: () => string | null
} | null>(null)
const headerMenu = ref<{ axis: Axis; index: number; x: number; y: number } | null>(null)

const readonly = computed(() => state.me.role === 'viewer')
const b = computed(() => bounds(sel.value))
const label = computed(() => (edit.value ? rangeLabel(edit.value.row, edit.value.col, edit.value.row, edit.value.col) : rangeLabel(b.value.r0, b.value.c0, b.value.r1, b.value.c1)))
const formulaText = computed(() => (edit.value ? edit.value.text : inputOf(session.cell(state.activeSheet, sel.value.row, sel.value.col))))
/** Does a click pick cells for the formula being typed (the caret is where a reference fits)? */
const pointing = computed(() => edit.value !== null && slotAt(edit.value.text, edit.value.caret) !== null)
const summary = computed(() => {
  void state.generation
  return summarize(sel.value, (r, c) => session.cell(state.activeSheet, r, c))
})

// ------------------------------------------------------------------------------ where I am
watch(
  [sel, () => state.activeSheet],
  () => {
    if (state.activeSheet && !edit.value) session.show(state.activeSheet, b.value.r0, b.value.c0, b.value.r1, b.value.c1)
  },
  { deep: true },
)

function select(next: Sel) {
  if (edit.value && pointing.value) return point(next)
  sel.value = next
}

/** Write the cells picked with the mouse into the formula, in place of the previous pick if there is one. */
function point(next: Sel) {
  const e = edit.value!
  const sheet = state.sheets.find((s) => s.id === state.activeSheet)
  const reference = refOf(next, SIZE, state.activeSheet === e.sheet || !sheet ? '' : sheetPrefix(sheet.name))
  const placed = reference === null ? null : pointTo(e.text, e.caret, reference)
  if (!placed) return
  e.text = placed.text
  e.caret = placed.caret
  sel.value = next
  pointed.value = true
  void nextTick(() => putCaret(placed.caret))
}

/** The text being typed keeps the focus, with the caret behind what was picked. */
function putCaret(position: number) {
  const inputs = [...document.querySelectorAll<HTMLInputElement>('input[data-editing]')]
  const target = inputs.find((i) => i === document.activeElement) ?? inputs.find((i) => i.classList.contains('editor')) ?? inputs[0]
  if (!target) return
  target.focus()
  target.setSelectionRange(position, position)
}

function moveBy(dr: number, dc: number, extend: boolean, jumping: boolean) {
  const sheet = state.activeSheet
  sel.value = jumping
    ? jump(sel.value, dr, dc, extend, SIZE, (r, c) => session.cell(sheet, r, c) !== null)
    : move(sel.value, dr, dc, extend, SIZE)
}

function goto(text: string) {
  const cell = parseCell(text)
  if (cell) sel.value = single(cell[0], cell[1])
  grid.value?.focus()
}

// ------------------------------------------------------------------------------ editing
async function beginEdit(initial?: string) {
  if (edit.value) return
  if (readonly.value) return session.notice('You can only look at this document.', 'warning')
  const { row, col } = sel.value
  original = inputOf(session.cell(state.activeSheet, row, col))
  const text = initial ?? original
  pointed.value = false
  edit.value = { sheet: state.activeSheet, row, col, text, caret: text.length }
  if (!(await session.beginEdit(state.activeSheet, row, col))) edit.value = null
}

async function commit(dir: 'down' | 'up' | 'right' | 'left' | 'none' = 'none') {
  const e = edit.value
  if (!e) return
  edit.value = null
  state.activeSheet = e.sheet // (a formula may have been typed while looking at another sheet)
  const delta = { down: [1, 0], up: [-1, 0], right: [0, 1], left: [0, -1], none: [0, 0] }[dir]
  sel.value = move(single(e.row, e.col), delta[0]!, delta[1]!, false, SIZE)
  grid.value?.focus()
  if (e.text !== original) await session.setCells(e.sheet, [{ row: e.row, col: e.col, input: e.text }])
  await session.endEdit()
}

async function cancel() {
  if (!edit.value) return
  state.activeSheet = edit.value.sheet
  edit.value = null
  grid.value?.focus()
  await session.endEdit()
}

function updateText(text: string) {
  if (!edit.value) return
  edit.value.text = text
  pointed.value = false
}

function moveCaret(position: number) {
  if (edit.value) edit.value.caret = position
}

// ------------------------------------------------------------------------------ in-context function help (E13.5)
// While a formula is typed, the formula bar shows the signature and a short example of the function the caret is
// inside of — the one piece of "help in context" this iteration builds; "Help on this" and hovering a menu item
// wait for the action manifest itself (E5.1), which is not built yet.
const currentFunctionName = computed(() => (edit.value ? currentFunctionAt(edit.value.text, edit.value.caret) : null))
const formulaHelp = ref<{ signature: string; help: string } | null>(null)
watch(currentFunctionName, async (name) => {
  if (!name) {
    formulaHelp.value = null
    return
  }
  const found = await session.functionHelp(name)
  if (currentFunctionName.value !== name) return // the caret moved again before the server answered
  formulaHelp.value = found === false ? null : found
})
/** The help text's first worked example (after the blank line that separates it from the description), if there
 * is one — core functions (`IF`, `XLOOKUP`, ...) have no `Example`s to draw one from, only the description. */
const formulaExample = computed(() => formulaHelp.value?.help.split('\n\n')[1]?.split('\n')[0] ?? '')

async function clearSelection() {
  if (readonly.value) return session.notice('You can only look at this document.', 'warning')
  const cells = session.filledIn(state.activeSheet, b.value.r0, b.value.c0, b.value.r1, b.value.c1)
  if (cells.length) await session.setCells(state.activeSheet, cells.map(([row, col]) => ({ row, col, input: '' })))
}

async function paste(rows: string[][]) {
  if (readonly.value) return session.notice('You can only look at this document.', 'warning')
  const cells = rows.flatMap((line, i) => line.map((input, j) => ({ row: b.value.r0 + i, col: b.value.c0 + j, input })))
  if (!cells.length) return
  if (cells.length > 10_000) return session.notice('That is too much to paste at once (at most 10,000 cells).', 'warning')
  if (cells.some((c) => c.row >= VIEW_ROWS || c.col >= VIEW_COLS)) return session.notice('That does not fit on the sheet.', 'warning')
  if (await session.setCells(state.activeSheet, cells)) {
    const last = cells[cells.length - 1]!
    sel.value = { row: b.value.r0, col: b.value.c0, row2: last.row, col2: last.col }
  }
}

/** Edit ▸ Paste / Paste as plain text, from a menu click rather than the grid's own native `paste` DOM event
 * (`@paste="paste"` below) — same destination (`paste(rows)`, which already knows where the selection is and checks
 * its bounds), only the source of the text differs: the Clipboard API instead of a browser paste event's data. */
async function pasteFromClipboard() {
  let text: string
  try {
    text = await navigator.clipboard.readText()
  } catch {
    return
  }
  if (text) await paste(text.split('\n').map((line) => line.split('\t')))
}

// ------------------------------------------------------------------------------ sheets, rows, columns
async function pickSheet(id: string) {
  if (edit.value && !pointing.value) await commit('none') // (a formula being typed can point at another sheet)
  state.activeSheet = id
  sel.value = single(0, 0)
  pointed.value = false
}

/** `FooterBar`'s `pick`: a sheet tab behaves exactly as before; a chart tab just swaps what the main pane
 * shows, with no selection, formula bar or editing of its own to settle first. */
async function pickTab(id: string, kind: 'sheet' | 'chart') {
  if (kind === 'chart') {
    activeChart.value = id
    return
  }
  activeChart.value = null
  await pickSheet(id)
}

async function addSheet(name: string) {
  dialog.value = null
  await session.addSheet(name)
  sel.value = single(0, 0)
}

async function structure(axis: 'row' | 'col', insert: boolean, after = false) {
  if (readonly.value) return session.notice('You can only look at this document.', 'warning')
  const first = axis === 'row' ? b.value.r0 : b.value.c0
  const last = axis === 'row' ? b.value.r1 : b.value.c1
  const count = last - first + 1
  await session.structure(state.activeSheet, axis, insert, insert && after ? last + 1 : first, count)
}

const styleHost = objectStyleHost({
  get readOnly() {
    return session.readOnly
  },
  get styles() {
    return session.styleViews()
  },
  get roles() {
    return state.palette?.roles ?? []
  },
  get readings() {
    return state.palette?.readings ?? []
  },
  get selected() {
    const id = grid.value?.selectedObject() ?? null
    return id ? state.objects[id] ?? null : null
  },
  get model() {
    return state.styleModel
  },
  get bodies() {
    return session.bodies()
  },
  applyStyle: (targets, style, slot) => session.applyStyle(targets, style, slot),
  changeStyle: (style, edit) => session.changeStyle(style, edit),
  deviateStyle: (parent, targets, slot, edit) => session.deviateStyle(parent, targets, slot, edit),
  renameStyle: (style, name) => session.renameStyle(style, name),
  checkCss: (text) => session.checkCss(text),
  setRole: (role, colour) => session.setRole(role, colour),
})

/** The selected cells as a style host (E6.13, D311): what the Format menu, the quick list, the popover at the active
 * cell and the All styles dialog style while no object is selected. */
const cellHost = cellStyleHost({
  get readOnly() {
    return session.readOnly
  },
  get styles() {
    return session.styleViews()
  },
  get roles() {
    return state.palette?.roles ?? []
  },
  get readings() {
    return state.palette?.readings ?? []
  },
  get model() {
    return state.styleModel
  },
  get sheet() {
    return state.activeSheet
  },
  get area(): [number, number, number, number] | null {
    if (!state.activeSheet || activeChart.value || objectSelected.value) return null
    return sheetArea([b.value.r0, b.value.c0, b.value.r1, b.value.c1], SIZE)
  },
  get anchor() {
    return { row: sel.value.row, col: sel.value.col }
  },
  ranges: () => session.cellStyles(state.activeSheet),
  uses: () => state.styleUses,
  applyStyle: (targets, style, slot) => session.applyStyle(targets, style, slot),
  changeStyle: (style, edit) => session.changeStyle(style, edit),
  deviateStyle: (parent, targets, slot, edit) => session.deviateStyle(parent, targets, slot, edit),
  renameStyle: (style, name) => session.renameStyle(style, name),
  clearCellStyle: (sheet, range, slot) => session.clearCellStyle(sheet, range, slot),
  checkCss: (text) => session.checkCss(text),
  setRole: (role, colour) => session.setRole(role, colour),
})

/** Whether a floating object is selected: then it, not the cells, is what the menus style (D209). The grid keeps
 * the selection; this mirrors it so that the menus follow it. */
const objectSelected = ref(false)
/** The host the menus use: the selected object's, or the selected cells'. */
const activeHost = computed(() => (objectSelected.value ? styleHost : cellHost))

/** Edit this style… at the active cell, or beside the selected object (D300, D302). */
const LOOK: ShortcutDef = { id: 'format.look', label: 'Edit this style…', chord: { key: 'F10', shift: true }, run: () => grid.value?.openStyleMenu() }
const extraShortcuts = [LOOK]

/**
 * The Format menu (D300): what it styles follows the selection — the selected cells (`computes-cell-styles.svg`,
 * panel B: both slots, D311, and Clear cell style, D317), or the floating object selected, in the slot the style
 * menu works on (D304, D316); the flyout's first line says which. The colours are the document's.
 */
function styleItems() {
  if (session.styleViews().length === 0) return [{ label: t('No styles yet'), disabled: true }]
  const selected = grid.value?.selectedObject()
  const body = selected ? state.objects[selected] : undefined
  const look = { hint: chordLabel(LOOK.chord), open: () => grid.value?.openStyleMenu() }
  const common = {
    openApply: () => grid.value?.openStyleMenu(undefined, 'apply'),
    allStyles: () => (dialog.value = 'styles'),
    colours: () => (dialog.value = 'colours'),
  }
  if (body) {
    const offered = galleryFor(styleHost.styles, styleHost.slot, state.styleModel)
    return formatItems(t, {
      ...common,
      groups: [offered.own, offered.bundles],
      heading: t('For the {thing}', { thing: styleHost.noun }),
      current: styleHost.current?.id,
      canApply: !readonly.value,
      apply: (id) => void styleHost.apply(id),
      look: { ...look, disabled: false },
    })
  }
  const offered = galleryFor(cellHost.styles, cellHost.slot, state.styleModel)
  const [r0, c0, r1, c1] = sheetArea([b.value.r0, b.value.c0, b.value.r1, b.value.c1], SIZE)
  const cells = (r1 - r0 + 1) * (c1 - c0 + 1)
  const some = !!state.activeSheet && !activeChart.value
  return formatItems(t, {
    ...common,
    groups: some ? [offered.own] : [],
    heading: !some ? t('Select cells or an object to style them') : cells === 1 ? t('For cell {cell}', { cell: label.value }) : t('For the {count} selected cells', { count: cells.toLocaleString('en-US') }),
    current: cellHost.current?.id,
    canApply: !readonly.value && some,
    apply: (id) => void cellHost.apply(id),
    look: { ...look, disabled: !some },
    more: some ? [{ id: 'format.clear-cell-style', label: t('Clear cell style'), disabled: readonly.value, action: () => void cellHost.clear?.() }] : [],
  })
}

/** Put the colours the document started with back, as the server itself states them. */
async function resetPalette() {
  const started = state.palette?.builtin ?? []
  if (started.length && (await session.replacePalette(started))) dialog.value = null
}

// Row/column header menu (mockup 1) and the resize dialog it opens (mockup 2) — SheetGrid.vue already made sure
// the selection covers the header that was right-clicked, so `b` (above) is the right range for all three actions.
function openHeaderMenu(axis: Axis, index: number, x: number, y: number) {
  headerMenu.value = { axis, index, x, y }
}
async function headerInsert(after: boolean) {
  const axis = headerMenu.value!.axis
  headerMenu.value = null
  await structure(axis, true, after)
}
async function headerDelete() {
  const axis = headerMenu.value!.axis
  headerMenu.value = null
  await structure(axis, false)
}
function headerResize() {
  if (readonly.value) {
    headerMenu.value = null
    return session.notice('You can only look at this document.', 'warning')
  }
  dialog.value = headerMenu.value!.axis === 'row' ? 'row-size' : 'col-size'
  headerMenu.value = null
}

// ------------------------------------------------------------------------------ images (E6.17)
const IMAGE_HEIGHT = 240 // pixels; an image is sized to this height and whatever width keeps its own aspect

/** Anchor a new image at the current selection's top-left cell, sized to keep its own aspect (the server rejects
 * any other size for an image, within one pixel — mirrors creates' `insertFrame('image', aspect, …)`). */
function anchorForImage(aspect: number) {
  return { row: b.value.r0, col: b.value.c0, w: Math.round(IMAGE_HEIGHT * aspect), h: IMAGE_HEIGHT }
}

function imageInserted(id: string) {
  dialog.value = null
  grid.value?.selectObject(id)
  grid.value?.focus()
}

// ------------------------------------------------------------------------------ charts (E6.6)
const CHART_HEIGHT = 300 // pixels; a chart has no aspect of its own to keep, so this default is just a size
const CHART_WIDTH = 480

/** Anchor a new chart's floating object at the current selection's top-left cell — same corner as the data it
 * charts, same precedent as `anchorForImage`; moving it off the data afterwards is a drag away. */
function anchorForChart() {
  return { row: b.value.r0, col: b.value.c0, w: CHART_WIDTH, h: CHART_HEIGHT }
}

/** The insert dialog places a chart as a floating object or as a tab of its own (D204): select the object, or
 * show the tab. */
function chartInserted(objectId: string | null, chartId: string | null) {
  dialog.value = null
  if (objectId) {
    grid.value?.selectObject(objectId)
    grid.value?.focus()
  } else if (chartId) {
    activeChart.value = chartId
  }
}

// ------------------------------------------------------------------------------ menus
/** What the shared menu items need from this window (`lib/document-menus.ts`). */
const shared = computed<DocumentMenuContext>(() => ({
  t,
  role: state.me.role,
  open: (name) => frame.value?.openDialog(name),
  leave: (opts) => emit('leave', opts),
  save: () => frame.value?.checkpoint(null),
}))

function ask(text: string) {
  frame.value?.ask(text)
}

const menus = computed<Menu[]>(() => {
  const c = shared.value
  return [
    fileMenu(c),
    {
      label: t('Edit'),
      items: [
        ...undoRedoItems(c, {
          canUndo: state.canUndo,
          undoLabel: state.undoLabel,
          canRedo: state.canRedo,
          redoLabel: state.redoLabel,
          undo: () => session.undo(),
          redo: () => session.redo(),
        }),
        { label: '', separator: true },
        ...clipboardItems(c, () => pasteFromClipboard()),
        { label: '', separator: true },
        { id: 'edit.new-sheet', label: t('New sheet…'), action: () => (dialog.value = 'sheet'), disabled: readonly.value },
        { id: 'edit.image', label: t('Image…'), action: () => (dialog.value = 'image'), disabled: readonly.value },
        { id: 'edit.chart', label: t('Chart…'), action: () => (dialog.value = 'chart'), disabled: readonly.value },
        { label: '', separator: true },
        // D130 (confirmed by the owner 2026-11-10): grouped into Row ▸ / Column ▸ rather
        // than six flat items, reusing the submenu mechanism Edit ▸ Paste as ▸ already needed.
        {
          id: 'edit.row',
          label: t('Row'),
          disabled: readonly.value,
          items: [
            { id: 'edit.row-insert-above', label: t('Insert above'), action: () => structure('row', true), disabled: readonly.value },
            { id: 'edit.row-insert-below', label: t('Insert below'), action: () => structure('row', true, true), disabled: readonly.value },
            { id: 'edit.row-delete', label: t('Delete'), action: () => structure('row', false), disabled: readonly.value },
          ],
        },
        {
          id: 'edit.column',
          label: t('Column'),
          disabled: readonly.value,
          items: [
            { id: 'edit.column-insert-left', label: t('Insert left'), action: () => structure('col', true), disabled: readonly.value },
            { id: 'edit.column-insert-right', label: t('Insert right'), action: () => structure('col', true, true), disabled: readonly.value },
            { id: 'edit.column-delete', label: t('Delete'), action: () => structure('col', false), disabled: readonly.value },
          ],
        },
        { label: '', separator: true },
        { id: 'edit.clear', label: t('Clear cells'), hint: 'Del', action: () => clearSelection(), disabled: readonly.value },
      ],
    },
    { label: t('Format'), items: styleItems() },
    {
      label: t('View'),
      items: [
        authorsItemUnavailable(c), // computes tracks no per-cell authorship yet
        panelItem(c, { open: () => frame.value?.isPanelOpen() ?? true, toggle: () => frame.value?.togglePanel() }),
        darkItem(c, { on: dark, toggle: toggleDark }),
      ],
    },
    {
      label: t('Tools'),
      items: [askItem(c, ask), { id: 'tools.example-budget', label: t('Ask for an example budget'), action: () => ask('@ai build an example budget') }],
    },
    configMenu(c, { current: locale.value, choose }),
    helpMenu(c, { ask, openHelp: (mode) => frame.value?.openHelp(mode) }),
  ]
})

// Config ▸ Shortcuts: the grid's own mouse and keyboard conventions, which are not a single `keydown` chord and so
// were never candidates for the shared map.
const SHORTCUT_NOTES: [string, string][] = [
  ['Arrows, Tab, Enter', 'move through the table'],
  ['Shift + arrows or drag', 'select a block'],
  ['Ctrl + arrows', 'jump to the edge of a block of data'],
  ['Type, F2 or double click', 'edit a cell (others are kept out of it while you do)'],
  ['Enter / Tab / Esc', 'keep and go down / keep and go right / cancel'],
  ['Ctrl + C / X / V', 'copy, cut and paste, also from and to other programs'],
]
</script>

<template>
  <DocumentFrame
    ref="frame"
    app="computes"
    :session="session"
    :menus="menus"
    :export-formats="EXPORT_FORMATS"
    :shortcut-notes="SHORTCUT_NOTES"
    :extra-shortcuts="extraShortcuts"
    @leave="(opts) => emit('leave', opts)"
    @saved="grid?.focus()"
  >
    <template #toolbar>
      <div class="formulaRow">
        <FormulaBar
          :label="label"
          :text="formulaText"
          :editing="edit !== null"
          :can-undo="state.canUndo"
          :can-redo="state.canRedo"
          :undo-label="state.undoLabel"
          :redo-label="state.redoLabel"
          :readonly="readonly"
          @goto="goto"
          @focus-text="beginEdit()"
          @update:text="updateText"
          @caret="moveCaret"
          @commit="commit('down')"
          @cancel="cancel"
          @undo="session.undo()"
          @redo="session.redo()"
        >
          <StylePicker v-if="state.activeSheet && !activeChart" :host="activeHost" :hint="chordLabel(LOOK.chord)" @look="grid?.openStyleMenu()" @styled="grid?.focus()" />
        </FormulaBar>
        <div v-if="formulaHelp" class="formulaHelp" role="status">
          <span class="sig mono">{{ formulaHelp.signature }}</span>
          <span v-if="formulaExample" class="example mono">{{ formulaExample }}</span>
        </div>
      </div>
    </template>
    <div v-if="activeChart" class="chart-tab">
      <ChartView v-if="activeChartSpec" :session="session" :diagram-id="activeChartSpec" />
      <div v-else class="nosheet">This chart's definition is gone.</div>
    </div>
    <SheetGrid
      v-else-if="state.activeSheet"
      ref="grid"
      :session="session"
      :sheet="state.activeSheet"
      :sel="sel"
      :edit="edit"
      :pointing="pointing"
      :anchored="pointed"
      :cell-host="cellHost"
      @object="objectSelected = $event"
      @styles="dialog = 'styles'"
      @select="select"
      @move="moveBy"
      @type="beginEdit($event)"
      @begin-edit="beginEdit()"
      @update:edit-text="updateText"
      @caret="moveCaret"
      @commit="commit($event)"
      @cancel="cancel"
      @clear="clearSelection"
      @paste="paste"
      @select-all="sel = { row: 0, col: 0, row2: VIEW_ROWS - 1, col2: VIEW_COLS - 1 }"
      @header-menu="openHeaderMenu"
    />
    <div v-else class="nosheet">This document has no sheet yet.</div>
    <template #footer>
      <FooterBar :state="state" :summary="summary" :can-add="!readonly" :active-chart="activeChart" @pick="pickTab" @add="dialog = 'sheet'" />
    </template>
    <template #overlay>
      <PromptDialog v-if="dialog === 'sheet'" title="New sheet" label="Name" ok="Add sheet" required placeholder="Forecast" @ok="addSheet" @close="dialog = null" />
      <SheetImageImportDialog v-if="dialog === 'image'" :session="session" :anchor-for="anchorForImage" @close="dialog = null" @inserted="imageInserted" />
      <SheetChartInsertDialog
        v-if="dialog === 'chart'"
        :session="session"
        :sheet="state.activeSheet"
        :range="b"
        :anchor-for="anchorForChart"
        @close="dialog = null"
        @inserted="chartInserted"
      />
      <StylesDialog v-if="dialog === 'styles'" :host="cellHost" @close="dialog = null" />
      <PaletteDialog v-if="dialog === 'colours'" :host="styleHost" :builtin="state.palette?.builtin ?? []" @close="dialog = null" @reset="resetPalette" />
      <LineSizeDialog
        v-if="dialog === 'row-size' || dialog === 'col-size'"
        :session="session"
        :sheet="state.activeSheet"
        :axis="dialog === 'row-size' ? 'row' : 'col'"
        :first="dialog === 'row-size' ? b.r0 : b.c0"
        :last="dialog === 'row-size' ? b.r1 : b.c1"
        @close="dialog = null"
      />
      <HeaderMenu
        v-if="headerMenu"
        :axis="headerMenu.axis"
        :x="headerMenu.x"
        :y="headerMenu.y"
        :readonly="readonly"
        @insert="headerInsert"
        @delete="headerDelete"
        @resize="headerResize"
        @close="headerMenu = null"
      />
    </template>
  </DocumentFrame>
</template>

<style scoped>
.formulaRow {
  position: relative;
}
.formulaHelp {
  position: absolute;
  z-index: 5;
  top: 100%;
  left: 118px; /* roughly where the formula text starts, past the cell-name box and undo/redo (FormulaBar.vue) */
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: calc(100% - 140px);
  padding: 5px 10px;
  border-radius: 0 0 8px 8px;
  background: var(--ink);
  color: #e6e0f5;
  font-size: 11.5px;
  box-shadow: 0 4px 10px rgb(0 0 0 / 18%);
  /* It sits over the column letters exactly while a formula is being typed — the moment a person clicks a letter
     to pick a whole column (e2e/pointing.cjs). It only reads, so clicks go through it to the header beneath. */
  pointer-events: none;
}
.formulaHelp .sig {
  color: #fff;
  flex: 0 0 auto;
}
.formulaHelp .example {
  color: rgb(230 224 245 / 65%);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.nosheet {
  display: grid;
  place-items: center;
  color: var(--muted);
}
.chart-tab {
  min-width: 0;
  min-height: 0;
  padding: 16px;
  background: var(--paper);
}
</style>
