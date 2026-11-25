<script setup lang="ts">
import { computed } from 'vue'
import { show } from '~/lib/cells'
import type { Summary } from '~/lib/selection'
import type { State, TabInfo } from '~/lib/session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{
  state: State
  summary: Summary
  canAdd: boolean
  /** How many cells of the computation being followed each sheet has (E6.23): a marker on the tab of the others. */
  marks?: Record<string, number>
}>()
defineEmits<{ pick: [id: string, kind: 'sheet' | 'slide']; add: []; rename: [id: string] }>()

/** Is this sheet or slide the tab on show? A slide is shown in place of the sheet (`state.activeSlide`, E6.31). */
const isShown = (tab: TabInfo) => (tab.kind === 'slide' ? tab.id === props.state.activeSlide : !props.state.activeSlide && tab.id === props.state.activeSheet)

const shownSum = computed(() => show({ t: 'float', v: props.summary.sum }))
const shownAverage = computed(() => (props.summary.average === null ? '' : show({ t: 'float', v: props.summary.average })))
</script>

<template>
  <footer class="foot">
    <div class="tabs">
      <div class="tablist" role="tablist" :aria-label="t('sheets and slides')">
        <button
          v-for="s in state.tabs"
          :key="s.id"
          type="button"
          role="tab"
          :data-thing="s.id"
          :data-kind="s.kind"
          :aria-selected="isShown(s)"
          :class="{ on: isShown(s), slide: s.kind === 'slide' }"
          :aria-label="s.kind === 'slide' ? t('Slide: {name}', { name: s.name }) : undefined"
          :title="canAdd ? t('Double-click to rename') : undefined"
          @click="$emit('pick', s.id, s.kind)"
          @dblclick="canAdd && $emit('rename', s.id)"
        >
          {{ s.name }}
          <span v-if="marks?.[s.id]" class="mark" :title="`${marks[s.id]}`" :aria-label="`${marks[s.id]} connected cells on this sheet`">◆ {{ marks[s.id] }}</span>
        </button>
      </div>
      <!-- a button that adds a sheet is not a tab: it sits beside the tab list, not in it -->
      <button v-if="canAdd" type="button" class="add" :title="t('New sheet')" :aria-label="t('new sheet')" @click="$emit('add')">+</button>
    </div>
    <div class="stats mono" aria-live="polite">
      <template v-if="summary.numbers > 1">
        <TransText :text="t('Sum {value}')"><template #value><b>{{ shownSum }}</b></template></TransText>
        <TransText :text="t('Average {value}')"><template #value><b>{{ shownAverage }}</b></template></TransText>
      </template>
      <TransText v-if="summary.count > 1" :text="t('Count {value}')"><template #value><b>{{ summary.count }}</b></template></TransText>
      <span class="rev" :title="t('branch {branch}', { branch: state.branch })">{{ state.revision ?? t('empty') }}</span>
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
.tablist {
  display: flex;
  gap: 4px;
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
/* a slide's tab: a small 16:9 frame before its name, so it is told apart from a sheet's (mock 1 of E6.31) */
.tabs button.slide::before {
  content: '';
  display: inline-block;
  width: 12px;
  height: 7px;
  margin-right: 6px;
  border: 1.5px solid currentColor;
  border-radius: 1px;
  opacity: 0.7;
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
</style>
