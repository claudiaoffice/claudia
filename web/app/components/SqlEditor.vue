<script setup lang="ts">
// The SQL editor (E4.9/E6.5, mock 4): write a query over the tables of the workbook, see its first rows as you type,
// and put it into a cell with Apply. The cell then holds `=SQL("…")` — the formula bar still shows that text — and the
// rows spill below and beside it. "Result name" makes the result a table of its own, for another query, a chart or
// `=SUM(ByRegion[Revenue])` to read.
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { cellLabel } from '~/lib/cells'
import { didYouMean, nameProblem, quoteIdentifier, replaceWord, visibleNames } from '~/lib/names'
import { insertAt, previewCell, previewSummary } from '~/lib/sql'
import type { Session, SqlPreview } from '~/lib/session'
import { useI18n } from '~/lib/i18n'

const { t, locale } = useI18n()

const props = defineProps<{
  session: Session
  sheet: string
  row: number
  col: number
  x: number
  y: number
  /** The query already in the cell, and the name its result has, when there are any. */
  query: string
  resultName: string
  readonly: boolean
}>()
const emit = defineEmits<{ close: []; applied: [] }>()

const PREVIEW_ROWS = 8
const MAX_RESULT_ROWS = 100_000

const text = ref(props.query)
const name = ref(props.resultName)
const preview = ref<SqlPreview | null>(null)
const busy = ref(false)
const applying = ref(false)
const area = ref<HTMLTextAreaElement | null>(null)
const tables = computed(() => visibleNames(props.session.state.names, props.sheet).filter((n) => n.region !== null && (n.header || n.kind === 'result')))
const nameProblemText = computed(() => (name.value.trim() ? nameProblem(name.value.trim()) : null))
const mend = computed(() => (preview.value && !preview.value.ok ? didYouMean(preview.value.error.detail, tables.value) : null))
const canApply = computed(() => !props.readonly && !applying.value && text.value.trim() !== '' && preview.value?.ok === true && nameProblemText.value === null)
const target = computed(() => cellLabel(props.row, props.col))

let timer: ReturnType<typeof setTimeout> | undefined
let asked = 0
async function run() {
  const query = text.value
  if (!query.trim()) {
    preview.value = null
    return
  }
  const mine = ++asked
  busy.value = true
  try {
    const answer = await props.session.sqlPreview(query, props.sheet, PREVIEW_ROWS)
    if (mine === asked) preview.value = answer
  } catch {
    if (mine === asked) preview.value = { ok: false, error: { code: '#SQL!', detail: t('The server could not be asked right now.') } }
  } finally {
    if (mine === asked) busy.value = false
  }
}
watch(text, () => {
  clearTimeout(timer)
  timer = setTimeout(run, 280)
})
onMounted(() => {
  void run()
  void nextTick(() => area.value?.focus())
})
onBeforeUnmount(() => clearTimeout(timer))

async function put(word: string) {
  const el = area.value
  const from = el?.selectionStart ?? text.value.length
  const to = el?.selectionEnd ?? from
  const next = insertAt(text.value, from, word, to)
  text.value = next.text
  await nextTick()
  el?.focus()
  el?.setSelectionRange(next.caret, next.caret)
}

function useRight() {
  if (mend.value) text.value = replaceWord(text.value, mend.value.wrong, mend.value.right)
}

async function apply() {
  if (!canApply.value) return
  applying.value = true
  const done = await props.session.defineSql(props.sheet, props.row, props.col, text.value.trim(), name.value.trim() || null)
  applying.value = false
  if (done) emit('applied')
}

function onKey(event: KeyboardEvent) {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault()
    void apply()
  }
}
</script>

<template>
  <Popover :x="x" :y="y" :width="640" :label="t('SQL editor')" @close="emit('close')">
    <div class="sql" data-testid="sql-editor" @keydown="onKey">
      <header>
        <h3><TransText :text="t('Query in {target}')"><template #target><span class="mono">{{ target }}</span></template></TransText></h3>
        <label class="result">
          {{ t('Result name') }}
          <input v-model="name" class="mono" :placeholder="t('(none)')" autocomplete="off" spellcheck="false" :aria-label="t('result name')" >
        </label>
      </header>
      <p v-if="nameProblemText" class="problem" role="alert">{{ nameProblemText }}</p>
      <div class="body">
        <aside :aria-label="t('tables')">
          <p class="cap">{{ t('Tables') }}</p>
          <p v-if="!tables.length" class="none">{{ t('Name some cells with a header row to query them.') }}</p>
          <div v-for="tb in tables" :key="`${tb.scope}:${tb.name}`" class="table">
            <button type="button" class="mono tname" @click="put(quoteIdentifier(tb.name))">{{ tb.name }}</button>
            <button v-for="c in tb.columns" :key="c.name" type="button" class="col" :title="c.type" @click="put(quoteIdentifier(c.name))">
              <span class="mono">{{ c.name }}</span><small>{{ c.type }}</small>
            </button>
          </div>
        </aside>
        <div class="main">
          <textarea
            ref="area"
            v-model="text"
            class="mono"
            rows="6"
            spellcheck="false"
            autocomplete="off"
            :aria-label="t('query')"
            :placeholder="t('SELECT Region, SUM(Amount) AS Revenue FROM Sales GROUP BY Region')"
          />
          <div class="preview" :class="{ stale: busy }" aria-live="polite">
            <template v-if="preview === null"><p class="hint">{{ t('The first rows show here as you type.') }}</p></template>
            <template v-else-if="preview.ok">
              <p class="chips">
                <span class="chip ok">{{ previewSummary(preview.row_count, preview.ms, preview.row_count >= MAX_RESULT_ROWS) }}</span>
                <span class="chip">{{ preview.columns.length === 1 ? t('1 column') : t('{count} columns', { count: preview.columns.length }) }}</span>
                <span v-if="preview.row_count > preview.rows.length" class="chip">{{ t('first {length} shown', { length: preview.rows.length }) }}</span>
              </p>
              <div class="grid">
                <table>
                  <thead><tr><th v-for="c in preview.columns" :key="c" class="mono">{{ c }}</th></tr></thead>
                  <tbody>
                    <tr v-for="(r, i) in preview.rows" :key="i"><td v-for="(v, j) in r" :key="j" :class="{ num: typeof v === 'number' }">{{ previewCell(v) }}</td></tr>
                  </tbody>
                </table>
              </div>
            </template>
            <template v-else>
              <p class="chips"><span class="chip bad">{{ preview.error.code }}</span></p>
              <p class="error mono" role="alert">{{ preview.error.detail }}</p>
              <p v-if="mend" class="mend"><TransText :text="t('Did you mean {word}?')"><template #word><b class="mono">{{ mend.right }}</b></template></TransText> <button type="button" class="use" @click="useRight">{{ t('Use {right}', { right: mend.right }) }}</button></p>
            </template>
          </div>
        </div>
      </div>
      <footer>
        <span class="note">{{ t('Reads only · one second · {rows} rows at most', { rows: MAX_RESULT_ROWS.toLocaleString(locale) }) }}</span>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
        <button class="btn primary" type="button" :disabled="!canApply" @click="apply">{{ t('Apply') }} <span class="kbd">{{ t('Ctrl+Enter') }}</span></button>
      </footer>
    </div>
  </Popover>
</template>

<style scoped>
.sql {
  display: grid;
  gap: 10px;
  padding: 10px 12px 12px;
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
h3 {
  margin: 0;
  font: 500 18px var(--font-display);
}
.result {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
}
.result input {
  width: 150px;
}
.problem {
  margin: -4px 0 0;
  color: var(--danger-dark, var(--rose));
  font-size: 12px;
  text-align: right;
}
.body {
  display: grid;
  grid-template-columns: 170px minmax(0, 1fr);
  gap: 12px;
}
aside {
  max-height: 300px;
  overflow: auto;
  border-right: 1px solid var(--line);
  padding-right: 8px;
  font-size: 12px;
}
.cap {
  margin: 0 0 4px;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
}
.none {
  margin: 0;
  color: var(--muted);
}
.table {
  display: grid;
  margin-bottom: 8px;
}
aside button {
  display: flex;
  justify-content: space-between;
  gap: 6px;
  padding: 2px 6px;
  border: 0;
  border-radius: 5px;
  background: none;
  color: var(--text);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}
aside button:hover {
  background: var(--mist);
  color: var(--ink);
}
.tname {
  font-weight: 600;
}
.col small {
  color: var(--muted);
}
.main {
  display: grid;
  gap: 8px;
  min-width: 0;
}
textarea {
  width: 100%;
  resize: vertical;
  padding: 8px 10px;
  border: 1px solid var(--line-field);
  border-radius: 8px;
  background: var(--page);
  color: var(--text);
  font-size: 13px;
  line-height: 1.5;
  tab-size: 2;
}
textarea:focus {
  outline: 2px solid var(--app);
  outline-offset: -1px;
}
.preview {
  min-height: 90px;
}
.preview.stale {
  opacity: 0.6;
}
.hint {
  color: var(--muted);
  font-size: 12px;
  margin: 0;
}
.chips {
  display: flex;
  gap: 6px;
  margin: 0 0 6px;
}
.chip {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--mist);
  color: var(--ink);
  font-size: 11px;
}
.chip.ok {
  background: var(--purpose-result);
  color: var(--text);
}
.chip.bad {
  background: var(--rose);
  color: #fff;
}
.grid {
  max-height: 190px;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
}
table {
  border-collapse: collapse;
  width: 100%;
  font-size: 12px;
}
th,
td {
  padding: 4px 8px;
  text-align: left;
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
}
th {
  position: sticky;
  top: 0;
  background: var(--purpose-result);
  color: var(--text);
  font-weight: 600;
}
td.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.error {
  margin: 0 0 6px;
  font-size: 12px;
  color: var(--danger-dark, var(--rose));
  white-space: pre-wrap;
}
.mend {
  margin: 0;
  font-size: 12px;
}
.use {
  margin-left: 6px;
  padding: 2px 8px;
  border: 1px solid var(--app);
  border-radius: 6px;
  background: none;
  color: var(--app-text);
  font-size: 12px;
  cursor: pointer;
}
footer {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: flex-end;
}
.note {
  flex: 1;
  color: var(--muted);
  font-size: 11px;
}
.kbd {
  margin-left: 6px;
  opacity: 0.75;
  font-size: 11px;
}
</style>
