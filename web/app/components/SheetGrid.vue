<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { alignment, columnName, inputOf, show, VIEW_COLS, VIEW_ROWS } from '~/lib/cells'
import { colorOf, inkOn } from '~/lib/people'
import { bounds, parseTsv, toTsv, type Sel } from '~/lib/selection'
import type { Session } from '~/lib/session'

export interface EditState {
  row: number
  col: number
  text: string
}

const props = defineProps<{ session: Session; sheet: string; sel: Sel; edit: EditState | null }>()
const emit = defineEmits<{
  select: [sel: Sel, dragging: boolean]
  move: [dr: number, dc: number, extend: boolean, jump: boolean]
  type: [text: string]
  beginEdit: []
  'update:editText': [text: string]
  commit: [dir: 'down' | 'up' | 'right' | 'left']
  cancel: []
  clear: []
  paste: [rows: string[][]]
  selectAll: []
}>()

const W = 96 // cell width
const H = 26 // cell height
const HW = 52 // width of the row numbers
const HH = 26 // height of the column letters

const viewport = ref<HTMLElement | null>(null)
const editor = ref<HTMLInputElement | null>(null)
const scroll = ref({ left: 0, top: 0 })
const size = ref({ w: 800, h: 600 })
let observer: ResizeObserver | null = null

const state = props.session.state
const totalW = HW + VIEW_COLS * W
const totalH = HH + VIEW_ROWS * H

const range = computed(() => ({
  r0: Math.max(0, Math.floor(scroll.value.top / H)),
  r1: Math.min(VIEW_ROWS - 1, Math.ceil((scroll.value.top + size.value.h - HH) / H)),
  c0: Math.max(0, Math.floor(scroll.value.left / W)),
  c1: Math.min(VIEW_COLS - 1, Math.ceil((scroll.value.left + size.value.w - HW) / W)),
}))

const x = (col: number) => HW + col * W - scroll.value.left
const y = (row: number) => HH + row * H - scroll.value.top

const cells = computed(() => {
  void state.generation
  const out: { key: number; left: number; top: number; text: string; align: string; kind: string }[] = []
  const { r0, r1, c0, c1 } = range.value
  for (let r = r0; r <= r1; r++) {
    for (let c = c0; c <= c1; c++) {
      const content = props.session.cell(props.sheet, r, c)
      if (content === null || (props.edit && props.edit.row === r && props.edit.col === c)) continue
      out.push({ key: r * 100_000 + c, left: x(c), top: y(r), text: show(content), align: alignment(content), kind: content.t })
    }
  }
  return out
})

const colHeads = computed(() => {
  const b = bounds(props.sel)
  const out = []
  for (let c = range.value.c0; c <= range.value.c1; c++) out.push({ c, left: x(c), name: columnName(c), on: c >= b.c0 && c <= b.c1 })
  return out
})
const rowHeads = computed(() => {
  const b = bounds(props.sel)
  const out = []
  for (let r = range.value.r0; r <= range.value.r1; r++) out.push({ r, top: y(r), on: r >= b.r0 && r <= b.r1 })
  return out
})

const box = (r0: number, c0: number, r1: number, c1: number) => ({
  left: `${x(c0)}px`,
  top: `${y(r0)}px`,
  width: `${(c1 - c0 + 1) * W}px`,
  height: `${(r1 - r0 + 1) * H}px`,
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

const linesStyle = computed(() => ({
  backgroundSize: `${W}px ${H}px`,
  backgroundPosition: `${HW - (scroll.value.left % W)}px ${HH - (scroll.value.top % H)}px`,
}))

const editorStyle = computed(() => {
  if (!props.edit) return {}
  const width = Math.max(W, Math.min(360, props.edit.text.length * 8 + 28))
  return { left: `${x(props.edit.col)}px`, top: `${y(props.edit.row)}px`, width: `${width}px`, height: `${H}px` }
})

// ------------------------------------------------------------------------------ loading what is in view
let pending = 0
function load() {
  cancelAnimationFrame(pending)
  pending = requestAnimationFrame(() => {
    const { r0, r1, c0, c1 } = range.value
    props.session.ensure(props.sheet, r0, r1, c0, c1).catch(() => undefined)
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
function reveal(row: number, col: number) {
  const el = viewport.value
  if (!el) return
  const left = col * W
  const top = row * H
  if (left < el.scrollLeft) el.scrollLeft = left
  else if (left + W > el.scrollLeft + el.clientWidth - HW) el.scrollLeft = left + W - (el.clientWidth - HW)
  if (top < el.scrollTop) el.scrollTop = top
  else if (top + H > el.scrollTop + el.clientHeight - HH) el.scrollTop = top + H - (el.clientHeight - HH)
}
watch(
  () => [props.sel.row2, props.sel.col2],
  ([row, col]) => reveal(row!, col!),
)

watch(
  () => props.edit !== null,
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

function cellAt(event: MouseEvent): { row: number; col: number; rowHead: boolean; colHead: boolean } | null {
  const stage = viewport.value?.querySelector('.stage')
  if (!stage || !(event.target as HTMLElement).closest('.stage')) return null
  const box = stage.getBoundingClientRect()
  const px = event.clientX - box.left
  const py = event.clientY - box.top
  const col = Math.max(0, Math.min(VIEW_COLS - 1, Math.floor((px - HW + scroll.value.left) / W)))
  const row = Math.max(0, Math.min(VIEW_ROWS - 1, Math.floor((py - HH + scroll.value.top) / H)))
  return { row, col, rowHead: px < HW, colHead: py < HH }
}

function onDown(event: MouseEvent) {
  if ((event.target as HTMLElement).closest('.editor')) return
  const hit = cellAt(event)
  if (!hit || event.button !== 0) return
  if (props.edit) emit('commit', 'down' as never) // clicking elsewhere keeps what was typed
  viewport.value?.focus()
  event.preventDefault()
  const { row, col } = hit
  let next: Sel
  if (hit.rowHead && hit.colHead) next = { row: 0, col: 0, row2: VIEW_ROWS - 1, col2: VIEW_COLS - 1 }
  else if (hit.colHead) next = { row: 0, col, row2: VIEW_ROWS - 1, col2: col }
  else if (hit.rowHead) next = { row, col: 0, row2: row, col2: VIEW_COLS - 1 }
  else if (event.shiftKey) next = { ...props.sel, row2: row, col2: col }
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
  const col = Math.max(0, Math.min(VIEW_COLS - 1, Math.floor((px - HW + scroll.value.left) / W)))
  const row = Math.max(0, Math.min(VIEW_ROWS - 1, Math.floor((py - HH + scroll.value.top) / H)))
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
  } else if (event.key === 'Delete' || event.key === 'Backspace') {
    event.preventDefault()
    emit('clear')
  } else if (mod && event.key.toLowerCase() === 'a') {
    event.preventDefault()
    emit('selectAll')
  } else if (!mod && !event.altKey && event.key.length === 1) {
    event.preventDefault()
    emit('type', event.key)
  }
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

defineExpose({ focus: () => viewport.value?.focus() })
</script>

<template>
  <div
    ref="viewport"
    class="viewport"
    tabindex="0"
    role="grid"
    aria-label="table"
    @scroll.passive="onScroll"
    @mousedown="onDown"
    @dblclick="onDouble"
    @keydown="onKey"
    @copy="onCopy"
    @paste="onPaste"
  >
    <div class="canvas" :style="{ width: `${totalW}px`, height: `${totalH}px` }">
      <div class="stage" :style="{ width: `${size.w}px`, height: `${size.h}px` }">
        <div class="lines" :style="linesStyle" />
        <div
          v-for="cell in cells"
          :key="cell.key"
          class="cell"
          :class="[cell.kind, cell.align]"
          :style="{ left: `${cell.left}px`, top: `${cell.top}px`, width: `${W}px`, height: `${H}px` }"
        >
          {{ cell.text }}
        </div>

        <div class="selection" :style="selectionStyle" />
        <div class="active" :style="activeStyle" />

        <div v-for="o in outlines" :key="o.id" class="outline" :class="{ locked: o.locked, ai: o.ai }" :style="o.style">
          <span class="tag">{{ o.name }}<template v-if="o.locked"> · editing</template></span>
        </div>

        <input
          v-if="edit"
          ref="editor"
          class="editor mono"
          :style="editorStyle"
          :value="edit.text"
          spellcheck="false"
          autocomplete="off"
          aria-label="editing cell"
          @input="$emit('update:editText', ($event.target as HTMLInputElement).value)"
          @keydown="onEditorKey"
        />

        <div class="colheads">
          <div v-for="h in colHeads" :key="h.c" class="colhead" :class="{ on: h.on }" :style="{ left: `${h.left - HW}px`, width: `${W}px` }">{{ h.name }}</div>
        </div>
        <div class="rowheads">
          <div v-for="h in rowHeads" :key="h.r" class="rowhead" :class="{ on: h.on }" :style="{ top: `${h.top - HH}px`, height: `${H}px` }">{{ h.r + 1 }}</div>
        </div>
        <div class="corner" />
      </div>
    </div>
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
.lines {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to bottom, transparent calc(100% - 1px), var(--line) 0),
    linear-gradient(to right, transparent calc(100% - 1px), var(--line) 0);
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
