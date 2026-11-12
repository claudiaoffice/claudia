<script setup lang="ts">
// The menu on a table's header chip (E6.5, mock 2): what this column is for, or what the whole table is for. The
// cells are tinted by it, so the choice shows at once. Text only, like every menu here (HeaderMenu.vue).
import { columnPurpose, PURPOSES, type NameInfo, type Purpose } from '~/lib/names'

const props = defineProps<{ table: NameInfo; offset: number; x: number; y: number; readonly: boolean }>()
const emit = defineEmits<{ pick: [offset: number | null, purpose: Purpose]; close: [] }>()

const column = props.table.columns[props.offset]?.name ?? `Column ${props.offset + 1}`
const current = columnPurpose(props.table, props.offset)
</script>

<template>
  <Popover :x="x" :y="y" :width="236" :label="`purpose of ${table.name}`" @close="emit('close')">
    <div class="menu" data-testid="table-menu">
      <p class="title">{{ column }} <span class="dim">in {{ table.name }}</span></p>
      <button v-for="p in PURPOSES.filter((q) => q.value !== 'result')" :key="p.value" type="button" :disabled="readonly" :class="{ on: p.value === current }" @click="emit('pick', offset, p.value)">
        <span class="swatch" :style="{ background: `var(--purpose-${p.value})` }" />
        <span class="what">{{ p.label }}<small>{{ p.hint }}</small></span>
        <span v-if="p.value === current" class="tick" aria-hidden="true">✓</span>
      </button>
      <div class="sep" />
      <p class="title">Whole table</p>
      <div class="row">
        <button v-for="p in PURPOSES.filter((q) => q.value !== 'result')" :key="p.value" type="button" class="small" :disabled="readonly" @click="emit('pick', null, p.value)">{{ p.label }}</button>
      </div>
    </div>
  </Popover>
</template>

<style scoped>
.menu {
  display: grid;
  padding: 2px;
}
.title {
  margin: 4px 10px 6px;
  font-size: 12px;
  font-weight: 600;
}
.dim {
  font-weight: 400;
  color: var(--muted);
}
button {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 6px 10px;
  border: 0;
  border-radius: 7px;
  background: none;
  color: var(--text);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}
button:hover:not(:disabled) {
  background: var(--mist);
  color: var(--ink);
}
button:disabled {
  color: var(--muted);
  cursor: default;
}
.swatch {
  flex: none;
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1px solid var(--line-field);
}
.what {
  flex: 1;
  display: grid;
}
.what small {
  color: var(--muted);
  font-size: 11px;
}
button:hover .what small {
  color: var(--ink);
}
.tick {
  color: var(--app-text);
  font-weight: 700;
}
.sep {
  height: 1px;
  margin: 6px 6px;
  background: var(--line);
}
.row {
  display: flex;
  gap: 4px;
  padding: 0 6px 4px;
}
button.small {
  padding: 5px 6px;
  justify-content: center;
  border: 1px solid var(--line);
  font-size: 12px;
}
</style>
