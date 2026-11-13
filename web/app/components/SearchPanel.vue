<script setup lang="ts">
// Edit ▸ Search & replace… (E5.15, D281–D286): one floating, non-modal panel for all three apps. The sheet stays
// editable and the matches show in it; the app's `SearchHost` says what can be searched, where, how to name a match and
// how to get to it (`lib/sheet-search-host.ts`). Three ways to say what to find, all compiled by the same server
// engine: the plain quick field; a builder of parts and conditions that says back in a sentence what it does; and,
// from the ⋯ menu, the person's own pattern. The words "regular expression" are never on the surface.
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from '~/lib/i18n'
import {
  addKept,
  emptyModel,
  excerptOf,
  explainError,
  keptNames,
  latest,
  newCondition,
  newPart,
  sentence,
  shownMatches,
  toPattern,
  toQuery,
  whyLeftOut,
  type ConditionKind,
  type Count,
  type Kinds,
  type PartWhat,
  type PreviewAnswer,
  type SearchAnswer,
  type SearchMatch,
  type SearchModel,
} from '~/lib/search'
import type { ScopeId, SearchHost } from '~/lib/sheet-search-host'
import type { SearchLeave } from '~/lib/session'
import Popover from './Popover.vue'

const props = defineProps<{
  host: SearchHost
  /** Open with Replace already showing (Ctrl+H). */
  replace?: boolean
}>()
const emit = defineEmits<{
  close: []
  /** What the document should draw: the matches shown, the one being looked at, and what a replacement would do. */
  view: [view: { matches: SearchMatch[]; current: number | null; preview: PreviewAnswer | null }]
  help: []
}>()

// `t` stays this bare: `scripts/extract_i18n.py` only recognises an unqualified `t('…')` call.
const { t } = useI18n()

// ------------------------------------------------------------------------------------------------------------- state
const model = reactive<SearchModel>(emptyModel())
const replaceOpen = ref(props.replace === true)
const kinds = reactive<Kinds>({ text: true, formulas: true, values: true })
const scope = ref<ScopeId>('sheet')
const answer = ref<SearchAnswer | null>(null)
const preview = ref<PreviewAnswer | null>(null)
const current = ref<number | null>(null)
const unchecked = reactive(new Set<string>()) // matches a person took the tick off: "number of the match in its cell"
const showAllLeft = ref(false)
const limit = ref(200)
const status = ref('')
const busy = ref(false)
const menu = ref<{ x: number; y: number } | null>(null)
const menuButton = ref<HTMLElement | null>(null)
const quickField = ref<HTMLInputElement | null>(null)
const root = ref<HTMLElement | null>(null)
/** The builder as it was when the person went to write the pattern herself: "Back to the builder" returns to it. */
const builderBefore = ref<{ model: string; mode: SearchModel['mode'] } | null>(null)
const askBack = ref(false)

const replacing = computed(() => replaceOpen.value && !props.host.readonly)
const query = computed(() => toQuery(model, { replace: replacing.value }))
const shown = computed(() => (answer.value ? shownMatches(answer.value.matches, kinds) : []))
const problem = computed(() => (answer.value?.error ? explainError(answer.value.error, t) : null))
const said = computed(() => (model.mode === 'builder' ? sentence(model, t) : ''))
const names = computed(() => keptNames(model))
const cellCount = computed(() => new Set(shown.value.map((m) => `${m.sheet},${m.row},${m.col}`)).size)
const left = computed(() => (answer.value?.left_out ?? []).filter((o) => (kinds[o.kind === 'formula' ? 'formulas' : o.kind === 'value' ? 'values' : 'text'] ?? true)))

const matchKey = (m: SearchMatch) => `${m.sheet},${m.row},${m.col},${m.number}`
const replaceable = (m: SearchMatch) => m.kind !== 'value'
const leave = computed<SearchLeave[]>(() =>
  shown.value.filter((m) => unchecked.has(matchKey(m))).map((m) => ({ sheet: m.sheet, row: m.row, col: m.col, match: m.number })),
)

/** A line the live region says: how many matches there are. */
const summary = computed(() => {
  const a = answer.value
  if (!query.value) return ''
  if (problem.value) return problem.value.headline
  if (!a) return t('Searching…')
  const n = shown.value.length
  if (n === 0) return t('No matches')
  if (n === 1) return t('One match')
  return cellCount.value === n ? t('{count} matches', { count: n }) : t('{count} matches in {cells} cells', { count: n, cells: cellCount.value })
})
const position = computed(() => (current.value === null || shown.value.length === 0 ? '' : t('{n} of {count}', { n: current.value + 1, count: shown.value.length })))
const changing = computed(() => preview.value?.total ?? 0)
const skipping = computed(() => preview.value?.skipped.length ?? 0)

// ------------------------------------------------------------------------------------------------------- the asking
const findLatest = latest<SearchAnswer | null>()
const previewLatest = latest<PreviewAnswer | null>()
let timer: ReturnType<typeof setTimeout> | undefined

function schedule(delay = 150) {
  clearTimeout(timer)
  timer = setTimeout(() => void run(), delay)
}

async function run() {
  const asked = query.value
  if (!asked) {
    answer.value = null
    preview.value = null
    current.value = null
    return
  }
  const where = props.host.scopeOf(scope.value)
  const found = await findLatest(() => props.host.find(asked, where))
  if (found === null) return // overtaken, or the server could not be asked: what was showing stays
  answer.value = found
  if (current.value !== null && current.value >= shown.value.length) current.value = shown.value.length ? 0 : null
  if (replacing.value && !found.error) {
    const planned = await previewLatest(() => props.host.preview(asked, kinds, where, leave.value))
    if (planned !== null) preview.value = planned
  } else preview.value = null
}

watch(
  [() => JSON.stringify(model), scope, () => props.host.revision(), replacing, () => ({ ...kinds }), () => leave.value.length],
  () => schedule(),
  { deep: true },
)
// What the document shows follows what was found and where she is in it.
watch(
  [shown, current, preview],
  () => emit('view', { matches: shown.value, current: current.value, preview: replacing.value ? preview.value : null }),
  { immediate: true },
)
// A new search starts at its first match without having moved the document to it: she may still be typing.
watch(
  () => JSON.stringify(query.value),
  () => {
    unchecked.clear()
    current.value = null
    limit.value = 200
    status.value = ''
  },
)

// ------------------------------------------------------------------------------------------------- going to a match
function go(index: number) {
  const matches = shown.value
  if (matches.length === 0) return
  const at = (index + matches.length) % matches.length
  current.value = at
  props.host.jump(matches[at]!)
}
const next = () => go(current.value === null ? 0 : current.value + 1)
const previous = () => go(current.value === null ? shown.value.length - 1 : current.value - 1)

function onQuickKey(event: KeyboardEvent) {
  if (event.key !== 'Enter') return
  event.preventDefault()
  if (event.shiftKey) previous()
  else next()
}
function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.stopPropagation()
    emit('close')
  }
}

// ------------------------------------------------------------------------------------------------------ the builder
const PARTS = computed<{ what: PartWhat; label: string }[]>(() => [
  { what: 'text', label: t('the text') },
  { what: 'any_of', label: t('any one of') },
  { what: 'none_of', label: t('any character except') },
  { what: 'letter', label: t('a letter') },
  { what: 'digit', label: t('a digit') },
  { what: 'space', label: t('a space') },
  { what: 'any', label: t('any character') },
  { what: 'number', label: t('a number') },
  { what: 'start', label: t('the start of the cell') },
  { what: 'end', label: t('the end of the cell') },
])
const partChoices = computed(() => [...PARTS.value, ...(props.host.extraParts.includes('cellref') ? [{ what: 'cellref' as PartWhat, label: t('a cell reference') }] : [])])
const COUNTS = computed<{ count: Count; label: string }[]>(() => [
  { count: 'once', label: t('once') },
  { count: 'optional', label: t('optional') },
  { count: 'one_or_more', label: t('one or more') },
  { count: 'any', label: t('any number') },
  { count: 'exactly', label: t('exactly') },
  { count: 'between', label: t('between') },
])
const CONDITIONS = computed<{ kind: ConditionKind; label: string }[]>(() => [
  { kind: 'contains', label: t('contain') },
  { kind: 'not_contains', label: t('do not contain') },
  { kind: 'starts_with', label: t('start with') },
  { kind: 'ends_with', label: t('end with') },
  { kind: 'is', label: t('are exactly') },
  { kind: 'contains_any_of', label: t('contain one of') },
  { kind: 'not_contains_any_of', label: t('contain none of') },
])
const takesText = (what: PartWhat) => what === 'text'
const takesChars = (what: PartWhat) => what === 'any_of' || what === 'none_of'
const isPlace = (what: PartWhat) => what === 'start' || what === 'end'

function startBuilder() {
  if (model.mode === 'builder') return
  if (model.mode === 'quick' && model.quick !== '') model.parts = [{ ...newPart('text'), value: model.quick }]
  if (model.parts.length === 0) model.parts = [newPart('text')]
  model.mode = 'builder'
}
function addPart(what: PartWhat) {
  model.parts.push(newPart(what))
  void nextTick(() => root.value?.querySelector<HTMLElement>('[data-part]:last-of-type input, [data-part]:last-of-type select')?.focus())
}
function removePart(id: number) {
  model.parts = model.parts.filter((p) => p.id !== id)
  model.replace = model.replace.filter((item) => !('keep' in item) || keptNames(model).includes(item.keep))
}
function keepPart(index: number) {
  Object.assign(model, addKept(model, index))
}
function unkeepPart(index: number) {
  const name = model.parts[index]!.keep
  model.parts[index]!.keep = ''
  model.replace = model.replace.filter((item) => !('keep' in item) || item.keep !== name)
}
function renameKept(index: number, value: string) {
  const old = model.parts[index]!.keep
  model.parts[index]!.keep = value
  // The replacement that used the old name follows the part, so renaming does not break it.
  model.replace = model.replace.map((item) => ('keep' in item && item.keep === old ? { keep: value } : item))
}
function addCondition(kind: ConditionKind) {
  model.conditions.push(newCondition(kind))
}
function onAddPart(event: Event) {
  const select = event.target as HTMLSelectElement
  if (select.value) addPart(select.value as PartWhat)
  select.value = ''
}
function onAddCondition(event: Event) {
  const select = event.target as HTMLSelectElement
  if (select.value) addCondition(select.value as ConditionKind)
  select.value = ''
}
function removeCondition(id: number) {
  model.conditions = model.conditions.filter((c) => c.id !== id)
}

// ------------------------------------------------------------------------------------------------------ replace with
function openReplace() {
  if (props.host.readonly) return
  replaceOpen.value = true
  kinds.text = true
  kinds.formulas = false // opens with Text only: replacing inside a formula can change what it computes (D285)
  kinds.values = false
  void nextTick(() => root.value?.querySelector<HTMLElement>('[data-replace-first]')?.focus())
}
function closeReplace() {
  replaceOpen.value = false
  kinds.text = kinds.formulas = kinds.values = true
}
/** The text box of a quick replacement: one plain text. */
const quickReplace = computed({
  get: () => model.replace.map((item) => ('text' in item ? item.text : '')).join(''),
  set: (value: string) => {
    model.replace = [{ text: value }]
  },
})
function insertKept(name: string) {
  model.replace = [...model.replace, { keep: name }, { text: '' }]
}
function removeReplaceItem(index: number) {
  model.replace = model.replace.filter((_, i) => i !== index)
}
function setReplaceText(index: number, value: string) {
  model.replace = model.replace.map((item, i) => (i === index ? { text: value } : item))
}
function trailingText() {
  const last = model.replace[model.replace.length - 1]
  if (!last || 'keep' in last) model.replace = [...model.replace, { text: '' }]
}

/** A kind that is not looked in while replacing is said so when the pattern is in it: formulas change meaning. */
const alsoIn = computed(() => (replacing.value && !kinds.formulas && (answer.value?.counts.formulas ?? 0) > 0 ? answer.value!.counts.formulas : 0))

async function doReplace(only?: SearchMatch) {
  const asked = query.value
  if (!asked || busy.value || problem.value) return
  const leaving: SearchLeave[] = only
    ? shown.value.filter((m) => m !== only && replaceable(m)).map((m) => ({ sheet: m.sheet, row: m.row, col: m.col, match: m.number }))
    : leave.value
  busy.value = true
  const done = await props.host.replace(asked, kinds, props.host.scopeOf(scope.value), leaving)
  busy.value = false
  if (done === false) return
  status.value = done.replaced === 0 ? t('Nothing was replaced.') : done.replaced === 1 ? t('Replaced in one cell. Undo brings it back.') : t('Replaced in {count} cells. Undo brings them back.', { count: done.replaced })
  unchecked.clear()
  schedule(0)
}
const replaceThis = () => {
  const m = current.value === null ? shown.value[0] : shown.value[current.value]
  if (m) void doReplace(m)
}

// -------------------------------------------------------------------------------------------- the pattern, as text
function writePattern() {
  menu.value = null
  if (model.mode === 'pattern') return
  builderBefore.value = { model: JSON.stringify(model), mode: model.mode }
  const fields = answer.value?.pattern ?? { find: '', filter: '', replace: '' }
  Object.assign(model, toPattern(model, fields))
  void nextTick(() => root.value?.querySelector<HTMLElement>('[data-pattern-find]')?.focus())
}
function backToBuilder() {
  askBack.value = false
  if (builderBefore.value) Object.assign(model, JSON.parse(builderBefore.value.model))
  else model.mode = 'quick'
  builderBefore.value = null
}
function startOver() {
  menu.value = null
  Object.assign(model, emptyModel())
  builderBefore.value = null
  if (replaceOpen.value) closeReplace()
  void nextTick(() => quickField.value?.focus())
}
function openHelp() {
  menu.value = null
  emit('help')
}
function openMenu() {
  const rect = menuButton.value?.getBoundingClientRect()
  menu.value = menu.value ? null : { x: (rect?.right ?? 0) - 230, y: (rect?.bottom ?? 0) + 4 }
}

// -------------------------------------------------------------------------------------------------------- the rows
const visibleRows = computed(() => shown.value.slice(0, limit.value))
const skippedRows = computed(() => preview.value?.skipped ?? [])
function why(reason: string, by: string | null) {
  if (reason === 'locked') return t('locked by {name}', { name: by ?? '' })
  if (reason === 'formula') return t('would no longer be a formula')
  return t('would be too long')
}
const noMore = computed(() => (answer.value?.truncated ? t('Only the first {count} matches are listed.', { count: answer.value.matches.length }) : ''))
const timedOut = computed(() => answer.value?.timed_out === true)
const leftReasons = computed(() => [...new Set(left.value.map((o) => whyLeftOut(o.why, t)))].join(' · '))

function focusQuick() {
  void nextTick(() => {
    quickField.value?.focus()
    quickField.value?.select()
  })
}
defineExpose({ focus: focusQuick, openReplace })

onMounted(() => {
  if (props.replace) openReplace()
  focusQuick()
})
onBeforeUnmount(() => clearTimeout(timer))
watch(() => props.replace, (on) => on && openReplace())
</script>

<template>
  <aside ref="root" class="search" role="search" :aria-label="t('Search & replace')" data-testid="search-panel" @keydown="onKey">
    <header>
      <h2>{{ t('Search & replace') }}</h2>
      <button ref="menuButton" type="button" class="icon" :aria-label="t('More')" aria-haspopup="menu" :aria-expanded="menu !== null" @click="openMenu">⋯</button>
      <button type="button" class="icon" :aria-label="t('Close')" @click="emit('close')">✕</button>
    </header>

    <Popover v-if="menu" :x="menu.x" :y="menu.y" :width="230" :label="t('More')" :anchor="menuButton" @close="menu = null">
      <div class="menu" role="menu">
        <button type="button" role="menuitem" :disabled="model.mode === 'pattern'" @click="writePattern">{{ t('Write the pattern yourself…') }}</button>
        <button type="button" role="menuitem" @click="startOver">{{ t('Start over') }}</button>
        <div class="sep" />
        <button type="button" role="menuitem" @click="openHelp">{{ t('About searching and patterns') }}</button>
      </div>
    </Popover>

    <div class="body">
      <!-- the quick field: plain text, never read as a pattern -->
      <section v-if="model.mode === 'quick'">
        <div class="quick">
          <input
            ref="quickField"
            v-model="model.quick"
            type="search"
            class="field"
            :placeholder="t('Find')"
            :aria-label="t('Find')"
            autocomplete="off"
            spellcheck="false"
            data-testid="search-quick"
            @keydown="onQuickKey"
          >
          <span v-if="position" class="pos" aria-hidden="true">{{ position }}</span>
          <button type="button" class="icon small" :aria-label="t('Previous match')" :disabled="shown.length === 0" @click="previous">▲</button>
          <button type="button" class="icon small" :aria-label="t('Next match')" :disabled="shown.length === 0" @click="next">▼</button>
        </div>
      </section>

      <!-- the builder -->
      <section v-else-if="model.mode === 'builder'" class="builder">
        <h3 class="label">{{ t('Find') }}</h3>
        <div v-for="(part, index) in model.parts" :key="part.id" class="row part" data-part>
          <select v-model="part.what" class="field" :aria-label="t('What to find')">
            <option v-for="choice in partChoices" :key="choice.what" :value="choice.what">{{ choice.label }}</option>
          </select>
          <input v-if="takesText(part.what)" v-model="part.value" class="field grow" :aria-label="t('The text')" autocomplete="off" spellcheck="false">
          <input v-else-if="takesChars(part.what)" v-model="part.chars" class="field grow" :aria-label="t('The characters')" autocomplete="off" spellcheck="false">
          <span v-else class="grow" />
          <template v-if="!isPlace(part.what)">
            <select v-model="part.count" class="field" :aria-label="t('How many')">
              <option v-for="choice in COUNTS" :key="choice.count" :value="choice.count">{{ choice.label }}</option>
            </select>
            <input v-if="part.count === 'exactly' || part.count === 'between'" v-model.number="part.n" type="number" min="0" class="field num" :aria-label="part.count === 'between' ? t('At least') : t('How many times')">
            <input v-if="part.count === 'between'" v-model.number="part.m" type="number" min="0" class="field num" :aria-label="t('At most')">
          </template>
          <span v-if="part.keep" class="kept">
            <input :value="part.keep" class="field keepname" :aria-label="t('Kept as')" autocomplete="off" @input="renameKept(index, ($event.target as HTMLInputElement).value)">
            <button type="button" class="icon small" :aria-label="t('Do not keep this part')" @click="unkeepPart(index)">✕</button>
          </span>
          <button v-else type="button" class="link" :title="t('Keep this part, to use it in the replacement')" @click="keepPart(index)">{{ t('Keep') }}</button>
          <button type="button" class="icon small" :aria-label="t('Remove this part')" @click="removePart(part.id)">✕</button>
        </div>
        <div class="add">
          <label class="adding">
            <span class="link">+ {{ t('Add a part') }}</span>
            <select class="addselect" :aria-label="t('Add a part')" @change="onAddPart">
              <option value="" selected disabled />
              <option v-for="choice in partChoices" :key="choice.what" :value="choice.what">{{ choice.label }}</option>
            </select>
          </label>
        </div>

        <h3 class="label">{{ t('Only in cells that…') }}</h3>
        <div v-for="condition in model.conditions" :key="condition.id" class="row condition">
          <select v-model="condition.kind" class="field" :aria-label="t('Condition')">
            <option v-for="choice in CONDITIONS" :key="choice.kind" :value="choice.kind">{{ choice.label }}</option>
          </select>
          <input v-model="condition.text" class="field grow" :aria-label="condition.kind.endsWith('any_of') ? t('The characters') : t('The text')" autocomplete="off" spellcheck="false">
          <button type="button" class="icon small" :aria-label="t('Remove this condition')" @click="removeCondition(condition.id)">✕</button>
        </div>
        <div v-if="model.conditions.length > 1" class="row">
          <label>
            <select v-model="model.combine" class="field" :aria-label="t('How the conditions go together')">
              <option value="all">{{ t('all of these must hold') }}</option>
              <option value="any">{{ t('any one of these may hold') }}</option>
            </select>
          </label>
        </div>
        <div class="add">
          <label class="adding">
            <span class="link">+ {{ t('Add a condition') }}</span>
            <select class="addselect" :aria-label="t('Add a condition')" @change="onAddCondition">
              <option value="" selected disabled />
              <option v-for="choice in CONDITIONS" :key="choice.kind" :value="choice.kind">{{ choice.label }}</option>
            </select>
          </label>
        </div>

        <p v-if="said" class="sentence" data-testid="search-sentence">{{ said }}</p>
      </section>

      <!-- the person's own pattern -->
      <section v-else class="typed">
        <label class="label" for="pattern-find">{{ t('Find — pattern') }}</label>
        <input id="pattern-find" v-model="model.pattern.find" class="field mono" :class="{ bad: problem?.field === 'find' }" autocomplete="off" spellcheck="false" data-pattern-find :aria-invalid="problem?.field === 'find'">
        <label class="label" for="pattern-filter">{{ t('Only in cells matching (optional)') }}</label>
        <input id="pattern-filter" v-model="model.pattern.filter" class="field mono" :class="{ bad: problem?.field === 'filter' }" autocomplete="off" spellcheck="false" :aria-invalid="problem?.field === 'filter'">
        <template v-if="replacing">
          <label class="label" for="pattern-replace">{{ t('Replace with') }}</label>
          <input id="pattern-replace" v-model="model.pattern.replace" class="field mono" :class="{ bad: problem?.field === 'replace' }" autocomplete="off" spellcheck="false" :aria-invalid="problem?.field === 'replace'">
        </template>
        <p class="hint">{{ t('Pattern syntax: Python re') }}</p>
        <p v-if="problem" class="error" role="alert"><strong>{{ problem.headline }}</strong><br>{{ problem.detail }}</p>
        <p v-else-if="query && answer" class="valid">{{ t('Valid.') }} {{ summary }}.</p>
        <div class="back">
          <p class="hint">{{ builderBefore?.mode === 'builder' ? t('Made by the builder. If you edit it here, the builder can no longer show it.') : t('Made from what you typed. Your own pattern replaces it.') }}</p>
          <button v-if="!askBack" type="button" class="btn" @click="askBack = true">{{ builderBefore?.mode === 'builder' ? t('Back to the builder') : t('Back to the simple field') }}</button>
          <span v-else class="confirm">
            {{ t('Your changes to the pattern are dropped.') }}
            <button type="button" class="btn" @click="backToBuilder">{{ t('Go back') }}</button>
            <button type="button" class="btn" @click="askBack = false">{{ t('Keep the pattern') }}</button>
          </span>
        </div>
      </section>

      <!-- what else decides what is found -->
      <section class="options">
        <h3 class="label">{{ t('Look in') }}</h3>
        <div class="chips" role="group" :aria-label="t('Look in')">
          <label class="chip" :class="{ on: kinds.text }"><input v-model="kinds.text" type="checkbox"><span aria-hidden="true">{{ kinds.text ? '✓ ' : '' }}</span>{{ t('Text') }} <small>{{ answer?.counts.text ?? 0 }}</small></label>
          <label class="chip" :class="{ on: kinds.formulas }"><input v-model="kinds.formulas" type="checkbox"><span aria-hidden="true">{{ kinds.formulas ? '✓ ' : '' }}</span>{{ t('Formulas') }} <small>{{ answer?.counts.formulas ?? 0 }}</small></label>
          <label class="chip" :class="{ on: kinds.values && !replacing, locked: replacing }" :title="replacing ? t('A value follows from its formula: it can be found, not replaced.') : ''">
            <input v-model="kinds.values" type="checkbox" :disabled="replacing"><span aria-hidden="true">{{ kinds.values && !replacing ? '✓ ' : '' }}</span>{{ t('Values') }}
            <small v-if="replacing" aria-hidden="true">🔒</small><small v-else>{{ answer?.counts.values ?? 0 }}</small>
          </label>
        </div>
        <div class="row flags">
          <select v-model="scope" class="field" :aria-label="t('Where to look')">
            <option v-for="id in host.scopes" :key="id" :value="id">{{ id === 'sheet' ? t('This sheet') : id === 'all' ? t('All sheets') : t('Selection') }}</option>
          </select>
          <label class="toggle" :class="{ on: model.matchCase }"><input v-model="model.matchCase" type="checkbox">{{ t('Match case') }}</label>
          <label v-if="model.mode !== 'pattern'" class="toggle" :class="{ on: model.whole === 'entire' }"><input type="checkbox" :checked="model.whole === 'entire'" @change="model.whole = ($event.target as HTMLInputElement).checked ? 'entire' : 'none'">{{ t('Whole cell') }}</label>
        </div>
        <div v-if="model.mode === 'quick'" class="row links">
          <button v-if="!replaceOpen && !host.readonly" type="button" class="link" @click="openReplace">{{ t('Replace with…') }} ›</button>
          <button type="button" class="link end" @click="startBuilder">{{ t('Build a pattern…') }}</button>
        </div>
        <div v-else-if="!replaceOpen && !host.readonly" class="row links">
          <button type="button" class="link" @click="openReplace">{{ t('Replace with…') }} ›</button>
        </div>
      </section>

      <!-- replace with -->
      <section v-if="replacing && model.mode !== 'pattern'" class="replace">
        <h3 class="label">{{ t('Replace with') }}</h3>
        <input v-if="model.mode === 'quick'" v-model="quickReplace" class="field" :aria-label="t('Replace with')" autocomplete="off" spellcheck="false" data-replace-first>
        <div v-else class="items" :aria-label="t('Replace with')">
          <template v-for="(item, index) in model.replace" :key="index">
            <span v-if="'keep' in item" class="chip on keptchip">{{ item.keep }}<button type="button" class="icon small" :aria-label="t('Remove')" @click="removeReplaceItem(index)">✕</button></span>
            <input v-else :value="item.text" class="field grow" :aria-label="t('Text of the replacement')" autocomplete="off" spellcheck="false" :data-replace-first="index === 0 ? '' : undefined" @input="setReplaceText(index, ($event.target as HTMLInputElement).value)">
          </template>
          <input v-if="model.replace.length === 0 || 'keep' in model.replace[model.replace.length - 1]!" class="field grow" :aria-label="t('Text of the replacement')" data-replace-first autocomplete="off" spellcheck="false" @focus="trailingText">
        </div>
        <p v-if="names.length && model.mode === 'builder'" class="hint">
          {{ t('Kept parts, click to insert:') }}
          <button v-for="name in names" :key="name" type="button" class="chip on keptchip insert" @click="insertKept(name)">{{ name }}</button>
        </p>
        <p v-if="alsoIn" class="warn" role="note">⚠ {{ t('This also appears in {count} formulas, which are left alone.', { count: alsoIn }) }}</p>
        <button type="button" class="link" @click="closeReplace">{{ t('Close Replace') }}</button>
      </section>
      <p v-else-if="replacing && alsoIn" class="warn" role="note">⚠ {{ t('This also appears in {count} formulas, which are left alone.', { count: alsoIn }) }}</p>
    </div>

    <!-- what was found -->
    <section class="results" :aria-label="t('Matches')">
      <div class="head">
        <strong role="status" aria-live="polite" data-testid="search-summary">{{ summary }}</strong>
        <span v-if="replacing && preview" class="sub">· {{ t('{changing} will change, {skipping} skipped', { changing, skipping }) }}</span>
      </div>
      <p v-if="timedOut" class="warn" role="note">{{ t('The search was stopped after a while, so this may not be everything.') }}</p>
      <p v-if="noMore" class="sub">{{ noMore }}</p>
      <ul v-if="shown.length" class="list">
        <li
          v-for="(m, index) in visibleRows"
          :key="matchKey(m)"
          :class="{ on: current === index, replaced: replacing && replaceable(m) }"
          :aria-current="current === index ? 'true' : undefined"
        >
          <input v-if="replacing && replaceable(m)" type="checkbox" :checked="!unchecked.has(matchKey(m))" :aria-label="t('Replace {where}', { where: host.where(m) })" @change="($event.target as HTMLInputElement).checked ? unchecked.delete(matchKey(m)) : unchecked.add(matchKey(m))">
          <button type="button" class="row" @click="go(index)">
            <span class="where mono">{{ host.where(m) }}</span>
            <span class="excerpt" :class="{ code: m.kind === 'formula' }">
              {{ excerptOf(m).before }}<mark>{{ excerptOf(m).hit }}</mark><template v-if="replacing && replaceable(m) && m.after !== null"> → <span class="after">{{ m.after }}</span></template><template v-else>{{ excerptOf(m).after }}</template>
            </span>
            <span class="kind">{{ m.kind === 'formula' ? t('formula') : m.kind === 'value' ? t('value') : t('text') }}</span>
          </button>
        </li>
        <li v-for="s in skippedRows" :key="`${s.sheet},${s.row},${s.col}`" class="skipped">
          <input type="checkbox" disabled :aria-label="t('Skipped {where}', { where: host.where(s) })">
          <span class="row"><span class="where mono">{{ host.where(s) }}</span><span class="why">🔒 {{ why(s.reason, s.by) }}</span><span class="kind">{{ t('skipped') }}</span></span>
        </li>
        <li v-if="shown.length > limit" class="more"><button type="button" class="link" @click="limit += 200">{{ t('Show more') }}</button></li>
      </ul>
      <details v-if="left.length" class="leftout" :open="showAllLeft" @toggle="showAllLeft = ($event.target as HTMLDetailsElement).open">
        <summary>{{ t('Left out ({count})', { count: left.length }) }} <span class="sub">{{ leftReasons }}</span></summary>
        <ul class="list">
          <li v-for="o in left" :key="`${o.sheet},${o.row},${o.col},${o.kind}`"><span class="row"><span class="where mono">{{ host.where(o) }}</span><span class="why">{{ whyLeftOut(o.why, t) }}</span></span></li>
        </ul>
      </details>
      <p v-if="status" class="status" role="status">{{ status }}</p>
    </section>

    <footer v-if="replacing">
      <button type="button" class="btn" :disabled="busy || !!problem || shown.length === 0" @click="replaceThis">{{ t('Replace this one') }}</button>
      <button type="button" class="btn primary" :disabled="busy || !!problem || changing === 0" data-testid="search-replace-all" @click="doReplace()">{{ t('Replace all {count}', { count: changing }) }}</button>
      <p class="hint">{{ t('One step in the history. Undo brings it back.') }}</p>
    </footer>
    <footer v-else class="keys">
      <p class="hint">{{ t('Enter: next match · Shift+Enter: previous · Esc: close') }}</p>
    </footer>
  </aside>
</template>

<style scoped>
.search {
  position: fixed;
  z-index: 40;
  top: 140px;
  right: 16px;
  bottom: 56px;
  width: 380px;
  max-width: calc(100vw - 32px);
  display: flex;
  flex-direction: column;
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--line);
  border-radius: 14px;
  box-shadow: 0 12px 40px rgb(31 26 51 / 22%);
  font-size: 13px;
  overflow: hidden;
}
header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 12px 8px 18px;
  border-bottom: 1px solid var(--line);
}
header h2 {
  flex: 1;
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.body {
  flex: 0 1 auto;
  overflow-y: auto;
  padding: 10px 16px 6px;
  display: grid;
  gap: 8px;
  align-content: start;
}
.label {
  margin: 6px 0 2px;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted);
}
.field {
  min-width: 0;
  padding: 6px 8px;
  border: 1px solid var(--line-field);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
}
.field:focus-visible,
.chip:focus-within,
.toggle:focus-within,
button:focus-visible {
  outline: 2px solid var(--app);
  outline-offset: 1px;
}
.field.bad {
  border-color: var(--danger);
  outline: 1px solid var(--danger);
}
.field.num {
  width: 52px;
}
.field.keepname {
  width: 92px;
}
.grow {
  flex: 1;
  min-width: 0;
}
.mono {
  font-family: var(--font-mono);
}
.row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.quick {
  display: flex;
  align-items: center;
  gap: 4px;
}
.quick .field {
  flex: 1;
  border-width: 2px;
  border-color: var(--app);
}
.pos {
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.icon {
  border: 0;
  background: none;
  color: var(--muted);
  font-size: 14px;
  line-height: 1;
  padding: 6px;
  border-radius: 6px;
  cursor: pointer;
}
.icon.small {
  font-size: 11px;
  padding: 4px;
}
.icon:hover:not(:disabled) {
  background: var(--faint);
  color: var(--text);
}
.icon:disabled {
  opacity: 0.4;
  cursor: default;
}
.link {
  border: 0;
  background: none;
  padding: 2px 0;
  color: var(--app-text);
  font-size: 13px;
  cursor: pointer;
}
.link:hover {
  text-decoration: underline;
}
.link.end {
  margin-left: auto;
}
.links {
  justify-content: space-between;
}
.add .adding {
  position: relative;
  display: inline-block;
}
.addselect {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}
.sentence {
  margin: 4px 0 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--mist);
  color: var(--ink);
  font-family: var(--font-display);
  font-style: italic;
  line-height: 1.45;
}
.kept {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.chip,
.toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid var(--line-field);
  border-radius: 999px;
  background: var(--surface);
  cursor: pointer;
  user-select: none;
}
.chip input,
.toggle input {
  position: absolute;
  opacity: 0;
  inset: 0;
  margin: 0;
  cursor: pointer;
}
.chip.on,
.toggle.on {
  border-color: var(--app);
  background: var(--app-soft);
  color: var(--app-text);
  font-weight: 500;
}
.chip.locked {
  opacity: 0.7;
  cursor: default;
}
.chip small {
  color: var(--muted);
}
.keptchip {
  gap: 2px;
  padding: 2px 4px 2px 10px;
}
.keptchip.insert {
  padding: 2px 10px;
}
.flags {
  margin-top: 6px;
}
.items {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 6px;
  border: 2px solid var(--app);
  border-radius: 10px;
}
.items .field {
  border: 0;
  padding: 4px;
}
.hint,
.sub {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.warn {
  margin: 0;
  padding: 6px 8px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--apricot) 18%, var(--surface));
  color: var(--text);
  font-size: 12px;
}
.error {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--danger) 12%, var(--surface));
  border: 1px solid var(--danger);
  font-size: 12.5px;
}
.valid {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--app-soft);
  color: var(--app-text);
  font-size: 12.5px;
}
.back {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  margin-top: 4px;
}
.confirm {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
  font-size: 12px;
}
.results {
  flex: 1 1 auto;
  min-height: 150px;
  overflow-y: auto;
  border-top: 1px solid var(--line);
  padding: 10px 16px;
  display: grid;
  gap: 6px;
  align-content: start;
}
.results .head {
  display: flex;
  gap: 6px;
  align-items: baseline;
}
.list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 2px;
}
.list li {
  display: flex;
  align-items: center;
  gap: 6px;
  border-radius: 8px;
  border-left: 3px solid transparent;
}
.list li.on {
  background: var(--mist);
  color: var(--ink);
  border-left-color: var(--app);
}
.list li .row {
  flex: 1;
  min-width: 0;
  flex-wrap: nowrap;
  padding: 5px 6px;
  border: 0;
  background: none;
  color: inherit;
  text-align: left;
  font: inherit;
  cursor: pointer;
}
.list li.skipped .row {
  cursor: default;
  color: var(--muted);
}
.where {
  flex: none;
  font-size: 11.5px;
  color: var(--muted);
}
.list li.on .where {
  color: var(--ink);
}
.excerpt {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.excerpt.code {
  font-family: var(--font-mono);
  font-size: 12px;
}
mark {
  background: var(--purpose-input);
  color: var(--ink);
  border-radius: 3px;
  padding: 0 2px;
  text-decoration: underline;
  text-decoration-thickness: 2px;
  text-underline-offset: 2px;
}
.after {
  color: var(--app-text);
  font-weight: 500;
}
.kind {
  flex: none;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--faint);
  color: var(--muted);
  font-size: 11px;
}
.why {
  flex: 1;
  color: var(--danger);
}
.leftout summary {
  cursor: pointer;
}
.status {
  margin: 0;
  color: var(--app-text);
}
footer {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 16px 12px;
  border-top: 1px solid var(--line);
}
footer .btn {
  flex: 1;
}
footer .hint {
  width: 100%;
}
.menu {
  display: grid;
  padding: 2px;
}
.menu button {
  display: block;
  width: 100%;
  padding: 7px 10px;
  border: 0;
  border-radius: 7px;
  background: none;
  color: var(--text);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}
.menu button:hover:not(:disabled) {
  background: var(--mist);
  color: var(--ink);
}
.menu button:disabled {
  color: var(--muted);
  cursor: default;
}
.sep {
  height: 1px;
  margin: 4px 6px;
  background: var(--line);
}
@media (max-width: 720px) {
  .search {
    top: auto;
    left: 8px;
    right: 8px;
    bottom: 8px;
    width: auto;
    max-width: none;
    max-height: 70vh;
  }
}
</style>
