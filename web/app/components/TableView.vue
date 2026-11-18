<script setup lang="ts">
// A table of the text, in the flow (E9.32, mock A): a real `<table>` between two paragraphs, so a screen reader reads
// rows, columns and the header as such (BITV). The editor's paragraphs are one contenteditable; a table's boxes are not
// paragraphs of the text, so each box is a one-line field of its own (a box is one line, D1212): typing changes nothing
// until the box is left or Enter is pressed, and then it is one `replace_text` with the box's id.
//
// Keys: Tab and Shift+Tab move to the next and previous box (Tab in the last box adds a row, as the table grows with
// its last row, D603); the arrow keys move between boxes, left and right where the caret is at the edge of the words;
// Enter commits and goes down; Esc gives back what was there and leaves the table for the text.
import { computed, nextTick, ref, watch } from 'vue'
import { paragraphCss } from '~/lib/style-css'
import { columnName, gridOf, stepBox, type Box, type Step, type TableInfo } from '~/lib/tables'
import type { BlockAnchor, VisualObject } from '~/lib/objects'
import type { TextSession } from '~/lib/text-session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()
const props = defineProps<{ session: TextSession; object: VisualObject<BlockAnchor>; table: TableInfo }>()
const emit = defineEmits<{ options: [table: string]; leave: [] }>()
const state = props.session.state

const grid = computed(() => gridOf(props.table))
const readonly = computed(() => props.session.readOnly)
const title = computed(() => props.object.name || t('Table'))
const description = computed(() => (props.object.decorative ? '' : props.object.description))

// ------------------------------------------------------------------------------ how a box looks
const styleCss = (id: string) => paragraphCss(state.styles.find((s) => s.id === id)?.resolved ?? {})
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

/** Put the words of a box in, when they are not what the table has. */
async function commit(box: Box, el: HTMLTextAreaElement): Promise<boolean> {
  if (readonly.value) {
    el.value = box.text
    return false
  }
  if (el.value === box.text) return true
  return props.session.setBox(props.table.id, box.row, box.col, el.value)
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
  if (!target || target === 'end') return
  await commit(box, el)
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
defineExpose({ focusBox })
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
  >
    <table :class="`look-${table.look}`" :style="tableCss">
      <caption>
        <span class="name">{{ title }}</span>
        <span v-if="description" class="sr-only"> — {{ description }}</span>
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
              :value="box.text"
              :readonly="readonly"
              :aria-label="label(box)"
              spellcheck="true"
              @focus="onFocus(box)"
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
              :value="box.text"
              :readonly="readonly"
              :aria-label="label(box)"
              spellcheck="true"
              @focus="onFocus(box)"
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
  </div>
</template>

<style scoped>
.table-island {
  margin: 0.4em 0 0.9em;
  overflow-x: auto;
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
.name {
  margin-right: 8px;
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
