<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{
  label: string
  text: string
  editing: boolean
  canUndo: boolean
  canRedo: boolean
  undoLabel: string
  redoLabel: string
  readonly: boolean
}>()
const emit = defineEmits<{
  goto: [label: string]
  focusText: []
  caret: [position: number]
  'update:text': [text: string]
  commit: []
  cancel: []
  undo: []
  redo: []
}>()

const jump = ref(props.label)
watch(
  () => props.label,
  (label) => (jump.value = label),
)

function reportCaret(event: Event) {
  const position = (event.target as HTMLInputElement).selectionStart
  if (position !== null) emit('caret', position)
}

function onInput(event: Event) {
  emit('update:text', (event.target as HTMLInputElement).value)
  reportCaret(event)
}

function submitJump() {
  emit('goto', jump.value)
}
</script>

<template>
  <div class="formula">
    <input
      v-model="jump"
      class="name mono"
      aria-label="cell"
      spellcheck="false"
      @keydown.enter.prevent="submitJump"
      @focus="($event.target as HTMLInputElement).select()"
    >
    <div class="history">
      <button type="button" class="icon" :disabled="!canUndo" :title="canUndo ? `Undo ${undoLabel}` : 'Nothing to undo'" aria-label="undo" @click="$emit('undo')">
        <svg viewBox="0 0 20 20" width="18" height="18"><path d="M7 5 3 9l4 4M3 9h8a5 5 0 0 1 0 10h-2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </button>
      <button type="button" class="icon" :disabled="!canRedo" :title="canRedo ? `Redo ${redoLabel}` : 'Nothing to redo'" aria-label="redo" @click="$emit('redo')">
        <svg viewBox="0 0 20 20" width="18" height="18"><path d="m13 5 4 4-4 4m4-4H9a5 5 0 0 0 0 10h2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </button>
    </div>
    <span class="eq" aria-hidden="true">=</span>
    <input
      class="text mono"
      aria-label="cell content"
      spellcheck="false"
      autocomplete="off"
      :readonly="readonly"
      :value="text"
      :class="{ editing }"
      :data-editing="editing || undefined"
      @focus="$emit('focusText')"
      @input="onInput"
      @keyup="reportCaret"
      @click="reportCaret"
      @keydown.enter.prevent="$emit('commit')"
      @keydown.esc.prevent="$emit('cancel')"
    >
  </div>
</template>

<style scoped>
.formula {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}
.name {
  width: 96px;
  text-align: center;
  border: 1px solid var(--line-field); /* a control boundary, not a divider — the owner's 2026-11-06 report */
  border-radius: 8px;
  padding: 5px 8px;
  background: var(--page);
}
.history {
  display: flex;
}
.icon {
  border: 0;
  background: transparent;
  border-radius: 6px;
  width: 30px;
  height: 28px;
  display: grid;
  place-items: center;
  color: var(--ink);
}
.icon:hover:not(:disabled) {
  background: var(--mist);
}
.icon:disabled {
  color: var(--muted);
  opacity: 0.5;
  cursor: default;
}
.eq {
  font: 500 17px var(--font-display);
  /* Base `--app` as literal text measured under 4.5:1 for Teal/Rose against `--surface-dark` (4.04:1 / 3.78:1) —
   * found while auditing every accent-as-text site, not separately reported. `--app-text` resolves to `--app-dark`
   * in light mode (visually near-identical to base `--app`) and the dark-mode-safe variant in dark mode. */
  color: var(--app-text);
  padding: 0 2px 0 8px;
}
.text {
  flex: 1;
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 5px 8px;
  background: transparent;
  min-width: 0;
}
.text:hover {
  border-color: var(--line);
}
.text.editing,
.text:focus {
  border-color: var(--app);
  background: var(--surface);
  outline: none;
}
</style>
