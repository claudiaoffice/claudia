<script setup lang="ts">
// "Row height…"/"Column width…" (mockup 2, D135): typing a new size for the top-most (rows) or left-most (columns)
// line of the selection scales every other selected line by the same percentage its own size changed by — the
// same rule a border drag uses (SheetGrid.vue), just driven by a field instead of the mouse. A single line selected
// is the trivial case of the same rule.
import { computed, onMounted, ref } from 'vue'
import { columnName } from '~/lib/cells'
import { DEFAULT_SIZE, formatPercent, lineRange, percentChange, proportionalResize, SIZE_LIMITS, type Axis } from '~/lib/line-sizes'
import type { Session } from '~/lib/session'

const props = defineProps<{ session: Session; sheet: string; axis: Axis; first: number; last: number }>()
const emit = defineEmits<{ close: [] }>()

const field = ref<HTMLInputElement | null>(null)
const lines = computed(() => lineRange(props.first, props.last))
const multiple = computed(() => props.last > props.first)
const limits = computed(() => SIZE_LIMITS[props.axis])
const defaultSize = computed(() => DEFAULT_SIZE[props.axis])

function sizeOf(index: number): number {
  return props.axis === 'col' ? props.session.colWidth(props.sheet, index) : props.session.rowHeight(props.sheet, index)
}
const currentFirst = computed(() => sizeOf(props.first))

const value = ref(String(Math.round(currentFirst.value)))
onMounted(() => {
  field.value?.focus()
  field.value?.select()
})

const parsed = computed(() => {
  const n = Number(value.value)
  return Number.isFinite(n) ? n : null
})
const pct = computed(() => (parsed.value === null ? 0 : percentChange(currentFirst.value, parsed.value)))
const valid = computed(() => parsed.value !== null && parsed.value > 0)

const lineLabel = computed(() => (props.axis === 'row' ? `Row ${props.first + 1}` : `Column ${columnName(props.first)}`))
const fieldLabel = computed(() => `${lineLabel.value}'s ${props.axis === 'row' ? 'height' : 'width'}, in pixels${multiple.value ? ' (top of the selection)' : ''}`)
const noun = computed(() => (props.axis === 'row' ? 'rows' : 'columns'))
const unit = computed(() => (props.axis === 'row' ? 'tall' : 'wide'))

/** The example footer (mockup 2): up to two other selected lines, with their own size before and after. */
const examples = computed(() => {
  if (parsed.value === null) return []
  const pairs = new Map(proportionalResize(lines.value, sizeOf, props.first, parsed.value, limits.value))
  return lines.value
    .filter((i) => i !== props.first)
    .slice(0, 2)
    .map((i) => ({
      label: props.axis === 'row' ? `row ${i + 1}` : `column ${columnName(i)}`,
      from: Math.round(sizeOf(i)),
      to: Math.round(pairs.get(i)!),
    }))
})
const moreCount = computed(() => Math.max(0, lines.value.length - 1 - examples.value.length))

function resetToDefault() {
  value.value = String(defaultSize.value)
  field.value?.focus()
  field.value?.select()
}

async function submit() {
  if (!valid.value || parsed.value === null) return
  const pairs = proportionalResize(lines.value, sizeOf, props.first, parsed.value, limits.value)
  if (await props.session.resizeLines(props.sheet, props.axis, pairs)) emit('close')
}
</script>

<template>
  <Modal :title="axis === 'row' ? 'Row height' : 'Column width'" :width="420" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <p v-if="multiple" class="lead">{{ lines.length }} {{ noun }} selected — {{ lineLabel }} to {{ axis === 'row' ? `row ${last + 1}` : `column ${columnName(last)}` }} — with different sizes.</p>
      <div class="row">
        <label class="field">
          {{ fieldLabel }}
          <input ref="field" v-model="value" type="number" :min="limits.lo" :max="limits.hi" inputmode="numeric" autocomplete="off" />
        </label>
        <span v-if="parsed !== null" class="tag" :class="{ zero: pct === 0 }">{{ formatPercent(pct) }}</span>
      </div>
      <p class="was">was {{ Math.round(currentFirst) }} px {{ unit }}</p>
      <button type="button" class="reset" @click="resetToDefault">Reset to default ({{ defaultSize }} px)</button>

      <template v-if="multiple && examples.length">
        <div class="sep" />
        <p class="example">
          Same {{ formatPercent(pct) }} applied to each {{ axis === 'row' ? 'row' : 'column' }}'s own size:
          <template v-for="(e, i) in examples" :key="e.label">
            {{ e.label }}: {{ e.from }} → {{ e.to }} px<template v-if="i < examples.length - 1 || moreCount">&nbsp;·&nbsp;</template>
          </template>
          <template v-if="moreCount">and {{ moreCount }} more</template>
        </p>
      </template>

      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="!valid">Set {{ axis === 'row' ? 'height' : 'width' }}</button>
        <button class="btn" type="button" @click="emit('close')">Cancel</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.form {
  display: grid;
  gap: 10px;
}
.lead {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
.row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}
.field {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 6px;
  font-size: 13px;
}
.field input {
  font-variant-numeric: tabular-nums;
}
.tag {
  flex-shrink: 0;
  background: var(--app);
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  padding: 6px 9px;
  border-radius: 999px;
  font-variant-numeric: tabular-nums;
}
.tag.zero {
  background: var(--muted);
}
.was {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.reset {
  justify-self: start;
  border: 0;
  background: none;
  padding: 0;
  color: var(--app-text);
  font-size: 12.5px;
  text-decoration: underline;
  cursor: pointer;
}
.sep {
  height: 1px;
  background: var(--line);
}
.example {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
