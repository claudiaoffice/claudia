<script setup lang="ts">
// Insert ▸ Table… (E9.32, mock B): how big the table is and whether its first row is the header. Everything else is the
// table's options, which the table has once it is there. The table goes after the paragraph the caret is in, in the flow.
import { computed, onMounted, ref } from 'vue'
import { MAX_COLUMNS, MAX_ROWS } from '~/lib/tables'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()
const emit = defineEmits<{ insert: [size: { rows: number; cols: number; headerRows: number }]; close: [] }>()

const cols = ref(3)
const rows = ref(4)
const header = ref(true)
const first = ref<HTMLInputElement | null>(null)
onMounted(() => {
  first.value?.focus()
  first.value?.select()
})

const whole = (n: number, max: number) => Number.isInteger(n) && n >= 1 && n <= max
const valid = computed(() => whole(cols.value, MAX_COLUMNS) && whole(rows.value, MAX_ROWS))
function submit() {
  if (valid.value) emit('insert', { rows: rows.value, cols: cols.value, headerRows: header.value ? 1 : 0 })
}
</script>

<template>
  <Modal :title="t('Insert table')" :width="380" @close="emit('close')">
    <form class="form" data-testid="table-dialog" @submit.prevent="submit">
      <div class="sizes">
        <label class="field">
          {{ t('Columns') }}
          <input ref="first" v-model.number="cols" type="number" min="1" :max="MAX_COLUMNS" inputmode="numeric" autocomplete="off" data-testid="table-cols" >
        </label>
        <label class="field">
          {{ t('Rows') }}
          <input v-model.number="rows" type="number" min="1" :max="MAX_ROWS" inputmode="numeric" autocomplete="off" data-testid="table-rows" >
        </label>
      </div>
      <label class="check"><input v-model="header" type="checkbox" data-testid="table-header" > {{ t('First row is the header (it names the columns)') }}</label>
      <p v-if="!valid" class="warn" role="alert">{{ t('A table has 1 to {columns} columns and 1 to {rows} rows.', { columns: MAX_COLUMNS, rows: MAX_ROWS }) }}</p>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="!valid" data-testid="table-insert">{{ t('Insert') }}</button>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.form {
  display: grid;
  gap: 12px;
}
.sizes {
  display: flex;
  gap: 12px;
}
.field {
  flex: 1;
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
.warn {
  margin: 0;
  color: var(--danger, #b3261e);
  font-size: 12.5px;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
