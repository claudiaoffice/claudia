<script setup lang="ts">
// A small menu at a point of the window, opened by a right click rather than a menu-bar title: the same `MenuItem`
// shape `MenuBar.vue` already uses (so a caller builds its items once and either bar can show them), just offered
// through `Popover` instead of a fixed dropdown. App-agnostic — knows nothing about slides, cells or paragraphs —
// so composes and computes can reuse it for their own objects the same way `SlideCanvas.vue` does for creates'.
import type { MenuItem } from './MenuBar.vue'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

defineProps<{ x: number; y: number; items: MenuItem[]; label?: string }>()
const emit = defineEmits<{ close: [] }>()

function choose(item: MenuItem) {
  if (item.disabled || item.separator) return
  emit('close')
  item.action?.()
}
</script>

<template>
  <Popover :x="x" :y="y" :width="200" :label="label ?? t('Object menu')" @close="emit('close')">
    <ul class="menu" role="menu" :aria-label="label ?? t('Object menu')">
      <template v-for="(item, i) in items" :key="i">
        <li v-if="item.separator" class="sep" role="separator" />
        <li v-else role="none">
          <button type="button" role="menuitem" :disabled="item.disabled" @click="choose(item)">
            <span>{{ item.label }}</span>
            <kbd v-if="item.hint">{{ item.hint }}</kbd>
          </button>
        </li>
      </template>
    </ul>
  </Popover>
</template>

<style scoped>
.menu {
  list-style: none;
  margin: 0;
  padding: 0;
}
.menu button {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  border: 0;
  background: transparent;
  text-align: left;
  padding: 6px 10px;
  border-radius: 6px;
}
.menu button:hover:not(:disabled) {
  background: var(--mist);
  color: var(--ink); /* `--mist` stays light in dark mode by design, same as MenuBar.vue's own `.drop button` */
}
.menu button:disabled {
  color: var(--muted);
  cursor: default;
}
.sep {
  height: 1px;
  background: var(--line);
  margin: 5px 4px;
}
kbd {
  font: 400 12px var(--font-mono);
  color: var(--muted);
}
</style>
