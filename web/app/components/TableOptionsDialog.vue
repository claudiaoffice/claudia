<script setup lang="ts">
// Table options (E9.32, mock D): how the table is set, and what one of its columns holds. Every change is one step in the
// history, for everybody, as in the options of a table of contents; the dialog shows the table as it is now, so it follows
// a colleague's change. Remove takes the table away with its object (undo brings it back).
import { computed, ref, watch } from 'vue'
import { columnName, LOOKS, type TableInfo } from '~/lib/tables'
import type { TextSession } from '~/lib/text-session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()
const props = defineProps<{ session: TextSession; table: string; startColumn?: string }>()
const emit = defineEmits<{ close: [] }>()

const info = computed<TableInfo | null>(() => props.session.state.tables[props.table] ?? null)
const readonly = computed(() => props.session.readOnly)
watch(info, (now) => !now && emit('close'))

const chosen = ref(props.startColumn ?? info.value?.columns[0]?.id ?? '')
const column = computed(() => info.value?.columns.find((c) => c.id === chosen.value) ?? null)

const lookName = (id: string) => (id === 'rules' ? t('Rules') : id === 'grid' ? t('Grid') : id === 'plain' ? t('Plain') : id)
const TOTALS = computed(() => [
  { value: '', label: t('none') },
  { value: 'sum', label: t('Sum') },
  { value: 'mean', label: t('Mean') },
  { value: 'count', label: t('Count') },
  { value: 'min', label: t('Smallest') },
  { value: 'max', label: t('Largest') },
])
/** A share of the line, as hundredths of a percent on the wire and whole percents on the screen; empty is "by the words". */
const percent = (width: number | null) => (width === null ? '' : String(width / 100))
const fromPercent = (text: string): number | null | undefined => {
  if (text.trim() === '') return null
  const n = Number(text)
  return Number.isFinite(n) ? Math.round(n * 100) : undefined
}

function option(key: string, value: unknown) {
  if (readonly.value || !info.value) return
  void props.session.setTableOptions(props.table, { [key]: value })
}
function setting(key: string, value: unknown) {
  if (readonly.value || !column.value) return
  void props.session.setColumn(props.table, column.value.id, { [key]: value })
}
function onWidth(event: Event, apply: (width: number | null) => void) {
  const width = fromPercent((event.target as HTMLInputElement).value)
  if (width !== undefined) apply(width)
}
async function remove() {
  if (!readonly.value && (await props.session.removeTable(props.table))) emit('close')
}
</script>

<template>
  <Modal :title="t('Table options')" :width="460" @close="emit('close')">
    <form v-if="info" class="form" data-testid="table-options-dialog" @submit.prevent="emit('close')">
      <fieldset>
        <legend>{{ t('Table') }}</legend>
        <label class="field">
          {{ t('Header rows (repeated on every page)') }}
          <input type="number" min="0" :max="info.rows.length" :value="info.header_rows" :disabled="readonly" data-testid="table-header-rows" @change="option('header_rows', Number(($event.target as HTMLInputElement).value))" >
        </label>
        <label class="check"><input type="checkbox" :checked="info.banded" :disabled="readonly" data-testid="table-banded" @change="option('banded', ($event.target as HTMLInputElement).checked)" > {{ t('Banded rows') }}</label>
        <label class="field">
          {{ t('Look') }}
          <select :value="info.look" :disabled="readonly" data-testid="table-look" @change="option('look', ($event.target as HTMLSelectElement).value)">
            <option v-for="look in LOOKS" :key="look" :value="look">{{ lookName(look) }}</option>
          </select>
        </label>
        <label class="field">
          {{ t('Width, in percent of the line (empty: all of it)') }}
          <input type="number" min="10" max="100" step="1" :value="percent(info.width)" :disabled="readonly" data-testid="table-width" @change="onWidth($event, (w) => option('width', w))" >
        </label>
        <p class="note">{{ t('In the flow: the table takes its own place after its paragraph and breaks between rows across pages.') }}</p>
      </fieldset>

      <fieldset>
        <legend>{{ t('Column') }}</legend>
        <label class="field">
          {{ t('Column') }}
          <select v-model="chosen" data-testid="table-column">
            <option v-for="c in info.columns" :key="c.id" :value="c.id">{{ columnName(info, c.id, (n) => t('Column {n}', { n })) }}</option>
          </select>
        </label>
        <template v-if="column">
          <label class="field">
            {{ t('Holds') }}
            <select :value="column.kind" :disabled="readonly" data-testid="column-kind" @change="setting('kind', ($event.target as HTMLSelectElement).value)">
              <option value="text">{{ t('Words') }}</option>
              <option value="number">{{ t('Numbers') }}</option>
            </select>
          </label>
          <label class="field">
            {{ t('Total row') }}
            <select :value="column.total ?? ''" :disabled="readonly" data-testid="column-total" @change="setting('total', ($event.target as HTMLSelectElement).value || null)">
              <option v-for="o in TOTALS" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
          </label>
          <label class="field">
            {{ t('Width, in percent of the table (empty: by its words)') }}
            <input type="number" min="1" max="100" step="1" :value="percent(column.width)" :disabled="readonly" data-testid="column-width" @change="onWidth($event, (w) => setting('width', w))" >
          </label>
        </template>
      </fieldset>

      <div class="buttons">
        <button class="btn primary" type="submit">{{ t('Close') }}</button>
        <button class="btn danger" type="button" :disabled="readonly" data-testid="table-remove" @click="remove">{{ t('Remove table') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.form {
  display: grid;
  gap: 14px;
}
fieldset {
  display: grid;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 10px 12px;
}
legend {
  font-size: 12px;
  color: var(--muted);
  padding: 0 4px;
}
.field {
  display: grid;
  gap: 6px;
  font-size: 13px;
}
.check {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
}
.note {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
