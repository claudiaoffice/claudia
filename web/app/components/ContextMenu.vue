<script setup lang="ts">
// A small menu at a point of the window, opened by a right click rather than a menu-bar title: the same `MenuItem`
// shape `MenuBar.vue` already uses (so a caller builds its items once and either bar can show them), just offered
// through `Popover` instead of a fixed dropdown. App-agnostic — knows nothing about slides, cells or paragraphs —
// so composes and computes can reuse it for their own objects the same way `SlideCanvas.vue` does for creates'.
import { ref } from 'vue'
import type { MenuItem } from './MenuBar.vue'
import { useI18n } from '~/lib/i18n'
import { hintOf } from '~/lib/shortcuts'

const { t } = useI18n()

defineProps<{ x: number; y: number; items: MenuItem[]; label?: string; width?: number }>()
const emit = defineEmits<{ close: [] }>()

/** The entry whose submenu is open (one level, as in `MenuBar.vue`): a click or Enter opens it in place below the
 * entry, so the menu stays one column and works with the keyboard exactly like the flat entries do. */
const open = ref<number | null>(null)

function choose(item: MenuItem, index?: number) {
  if (item.disabled || item.separator) return
  if (item.items) {
    open.value = open.value === index ? null : (index ?? null)
    return
  }
  emit('close')
  item.action?.()
}
</script>

<template>
  <Popover :x="x" :y="y" :width="width ?? 200" :label="label ?? t('Object menu')" @close="emit('close')">
    <ul class="menu" role="menu" :aria-label="label ?? t('Object menu')">
      <template v-for="(item, i) in items" :key="i">
        <li v-if="item.separator" class="sep" role="separator" />
        <li v-else role="none">
          <button
            type="button"
            :role="item.checked !== undefined ? 'menuitemcheckbox' : 'menuitem'"
            :aria-checked="item.checked"
            :aria-haspopup="item.items ? 'menu' : undefined"
            :aria-expanded="item.items ? open === i : undefined"
            :disabled="item.disabled"
            @click="choose(item, i)"
          >
            <span><span class="tick" aria-hidden="true">{{ item.checked ? '✓' : '' }}</span>{{ item.label }}<span v-if="item.items" aria-hidden="true"> ▸</span></span>
            <kbd v-if="hintOf(item.id) ?? item.hint">{{ hintOf(item.id) ?? item.hint }}</kbd>
          </button>
          <ul v-if="item.items && open === i" class="sub" role="menu" :aria-label="item.label">
            <template v-for="(sub, j) in item.items" :key="j">
              <li v-if="sub.separator" class="sep" role="separator" />
              <li v-else role="none">
                <button type="button" :role="sub.checked !== undefined ? 'menuitemradio' : 'menuitem'" :aria-checked="sub.checked" :disabled="sub.disabled" @click="choose(sub)">
                  <span><span class="tick" aria-hidden="true">{{ sub.checked ? '✓' : '' }}</span>{{ sub.label }}</span>
                  <kbd v-if="hintOf(sub.id) ?? sub.hint">{{ hintOf(sub.id) ?? sub.hint }}</kbd>
                </button>
              </li>
            </template>
          </ul>
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
.tick {
  display: inline-block;
  width: 1.2em;
}
.sub {
  list-style: none;
  margin: 0 0 0 12px;
  padding: 0;
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
