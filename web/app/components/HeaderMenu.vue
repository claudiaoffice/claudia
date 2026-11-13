<script setup lang="ts">
// The context menu on a row or column header (mockup 1, D135): insert/delete, mirrored for the two axes, and a
// text-only "Row height…"/"Column width…" item that opens LineSizeDialog.vue. Right-click only — no icons, per the
// style everywhere else in the app (StyleMenu.vue's gallery is the same convention).
import { computed } from 'vue'
import type { Axis } from '~/lib/line-sizes'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ axis: Axis; x: number; y: number; readonly: boolean }>()
const emit = defineEmits<{ insert: [after: boolean]; delete: []; resize: []; close: [] }>()

const row = computed(() => props.axis === 'row')
const menuLabel = computed(() => (row.value ? t('Row menu') : t('Column menu')))
const insertBefore = computed(() => (row.value ? t('Insert Row Above') : t('Insert Column Left')))
const insertAfter = computed(() => (row.value ? t('Insert Row Below') : t('Insert Column Right')))
const deleteLabel = computed(() => (row.value ? t('Delete Rows') : t('Delete Columns')))
const sizeLabel = computed(() => (row.value ? t('Row height…') : t('Column width…')))
</script>

<template>
  <Popover :x="x" :y="y" :width="200" :label="menuLabel" @close="emit('close')">
    <div class="menu" data-testid="header-menu">
      <button type="button" :disabled="readonly" @click="emit('insert', false)">{{ insertBefore }}</button>
      <button type="button" :disabled="readonly" @click="emit('insert', true)">{{ insertAfter }}</button>
      <div class="sep" />
      <button type="button" :disabled="readonly" @click="emit('delete')">{{ deleteLabel }}</button>
      <div class="sep" />
      <button type="button" :disabled="readonly" @click="emit('resize')">{{ sizeLabel }}</button>
    </div>
  </Popover>
</template>

<style scoped>
.menu {
  display: grid;
  padding: 2px;
}
.menu button {
  display: block;
  width: 100%;
  padding: 7px 10px;
  border: 0;
  border-radius: 7px;
  background: none;
  color: var(--text);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}
.menu button:hover:not(:disabled) {
  background: var(--mist);
  color: var(--ink); /* `--mist` stays light in dark mode, same fix as StyleMenu.vue's `.gallery button:hover` */
}
.menu button:disabled {
  color: var(--muted);
  cursor: default;
}
.sep {
  height: 1px;
  margin: 4px 6px;
  background: var(--line);
}
</style>
