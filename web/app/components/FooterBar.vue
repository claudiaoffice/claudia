<script setup lang="ts">
import { computed } from 'vue'
import { show } from '~/lib/cells'
import type { Summary } from '~/lib/selection'
import type { State } from '~/lib/session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{
  state: State
  summary: Summary
  canAdd: boolean
  /** The chart tab currently shown in place of a sheet, or `null` while a sheet is shown (E6.6). Who decides
   * which is active lives in `Workspace.vue` — there is nothing of this in the document itself, unlike
   * `state.activeSheet`, so two people looking at the same document may each have a different tab open. */
  activeChart: string | null
  /** How many cells of the computation being followed each sheet has (E6.23): a marker on the tab of the others. */
  marks?: Record<string, number>
}>()
defineEmits<{ pick: [id: string, kind: 'sheet' | 'chart']; add: [] }>()

const shownSum = computed(() => show({ t: 'float', v: props.summary.sum }))
const shownAverage = computed(() => (props.summary.average === null ? '' : show({ t: 'float', v: props.summary.average })))
</script>

<template>
  <footer class="foot">
    <div class="tabs" role="tablist" :aria-label="t('sheets')">
      <button
        v-for="s in state.sheets"
        :key="s.id"
        type="button"
        role="tab"
        :aria-selected="activeChart === null && s.id === state.activeSheet"
        :class="{ on: activeChart === null && s.id === state.activeSheet }"
        @click="$emit('pick', s.id, 'sheet')"
      >
        {{ s.name }}
        <span v-if="marks?.[s.id]" class="mark" :title="`${marks[s.id]}`" :aria-label="`${marks[s.id]} connected cells on this sheet`">◆ {{ marks[s.id] }}</span>
      </button>
      <span v-if="state.charts.length" class="sep" aria-hidden="true" />
      <button
        v-for="c in state.charts"
        :key="c.id"
        type="button"
        role="tab"
        :aria-selected="activeChart === c.id"
        :class="{ on: activeChart === c.id, chart: true }"
        @click="$emit('pick', c.id, 'chart')"
      >
        {{ c.name }}
      </button>
      <button v-if="canAdd" type="button" class="add" :title="t('New sheet')" :aria-label="t('new sheet')" @click="$emit('add')">+</button>
    </div>
    <div class="stats mono" aria-live="polite">
      <template v-if="summary.numbers > 1">
        <TransText :text="t('Sum {value}')"><template #value><b>{{ shownSum }}</b></template></TransText>
        <TransText :text="t('Average {value}')"><template #value><b>{{ shownAverage }}</b></template></TransText>
      </template>
      <TransText v-if="summary.count > 1" :text="t('Count {value}')"><template #value><b>{{ summary.count }}</b></template></TransText>
      <span class="rev" :title="t('line {line}', { line: state.line })">{{ state.revision ?? t('empty') }}</span>
    </div>
  </footer>
</template>

<style scoped>
.tabs .mark {
  margin-left: 6px;
  padding: 0 5px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--iris) 18%, var(--surface));
  color: var(--text);
  font-size: 11px;
}
.foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  height: 36px;
  padding: 0 10px;
  background: var(--surface);
  border-top: 1px solid var(--line);
}
.tabs {
  display: flex;
  gap: 4px;
  overflow-x: auto;
}
.tabs button {
  border: 0;
  background: transparent;
  padding: 4px 14px;
  border-radius: 8px;
  white-space: nowrap;
}
.tabs button:hover {
  background: var(--mist);
  color: var(--ink); /* `--mist` stays light in dark mode */
}
.tabs button.on {
  background: var(--app-soft);
  color: var(--app-dark);
  font-weight: 500;
  box-shadow: inset 0 -2px 0 var(--app);
  border-radius: 8px 8px 0 0;
}
.add {
  font-size: 18px;
  line-height: 1;
  padding: 3px 11px !important;
  color: var(--muted);
}
.sep {
  width: 1px;
  margin: 6px 2px;
  background: var(--line);
}
.tabs button.chart::before {
  content: '';
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 6px;
  border-radius: 2px;
  background: currentColor;
  opacity: 0.55;
  vertical-align: middle;
}
.stats {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
}
.stats b {
  color: var(--ink);
  font-weight: 500;
}
.rev {
  opacity: 0.8;
}
</style>
