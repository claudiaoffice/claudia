<script setup lang="ts">
// The tool bar of a slide: put a text box or a shape on it, take the selected object off it, undo and redo.
import type { ShapeDef } from '~/lib/slide-session'

defineProps<{
  shapes: ShapeDef[]
  canDelete: boolean
  canUndo: boolean
  canRedo: boolean
  undoLabel: string
  redoLabel: string
  readonly: boolean
}>()
defineEmits<{ text: []; shape: [id: string]; remove: []; undo: []; redo: [] }>()
</script>

<template>
  <div class="bar" role="toolbar" aria-label="insert">
    <div class="group">
      <button type="button" class="tool" :disabled="readonly" title="Text box" aria-label="text box" data-tool="text" @click="$emit('text')">
        <svg viewBox="0 0 20 20" width="18" height="18"><path d="M4 5V3.5h12V5M10 3.5v13M7.5 16.5h5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" /></svg>
        <span>Text</span>
      </button>
      <button v-for="s in shapes" :key="s.id" type="button" class="tool" :disabled="readonly" :title="s.name" :aria-label="s.name" :data-tool="s.id" @click="$emit('shape', s.id)">
        <svg viewBox="-6 -6 112 112" width="18" height="18" preserveAspectRatio="none" aria-hidden="true">
          <path :d="s.path" fill="none" stroke="currentColor" stroke-width="9" stroke-linejoin="round" />
        </svg>
        <span>{{ s.name }}</span>
      </button>
    </div>
    <div class="group">
      <button type="button" class="icon" :disabled="readonly || !canDelete" title="Delete the selected object (Del)" aria-label="delete" data-tool="delete" @click="$emit('remove')">
        <svg viewBox="0 0 20 20" width="18" height="18"><path d="M4 6h12M8 6V4h4v2m-6 0 .7 10h6.6L14 6M8.5 9v5m3-5v5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </button>
      <button type="button" class="icon" :disabled="!canUndo" :title="canUndo ? `Undo ${undoLabel}` : 'Nothing to undo'" aria-label="undo" @click="$emit('undo')">
        <svg viewBox="0 0 20 20" width="18" height="18"><path d="M7 5 3 9l4 4M3 9h8a5 5 0 0 1 0 10h-2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </button>
      <button type="button" class="icon" :disabled="!canRedo" :title="canRedo ? `Redo ${redoLabel}` : 'Nothing to redo'" aria-label="redo" @click="$emit('redo')">
        <svg viewBox="0 0 20 20" width="18" height="18"><path d="m13 5 4 4-4 4m4-4H9a5 5 0 0 0 0 10h2" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 10px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
  overflow-x: auto;
}
.group {
  display: flex;
  align-items: center;
  gap: 2px;
}
.tool,
.icon {
  border: 0;
  background: transparent;
  border-radius: 8px;
  color: var(--ink);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 10px;
  white-space: nowrap;
}
.icon {
  width: 30px;
  padding: 0;
  justify-content: center;
}
.tool:hover:not(:disabled),
.icon:hover:not(:disabled) {
  background: var(--app-soft);
}
.tool:disabled,
.icon:disabled {
  color: var(--muted);
  opacity: 0.5;
  cursor: default;
}
@media (max-width: 736px) {
  .tool span {
    display: none;
  }
}
</style>
