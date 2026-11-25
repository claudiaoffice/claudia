<script setup lang="ts">
// A table of the text, in the flow (E9.32, mock A): a real `<table>` between two paragraphs, so a screen reader reads
// rows, columns and the header as such (BITV). The editor's paragraphs are one contenteditable; a table's boxes are not
// paragraphs of the text, so each box is a one-line field of its own (a box is one line, D1212): typing changes nothing
// until the box is left or Enter is pressed, and then it is one `replace_text` with the box's id.
//
// Keys: Tab and Shift+Tab move to the next and previous box (Tab in the last box adds a row, as the table grows with
// its last row, D603); the arrow keys move between boxes, left and right where the caret is at the edge of the words;
// Enter commits and goes down; Esc gives back what was there and leaves the table for the text.
//
// The table is an object of the text, in the flow (D1201, D1224): drawn here and nowhere else, with a faint frame that is
// always on, so that it is clear where it starts and ends. Its name tab selects it; dragging the tab moves it, to after
// the paragraph a line shows; the right button on the tab, the frame or a box selects it and opens its menu (D1225) and
// never the paragraph menu of the words; Esc, in a box or on the tab, leaves it for the text.
import { computed, nextTick, reactive, ref, useId, watch } from 'vue'
import { paragraphCss } from '~/lib/style-css'
import { columnName, gridOf, leaveSide, stepBox, type Box, type Step, type TableInfo } from '~/lib/tables'
import { nearestGap } from '~/lib/text-object-host'
import type { ParagraphAnchor, VisualObject } from '~/lib/objects'
import type { TextSession } from '~/lib/text-session'
import { useI18n } from '~/lib/i18n'
import { colorOf } from '~/lib/people'

const { t } = useI18n()
const props = defineProps<{ session: TextSession; object: VisualObject<ParagraphAnchor>; table: TableInfo }>()
const emit = defineEmits<{ options: [table: string]; menu: [at: { id: string; x: number; y: number }]; leave: []; exit: [side: 'before' | 'after'] }>()
const state = props.session.state

const grid = computed(() => gridOf(props.table))
const readonly = computed(() => props.session.readOnly)
const title = computed(() => props.object.name || t('Table'))
const description = computed(() => (props.object.decorative ? '' : props.object.description))

// ------------------------------------------------------------------------------ how a box looks
const styleCss = (id: string) => paragraphCss(state.styles[id]?.resolved ?? {})
/** The style of a box: the person's own choice, or the look's for the row's role (D1206). */
const boxCss = (box: Box, role: 'header' | 'body' | 'band' | 'total'): Record<string, string> => ({
  ...styleCss(box.style || `table-${props.table.look}-${role}`),
  ...(box.kind === 'number' ? { 'text-align': 'right' } : {}),
})
const bodyRole = (i: number) => (props.table.banded && i % 2 === 1 ? 'band' : 'body')
const columnCss = (width: number | null) => (width === null ? {} : { width: `${width / 100}%` })
const tableCss = computed(() => (props.table.width === null ? {} : { width: `${props.table.width / 100}%` }))

const label = (box: Box) => t('{row}, {column}', { row: t('Row {n}', { n: box.rowIndex + 1 }), column: columnName(props.table, box.col, (n) => t('Column {n}', { n })) })

// ------------------------------------------------------------------------------ typing in a box
const root = ref<HTMLElement | null>(null)
const field = (row: string, col: string) => root.value?.querySelector<HTMLTextAreaElement>(`[data-box="${CSS.escape(`${row}/${col}`)}"]`) ?? null

function focusBox(at: { row: string; col: string } | null) {
  if (!at) return
  const el = field(at.row, at.col)
  el?.focus()
  el?.select()
}

/** What was typed into a box and is not in the table yet, by the box's `row/col`. A box is drawn from this, not from
 *  the table, until its words are in: the table is drawn again whenever anything arrives (the words of the box typed
 *  before, a total, another person), and that must not wipe words typed since (B4). */
const drafts = reactive<Record<string, string>>({})
const keyOf = (box: Box) => `${box.row}/${box.col}`
const shown = (box: Box) => drafts[keyOf(box)] ?? box.text
function onInput(box: Box, event: Event) {
  drafts[keyOf(box)] = (event.target as HTMLTextAreaElement).value
}
function dropDraft(box: Box, words?: string) {
  if (words === undefined || drafts[keyOf(box)] === words) delete drafts[keyOf(box)]
}

/** Put the words of a box in, when they are not what the table has. */
async function commit(box: Box, el: HTMLTextAreaElement): Promise<boolean> {
  if (readonly.value) {
    el.value = box.text
    dropDraft(box)
    return false
  }
  const words = el.value
  if (words === box.text) {
    dropDraft(box, words)
    return true
  }
  const done = await props.session.setBox(props.table.id, box.row, box.col, words)
  if (done) dropDraft(box, words) // typed more meanwhile: that stays until it is put in too
  else {
    dropDraft(box) // refused: the box shows what the table has
    el.value = props.table.entries.find(([r, c]) => r === box.row && c === box.col)?.[2].text ?? ''
  }
  return done
}

/** Rows that were there before a row was added, to find the new one and put the caret in it. */
let grew: Set<string> | null = null
watch(
  () => props.table.rows,
  async (rows) => {
    if (!grew) return
    const fresh = rows.find((r) => !grew!.has(r))
    if (!fresh) return
    grew = null
    await nextTick()
    const first = gridOf(props.table).body.find((r) => r[0]?.row === fresh)?.[0]
    focusBox(first ?? null)
  },
)

async function go(box: Box, el: HTMLTextAreaElement, step: Step) {
  const target = stepBox(props.table, box, step)
  if (step === 'next' && target === 'end') {
    if (readonly.value) return
    if (!(await commit(box, el))) return
    grew = new Set(props.table.rows)
    const last = props.table.rows.at(-1)
    if (last && !(await props.session.insertRows(props.table.id, { after: last }))) grew = null
    return
  }
  if (!target) {
    // past the edge of the table: the words go in first, then the caret goes on in the text (D1330)
    const side = leaveSide(props.table, box, step)
    if (side && (readonly.value || (await commit(box, el)))) emit('exit', side)
    return
  }
  if (target === 'end') return
  // The caret moves at once and the words follow to the server: the person goes on typing in the next box, and
  // waiting for the answer would put those words into this one (B4). The session takes the commits one after the other.
  void commit(box, el)
  focusBox(target)
}

function onKey(event: KeyboardEvent, box: Box) {
  const el = event.target as HTMLTextAreaElement
  if (event.isComposing) return
  const move = (step: Step) => {
    event.preventDefault()
    void go(box, el, step)
  }
  switch (event.key) {
    case 'Tab':
      return move(event.shiftKey ? 'prev' : 'next')
    case 'Enter':
      return event.shiftKey ? event.preventDefault() : move('down') // a box is one line
    case 'ArrowDown':
      return move('down')
    case 'ArrowUp':
      return move('up')
    case 'ArrowLeft':
      if (el.selectionStart === 0 && el.selectionEnd === 0) return move('left')
      return
    case 'ArrowRight':
      if (el.selectionStart === el.value.length && el.selectionEnd === el.value.length) return move('right')
      return
    case 'Escape':
      event.preventDefault()
      el.value = box.text
      dropDraft(box)
      return emit('leave')
  }
}

function onFocus(box: Box) {
  props.session.focusBox({ table: props.table.id, row: box.row, col: box.col })
}
async function onBlur(box: Box, event: FocusEvent) {
  await commit(box, event.target as HTMLTextAreaElement)
}

/** The words of the total row: derived, so they are read, not typed (D1203). */
const totalLabel = computed(() => t('Total'))

// ------------------------------------------------------------------------------ the object: select, move, menu
const DRAG_START = 3 // screen pixels the pointer must travel before a press on the tab becomes a drag
/** A press on the tab, and where it was; the paragraph the table would go after, and the line that shows it. */
const dragging = ref<{ x: number; y: number; moved: boolean; after: string | null; line: { left: number; top: number; width: number } | null } | null>(null)

const select = () => props.session.selectObject(props.object.id)
/** The table is read by its name, on its tab, and its description; not by the Options… button beside them (UX-89). */
const nameId = useId()
const descriptionId = useId()
/** The colleagues who have this table selected (D1223), drawn inside its frame, their names at its top right. */
const others = computed(() => props.session.selectedByOthers().filter((o) => o.id === props.object.id))
const OTHER_INSIDE = { inset: '0', '--tag-top': '2px', '--tag-left': 'auto', '--tag-right': '2px' }
const tab = ref<HTMLElement | null>(null)

// A selected table has the keys: Delete takes it away, Esc leaves it, however it was selected (a press on the tab or
// the frame, Select Next Object, the menu). Focus goes to the tab unless a box already has it.
watch(
  () => state.selectedObject === props.object.id,
  async (selected) => {
    if (!selected) return
    await nextTick()
    if (!root.value?.contains(document.activeElement)) tab.value?.focus()
  },
  { immediate: true, flush: 'post' },
)
/** A press on the frame or between the boxes selects the table; a press in a box or on a button is theirs. */
function onIslandDown(event: PointerEvent) {
  if (event.button !== 0 || (event.target as HTMLElement).closest('textarea, button')) return
  event.preventDefault()
  select()
  tab.value?.focus()
}

function paragraphs(): { id: string; bottom: number; left: number; width: number }[] {
  const doc = root.value?.closest('.doc')
  return [...(doc?.querySelectorAll<HTMLElement>('[data-paragraph]') ?? [])].map((el) => {
    const r = el.getBoundingClientRect()
    return { id: el.dataset.paragraph!, bottom: r.bottom, left: r.left, width: r.width }
  })
}

function onTabDown(event: PointerEvent) {
  if (event.button !== 0) return
  select()
  if (readonly.value) return
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
  dragging.value = { x: event.clientX, y: event.clientY, moved: false, after: null, line: null }
}
function onTabMove(event: PointerEvent) {
  const d = dragging.value
  if (!d) return
  if (!d.moved && Math.hypot(event.clientX - d.x, event.clientY - d.y) < DRAG_START) return
  d.moved = true
  const all = paragraphs()
  const id = nearestGap(all, event.clientY)
  const at = all.find((p) => p.id === id)
  d.after = id
  d.line = at ? { left: at.left, top: at.bottom, width: at.width } : null
}
async function onTabUp() {
  const d = dragging.value
  dragging.value = null
  if (d?.moved && d.after && d.after !== props.object.anchor.holder && !readonly.value) await props.session.moveObject(props.object.id, { paragraph: d.after, offset: 0 })
}
function onTabKey(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    if (dragging.value) return void (dragging.value = null) // what was being tried is dropped
    props.session.selectObject(null)
    return emit('leave')
  }
  if ((event.key === 'Delete' || event.key === 'Backspace') && !readonly.value) {
    event.preventDefault()
    void props.session.removeTable(props.table.id)
  }
}

/** The right button on the tab, the frame or a box: the table is selected, its menu opens where it was pressed, and
 * the box under the pointer takes the caret, so that Merge, Split and Sort work on it (D1224). */
function onContext(event: MouseEvent) {
  if (event.shiftKey && event.clientX !== 0) return // Shift + right button: the browser's own menu, as everywhere
  event.preventDefault()
  event.stopPropagation()
  select()
  ;(event.target as HTMLElement).closest('textarea')?.focus()
  const rect = (event.currentTarget as HTMLElement).getBoundingClientRect()
  const keyboard = event.clientX === 0 && event.clientY === 0
  emit('menu', { id: props.object.id, x: keyboard ? rect.left + 24 : event.clientX, y: keyboard ? rect.top + 12 : event.clientY })
}
/** The caret comes into the table from the text (D1330): `first` the first box, `lastRow` the first box of the last
 *  row, `lastBox` the end of the words of the very last box. */
function enter(where: 'first' | 'lastRow' | 'lastBox') {
  const grid = gridOf(props.table)
  const rows = [...grid.header, ...grid.body]
  const box = where === 'first' ? rows[0]?.[0] : where === 'lastRow' ? rows.at(-1)?.[0] : rows.at(-1)?.at(-1)
  if (!box) return
  if (where !== 'lastBox') return focusBox(box)
  const el = field(box.row, box.col)
  el?.focus()
  el?.setSelectionRange(el.value.length, el.value.length)
}

defineExpose({ focusBox, enter })
</script>

<template>
  <div
    ref="root"
    class="table-island"
    :class="{ selected: state.selectedObject === object.id }"
    contenteditable="false"
    data-table
    :data-object="object.id"
    data-testid="table"
    @pointerdown="onIslandDown"
    @contextmenu="onContext"
  >
    <!-- what colleagues have selected: their colour and name (D1223), inside the frame, which scrolls -->
    <OtherOnObject v-for="other in others" :key="other.user" :other="other" :color="colorOf(state, other.user)" :style="OTHER_INSIDE" />
    <table :class="`look-${table.look}`" :style="tableCss" :aria-labelledby="nameId" :aria-describedby="description ? descriptionId : undefined">
      <caption>
        <button
          :id="nameId"
          ref="tab"
          type="button"
          class="tab"
          data-testid="table-tab"
          :title="t('Drag to move the table')"
          @pointerdown="onTabDown"
          @pointermove="onTabMove"
          @pointerup="onTabUp"
          @pointercancel="onTabUp"
          @keydown="onTabKey"
        >{{ title }}</button>
        <span v-if="description" :id="descriptionId" class="sr-only">{{ description }}</span>
        <button type="button" class="chip" data-testid="table-options" @click="emit('options', table.id)">{{ t('Options…') }}</button>
      </caption>
      <colgroup>
        <col v-for="column in table.columns" :key="column.id" :style="columnCss(column.width)" >
      </colgroup>
      <thead v-if="grid.header.length">
        <tr v-for="(row, i) in grid.header" :key="`h${i}`">
          <th v-for="box in row" :key="box.id" scope="col" :colspan="box.cols" :rowspan="box.rows" :style="boxCss(box, 'header')">
            <textarea
              rows="1"
              class="box"
              :data-box="`${box.row}/${box.col}`"
              :value="shown(box)"
              :readonly="readonly"
              :aria-label="label(box)"
              spellcheck="true"
              @focus="onFocus(box)"
              @input="onInput(box, $event)"
              @blur="onBlur(box, $event)"
              @keydown="onKey($event, box)"
            />
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in grid.body" :key="row[0]?.row ?? i">
          <td v-for="box in row" :key="box.id" :colspan="box.cols" :rowspan="box.rows" :style="boxCss(box, bodyRole(i))">
            <textarea
              rows="1"
              class="box"
              :data-box="`${box.row}/${box.col}`"
              :value="shown(box)"
              :readonly="readonly"
              :aria-label="label(box)"
              spellcheck="true"
              @focus="onFocus(box)"
              @input="onInput(box, $event)"
              @blur="onBlur(box, $event)"
              @keydown="onKey($event, box)"
            />
          </td>
        </tr>
      </tbody>
      <tfoot v-if="grid.total">
        <tr>
          <td v-for="(box, j) in grid.total" :key="box.col" :style="boxCss({ id: '', row: '', col: box.col, rowIndex: 0, colIndex: j, rows: 1, cols: 1, text: box.text, style: '', kind: box.kind }, 'total')" :aria-label="t('Total')">
            <span class="derived">{{ box.text || (j === 0 ? totalLabel : '') }}</span>
          </td>
        </tr>
      </tfoot>
    </table>
    <div v-if="dragging?.moved && dragging.line" class="drop" data-testid="table-drop-line" :style="{ left: `${dragging.line.left}px`, top: `${dragging.line.top}px`, width: `${dragging.line.width}px` }" aria-hidden="true" />
  </div>
</template>

<style scoped>
.table-island {
  position: relative;
  margin: 0.4em 0 0.9em;
  overflow-x: auto;
  /* the faint frame, always on: where the table starts and ends, whatever its look draws (D1224) */
  border: 1px solid color-mix(in srgb, var(--ink) 18%, transparent);
  border-radius: 3px;
  padding: 0 4px 4px;
}
.table-island.selected {
  outline: 2px solid var(--app);
  outline-offset: 2px;
}
table {
  border-collapse: collapse;
  width: 100%;
  table-layout: auto;
}
caption {
  text-align: left;
  font-size: 0.85em;
  color: var(--muted);
  padding: 0 0 4px;
}
.tab {
  margin-right: 8px;
  border: 0;
  background: color-mix(in srgb, var(--ink) 8%, transparent);
  border-radius: 3px 3px 0 0;
  padding: 1px 8px;
  font: inherit;
  color: var(--app-text);
  cursor: grab;
}
.tab:active {
  cursor: grabbing;
}
.tab:focus-visible {
  outline: 2px solid var(--app);
  outline-offset: 1px;
}
/* where a dragged table goes: a line under the paragraph it would follow */
.drop {
  position: fixed;
  height: 3px;
  background: var(--app);
  pointer-events: none;
  z-index: 5;
}
.chip {
  border: 1px solid var(--line);
  background: var(--panel, transparent);
  border-radius: 999px;
  padding: 1px 8px;
  font-size: 0.85em;
  color: var(--app-text);
  cursor: pointer;
}
th,
td {
  vertical-align: top;
  text-align: inherit;
}
.box {
  display: block;
  width: 100%;
  box-sizing: border-box;
  border: 0;
  margin: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: inherit;
  line-height: inherit;
  resize: none;
  overflow: hidden;
  field-sizing: content;
}
.box:focus-visible {
  outline: 2px solid var(--app);
  outline-offset: 2px;
}
.derived {
  display: block;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
  white-space: nowrap;
}
</style>
