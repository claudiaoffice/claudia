<script setup lang="ts">
import { computed } from 'vue'
import { show } from '~/lib/cells'
import type { Summary } from '~/lib/selection'
import type { State } from '~/lib/session'

const props = defineProps<{ state: State; summary: Summary; canAdd: boolean }>()
defineEmits<{ pick: [id: string]; add: [] }>()

const shownSum = computed(() => show({ t: 'float', v: props.summary.sum }))
const shownAverage = computed(() => (props.summary.average === null ? '' : show({ t: 'float', v: props.summary.average })))
</script>

<template>
  <footer class="foot">
    <div class="tabs" role="tablist" aria-label="sheets">
      <button
        v-for="s in state.sheets"
        :key="s.id"
        type="button"
        role="tab"
        :aria-selected="s.id === state.activeSheet"
        :class="{ on: s.id === state.activeSheet }"
        @click="$emit('pick', s.id)"
      >
        {{ s.name }}
      </button>
      <button v-if="canAdd" type="button" class="add" title="New sheet" aria-label="new sheet" @click="$emit('add')">+</button>
    </div>
    <div class="stats mono" aria-live="polite">
      <template v-if="summary.numbers > 1">
        <span>Sum <b>{{ shownSum }}</b></span>
        <span>Average <b>{{ shownAverage }}</b></span>
      </template>
      <span v-if="summary.count > 1">Count <b>{{ summary.count }}</b></span>
      <span class="rev" :title="`line ${state.line}`">{{ state.revision ?? 'empty' }}</span>
    </div>
  </footer>
</template>

<style scoped>
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
