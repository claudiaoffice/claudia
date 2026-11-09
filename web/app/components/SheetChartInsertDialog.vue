<script setup lang="ts">
// Edit ▸ Chart… (E6.6): describe a bar chart over the current selection and place it. Mirrors
// `SheetImageImportDialog.vue`'s shape, but there is no file to pick — the "picture" is the live range itself,
// shown as a small preview of its own headers (so picking "columns" or "rows" is not a guess) rather than a
// rendered Plotly figure, which would mean standing up a definition before the person has agreed to one.
//
// A definition MAY be shown as a tab, a floating object, or both at once (D204) — the object layer underneath
// this dialog supports all three. But the dialog itself asks for exactly one (D211): the "both, always" default
// (D209's own fix, one round before this) still read as showing the same chart twice for no reason, so "Show
// as" is a radio choice, not a pair of independent checkboxes. Picking a different placement later just means
// inserting again — there is no "move" action, same as before either revision.
import { computed, onMounted, ref, watch } from 'vue'
import { show } from '~/lib/cells'
import { chartRange, type Session } from '~/lib/session'

const props = defineProps<{
  session: Session
  sheet: string
  range: { r0: number; c0: number; r1: number; c1: number }
  /** Where the floating object lands — the current selection's top-left cell, at a fixed default size (there is
   * no aspect to keep, unlike an image's `anchorFor`). */
  anchorFor: () => { row: number; col: number; w: number; h: number }
}>()
const emit = defineEmits<{ close: []; inserted: [objectId: string | null, chartId: string | null] }>()

const name = ref('Chart')
const seriesIn = ref<'columns' | 'rows'>('columns')
const headerRow = ref(true)
const title = ref('')
const xTitle = ref('')
const yTitle = ref('')
const legend = ref(true)
const gridlines = ref(true)
const placement = ref<'tab' | 'object'>('tab')
const busy = ref(false)
const error = ref('')

const multiRow = computed(() => props.range.r1 > props.range.r0)
const multiCol = computed(() => props.range.c1 > props.range.c0)
/** The first data column — the one past the category column, when there's room for a category column at all
 * (`chart_figure`'s own convention: a header *column* always goes by the range's shape). */
const dataCol0 = computed(() => props.range.c0 + (multiCol.value ? 1 : 0))
const canSubmit = computed(() => (placement.value !== 'tab' || name.value.trim() !== '') && !busy.value)

/** "First row is a header" is meant to save typing, not just toggle a server-side flag: the two cells that sit
 * over the category column and the first data column read exactly like the axis titles a person would
 * otherwise type by hand, so pre-fill them from the live sheet — once, and only into a field still blank, so
 * it never clobbers something already typed. Needs the header row's own cells loaded, which they usually are
 * already (the person just selected them), but `ensure` makes that true rather than assumed. */
async function autofillTitles() {
  if (!multiRow.value) return
  await props.session.ensure(props.sheet, props.range.r0, props.range.r0, props.range.c0, props.range.c1)
  const x = show(props.session.cell(props.sheet, props.range.r0, props.range.c0))
  const y = show(props.session.cell(props.sheet, props.range.r0, dataCol0.value))
  if (!xTitle.value.trim() && x) xTitle.value = x
  if (!yTitle.value.trim() && y) yTitle.value = y
}
onMounted(() => {
  if (headerRow.value) void autofillTitles()
})
watch(headerRow, (now) => {
  if (now) void autofillTitles()
})

async function submit() {
  if (!canSubmit.value) return
  busy.value = true
  error.value = ''
  const draft = {
    range: chartRange(props.sheet, props.range.r0, props.range.c0, props.range.r1, props.range.c1),
    series_in: seriesIn.value,
    header_row: headerRow.value,
    title: title.value.trim(),
    x_title: xTitle.value.trim(),
    y_title: yTitle.value.trim(),
    legend: legend.value,
    gridlines: gridlines.value,
  }
  const diagramId = await props.session.defineDiagram(draft)
  if (!diagramId) {
    busy.value = false
    error.value = 'That range will not make a chart.'
    return
  }
  const chartId = placement.value === 'tab' ? await props.session.addChart(name.value.trim(), diagramId) : null
  const objectId = placement.value === 'object' ? await props.session.addDiagramObject(diagramId, props.anchorFor()) : null
  busy.value = false
  if (objectId || chartId) emit('inserted', objectId, chartId)
  else error.value = 'Could not place the chart.'
}
</script>

<template>
  <Modal title="Insert chart" :width="520" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <p class="hint">
        Bar chart over <strong>{{ range.r1 - range.r0 + 1 }}</strong> rows × <strong>{{ range.c1 - range.c0 + 1 }}</strong> columns.
        <template v-if="multiCol">The first column is read as category or series names.</template>
        <template v-else>Only one column — no room for a header there; a label is made up.</template>
      </p>
      <fieldset class="field">
        <legend>Show as</legend>
        <label class="radio"><input type="radio" value="tab" v-model="placement" />A tab</label>
        <label class="radio"><input type="radio" value="object" v-model="placement" />A floating object on the sheet</label>
      </fieldset>
      <label class="field" :class="{ disabled: placement !== 'tab' }">
        Name (the tab it opens as)
        <input v-model="name" autocomplete="off" maxlength="60" :disabled="placement !== 'tab'" />
      </label>
      <div class="two">
        <fieldset class="field" :disabled="!multiRow || !multiCol">
          <legend>Series are in</legend>
          <label class="radio"><input type="radio" value="columns" v-model="seriesIn" />Columns</label>
          <label class="radio"><input type="radio" value="rows" v-model="seriesIn" />Rows</label>
        </fieldset>
        <div class="field">
          <label class="check" :class="{ disabled: !multiRow }">
            <input type="checkbox" v-model="headerRow" :disabled="!multiRow" />
            First row is a header
          </label>
          <p class="subhint">
            <template v-if="multiRow">Off reads every row as data — no row is skipped. On fills the axis titles below, for a field still blank.</template>
            <template v-else>Only one row — no room for a header there either.</template>
          </p>
        </div>
      </div>
      <label class="field">Title (optional)<input v-model="title" autocomplete="off" maxlength="120" /></label>
      <div class="two">
        <label class="field">X axis (optional)<input v-model="xTitle" autocomplete="off" maxlength="120" /></label>
        <label class="field">Y axis (optional)<input v-model="yTitle" autocomplete="off" maxlength="120" /></label>
      </div>
      <div class="two">
        <label class="check"><input type="checkbox" v-model="legend" />Legend</label>
        <label class="check"><input type="checkbox" v-model="gridlines" />Gridlines</label>
      </div>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="!canSubmit">{{ busy ? 'Inserting…' : 'Insert' }}</button>
        <button class="btn" type="button" @click="emit('close')">Cancel</button>
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
.subhint {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 12px;
}
.error {
  margin: 0;
  color: var(--rose);
  font-size: 13px;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
