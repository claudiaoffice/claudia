<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'

defineProps<{ title: string; width?: number }>()
const emit = defineEmits<{ close: [] }>()

function escape(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}
onMounted(() => window.addEventListener('keydown', escape))
onBeforeUnmount(() => window.removeEventListener('keydown', escape))
</script>

<template>
  <div class="backdrop" @mousedown.self="emit('close')">
    <div class="modal" role="dialog" aria-modal="true" :aria-label="title" :style="width ? { width: `min(${width}px, calc(100vw - 32px))` } : undefined">
      <h2>{{ title }}</h2>
      <slot />
    </div>
  </div>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  background: rgb(31 26 51 / 38%);
}
.modal {
  width: min(440px, calc(100vw - 32px));
  background: var(--surface);
  border-radius: 16px;
  padding: 24px 26px;
  box-shadow: var(--shadow);
  display: grid;
  gap: 14px;
}
h2 {
  margin: 0;
  font: 400 24px/1.1 var(--font-display);
}
</style>
