<script setup lang="ts">
// What a rendered container shows when nobody is editing it: its picture, or why there is none yet. The type is named
// on the corner so it is never colour alone (BITV); a failure is an alert, "Drawing…" a polite status (D560).
import { computed } from 'vue'
import { useI18n } from '~/lib/i18n'
import { statusText, type RenderStatus } from '~/lib/rendering'

const props = defineProps<{ src: string; status: RenderStatus; label: string }>()
const { t } = useI18n()
const said = computed(() => statusText(props.status, props.label, t))
</script>

<template>
  <div class="face" :class="props.status.kind" data-testid="rendered-face">
    <img v-if="props.src" class="picture" :src="props.src" alt="" draggable="false" >
    <p v-if="said.text" class="state" :role="said.urgent ? 'alert' : 'status'">
      {{ said.text }}
      <template v-if="props.status.kind === 'failed'">
        <span v-for="(d, i) in props.status.diagnostics.slice(0, 3)" :key="i" class="diag">
          {{ d.line ? t('line {line}: {message}', { line: d.line, message: d.message }) : d.message }}
        </span>
      </template>
    </p>
    <span class="type" aria-hidden="true">{{ props.label }}</span>
  </div>
</template>

<style scoped>
.face {
  position: absolute;
  inset: 0;
}
.picture {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
  user-select: none;
}
.state {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  margin: 0;
  padding: 8px;
  text-align: center;
  font-size: 0.8em;
  color: var(--muted);
  font-style: italic;
  background: color-mix(in srgb, var(--paper) 70%, transparent);
  overflow: hidden;
}
.face.failed .state,
.face.unavailable .state {
  color: var(--ink);
  font-style: normal;
  border: 2px dashed var(--ink);
}
.diag {
  font-family: ui-monospace, monospace;
  font-style: normal;
}
.face.empty,
.face.drawing {
  outline: 1px dashed var(--line);
}
.type {
  position: absolute;
  right: 0;
  bottom: 0;
  padding: 0 6px;
  font-size: 10px;
  background: var(--paper);
  color: var(--muted);
  border: 1px solid var(--line);
  pointer-events: none;
}
</style>
