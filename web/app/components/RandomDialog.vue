<script setup lang="ts">
// The Random generator (E6.22, D292, D293; mock computes-random-generator-dialog): pick a distribution, set its numbers
// with a slider or by typing, see what it gives (the server's own quantile functions, `random_preview`) and the text
// an Excel file would hold, then put `RANDOM("…", …)` into the cell. The seed of the workbook's random numbers is set here too.
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from '~/lib/i18n'
import {
  defaultParams,
  distribution,
  DISTRIBUTIONS,
  histogram,
  parseDiscrete,
  previewRequest,
  spanOf,
  validate,
  type Problem,
} from '~/lib/random-generator'
import type { RandomPreview, Session } from '~/lib/session'
import { stat } from '~/lib/outcomes'
import Modal from './Modal.vue'

const props = defineProps<{ session: Session; /** The cell the formula goes into, "B3". */ target: string; readonly: boolean }>()
const emit = defineEmits<{ close: []; insert: [formula: string] }>()
const { t } = useI18n()

const kind = ref('normal')
const spec = computed(() => distribution(kind.value))
const params = ref<number[]>(defaultParams(spec.value))
const typed = ref<string[]>(params.value.map(String))
const discrete = ref('10 1\n20 3\n30 1')
const cutOn = ref(false)
const low = ref('')
const high = ref('')
const seed = ref(String(props.session.state.random?.seed ?? 0))
const preview = ref<RandomPreview | null>(null)
const remote = ref<string | null>(null)

watch(kind, () => {
  params.value = defaultParams(spec.value)
  typed.value = params.value.map(String)
  cutOn.value = false
})

function setParam(i: number, text: string) {
  typed.value[i] = text
  const n = Number(text)
  params.value[i] = text.trim() === '' ? Number.NaN : n
}

const cut = computed(() => ({ on: cutOn.value, low: low.value.trim() === '' ? null : Number(low.value), high: high.value.trim() === '' ? null : Number(high.value) }))
const discreteValues = computed(() => (kind.value === 'discrete' ? parseDiscrete(discrete.value) : null))
const effective = computed<number[]>(() => (Array.isArray(discreteValues.value) ? discreteValues.value : params.value))

const problem = computed<Problem | 'lines' | null>(() => {
  if (kind.value === 'discrete') return Array.isArray(discreteValues.value) ? null : 'lines'
  return validate(spec.value, params.value, cut.value.on ? cut.value.low : null, cut.value.on ? cut.value.high : null)
})
function say(p: Problem | 'lines'): string {
  switch (p) {
    case 'number':
      return t('Every number must be filled in.')
    case 'positive':
      return t('This number must be greater than zero.')
    case 'order':
      return t('The numbers must run from low to high.')
    case 'chance':
      return t('The chance must be between 0 and 1.')
    case 'integer':
      return t('The number of trials must be a whole number, 1 or more.')
    case 'limits':
      return t('The lower limit must be below the upper limit.')
    default:
      return t('Each line is a value and, if you like, its weight: "10 3".')
  }
}

let token = 0
async function refresh() {
  if (problem.value) {
    preview.value = null
    remote.value = null
    return
  }
  const mine = ++token
  const answer = await props.session.randomPreview({ ...previewRequest(kind.value, effective.value, cut.value), draws: 400 })
  if (mine !== token) return // a newer one is on its way
  if ('error' in answer) {
    preview.value = null
    remote.value = answer.error
  } else {
    preview.value = answer
    remote.value = null
  }
}
watch([kind, effective, cut, problem], refresh, { deep: true })
onMounted(refresh)

const BINS = 16
const bins = computed(() => histogram(preview.value?.draws ?? [], BINS))
const tallest = computed(() => Math.max(1, ...bins.value.map((b) => b.count)))
const span = computed(() => spanOf(preview.value?.draws ?? [], 0.68))

function nameOf(id: string): string {
  switch (id) {
    case 'uniform': return t('Uniform')
    case 'normal': return t('Normal')
    case 'lognormal': return t('Log-normal')
    case 'triangular': return t('Triangular')
    case 'pert': return t('PERT')
    case 'exponential': return t('Exponential')
    case 'weibull': return t('Weibull')
    case 'beta': return t('Beta')
    case 'gamma': return t('Gamma')
    case 'binomial': return t('Binomial')
    case 'poisson': return t('Poisson')
    default: return t('Discrete (values and weights)')
  }
}
function paramName(key: string): string {
  switch (key) {
    case 'low': return t('low')
    case 'high': return t('high')
    case 'mode': return t('most likely')
    case 'mean': return t('mean')
    case 'spread': return t('spread (standard deviation)')
    case 'mean of ln': return t('mean of the logarithm')
    case 'spread of ln': return t('spread of the logarithm')
    case 'rate': return t('rate')
    case 'shape': return t('shape')
    case 'scale': return t('scale')
    case 'alpha': return t('alpha')
    case 'beta': return t('beta')
    case 'trials': return t('trials')
    default: return t('chance')
  }
}

const seedNumber = computed(() => (/^\d+$/.test(seed.value.trim()) ? Number(seed.value) : null))
async function applySeed() {
  if (seedNumber.value !== null) await props.session.setRandomSeed(seedNumber.value)
}
function insert() {
  if (preview.value) emit('insert', preview.value.formula)
}
</script>

<template>
  <Modal :title="t('Random generator')" :width="560" @close="emit('close')">
    <form class="gen" @submit.prevent="insert">
      <label class="field">
        {{ t('Distribution') }}
        <select v-model="kind">
          <option v-for="d in DISTRIBUTIONS" :key="d.id" :value="d.id">{{ nameOf(d.id) }}</option>
        </select>
      </label>

      <div v-if="kind !== 'discrete'" class="params">
        <div v-for="(p, i) in spec.params" :key="p.key" class="param">
          <label :for="`rp-${i}`">{{ paramName(p.key) }}</label>
          <input
            type="range"
            :min="p.slider[0]"
            :max="p.slider[1]"
            :step="p.slider[2]"
            :value="params[i]"
            :aria-label="paramName(p.key)"
            @input="setParam(i, ($event.target as HTMLInputElement).value)"
          >
          <input :id="`rp-${i}`" type="number" step="any" :value="typed[i]" @input="setParam(i, ($event.target as HTMLInputElement).value)" >
        </div>
      </div>
      <label v-else class="field">
        {{ t('Values and weights, one pair a line') }}
        <textarea v-model="discrete" rows="4" spellcheck="false" />
      </label>

      <fieldset v-if="spec.continuous" class="cut">
        <label class="check"><input v-model="cutOn" type="checkbox" > {{ t('Cut off at limits') }}</label>
        <template v-if="cutOn">
          <label>{{ t('from') }} <input v-model="low" type="number" step="any" ></label>
          <label>{{ t('to') }} <input v-model="high" type="number" step="any" ></label>
        </template>
      </fieldset>

      <p v-if="problem" class="problem" role="alert">{{ say(problem) }}</p>
      <p v-else-if="remote" class="problem" role="alert">{{ remote }}</p>

      <figure v-if="preview" class="preview">
        <svg viewBox="0 0 320 70" role="img" :aria-label="t('What {n} draws look like', { n: preview.draws.length })">
          <rect
            v-for="(b, i) in bins"
            :key="i"
            :x="i * (320 / bins.length) + 1"
            :y="66 - (b.count / tallest) * 60"
            :width="320 / bins.length - 2"
            :height="(b.count / tallest) * 60"
            rx="1.5"
            class="bin"
          />
          <line x1="0" y1="66.5" x2="320" y2="66.5" class="axis" />
        </svg>
        <figcaption v-if="span">{{ t('68 % of the values fall between {low} and {high}', { low: stat(span[0]), high: stat(span[1]) }) }}</figcaption>
      </figure>

      <dl v-if="preview" class="texts">
        <dt>{{ t('Formula') }}</dt>
        <dd><code>{{ preview.formula }}</code></dd>
        <dt>{{ t('In an Excel file') }}</dt>
        <dd v-if="preview.excel"><code>{{ preview.excel }}</code></dd>
        <dd v-else class="muted">{{ t('Excel has no formula for this: the file holds the current value.') }}</dd>
      </dl>

      <label class="seed">
        {{ t('Seed of the random numbers') }}
        <input v-model="seed" type="number" min="0" step="1" :disabled="readonly" >
        <button type="button" class="btn" :disabled="readonly || seedNumber === null" @click="applySeed">{{ t('Set seed') }}</button>
      </label>

      <div class="buttons">
        <button type="submit" class="btn primary" :disabled="!preview || readonly">{{ t('Put in {cell}', { cell: target }) }}</button>
        <button type="button" class="btn" @click="emit('close')">{{ t('Close') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.gen {
  display: grid;
  gap: 12px;
  font-size: 13px;
}
.field {
  display: grid;
  gap: 6px;
}
.params {
  display: grid;
  gap: 8px;
}
.param {
  display: grid;
  grid-template-columns: 170px 1fr 100px;
  align-items: center;
  gap: 10px;
}
.param input[type='number'] {
  font-variant-numeric: tabular-nums;
}
.cut {
  display: flex;
  align-items: center;
  gap: 14px;
  border: 0;
  padding: 0;
  margin: 0;
}
.cut input[type='number'] {
  width: 90px;
}
.check {
  display: flex;
  align-items: center;
  gap: 6px;
}
.problem {
  margin: 0;
  color: var(--rose-dark);
}
.preview {
  margin: 0;
  display: grid;
  gap: 4px;
}
.preview svg {
  width: 100%;
  height: auto;
}
.bin {
  fill: var(--app-text);
  fill-opacity: 0.75;
}
.axis {
  stroke: var(--line-field);
}
figcaption,
.muted {
  color: var(--muted);
  font-size: 12px;
}
.texts {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 4px 12px;
  margin: 0;
}
.texts dt {
  color: var(--muted);
}
.texts dd {
  margin: 0;
  overflow-x: auto;
}
.seed {
  display: flex;
  align-items: center;
  gap: 8px;
}
.seed input {
  width: 120px;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
