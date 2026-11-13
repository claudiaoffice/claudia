<script setup lang="ts">
// "Row height…"/"Column width…" (mockup 2, D135): typing a new size for the top-most (rows) or left-most (columns)
// line of the selection scales every other selected line by the same percentage its own size changed by — the
// same rule a border drag uses (SheetGrid.vue), just driven by a field instead of the mouse. A single line selected
// is the trivial case of the same rule.
import { computed, onMounted, ref } from 'vue'
import { columnName } from '~/lib/cells'
import { DEFAULT_SIZE, formatPercent, lineRange, percentChange, proportionalResize, SIZE_LIMITS, type Axis } from '~/lib/line-sizes'
import type { Session } from '~/lib/session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

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

const lineLabel = computed(() => (props.axis === 'row' ? t('Row {n}', { n: props.first + 1 }) : t('Column {n}', { n: columnName(props.first) })))
const fieldLabel = computed(() => {
  const line = lineLabel.value
  const base = props.axis === 'row' ? t("{line}'s height, in pixels", { line }) : t("{line}'s width, in pixels", { line })
  return multiple.value ? t('{label} (top of the selection)', { label: base }) : base
})
/** "5 rows selected — Row 2 to row 6 — with different sizes." as one sentence per axis, so a translator moves the
 * whole thing around rather than assembling it from a noun and a label. */
const selectedNote = computed(() => {
  const count = lines.value.length
  return props.axis === 'row'
    ? t('{count} rows selected — {line} to row {last} — with different sizes.', { count, line: lineLabel.value, last: props.last + 1 })
    : t('{count} columns selected — {line} to column {last} — with different sizes.', { count, line: lineLabel.value, last: columnName(props.last) })
})
const wasNote = computed(() => {
  const size = Math.round(currentFirst.value)
  return props.axis === 'row' ? t('was {size} px tall', { size }) : t('was {size} px wide', { size })
})
const sameNote = computed(() =>
  props.axis === 'row'
    ? t("Same {pct} applied to each row's own size:", { pct: formatPercent(pct.value) })
    : t("Same {pct} applied to each column's own size:", { pct: formatPercent(pct.value) }),
)

/** The example footer (mockup 2): up to two other selected lines, with their own size before and after. */
const examples = computed(() => {
  if (parsed.value === null) return []
  const pairs = new Map(proportionalResize(lines.value, sizeOf, props.first, parsed.value, limits.value))
  return lines.value
    .filter((i) => i !== props.first)
    .slice(0, 2)
    .map((i) => ({
      label: props.axis === 'row' ? t('row {n}', { n: i + 1 }) : t('column {n}', { n: columnName(i) }),
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
  <Modal :title="axis === 'row' ? t('Row height') : t('Column width')" :width="420" @close="emit('close')">
    <form class="form" @submit.prevent="submit">
      <p v-if="multiple" class="lead">{{ selectedNote }}</p>
      <div class="row">
        <label class="field">
          {{ fieldLabel }}
          <input ref="field" v-model="value" type="number" :min="limits.lo" :max="limits.hi" inputmode="numeric" autocomplete="off" >
        </label>
        <span v-if="parsed !== null" class="tag" :class="{ zero: pct === 0 }">{{ formatPercent(pct) }}</span>
      </div>
      <p class="was">{{ wasNote }}</p>
      <button type="button" class="reset" @click="resetToDefault">{{ t('Reset to default ({defaultSize} px)', { defaultSize }) }}</button>

      <template v-if="multiple && examples.length">
        <div class="sep" />
        <p class="example">
          {{ sameNote }}
          <template v-for="(e, i) in examples" :key="e.label">
            {{ t('{label}: {from} → {to} px', { label: e.label, from: e.from, to: e.to }) }}<template v-if="i < examples.length - 1 || moreCount">&nbsp;·&nbsp;</template>
          </template>
          <template v-if="moreCount">{{ t('and {moreCount} more', { moreCount }) }}</template>
        </p>
      </template>

      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="!valid">{{ axis === 'row' ? t('Set height') : t('Set width') }}</button>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
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
