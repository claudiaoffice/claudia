<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { alignment, columnName, inputOf, show, VIEW_COLS, VIEW_ROWS } from '~/lib/cells'
import { imageDataUrl } from '~/lib/images'
import { besideRect } from '~/lib/geometry'
import {
  buildSizeTable,
  DEFAULT_COL_WIDTH,
  DEFAULT_ROW_HEIGHT,
  formatPercent,
  indexAt,
  lineRange,
  lineStart,
  percentChange,
  proportionalResize,
  SIZE_LIMITS,
  type Axis,
  type SizeTable,
} from '~/lib/line-sizes'
import { objectStyleHost } from '~/lib/object-style-host'
import { colorOf, inkOn } from '~/lib/people'
import { REFERENCE_COLORS, referencesIn } from '~/lib/pointing'
import { bounds, parseTsv, toTsv, type Sel } from '~/lib/selection'
import type { Session, SheetObject } from '~/lib/session'

/** The cell being edited (on which sheet), what is typed so far and where the caret stands in it. */
export interface EditState {
  sheet: string
  row: number
  col: number
  text: string
  caret: number
}

const props = defineProps<{
  session: Session
  sheet: string
  sel: Sel
  edit: EditState | null
  /** Typing a formula where a picked reference fits: a click picks cells instead of ending the edit. */
  pointing: boolean
  /** The last pick is the selection, so shift+click may extend it. */
  anchored: boolean
}>()
const emit = defineEmits<{
  /** Asks the workspace to open the all-styles dialog, which owns the modal layer. */
  styles: []
  select: [sel: Sel, dragging: boolean]
  move: [dr: number, dc: number, extend: boolean, jump: boolean]
  type: [text: string]
  beginEdit: []
  'update:editText': [text: string]
  caret: [position: number]
  commit: [dir: 'down' | 'up' | 'right' | 'left']
  cancel: []
  clear: []
  paste: [rows: string[][]]
  selectAll: []
  /** A row or column header was right-clicked: open its menu (insert/delete/resize, mockup 1) at this point. */
  headerMenu: [axis: Axis, index: number, x: number, y: number]
}>()

const W = DEFAULT_COL_WIDTH // a column's width when it has no size of its own
const H = DEFAULT_ROW_HEIGHT // a row's height when it has no size of its own
const HW = 52 // width of the row numbers
const HH = 26 // height of the column letters
const BORDER = 4 // px on either side of a header's line between two lines that still counts as "on" it, for dragging

const viewport = ref<HTMLElement | null>(null)
const editor = ref<HTMLInputElement | null>(null)
const scroll = ref({ left: 0, top: 0 })
const size = ref({ w: 800, h: 600 })
let observer: ResizeObserver | null = null

const state = props.session.state

// ------------------------------------------------------------------------------ row heights and column widths
// Sparse, like the server's own storage (D135): most lines are `H`/`W`, a few have their own size. While a border
// is being dragged (`resizeDrag`, below), the line(s) it affects are shown at their live, not-yet-sent size, so the
// grid reflows as the mouse moves instead of jumping once the server answers.
const dragPairs = computed<[number, number][]>(() => {
  const d = resizeDrag.value
  if (!d) return []
  const committed = (i: number) => (d.axis === 'col' ? props.session.colWidth(props.sheet, i) : props.session.rowHeight(props.sheet, i))
  return proportionalResize(d.lines, committed, d.first, d.to, SIZE_LIMITS[d.axis])
})
const liveRowHeights = computed<Map<number, number>>(() => {
  const base = state.rowHeights[props.sheet]
  if (resizeDrag.value?.axis !== 'row') return base ?? new Map()
  const merged = new Map(base ?? [])
  for (const [i, h] of dragPairs.value) merged.set(i, h)
  return merged
})
const liveColWidths = computed<Map<number, number>>(() => {
  const base = state.colWidths[props.sheet]
  if (resizeDrag.value?.axis !== 'col') return base ?? new Map()
  const merged = new Map(base ?? [])
  for (const [i, w] of dragPairs.value) merged.set(i, w)
  return merged
})
const rowTable = computed<SizeTable>(() => buildSizeTable(liveRowHeights.value, H))
const colTable = computed<SizeTable>(() => buildSizeTable(liveColWidths.value, W))

function rowHeightAt(row: number): number {
  return liveRowHeights.value.get(row) ?? H
}
function colWidthAt(col: number): number {
  return liveColWidths.value.get(col) ?? W
}

const totalW = computed(() => HW + lineStart(colTable.value, W, VIEW_COLS))
const totalH = computed(() => HH + lineStart(rowTable.value, H, VIEW_ROWS))

const range = computed(() => ({
  r0: indexAt(rowTable.value, H, scroll.value.top, VIEW_ROWS),
  r1: indexAt(rowTable.value, H, scroll.value.top + size.value.h - HH, VIEW_ROWS),
  c0: indexAt(colTable.value, W, scroll.value.left, VIEW_COLS),
  c1: indexAt(colTable.value, W, scroll.value.left + size.value.w - HW, VIEW_COLS),
}))

const x = (col: number) => HW + lineStart(colTable.value, W, col) - scroll.value.left
const y = (row: number) => HH + lineStart(rowTable.value, H, row) - scroll.value.top

const editHere = computed(() => props.edit !== null && props.edit.sheet === props.sheet)

const cells = computed(() => {
  void state.generation
  const out: { key: number; left: number; top: number; width: number; height: number; text: string; align: string; kind: string }[] = []
  const { r0, r1, c0, c1 } = range.value
  for (let r = r0; r <= r1; r++) {
    for (let c = c0; c <= c1; c++) {
      const content = props.session.cell(props.sheet, r, c)
      if (content === null || (editHere.value && props.edit!.row === r && props.edit!.col === c)) continue
      out.push({ key: r * 100_000 + c, left: x(c), top: y(r), width: colWidthAt(c), height: rowHeightAt(r), text: show(content), align: alignment(content), kind: content.t })
    }
  }
  return out
})

const colHeads = computed(() => {
  const b = bounds(props.sel)
  const out = []
  for (let c = range.value.c0; c <= range.value.c1; c++) out.push({ c, left: x(c), width: colWidthAt(c), name: columnName(c), on: c >= b.c0 && c <= b.c1 })
  return out
})
const rowHeads = computed(() => {
  const b = bounds(props.sel)
  const out = []
  for (let r = range.value.r0; r <= range.value.r1; r++) out.push({ r, top: y(r), height: rowHeightAt(r), on: r >= b.r0 && r <= b.r1 })
  return out
})

const box = (r0: number, c0: number, r1: number, c1: number) => ({
  left: `${x(c0)}px`,
  top: `${y(r0)}px`,
  width: `${lineStart(colTable.value, W, c1 + 1) - lineStart(colTable.value, W, c0)}px`,
  height: `${lineStart(rowTable.value, H, r1 + 1) - lineStart(rowTable.value, H, r0)}px`,
})

const selectionStyle = computed(() => {
  const b = bounds(props.sel)
  return box(b.r0, b.c0, b.r1, b.c1)
})
const activeStyle = computed(() => box(props.sel.row, props.sel.col, props.sel.row, props.sel.col))

const outlines = computed(() => {
  const out: { id: string; style: Record<string, string>; name: string; locked: boolean; ai: boolean }[] = []
  for (const [user, hold] of Object.entries(state.presence)) {
    if (user === state.me.user) continue
    const color = colorOf(state, user)
    hold.regions.forEach((region, i) => {
      if (region.kind !== 'cells' || region.range.first.sheet !== props.sheet) return
      const { first, last } = region.range
      out.push({
        id: `${user}:${i}`,
        name: user,
        locked: hold.locked,
        ai: user.toLowerCase() === 'ai',
        style: { ...box(first.row, first.col, last.row, last.col), '--who': color, '--who-ink': inkOn(color) },
      })
    })
  }
  return out
})

// ------------------------------------------------------------------------------ floating objects (images)
/** Selecting an image is local to this view (not shared with colleagues, unlike cell presence): E6.17 only
 * asked that an image never resizes on a structural edit and takes click priority over the cells beneath it. */
const selectedObject = ref<string | null>(null)

const objects = computed(() => props.session.objectsOn(props.sheet))

/** An object's own anchor, or the live position of the drag in progress that is moving it. */
function anchorOf(o: SheetObject): { row: number; col: number } {
  return objDrag.value?.id === o.id ? objDrag.value.pos : { row: o.anchor.row, col: o.anchor.col }
}
function objectStyle(o: SheetObject) {
  const { row, col } = anchorOf(o)
  return { left: `${x(col)}px`, top: `${y(row)}px`, width: `${o.w}px`, height: `${o.h}px` }
}
function pictureSrc(o: SheetObject): string | null {
  const asset = o.image ? state.images[o.image] : null
  return asset ? imageDataUrl(asset) : null
}

type ObjDrag = { id: string; from: { x: number; y: number }; start: { row: number; col: number }; pos: { row: number; col: number }; moved: boolean }
const objDrag = ref<ObjDrag | null>(null)

/** `stopPropagation` here is the whole of "the image takes click priority": the cell grid's own `onDown` is
 * bound on the outer `.viewport` and never even sees a mousedown that an object already caught, so a cell
 * underneath an image cannot be reached by clicking — only by moving the image out of the way. */
function onObjectDown(event: MouseEvent, o: SheetObject) {
  if (event.button !== 0) return
  event.stopPropagation()
  if (props.edit) emit('commit', 'down')
  viewport.value?.focus() // so Delete/Escape reach `onKey` even if the focus was elsewhere (the formula bar, say)
  selectedObject.value = o.id
  objDrag.value = { id: o.id, from: { x: event.clientX, y: event.clientY }, start: { row: o.anchor.row, col: o.anchor.col }, pos: { row: o.anchor.row, col: o.anchor.col }, moved: false }
  window.addEventListener('mousemove', onObjectDrag)
  window.addEventListener('mouseup', onObjectUp)
}

function onObjectDrag(event: MouseEvent) {
  const d = objDrag.value
  if (!d) return
  const dCol = Math.round((event.clientX - d.from.x) / W)
  const dRow = Math.round((event.clientY - d.from.y) / H)
  const row = Math.max(0, Math.min(VIEW_ROWS - 1, d.start.row + dRow))
  const col = Math.max(0, Math.min(VIEW_COLS - 1, d.start.col + dCol))
  if (row !== d.pos.row || col !== d.pos.col) {
    d.pos = { row, col }
    d.moved = true
  }
}

function onObjectUp() {
  const d = objDrag.value
  objDrag.value = null
  window.removeEventListener('mousemove', onObjectDrag)
  window.removeEventListener('mouseup', onObjectUp)
  if (d && d.moved && (d.pos.row !== d.start.row || d.pos.col !== d.start.col)) void props.session.moveObject(d.id, d.pos.row, d.pos.col)
}
onBeforeUnmount(onObjectUp)

/** Grid lines for the rows and columns currently in view, at their own (possibly resized) positions — a plain
 * repeating background, as it was before D135, can only draw lines evenly spaced apart. */
const rowLines = computed(() => {
  const out: { key: number; top: number }[] = []
  const { r0, r1 } = range.value
  for (let r = r0; r <= r1; r++) out.push({ key: r, top: y(r) + rowHeightAt(r) })
  return out
})
const colLines = computed(() => {
  const out: { key: number; left: number }[] = []
  const { c0, c1 } = range.value
  for (let c = c0; c <= c1; c++) out.push({ key: c, left: x(c) + colWidthAt(c) })
  return out
})

/** The cells the formula being typed refers to, outlined in the colour its reference has in the text. */
const referenced = computed(() => {
  if (!props.edit) return []
  const wanted = (name: string | null) =>
    name === null ? props.edit!.sheet : state.sheets.find((s) => s.name.toLowerCase() === name.toLowerCase())?.id
  const last = { row: VIEW_ROWS - 1, col: VIEW_COLS - 1 }
  return referencesIn(props.edit.text).flatMap((ref, i) =>
    wanted(ref.sheet) === props.sheet && ref.r0 <= last.row && ref.c0 <= last.col
      ? [{ key: i, color: REFERENCE_COLORS[i % REFERENCE_COLORS.length]!, style: box(ref.r0, ref.c0, Math.min(ref.r1, last.row), Math.min(ref.c1, last.col)) }]
      : [],
  )
})

const editorStyle = computed(() => {
  if (!props.edit) return {}
  const width = Math.max(colWidthAt(props.edit.col), Math.min(360, props.edit.text.length * 8 + 28))
  return { left: `${x(props.edit.col)}px`, top: `${y(props.edit.row)}px`, width: `${width}px`, height: `${rowHeightAt(props.edit.row)}px` }
})

// ------------------------------------------------------------------------------ loading what is in view
let pending = 0
function load() {
  cancelAnimationFrame(pending)
  pending = requestAnimationFrame(() => {
    const { r0, r1, c0, c1 } = range.value
    props.session.ensure(props.sheet, r0, r1, c0, c1).catch(() => undefined)
    props.session.ensureSizes(props.sheet).catch(() => undefined)
  })
}

function onScroll() {
  const el = viewport.value
  if (!el) return
  scroll.value = { left: el.scrollLeft, top: el.scrollTop }
  load()
}

function measure() {
  const el = viewport.value
  if (el) size.value = { w: el.clientWidth, h: el.clientHeight }
  load()
}

onMounted(() => {
  measure()
  observer = new ResizeObserver(measure)
  if (viewport.value) observer.observe(viewport.value)
  viewport.value?.focus()
})
onBeforeUnmount(() => {
  observer?.disconnect()
  cancelAnimationFrame(pending)
})
watch(() => [state.generation, props.sheet], load)

// ------------------------------------------------------------------------------ keeping the focus cell in view
function reveal(row: number, col: number, vertically: boolean, horizontally: boolean) {
  const el = viewport.value
  if (!el) return
  const left = lineStart(colTable.value, W, col)
  const top = lineStart(rowTable.value, H, row)
  const colW = colWidthAt(col)
  const rowH = rowHeightAt(row)
  if (horizontally) {
    if (left < el.scrollLeft) el.scrollLeft = left
    else if (left + colW > el.scrollLeft + el.clientWidth - HW) el.scrollLeft = left + colW - (el.clientWidth - HW)
  }
  if (vertically) {
    if (top < el.scrollTop) el.scrollTop = top
    else if (top + rowH > el.scrollTop + el.clientHeight - HH) el.scrollTop = top + rowH - (el.clientHeight - HH)
  }
}
watch(
  () => [props.sel.row, props.sel.col, props.sel.row2, props.sel.col2],
  ([row, col, row2, col2]) => {
    // a whole column (or row) was picked at its header: the view stays where it is instead of running to its far end
    const wholeColumn = row === 0 && row2 === VIEW_ROWS - 1
    const wholeRow = col === 0 && col2 === VIEW_COLS - 1
    reveal(row2!, col2!, !wholeColumn, !wholeRow)
  },
)

watch(
  editHere,
  async (editing) => {
    if (!editing) return
    await nextTick()
    const input = editor.value
    if (input) {
      input.focus()
      input.setSelectionRange(input.value.length, input.value.length)
    }
  },
)

// ------------------------------------------------------------------------------ mouse
let dragging = false

function stagePoint(event: MouseEvent): { px: number; py: number } | null {
  if (!(event.target as HTMLElement).closest('.stage')) return null
  const stage = viewport.value?.querySelector('.stage')
  if (!stage) return null
  const box = stage.getBoundingClientRect()
  return { px: event.clientX - box.left, py: event.clientY - box.top }
}

function cellAt(event: MouseEvent): { row: number; col: number; rowHead: boolean; colHead: boolean } | null {
  const p = stagePoint(event)
  if (!p) return null
  const { px, py } = p
  const col = indexAt(colTable.value, W, px - HW + scroll.value.left, VIEW_COLS)
  const row = indexAt(rowTable.value, H, py - HH + scroll.value.top, VIEW_ROWS)
  return { row, col, rowHead: px < HW, colHead: py < HH }
}

/** The column whose right border is within `BORDER` px of screen position `px` in the header strip, if any. */
function colBorderNear(px: number): number | null {
  const near = indexAt(colTable.value, W, px - HW + scroll.value.left, VIEW_COLS)
  for (const c of [near - 1, near]) {
    if (c < 0 || c >= VIEW_COLS) continue
    if (Math.abs(px - (x(c) + colWidthAt(c))) <= BORDER) return c
  }
  return null
}
/** Same as `colBorderNear`, for a row's bottom border in the row-number strip. */
function rowBorderNear(py: number): number | null {
  const near = indexAt(rowTable.value, H, py - HH + scroll.value.top, VIEW_ROWS)
  for (const r of [near - 1, near]) {
    if (r < 0 || r >= VIEW_ROWS) continue
    if (Math.abs(py - (y(r) + rowHeightAt(r))) <= BORDER) return r
  }
  return null
}

function onDown(event: MouseEvent) {
  if ((event.target as HTMLElement).closest('.editor')) return
  if (event.button !== 0) return
  const p = stagePoint(event)
  if (p) {
    if (p.py < HH && p.px >= HW) {
      const c = colBorderNear(p.px)
      if (c !== null) return startResizeDrag('col', c, event)
    }
    if (p.px < HW && p.py >= HH) {
      const r = rowBorderNear(p.py)
      if (r !== null) return startResizeDrag('row', r, event)
    }
  }
  const hit = cellAt(event)
  if (!hit) return
  selectedObject.value = null
  const picking = props.edit !== null && props.pointing // (then the focus stays in the text being typed)
  if (props.edit && !picking) emit('commit', 'down') // clicking elsewhere keeps what was typed
  if (!picking) viewport.value?.focus()
  event.preventDefault()
  const { row, col } = hit
  let next: Sel
  if (hit.rowHead && hit.colHead) next = { row: 0, col: 0, row2: VIEW_ROWS - 1, col2: VIEW_COLS - 1 }
  else if (hit.colHead) next = { row: 0, col, row2: VIEW_ROWS - 1, col2: col }
  else if (hit.rowHead) next = { row, col: 0, row2: row, col2: VIEW_COLS - 1 }
  else if (event.shiftKey && (!picking || props.anchored)) next = { ...props.sel, row2: row, col2: col }
  else next = { row, col, row2: row, col2: col }
  dragging = !hit.rowHead && !hit.colHead
  emit('select', next, dragging)
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', onUp)
}

function onDrag(event: MouseEvent) {
  if (!dragging) return
  const stage = viewport.value?.getBoundingClientRect()
  if (!stage) return
  const px = event.clientX - stage.left
  const py = event.clientY - stage.top
  const col = indexAt(colTable.value, W, px - HW + scroll.value.left, VIEW_COLS)
  const row = indexAt(rowTable.value, H, py - HH + scroll.value.top, VIEW_ROWS)
  if (row !== props.sel.row2 || col !== props.sel.col2) emit('select', { ...props.sel, row2: row, col2: col }, true)
}

function onUp() {
  dragging = false
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', onUp)
}
onBeforeUnmount(onUp)

function onDouble(event: MouseEvent) {
  const hit = cellAt(event)
  if (hit && !hit.rowHead && !hit.colHead) emit('beginEdit')
}

// ------------------------------------------------------------------------------ resizing rows and columns (D135)
// The rule agreed over the mockups (round 2): dragging the border that follows the top-most/left-most line of a
// multi-line selection scales every other selected line by the same percentage; any other border — including that
// same border with only one line selected — resizes just the one line it belongs to. `first`/`lines` below already
// encode which of those this drag is.
interface ResizeDrag {
  axis: Axis
  first: number
  lines: number[]
  startSize: number
  startClient: number
  to: number
}
const resizeDrag = ref<ResizeDrag | null>(null)

function dragTarget(axis: Axis, index: number): { first: number; lines: number[] } {
  const b = bounds(props.sel)
  const whole = axis === 'col' ? props.sel.row === 0 && props.sel.row2 === VIEW_ROWS - 1 : props.sel.col === 0 && props.sel.col2 === VIEW_COLS - 1
  const lo = axis === 'col' ? b.c0 : b.r0
  const hi = axis === 'col' ? b.c1 : b.r1
  if (whole && index === lo && hi > lo) return { first: lo, lines: lineRange(lo, hi) }
  return { first: index, lines: [index] }
}

function startResizeDrag(axis: Axis, index: number, event: MouseEvent) {
  event.preventDefault()
  const target = dragTarget(axis, index)
  const startSize = axis === 'col' ? props.session.colWidth(props.sheet, target.first) : props.session.rowHeight(props.sheet, target.first)
  resizeDrag.value = { axis, first: target.first, lines: target.lines, startSize, startClient: axis === 'col' ? event.clientX : event.clientY, to: startSize }
  window.addEventListener('mousemove', onResizeMove)
  window.addEventListener('mouseup', onResizeUp)
}

function onResizeMove(event: MouseEvent) {
  const d = resizeDrag.value
  if (!d) return
  const client = d.axis === 'col' ? event.clientX : event.clientY
  const limits = SIZE_LIMITS[d.axis]
  d.to = Math.min(limits.hi, Math.max(limits.lo, d.startSize + (client - d.startClient)))
}

async function onResizeUp() {
  window.removeEventListener('mousemove', onResizeMove)
  window.removeEventListener('mouseup', onResizeUp)
  const d = resizeDrag.value
  if (!d) return
  const changed = Math.round(d.to) !== Math.round(d.startSize)
  const pairs = dragPairs.value
  resizeDrag.value = null
  if (changed) await props.session.resizeLines(props.sheet, d.axis, pairs)
}
onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onResizeMove)
  window.removeEventListener('mouseup', onResizeUp)
})

/** The live "144 px · +50%" readout beside the dragged border (mockups 3/4). */
const dragTag = computed(() => {
  const d = resizeDrag.value
  if (!d) return null
  const text = `${Math.round(d.to)} px · ${formatPercent(percentChange(d.startSize, d.to))}`
  if (d.axis === 'col') return { left: x(d.first) + colWidthAt(d.first), top: HH + 8, text }
  return { left: HW + 8, top: y(d.first) + rowHeightAt(d.first), text }
})
/** The border being dragged, highlighted at its live position (on top of the ordinary grid line, which already
 * moved there too). */
const activeBorder = computed(() => {
  const d = resizeDrag.value
  if (!d) return null
  return d.axis === 'col' ? { axis: 'col' as const, pos: x(d.first) + colWidthAt(d.first) } : { axis: 'row' as const, pos: y(d.first) + rowHeightAt(d.first) }
})

/** Cursor feedback when hovering a resizable border, outside of an actual drag. */
const hoverAxis = ref<Axis | null>(null)
function onHeaderHover(event: MouseEvent) {
  if (resizeDrag.value || dragging) return
  const p = stagePoint(event)
  if (p && p.py < HH && p.px >= HW && colBorderNear(p.px) !== null) {
    hoverAxis.value = 'col'
  } else if (p && p.px < HW && p.py >= HH && rowBorderNear(p.py) !== null) {
    hoverAxis.value = 'row'
  } else {
    hoverAxis.value = null
  }
}

// ------------------------------------------------------------------------------ the row/column header menu
function onHeaderContext(event: MouseEvent) {
  if (event.shiftKey && event.clientX !== 0) return // Shift + right button: the browser's own menu, as in TextEditor.vue
  const hit = cellAt(event)
  if (!hit || hit.rowHead === hit.colHead) return // a normal cell, or the corner: no menu for either
  event.preventDefault()
  const axis: Axis = hit.colHead ? 'col' : 'row'
  const index = axis === 'col' ? hit.col : hit.row
  const b = bounds(props.sel)
  const whole = axis === 'col' ? props.sel.row === 0 && props.sel.row2 === VIEW_ROWS - 1 : props.sel.col === 0 && props.sel.col2 === VIEW_COLS - 1
  const within = whole && (axis === 'col' ? index >= b.c0 && index <= b.c1 : index >= b.r0 && index <= b.r1)
  if (!within) {
    const next: Sel = axis === 'col' ? { row: 0, col: index, row2: VIEW_ROWS - 1, col2: index } : { row: index, col: 0, row2: index, col2: VIEW_COLS - 1 }
    emit('select', next, false)
  }
  emit('headerMenu', axis, index, event.clientX, event.clientY)
}

// ------------------------------------------------------------------------------ keyboard
const ARROWS: Record<string, [number, number]> = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }

function onKey(event: KeyboardEvent) {
  if (props.edit) return
  const mod = event.ctrlKey || event.metaKey
  const arrow = ARROWS[event.key]
  if (arrow) {
    event.preventDefault()
    emit('move', arrow[0], arrow[1], event.shiftKey, mod)
  } else if (event.key === 'Tab') {
    event.preventDefault()
    emit('move', 0, event.shiftKey ? -1 : 1, false, false)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    if (event.shiftKey) emit('move', -1, 0, false, false)
    else emit('beginEdit')
  } else if (event.key === 'F2') {
    event.preventDefault()
    emit('beginEdit')
  } else if (event.key === 'PageDown' || event.key === 'PageUp') {
    event.preventDefault()
    const rows = Math.max(1, Math.floor((size.value.h - HH) / H) - 1)
    emit('move', event.key === 'PageDown' ? rows : -rows, 0, event.shiftKey, false)
  } else if (event.key === 'Home') {
    event.preventDefault()
    emit('move', 0, -VIEW_COLS, event.shiftKey, false)
  } else if (event.key === 'Escape' && selectedObject.value) {
    event.preventDefault()
    selectedObject.value = null
  } else if (event.key === 'Delete' || event.key === 'Backspace') {
    event.preventDefault()
    if (selectedObject.value) {
      void props.session.removeObject(selectedObject.value)
      selectedObject.value = null
    } else emit('clear')
  } else if (mod && event.key.toLowerCase() === 'a') {
    event.preventDefault()
    emit('selectAll')
  } else if (!mod && !event.altKey && event.key.length === 1) {
    event.preventDefault()
    emit('type', event.key)
  }
}

function reportCaret(event: Event) {
  const position = (event.target as HTMLInputElement).selectionStart
  if (position !== null) emit('caret', position)
}

function onEditorInput(event: Event) {
  emit('update:editText', (event.target as HTMLInputElement).value)
  reportCaret(event)
}

function onEditorKey(event: KeyboardEvent) {
  event.stopPropagation()
  if (event.key === 'Enter') {
    event.preventDefault()
    emit('commit', event.shiftKey ? 'up' : 'down')
  } else if (event.key === 'Tab') {
    event.preventDefault()
    emit('commit', event.shiftKey ? 'left' : 'right')
  } else if (event.key === 'Escape') {
    event.preventDefault()
    emit('cancel')
  }
}

// ------------------------------------------------------------------------------ clipboard
function onCopy(event: ClipboardEvent) {
  if (props.edit) return
  const b = bounds(props.sel)
  if ((b.r1 - b.r0 + 1) * (b.c1 - b.c0 + 1) > 50_000) return
  const rows: string[][] = []
  for (let r = b.r0; r <= b.r1; r++) {
    const row: string[] = []
    for (let c = b.c0; c <= b.c1; c++) row.push(inputOf(props.session.cell(props.sheet, r, c)))
    rows.push(row)
  }
  event.clipboardData?.setData('text/plain', toTsv(rows))
  event.preventDefault()
}

function onPaste(event: ClipboardEvent) {
  if (props.edit) return
  const text = event.clipboardData?.getData('text/plain')
  if (!text) return
  event.preventDefault()
  emit('paste', parseTsv(text))
}

// ------------------------------------------------------------------------------ the style menu (E9.7, D203)
/** A floating object's own look: its fill, its border. The same menu composes and creates use — what it styles is
 * whatever `objectStyleHost` says is selected, which here is this grid's own `selectedObject`. */
const styleMenu = ref<{ x: number; y: number; mode?: 'edit' | 'apply' } | null>(null)
const styleHost = objectStyleHost({
  get readOnly() {
    return props.session.readOnly
  },
  get styles() {
    return props.session.styleViews()
  },
  get roles() {
    return props.session.state.palette?.roles ?? []
  },
  get readings() {
    return props.session.state.palette?.readings ?? []
  },
  get selected() {
    const id = selectedObject.value
    return id ? props.session.state.objects[id] ?? null : null
  },
  get model() {
    return props.session.state.styleModel
  },
  get bodies() {
    return props.session.bodies()
  },
  applyStyle: (targets, style, slot) => props.session.applyStyle(targets, style, slot),
  changeStyle: (style, edit) => props.session.changeStyle(style, edit),
  deviateStyle: (parent, targets, slot, edit) => props.session.deviateStyle(parent, targets, slot, edit),
  renameStyle: (style, name) => props.session.renameStyle(style, name),
  checkCss: (text) => props.session.checkCss(text),
  setRole: (role, colour) => props.session.setRole(role, colour),
})

/** Format ▸ Edit this style…, Apply style…: beside the selected object, so it stays in view. */
function openStyleMenu(at?: { x: number; y: number }, mode: 'edit' | 'apply' = 'edit') {
  if (!selectedObject.value) return
  const el = viewport.value?.querySelector(`[data-object="${CSS.escape(selectedObject.value)}"]`)
  const where = at ?? (el ? besideRect(el.getBoundingClientRect(), mode === 'apply' ? 280 : 360, window.innerWidth) : { x: 160, y: 180 })
  styleMenu.value = { ...where, mode }
}

defineExpose({
  focus: () => viewport.value?.focus(),
  selectObject: (id: string) => (selectedObject.value = id),
  openStyleMenu,
  /** What the Format menu ticks and disables itself by. */
  selectedObject: () => selectedObject.value,
})
</script>

<template>
  <div
    ref="viewport"
    class="viewport"
    :class="{ 'resize-col': hoverAxis === 'col' || resizeDrag?.axis === 'col', 'resize-row': hoverAxis === 'row' || resizeDrag?.axis === 'row' }"
    tabindex="0"
    role="grid"
    aria-label="table"
    @scroll.passive="onScroll"
    @mousedown="onDown"
    @mousemove.passive="onHeaderHover"
    @dblclick="onDouble"
    @contextmenu.capture="onHeaderContext"
    @keydown="onKey"
    @copy="onCopy"
    @paste="onPaste"
  >
    <div class="canvas" :style="{ width: `${totalW}px`, height: `${totalH}px` }">
      <div class="stage" :style="{ width: `${size.w}px`, height: `${size.h}px` }">
        <div v-for="rl in rowLines" :key="`r${rl.key}`" class="gridline horiz" :style="{ top: `${rl.top}px` }" />
        <div v-for="cl in colLines" :key="`c${cl.key}`" class="gridline vert" :style="{ left: `${cl.left}px` }" />
        <div
          v-for="cell in cells"
          :key="cell.key"
          class="cell"
          :class="[cell.kind, cell.align]"
          :style="{ left: `${cell.left}px`, top: `${cell.top}px`, width: `${cell.width}px`, height: `${cell.height}px` }"
        >
          {{ cell.text }}
        </div>

        <div class="selection" :class="{ picking: edit && pointing }" :style="selectionStyle" />
        <div class="active" :class="{ picking: edit && pointing }" :style="activeStyle" />
        <div v-for="r in referenced" :key="r.key" class="reference" :style="{ ...r.style, '--color': r.color }" />

        <div
          v-for="o in objects"
          :key="o.id"
          class="object"
          :class="{ selected: o.id === selectedObject }"
          :data-object="o.id"
          :style="objectStyle(o)"
          @mousedown.stop="onObjectDown($event, o)"
          @dblclick.stop
        >
          <ChartView v-if="o.kind === 'diagram' && o.diagram" :session="session" :diagram-id="o.diagram" :width="o.w" :height="o.h" />
          <img v-else-if="pictureSrc(o)" :src="pictureSrc(o)!" :alt="o.imported?.alt ?? ''" draggable="false" >
        </div>

        <div v-for="o in outlines" :key="o.id" class="outline" :class="{ locked: o.locked, ai: o.ai }" :style="o.style">
          <span class="tag">{{ o.name }}<template v-if="o.locked"> · editing</template></span>
        </div>

        <div v-if="activeBorder" class="active-border" :class="activeBorder.axis" :style="activeBorder.axis === 'col' ? { left: `${activeBorder.pos}px` } : { top: `${activeBorder.pos}px` }" />
        <div v-if="dragTag" class="size-tag" :style="{ left: `${dragTag.left}px`, top: `${dragTag.top}px` }">{{ dragTag.text }}</div>

        <input
          v-if="editHere"
          ref="editor"
          data-editing
          class="editor mono"
          :style="editorStyle"
          :value="edit!.text"
          spellcheck="false"
          autocomplete="off"
          aria-label="editing cell"
          @input="onEditorInput"
          @keyup="reportCaret"
          @click="reportCaret"
          @keydown="onEditorKey"
        >

        <div class="colheads">
          <div v-for="h in colHeads" :key="h.c" class="colhead" :class="{ on: h.on }" :style="{ left: `${h.left - HW}px`, width: `${h.width}px` }">{{ h.name }}</div>
        </div>
        <div class="rowheads">
          <div v-for="h in rowHeads" :key="h.r" class="rowhead" :class="{ on: h.on }" :style="{ top: `${h.top - HH}px`, height: `${h.height}px` }">{{ h.r + 1 }}</div>
        </div>
        <div class="corner" />
      </div>
    </div>
    <StyleMenu v-if="styleMenu" :host="styleHost" :x="styleMenu.x" :y="styleMenu.y" :mode="styleMenu.mode" @close="styleMenu = null" @styles="((styleMenu = null), emit('styles'))" />
  </div>
</template>

<style scoped>
.viewport {
  position: relative;
  overflow: auto;
  background: var(--surface);
  outline: none;
  min-height: 0;
  min-width: 0;
}
.viewport.resize-col {
  cursor: col-resize;
}
.viewport.resize-row {
  cursor: row-resize;
}
.canvas {
  position: relative;
}
.stage {
  position: sticky;
  top: 0;
  left: 0;
  overflow: hidden;
  font-size: 13px;
  user-select: none;
}
.gridline {
  position: absolute;
  background: var(--line);
}
.gridline.horiz {
  left: 0;
  right: 0;
  height: 1px;
}
.gridline.vert {
  top: 0;
  bottom: 0;
  width: 1px;
}
.cell {
  position: absolute;
  padding: 0 7px;
  line-height: 26px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-variant-numeric: tabular-nums;
}
.cell.right {
  text-align: right;
}
.cell.center {
  text-align: center;
  font-weight: 500;
}
.cell.error {
  color: var(--rose);
}
.selection {
  position: absolute;
  background: color-mix(in srgb, var(--app) 9%, transparent);
  border: 1px solid color-mix(in srgb, var(--app) 60%, transparent);
  pointer-events: none;
}
.active {
  position: absolute;
  border: 2px solid var(--app);
  pointer-events: none;
}
.selection.picking,
.active.picking {
  border-style: dashed;
}
.reference {
  position: absolute;
  border: 2px solid var(--color);
  background: color-mix(in srgb, var(--color) 8%, transparent);
  pointer-events: none;
}
.object {
  position: absolute;
  overflow: hidden;
  cursor: grab;
  outline: 2px solid transparent;
}
.object.selected {
  outline-color: var(--app);
}
.object img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
  user-select: none;
}
.outline {
  position: absolute;
  border: 2px solid var(--who);
  pointer-events: none;
}
.outline.locked {
  background: color-mix(in srgb, var(--who) 14%, transparent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--who) 25%, transparent);
}
.outline .tag {
  position: absolute;
  left: -2px;
  bottom: 100%;
  background: var(--who);
  color: var(--who-ink);
  font-size: 11px;
  font-weight: 500;
  line-height: 1;
  padding: 3px 6px;
  border-radius: 6px 6px 6px 0;
  white-space: nowrap;
}
.active-border {
  position: absolute;
  background: var(--app);
  pointer-events: none;
  z-index: 4;
}
.active-border.col {
  top: 0;
  bottom: 0;
  width: 2px;
}
.active-border.row {
  left: 0;
  right: 0;
  height: 2px;
}
.size-tag {
  position: absolute;
  z-index: 5;
  background: var(--app);
  color: #fff;
  font-size: 11px;
  font-weight: 500;
  line-height: 1;
  padding: 3px 7px;
  border-radius: 6px;
  white-space: nowrap;
  pointer-events: none;
  font-variant-numeric: tabular-nums;
}
.editor {
  position: absolute;
  z-index: 3;
  border: 2px solid var(--app);
  background: var(--surface);
  padding: 0 6px;
  font-size: 13px;
  outline: none;
  user-select: text;
}
.colheads {
  position: absolute;
  top: 0;
  left: 52px;
  right: 0;
  height: 26px;
  overflow: hidden;
  pointer-events: none;
}
.rowheads {
  position: absolute;
  top: 26px;
  left: 0;
  bottom: 0;
  width: 52px;
  overflow: hidden;
  pointer-events: none;
}
.colhead,
.rowhead,
.corner {
  position: absolute;
  background: var(--page);
  color: var(--muted);
  font-size: 12px;
  display: grid;
  place-items: center;
  border-right: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
}
.colhead {
  top: 0;
  height: 26px;
}
.rowhead {
  left: 0;
  width: 52px;
}
.colhead.on,
.rowhead.on {
  background: var(--mist);
  color: var(--ink);
  font-weight: 500;
}
.corner {
  left: 0;
  top: 0;
  width: 52px;
  height: 26px;
}
</style>
