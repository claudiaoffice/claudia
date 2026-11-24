<script setup lang="ts">
// Edit ▸ Chart… (E6.6): describe a bar chart over the current selection, or a table or query result, and place it.
// There is no file to pick — the "picture" is the live range itself, described by its size and headers (so picking
// "columns" or "rows" is not a guess) rather than a rendered Plotly figure.
//
// "Show as" (E6.31, D1475) is one choice: a slide of its own right after the tab shown (the default), or, on a sheet,
// a floating object on it, and on a slide, on that slide. A slide has no cells to select, so there the chart reads a
// table or a query result. The name is the chart's, whatever it is shown as; it starts as the next free "Chart n".
import { computed, onMounted, ref, watch } from 'vue'
import { show } from '~/lib/cells'
import { nameAt, purposeLabel, referLabel, visibleNames, type NameInfo } from '~/lib/names'
import { chartRange, type ChartShownAs, type Session } from '~/lib/session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{
  session: Session
  /** the sheet shown, or the one last shown while a slide is */
  sheet: string
  /** the slide shown, or `''` while a sheet is */
  slide: string
  range: { r0: number; c0: number; r1: number; c1: number }
  /** Where the floating object lands — the current selection's top-left cell, at a fixed default size (there is
   * no aspect to keep, unlike an image's `anchorFor`). */
  anchorFor: () => { row: number; col: number; w: number; h: number }
}>()
const emit = defineEmits<{ close: []; inserted: [made: { object: string; slide: string | null }, showAs: ChartShownAs] }>()

const onSlide = computed(() => props.slide !== '')
const name = ref('')
onMounted(async () => {
  const free = await props.session.freeName('chart')
  if (!name.value) name.value = free ?? t('Chart')
})
// Where the chart reads from (E6.5, mock 6): the cells that are selected, or the table or query result of a name — which
// the chart follows as it grows or moves. A selection that is exactly a name starts as that name. On a slide there are
// no cells: every table and query result of the workbook, and the first is chosen.
const sources = computed(() =>
  (onSlide.value ? props.session.state.names : visibleNames(props.session.state.names, props.sheet)).filter((n) => n.header && n.region !== null),
)
const keyOf = (n: NameInfo) => `${n.scope ?? ''}:${n.name}`
const atSelection = onSlide.value ? null : nameAt(props.session.state.names, props.sheet, props.range.r0, props.range.c0, props.range.r1, props.range.c1)
const picked = ref<string | null>(atSelection ? keyOf(atSelection) : onSlide.value && sources.value[0] ? keyOf(sources.value[0]) : null)
const source = computed<NameInfo | null>(() => sources.value.find((n) => keyOf(n) === picked.value) ?? null)
const onNamed = computed(() => source.value !== null)
const seriesIn = ref<'columns' | 'rows'>('columns')
const headerRow = ref(true)
const title = ref('')
const xTitle = ref('')
const yTitle = ref('')
const legend = ref(true)
const gridlines = ref(true)
const placement = ref<ChartShownAs>('slide')
const busy = ref(false)

const multiRow = computed(() => (source.value ? true : props.range.r1 > props.range.r0))
const multiCol = computed(() => (source.value ? source.value.columns.length > 1 : props.range.c1 > props.range.c0))
/** The first data column — the one past the category column, when there's room for a category column at all
 * (`chart_figure`'s own convention: a header *column* always goes by the range's shape). */
const dataCol0 = computed(() => props.range.c0 + (multiCol.value ? 1 : 0))
const canSubmit = computed(() => (!onSlide.value || source.value !== null) && !busy.value)

/** "First row is a header" is meant to save typing, not just toggle a server-side flag: the two cells that sit
 * over the category column and the first data column read exactly like the axis titles a person would
 * otherwise type by hand, so pre-fill them from the live sheet — once, and only into a field still blank, so
 * it never clobbers something already typed. Needs the header row's own cells loaded, which they usually are
 * already (the person just selected them), but `ensure` makes that true rather than assumed. */
async function autofillTitles() {
  if (source.value) {
    // a table has its column names already
    const [first, second] = source.value.columns
    if (!xTitle.value.trim() && first) xTitle.value = first.name
    if (!yTitle.value.trim() && second) yTitle.value = second.name
    return
  }
  if (!multiRow.value) return
  await props.session.ensure(props.sheet, props.range.r0, props.range.r0, props.range.c0, props.range.c1)
  const x = show(props.session.cell(props.sheet, props.range.r0, props.range.c0))
  const y = show(props.session.cell(props.sheet, props.range.r0, dataCol0.value))
  if (!xTitle.value.trim() && x) xTitle.value = x
  if (!yTitle.value.trim() && y) yTitle.value = y
}
onMounted(() => {
  if (headerRow.value || source.value) void autofillTitles()
})
watch(headerRow, (now) => {
  if (now) void autofillTitles()
})
watch(picked, () => {
  xTitle.value = ''
  yTitle.value = ''
  void autofillTitles()
})

async function submit() {
  if (!canSubmit.value) return
  busy.value = true
  const where = source.value
    ? { source: source.value.name, source_scope: source.value.scope }
    : { range: chartRange(props.sheet, props.range.r0, props.range.c0, props.range.r1, props.range.c1) }
  const draft = {
    ...where,
    series_in: seriesIn.value,
    header_row: source.value ? true : headerRow.value,
    title: title.value.trim(),
    x_title: xTitle.value.trim(),
    y_title: yTitle.value.trim(),
    legend: legend.value,
    gridlines: gridlines.value,
  }
  const made = await props.session.insertChart(draft, placement.value, name.value.trim(), placement.value === 'sheet' ? props.anchorFor() : undefined)
  busy.value = false
  if (made) emit('inserted', made, placement.value)
}
</script>

<template>
  <Modal :title="t('Insert chart')" :width="520" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <fieldset class="field kinds" :aria-label="t('chart type')">
        <legend>{{ t('Chart') }}</legend>
        <span class="kind on">{{ t('Bar') }}</span>
        <span class="kind soon" aria-disabled="true">{{ t('Line · soon') }}</span>
        <span class="kind soon" aria-disabled="true">{{ t('Scatter · soon') }}</span>
      </fieldset>
      <fieldset class="field sourcelist" data-testid="chart-source">
        <legend>{{ t('Data from') }}</legend>
        <label v-for="n in sources" :key="keyOf(n)" class="radio source" :class="{ on: picked === keyOf(n) }">
          <input v-model="picked" type="radio" :value="keyOf(n)" >
          <span class="mono strong">{{ n.name }}</span>
          <span v-if="n.kind === 'result'" class="badge">{{ t('SQL') }}</span>
          <span class="dim">{{ t('{range} · {rows} rows · {purpose}', { range: referLabel(n), rows: n.rows, purpose: purposeLabel(n.purpose) }) }}</span>
        </label>
        <label v-if="!onSlide" class="radio source" :class="{ on: picked === null }">
          <input v-model="picked" type="radio" :value="null" >
          <span>{{ t('Pick cells instead…') }}</span>
          <span class="dim">{{ t('the selection, as it is now') }}</span>
        </label>
        <p v-else-if="!sources.length" class="hint" role="alert">{{ t('This workbook has no table or query result yet: select the cells on a sheet first.') }}</p>
      </fieldset>
      <p v-if="onNamed" class="hint">
        <TransText :text="t('Bar chart of {name}: it follows the table as rows are added, and as a query result changes size.')"><template #name><strong class="mono">{{ source?.name }}</strong></template></TransText>
        <template v-if="multiCol">{{ t('The first column is read as category names.') }}</template>
      </p>
      <p v-else-if="!onSlide" class="hint">
        <TransText :text="t('Bar chart over {rows} rows × {columns} columns.')"><template #rows><strong>{{ range.r1 - range.r0 + 1 }}</strong></template><template #columns><strong>{{ range.c1 - range.c0 + 1 }}</strong></template></TransText>
        <template v-if="multiCol">{{ t('The first column is read as category or series names.') }}</template>
        <template v-else>{{ t('Only one column — no room for a header there; a label is made up.') }}</template>
      </p>
      <fieldset class="field">
        <legend>{{ t('Show as') }}</legend>
        <label class="radio"><input v-model="placement" type="radio" value="slide" >{{ t('A slide') }}</label>
        <label v-if="onSlide" class="radio"><input v-model="placement" type="radio" value="on_slide" >{{ t('On this slide') }}</label>
        <label v-else class="radio"><input v-model="placement" type="radio" value="sheet" >{{ t('A floating object on the sheet') }}</label>
      </fieldset>
      <label class="field">
        {{ t('Name of the chart') }}
        <input v-model="name" autocomplete="off" maxlength="60" >
      </label>
      <div class="two">
        <fieldset class="field" :disabled="!multiRow || !multiCol">
          <legend>{{ t('Series are in') }}</legend>
          <label class="radio"><input v-model="seriesIn" type="radio" value="columns" >{{ t('Columns') }}</label>
          <label class="radio"><input v-model="seriesIn" type="radio" value="rows" >{{ t('Rows') }}</label>
        </fieldset>
        <div class="field">
          <label class="check" :class="{ disabled: !multiRow }">
            <input v-model="headerRow" type="checkbox" :disabled="!multiRow || onNamed" >
            {{ t('First row is a header') }}
          </label>
          <p class="subhint">
            <template v-if="onNamed">{{ t('A table always has its header row.') }}</template>
            <template v-else-if="multiRow">{{ t('Off reads every row as data — no row is skipped. On fills the axis titles below, for a field still blank.') }}</template>
            <template v-else>{{ t('Only one row — no room for a header there either.') }}</template>
          </p>
        </div>
      </div>
      <label class="field">{{ t('Title (optional)') }}<input v-model="title" autocomplete="off" maxlength="120" ></label>
      <div class="two">
        <label class="field">{{ t('X axis (optional)') }}<input v-model="xTitle" autocomplete="off" maxlength="120" ></label>
        <label class="field">{{ t('Y axis (optional)') }}<input v-model="yTitle" autocomplete="off" maxlength="120" ></label>
      </div>
      <div class="two">
        <label class="check"><input v-model="legend" type="checkbox" >{{ t('Legend') }}</label>
        <label class="check"><input v-model="gridlines" type="checkbox" >{{ t('Gridlines') }}</label>
      </div>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="!canSubmit">{{ busy ? t('Inserting…') : t('Insert') }}</button>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.form {
  display: grid;
  gap: 14px;
}
.hint {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
.two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
fieldset.field {
  border: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 6px;
}
fieldset.field legend {
  font-size: 13px;
  padding: 0;
  margin: 0 0 2px;
}
.radio,
.check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: normal;
}
.check.disabled,
.field.disabled {
  color: var(--muted);
}
fieldset.field.kinds {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.kind {
  padding: 4px 12px;
  border: 1px solid var(--line-field);
  border-radius: 999px;
  font-size: 12px;
}
.kind.on {
  border-color: var(--app);
  box-shadow: 0 0 0 1px var(--app);
}
.kind.soon {
  color: var(--muted);
  border-style: dashed;
  cursor: not-allowed;
}
.sourcelist {
  max-height: 170px;
  overflow: auto;
}
.source {
  flex-wrap: wrap;
  padding: 5px 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.source.on {
  border-color: var(--app);
  box-shadow: 0 0 0 1px var(--app);
}
.strong {
  font-weight: 600;
}
.dim {
  color: var(--muted);
  font-size: 12px;
}
.badge {
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--purpose-result);
  font-size: 10px;
}
.subhint {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 12px;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
