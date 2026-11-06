<script setup lang="ts">
// The size of the type: a number with − and + around it. Units stay as the style has them (pt, px, em…).
import { computed, ref, watch } from 'vue'
import { fontSizeOf, type Css } from '~/lib/style-css'

const props = defineProps<{ look: Css; disabled?: boolean }>()
const emit = defineEmits<{ step: [direction: 1 | -1]; size: [value: number, unit: string] }>()

const size = computed(() => fontSizeOf(props.look))
const typed = ref(String(size.value?.value ?? ''))
watch(size, (s) => (typed.value = s ? String(s.value) : ''))

function commit() {
  const value = Number(typed.value.replace(',', '.'))
  if (Number.isFinite(value) && value > 0) emit('size', value, size.value?.unit ?? 'pt')
  else typed.value = String(size.value?.value ?? '')
}
</script>

<template>
  <div class="size" role="group" aria-label="Size" data-testid="size-field">
    <button type="button" :disabled="disabled" aria-label="Smaller" title="Smaller" @click="emit('step', -1)">−</button>
    <input v-model="typed" inputmode="decimal" aria-label="Font size" :disabled="disabled" @keydown.enter.prevent="commit" @blur="commit" />
    <span class="unit mono">{{ size?.unit ?? 'pt' }}</span>
    <button type="button" :disabled="disabled" aria-label="Larger" title="Larger" @click="emit('step', 1)">+</button>
  </div>
</template>

<style scoped>
.size {
  display: inline-flex;
  align-items: center;
  height: 30px;
  border: 1px solid var(--line-field); /* a control boundary, not a divider — the owner's 2026-11-06 report */
  border-radius: 8px;
  background: var(--surface);
  overflow: hidden;
}
.size button {
  width: 26px;
  height: 100%;
  border: 0;
  background: none;
  font-size: 16px;
}
.size button:hover:not(:disabled) {
  background: var(--mist);
  color: var(--ink); /* `--mist` stays light in dark mode */
}
input {
  width: 42px;
  height: 100%;
  border: 0;
  text-align: right;
  padding: 0;
  background: none;
}
.unit {
  padding: 0 4px 0 2px;
  font-size: 11px;
  color: var(--muted);
}
</style>
