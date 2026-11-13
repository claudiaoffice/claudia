<script setup lang="ts">
// What came out of the alternatives (E6.21, D294–D296; mock computes-alternatives-sheet-and-outcomes): every outcome of
// a result cell as a dot plot with the median, a threshold to count against, the outcomes as a table, and which input
// moves the result most. The server runs the alternatives through the calculation (`outcome_table`); this only draws it.
import { computed, onMounted, ref } from 'vue'
import { cellLabel, show } from '~/lib/cells'
import { useI18n } from '~/lib/i18n'
import { altText, canPair, dotFractions, inputNames, outcomesToTsv, shadeOf, shareBelow, stat, tornado, type Alt, type OutcomeTable } from '~/lib/outcomes'
import type { Session } from '~/lib/session'
import Popover from './Popover.vue'

const props = defineProps<{ session: Session; sheet: string; row: number; col: number; x: number; y: number }>()
const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()

const table = ref<OutcomeTable | null>(null)
const combine = ref<'all' | 'pair'>('all')
const loading = ref(true)
const threshold = ref('')
const copied = ref(false)

async function load() {
  loading.value = true
  const answer = await props.session.outcomeTable(props.sheet, props.row, props.col, combine.value)
  if (answer === false || answer === null) {
    emit('close') // the cell depends on no alternatives any more, or the person was told why not
    return
  }
  table.value = answer
  loading.value = false
}
onMounted(load)

async function setCombine(how: 'all' | 'pair') {
  if (combine.value === how) return
  combine.value = how
  await load()
}

const result = computed(() => cellLabel(props.row, props.col))
const names = computed(() => (table.value ? inputNames(table.value, t) : []))
const values = computed(() =>
  (table.value?.rows ?? []).map((r) => r.value).filter((v): v is NonNullable<typeof v> => v !== null && (v.t === 'int' || v.t === 'float')).map((v) => Number(v.v)),
)
const sorted = computed(() => [...values.value].sort((a, b) => a - b))
const median = computed(() => {
  const s = sorted.value
  if (s.length === 0) return null
  const mid = Math.floor(s.length / 2)
  return s.length % 2 ? s[mid]! : (s[mid - 1]! + s[mid]!) / 2
})
const mean = computed(() => (values.value.length ? values.value.reduce((a, b) => a + b, 0) / values.value.length : null))
const least = computed(() => sorted.value[0] ?? null)
const greatest = computed(() => sorted.value[sorted.value.length - 1] ?? null)
const dots = computed(() => dotFractions(values.value, 60))

const limit = computed(() => {
  const n = Number(threshold.value)
  return threshold.value.trim() !== '' && Number.isFinite(n) ? n : null
})
const below = computed(() => (limit.value === null ? null : shareBelow(values.value, limit.value)))
const bars = computed(() => (table.value ? tornado(table.value, t) : []))

function altOf(input: number, choice: number): string {
  const spec = table.value?.inputs[input]
  if (!spec) return ''
  const alts = props.session.cell(spec.sheet, spec.row, spec.col)?.alts as Alt[] | undefined
  return alts?.[choice] ? altText(alts[choice]!) : (spec.labels[choice] ?? String(choice + 1))
}

async function copy() {
  if (!table.value) return
  await navigator.clipboard?.writeText(outcomesToTsv(table.value, altOf, result.value, t))
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}

const FIRST = 14
const PLOT_W = 360
</script>

<template>
  <Popover :x="x" :y="y" :label="t('Outcomes of {cell}', { cell: result })" :width="420" @close="emit('close')">
    <div class="out">
      <header>
        <h3>{{ t('Outcomes of {cell}', { cell: result }) }}</h3>
        <div v-if="table && canPair(table)" class="seg" role="group" :aria-label="t('How the inputs combine')">
          <button type="button" :aria-pressed="combine === 'all'" @click="setCombine('all')">{{ t('All combinations') }}</button>
          <button type="button" :aria-pressed="combine === 'pair'" @click="setCombine('pair')">{{ t('Pair by position') }}</button>
        </div>
      </header>

      <p v-if="loading" class="hint" role="status">{{ t('Working it out…') }}</p>
      <template v-else-if="table">
        <svg class="plot" :viewBox="`0 0 ${PLOT_W} 54`" role="img" :aria-label="t('Dot plot of {n} outcomes, from {low} to {high}, median {median}', { n: values.length, low: stat(least), high: stat(greatest), median: stat(median) })">
          <line x1="0" y1="34" :x2="PLOT_W" y2="34" class="axis" />
          <circle v-for="(f, i) in dots" :key="i" :cx="8 + f * (PLOT_W - 16)" cy="34" r="4.5" class="point" />
          <g v-if="median !== null && least !== null && greatest !== null">
            <line :x1="8 + ((median - least) / (greatest - least || 1)) * (PLOT_W - 16)" y1="14" :x2="8 + ((median - least) / (greatest - least || 1)) * (PLOT_W - 16)" y2="46" class="median" />
          </g>
        </svg>

        <dl class="stats">
          <div><dt>{{ t('least') }}</dt><dd>{{ stat(least) }}</dd></div>
          <div><dt>{{ t('median') }}</dt><dd>{{ stat(median) }}</dd></div>
          <div><dt>{{ t('mean') }}</dt><dd>{{ stat(mean) }}</dd></div>
          <div><dt>{{ t('greatest') }}</dt><dd>{{ stat(greatest) }}</dd></div>
        </dl>
        <p v-if="table.sampled" class="hint">{{ t('{n} samples were drawn, there are too many combinations to run all.', { n: table.rows.length }) }}</p>

        <label class="limit">
          {{ t('How many fall below') }}
          <input v-model="threshold" type="number" inputmode="decimal" autocomplete="off" >
        </label>
        <p v-if="below" class="hint" role="status">{{ t('{below} of {total} outcomes, {percent} %', { below: below.below, total: below.total, percent: below.percent }) }}</p>

        <section v-if="bars.length" :aria-label="t('What moves the result most')">
          <h4>{{ t('What moves the result most') }}</h4>
          <ul class="tornado">
            <li v-for="bar in bars" :key="bar.input">
              <span class="name">{{ bar.name }}</span>
              <svg viewBox="0 0 160 12" aria-hidden="true">
                <rect :x="bar.from * 150 + 2" y="2" :width="Math.max(2, (bar.to - bar.from) * 150)" height="8" rx="2" class="bar" />
                <line :x1="bar.mean * 150 + 2" y1="0" :x2="bar.mean * 150 + 2" y2="12" class="median" />
              </svg>
              <span class="range">{{ stat(bar.low) }} … {{ stat(bar.high) }}</span>
            </li>
          </ul>
        </section>

        <section :aria-label="t('The outcomes')">
          <h4>{{ t('The outcomes') }}</h4>
          <div class="scroll">
            <table>
              <thead>
                <tr>
                  <th v-for="(name, i) in names" :key="i" scope="col">{{ name }}</th>
                  <th scope="col">{{ result }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(r, i) in table.rows.slice(0, FIRST)" :key="i">
                  <td v-for="(c, j) in r.choice" :key="j">
                    <span class="shade" :style="{ opacity: 0.35 + 0.65 * shadeOf(c, table.inputs[j]!.count) }" aria-hidden="true" />{{ altOf(j, c) }}
                  </td>
                  <td class="num">{{ show(r.value) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="table.rows.length > FIRST" class="hint">{{ t('and {n} more', { n: table.rows.length - FIRST }) }}</p>
        </section>

        <footer>
          <button type="button" class="btn" @click="copy">{{ copied ? t('Copied') : t('Copy as table') }}</button>
          <button type="button" class="btn" @click="emit('close')">{{ t('Close') }}</button>
        </footer>
      </template>
    </div>
  </Popover>
</template>

<style scoped>
.out {
  display: grid;
  gap: 10px;
  font-size: 13px;
}
header {
  display: grid;
  gap: 8px;
}
h3 {
  margin: 0;
  font-size: 14px;
}
h4 {
  margin: 4px 0 4px;
  font-size: 12px;
  color: var(--muted);
  font-weight: 600;
}
.seg {
  display: inline-flex;
  border: 1px solid var(--line-field);
  border-radius: 8px;
  overflow: hidden;
  width: max-content;
}
.seg button {
  border: 0;
  background: none;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--text);
  cursor: pointer;
}
.seg button[aria-pressed='true'] {
  background: var(--app-dark);
  color: #fff;
}
.plot {
  width: 100%;
  height: auto;
}
.axis {
  stroke: var(--line-field);
  stroke-width: 1;
}
.point {
  fill: var(--app-text);
  fill-opacity: 0.8;
}
.median {
  stroke: var(--rose-dark);
  stroke-width: 2;
}
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  margin: 0;
}
.stats dt {
  color: var(--muted);
  font-size: 11px;
}
.stats dd {
  margin: 0;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.limit {
  display: flex;
  align-items: center;
  gap: 8px;
}
.limit input {
  width: 110px;
}
.hint {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.tornado {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
}
.tornado li {
  display: grid;
  grid-template-columns: 90px 1fr auto;
  align-items: center;
  gap: 8px;
}
.tornado .name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tornado .bar {
  fill: var(--iris);
}
.tornado .range {
  color: var(--muted);
  font-size: 11.5px;
  font-variant-numeric: tabular-nums;
}
.scroll {
  max-height: 180px;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 6px;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: 3px 8px;
  text-align: left;
  border-bottom: 1px solid var(--line);
  white-space: nowrap;
}
th {
  position: sticky;
  top: 0;
  background: var(--surface);
  font-size: 11.5px;
}
td.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.shade {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 6px;
  border-radius: 50%;
  background: var(--apricot);
}
footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
