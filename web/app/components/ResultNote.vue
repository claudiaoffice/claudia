<script setup lang="ts">
// What to say about a cell of a query result (E6.5, mock 5): a cell that shows part of a result cannot be typed into,
// and says where it comes from; a result that does not fit says what is in the way (#SPILL!); a query that failed says
// why (#SQL!) and, when a column was misspelled, offers the one that was probably meant.
import { computed } from 'vue'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{
  x: number
  y: number
  note: { kind: 'spill'; from: string } | { kind: 'blocked'; detail: string; blocker: string | null } | { kind: 'sql'; detail: string; mend: { wrong: string; right: string } | null }
  readonly: boolean
}>()
const emit = defineEmits<{ close: []; editQuery: []; copyValues: []; selectBlocker: []; useWord: []; edit: [] }>()

const title = computed(() => {
  switch (props.note.kind) {
    case 'spill':
      return t('Part of the result of the query in {cell}', { cell: props.note.from })
    case 'blocked':
      return t('#SPILL! — the result does not fit')
    default:
      return t('#SQL! — the query did not run')
  }
})
</script>

<template>
  <Popover :x="x" :y="y" :width="300" :label="t('about this cell')" @close="emit('close')">
    <div class="note" data-testid="result-note">
      <p class="title">{{ title }}</p>
      <template v-if="note.kind === 'spill'">
        <p class="text">{{ t('These cells are filled by the query, so they are not typed into.') }}</p>
        <div class="buttons">
          <button type="button" class="btn primary small" :disabled="readonly" @click="emit('editQuery')">{{ t('Edit query…') }}</button>
          <button type="button" class="btn small" @click="emit('copyValues')">{{ t('Copy as values') }}</button>
        </div>
      </template>
      <template v-else-if="note.kind === 'blocked'">
        <p class="text">{{ note.detail }}.</p>
        <div class="buttons">
          <button v-if="note.blocker" type="button" class="btn primary small" @click="emit('selectBlocker')">{{ t('Select {blocker}', { blocker: note.blocker }) }}</button>
          <button type="button" class="btn small" :disabled="readonly" @click="emit('editQuery')">{{ t('Edit query…') }}</button>
        </div>
      </template>
      <template v-else>
        <p class="text mono">{{ note.detail }}</p>
        <TransText v-if="note.mend" tag="p" class="text" :text="t('Did you mean {word}?')"><template #word><b class="mono">{{ note.mend.right }}</b></template></TransText>
        <div class="buttons">
          <button v-if="note.mend" type="button" class="btn primary small" :disabled="readonly" @click="emit('useWord')">{{ t('Use {right}', { right: note.mend.right }) }}</button>
          <button type="button" class="btn small" :disabled="readonly" @click="emit('editQuery')">{{ t('Edit query…') }}</button>
        </div>
      </template>
    </div>
  </Popover>
</template>

<style scoped>
.note {
  display: grid;
  gap: 8px;
  padding: 8px 10px 10px;
}
.title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
}
.text {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}
.buttons {
  display: flex;
  gap: 8px;
}
.small {
  padding: 4px 10px;
  font-size: 12px;
}
</style>
