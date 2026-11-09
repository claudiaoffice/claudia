<script setup lang="ts">
// Edit ▸ Chart… (E6.6): describe a bar chart over the current selection and place it. Mirrors
// `SheetImageImportDialog.vue`'s shape, but there is no file to pick — the "picture" is the live range itself,
// shown as a small preview of its own headers (so picking "columns" or "rows" is not a guess) rather than a
// rendered Plotly figure, which would mean standing up a definition before the person has agreed to one.
//
// Per the approved mock, a new chart always gets both placements from the one definition it is given here
// (`defineDiagram`, then `addChart` and `addDiagramObject` together) — there is no "where should this go?"
// choice to make, because the whole point of a shared definition is that either one can be removed later
// without losing the other (`lib/session.ts`'s `forgetDiagram`/`removeChart` docstrings).
import { computed, ref } from 'vue'
import { chartRange, type Session } from '~/lib/session'

const props = defineProps<{
  session: Session
  sheet: string
  range: { r0: number; c0: number; r1: number; c1: number }
  /** Where the floating object lands — the current selection's top-left cell, at a fixed default size (there is
   * no aspect to keep, unlike an image's `anchorFor`). */
  anchorFor: () => { row: number; col: number; w: number; h: number }
}>()
const emit = defineEmits<{ close: []; inserted: [id: string] }>()

const name = ref('Chart')
const seriesIn = ref<'columns' | 'rows'>('columns')
const title = ref('')
const xTitle = ref('')
const yTitle = ref('')
const legend = ref(true)
const gridlines = ref(true)
const busy = ref(false)
const error = ref('')

const multiRow = computed(() => props.range.r1 > props.range.r0)
const multiCol = computed(() => props.range.c1 > props.range.c0)
const canSubmit = computed(() => name.value.trim() !== '' && !busy.value)

async function submit() {
  if (!canSubmit.value) return
  busy.value = true
  error.value = ''
  const draft = {
    range: chartRange(props.sheet, props.range.r0, props.range.c0, props.range.r1, props.range.c1),
    series_in: seriesIn.value,
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
  const [chartId, objectId] = await Promise.all([
    props.session.addChart(name.value.trim(), diagramId),
    props.session.addDiagramObject(diagramId, props.anchorFor()),
  ])
  busy.value = false
  // A definition still in use refuses to go, so a partial failure here (one placement went through, the other
  // did not) leaves a chart reachable at least one way rather than an orphaned definition nobody can see.
  if (objectId) emit('inserted', objectId)
  else if (chartId) emit('inserted', chartId)
  else error.value = 'Could not place the chart.'
}
</script>

<template>
  <Modal title="Insert chart" :width="440" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <p class="hint">
        Bar chart over <strong>{{ range.r1 - range.r0 + 1 }}</strong> rows × <strong>{{ range.c1 - range.c0 + 1 }}</strong> columns.
        <template v-if="multiRow && multiCol">The first row and column are read as headers.</template>
        <template v-else>Too small for a header on every side — missing labels are made up ("Series 1", "1", "2"…).</template>
      </p>
      <label class="field">Name (the tab it opens as)<input v-model="name" autocomplete="off" maxlength="60" /></label>
      <fieldset class="field" :disabled="!multiRow || !multiCol">
        <legend>Series are in</legend>
        <label class="radio"><input type="radio" value="columns" v-model="seriesIn" />Columns</label>
        <label class="radio"><input type="radio" value="rows" v-model="seriesIn" />Rows</label>
      </fieldset>
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
