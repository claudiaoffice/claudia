<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { inputOf, rangeLabel, parseCell, VIEW_COLS, VIEW_ROWS } from '~/lib/cells'
import { bounds, jump, move, single, summarize, type Sel } from '~/lib/selection'
import type { Session } from '~/lib/session'
import type { Menu } from './MenuBar.vue'
import type { EditState } from './SheetGrid.vue'

const props = defineProps<{ session: Session }>()
const emit = defineEmits<{ leave: [] }>()

const session = props.session
const state = session.state
const SIZE = { rows: VIEW_ROWS, cols: VIEW_COLS }

const sel = ref<Sel>(single(0, 0))
const edit = ref<EditState | null>(null)
let original = ''
const dialog = ref<null | 'sheet' | 'checkpoint' | 'share' | 'help'>(null)
const panelOpen = ref(true)
const grid = ref<{ focus: () => void } | null>(null)
const panel = ref<{ ask: (text?: string) => void } | null>(null)

const readonly = computed(() => state.me.role === 'viewer')
const b = computed(() => bounds(sel.value))
const label = computed(() => (edit.value ? rangeLabel(edit.value.row, edit.value.col, edit.value.row, edit.value.col) : rangeLabel(b.value.r0, b.value.c0, b.value.r1, b.value.c1)))
const formulaText = computed(() => (edit.value ? edit.value.text : inputOf(session.cell(state.activeSheet, sel.value.row, sel.value.col))))
const summary = computed(() => {
  void state.generation
  return summarize(sel.value, (r, c) => session.cell(state.activeSheet, r, c))
})

// ------------------------------------------------------------------------------ where I am
watch(
  [sel, () => state.activeSheet],
  () => {
    if (state.activeSheet) session.show(state.activeSheet, b.value.r0, b.value.c0, b.value.r1, b.value.c1)
  },
  { deep: true },
)

function select(next: Sel) {
  sel.value = next
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
  edit.value = { row, col, text: initial ?? original }
  if (!(await session.beginEdit(state.activeSheet, row, col))) edit.value = null
}

async function commit(dir: 'down' | 'up' | 'right' | 'left' | 'none' = 'none') {
  const e = edit.value
  if (!e) return
  edit.value = null
  const delta = { down: [1, 0], up: [-1, 0], right: [0, 1], left: [0, -1], none: [0, 0] }[dir]
  sel.value = move(single(e.row, e.col), delta[0]!, delta[1]!, false, SIZE)
  grid.value?.focus()
  if (e.text.startsWith('=') && e.text !== original) session.notice('Formulas are not there yet: this is kept as text.')
  if (e.text !== original) await session.setCells(state.activeSheet, [{ row: e.row, col: e.col, input: e.text }])
  await session.endEdit()
}

async function cancel() {
  if (!edit.value) return
  edit.value = null
  grid.value?.focus()
  await session.endEdit()
}

function updateText(text: string) {
  if (edit.value) edit.value.text = text
}

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

// ------------------------------------------------------------------------------ sheets, rows, columns
function pickSheet(id: string) {
  state.activeSheet = id
  sel.value = single(0, 0)
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

async function checkpoint(label: string | null) {
  dialog.value = null
  if (await session.saveCheckpoint(label || null)) session.notice('Checkpoint saved.')
  grid.value?.focus()
}

// ------------------------------------------------------------------------------ menus and keys
const menus = computed<Menu[]>(() => [
  {
    label: 'File',
    items: [
      { label: 'New sheet…', action: () => (dialog.value = 'sheet'), disabled: readonly.value },
      { label: '', separator: true },
      { label: 'Save', hint: 'Ctrl+S', action: () => checkpoint(null), disabled: readonly.value },
      { label: 'Save with a name…', action: () => (dialog.value = 'checkpoint'), disabled: readonly.value },
      { label: '', separator: true },
      { label: 'Share…', action: () => (dialog.value = 'share'), disabled: state.me.role !== 'owner' },
      { label: '', separator: true },
      { label: 'Close document', action: () => emit('leave') },
    ],
  },
  {
    label: 'Edit',
    items: [
      { label: state.canUndo ? `Undo ${state.undoLabel}` : 'Undo', hint: 'Ctrl+Z', action: () => session.undo(), disabled: !state.canUndo },
      { label: state.canRedo ? `Redo ${state.redoLabel}` : 'Redo', hint: 'Ctrl+Y', action: () => session.redo(), disabled: !state.canRedo },
      { label: '', separator: true },
      { label: 'Insert row above', action: () => structure('row', true), disabled: readonly.value },
      { label: 'Insert row below', action: () => structure('row', true, true), disabled: readonly.value },
      { label: 'Delete row', action: () => structure('row', false), disabled: readonly.value },
      { label: '', separator: true },
      { label: 'Insert column left', action: () => structure('col', true), disabled: readonly.value },
      { label: 'Insert column right', action: () => structure('col', true, true), disabled: readonly.value },
      { label: 'Delete column', action: () => structure('col', false), disabled: readonly.value },
      { label: '', separator: true },
      { label: 'Clear cells', hint: 'Del', action: () => clearSelection(), disabled: readonly.value },
    ],
  },
  {
    label: 'Tools',
    items: [
      { label: 'Ask the assistant…', action: () => ask('@ai ') },
      { label: 'Ask for an example budget', action: () => ask('@ai build an example budget') },
    ],
  },
  { label: 'Help', items: [{ label: 'Keyboard', action: () => (dialog.value = 'help') }] },
])

function ask(text: string) {
  panelOpen.value = true
  setTimeout(() => panel.value?.ask(text), 0)
}

function onWindowKey(event: KeyboardEvent) {
  const target = event.target as HTMLElement
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return
  if (!(event.ctrlKey || event.metaKey)) return
  const key = event.key.toLowerCase()
  if (key === 'z' && !event.shiftKey) {
    event.preventDefault()
    session.undo()
  } else if (key === 'y' || (key === 'z' && event.shiftKey)) {
    event.preventDefault()
    session.redo()
  } else if (key === 's') {
    event.preventDefault()
    if (!readonly.value) checkpoint(null)
  }
}
onMounted(() => window.addEventListener('keydown', onWindowKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onWindowKey))

// ------------------------------------------------------------------------------ notices
let timer: ReturnType<typeof setTimeout> | undefined
watch(
  () => state.notice?.id,
  (id) => {
    clearTimeout(timer)
    if (id !== undefined) timer = setTimeout(() => state.notice?.id === id && (state.notice = null), 6000)
  },
)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <div class="workspace">
    <TopBar :session="session" :panel-open="panelOpen" @toggle-panel="panelOpen = !panelOpen" />
    <div v-if="state.status === 'reconnecting'" class="banner" role="alert">The connection was lost. Trying to get back… what you type now is not saved.</div>
    <MenuBar :menus="menus" />
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
      @commit="commit('down')"
      @cancel="cancel"
      @undo="session.undo()"
      @redo="session.redo()"
    />
    <div class="main" :class="{ wide: !panelOpen }">
      <SheetGrid
        v-if="state.activeSheet"
        ref="grid"
        :session="session"
        :sheet="state.activeSheet"
        :sel="sel"
        :edit="edit"
        @select="select"
        @move="moveBy"
        @type="beginEdit($event)"
        @begin-edit="beginEdit()"
        @update:edit-text="updateText"
        @commit="commit($event)"
        @cancel="cancel"
        @clear="clearSelection"
        @paste="paste"
        @select-all="sel = { row: 0, col: 0, row2: VIEW_ROWS - 1, col2: VIEW_COLS - 1 }"
      />
      <div v-else class="nosheet">This document has no sheet yet.</div>
      <SidePanel v-show="panelOpen" ref="panel" :session="session" />
    </div>
    <FooterBar :state="state" :summary="summary" :can-add="!readonly" @pick="pickSheet" @add="dialog = 'sheet'" />

    <PromptDialog v-if="dialog === 'sheet'" title="New sheet" label="Name" ok="Add sheet" required placeholder="Forecast" @ok="addSheet" @close="dialog = null" />
    <PromptDialog
      v-if="dialog === 'checkpoint'"
      title="Save with a name"
      label="Name of this state (you can leave it empty)"
      ok="Save"
      placeholder="before the review"
      @ok="checkpoint"
      @close="dialog = null"
    />
    <ShareDialog v-if="dialog === 'share'" :session="session" @close="dialog = null" />
    <HelpDialog v-if="dialog === 'help'" @close="dialog = null" />

    <div v-if="state.notice" class="toast" :class="state.notice.kind" role="status" @click="state.notice = null">{{ state.notice.text }}</div>

    <div v-if="state.status === 'closed'" class="gone" role="alertdialog">
      <div>
        <h2>You are not connected any more</h2>
        <p>{{ state.error || 'The connection was closed.' }}</p>
        <button class="btn primary" type="button" @click="emit('leave')">Back to the documents</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.workspace {
  height: 100%;
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr) auto;
  grid-template-columns: minmax(0, 1fr);
  position: relative;
}
.main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  min-height: 0;
}
.main.wide {
  grid-template-columns: minmax(0, 1fr);
}
.banner {
  background: var(--apricot);
  color: var(--ink);
  padding: 6px 16px;
  font-weight: 500;
}
.nosheet {
  display: grid;
  place-items: center;
  color: var(--muted);
}
.toast {
  position: absolute;
  left: 50%;
  bottom: 54px;
  transform: translateX(-50%);
  max-width: min(560px, calc(100% - 32px));
  background: var(--ink);
  color: var(--paper);
  padding: 9px 16px;
  border-radius: 999px;
  box-shadow: var(--shadow);
  z-index: 50;
  cursor: pointer;
}
.toast.warning {
  background: var(--apricot);
  color: var(--ink);
}
.toast.error {
  background: var(--rose);
  color: #fff;
}
.gone {
  position: absolute;
  inset: 0;
  z-index: 70;
  display: grid;
  place-items: center;
  background: rgb(247 243 236 / 92%);
  text-align: center;
}
.gone h2 {
  font: 400 26px var(--font-display);
  margin: 0 0 8px;
}
@media (max-width: 736px) {
  .main {
    grid-template-columns: minmax(0, 1fr);
    grid-template-rows: minmax(0, 1fr) 40%;
  }
}
</style>
