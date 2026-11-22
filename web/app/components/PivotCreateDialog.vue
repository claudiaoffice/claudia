<script setup lang="ts">
// Tools ▸ Pivot Table… (E6.30, D624, mock 2): a name, the table or range to analyse — the one the cursor is in is
// preselected, as in Excel — and a place: a sheet of its own, or a cell of this one. Create gives an empty pivot; the
// field panel opens on it. The source is a name, never loose cells, so the pivot grows with it (D620).
import { computed, onMounted, ref } from 'vue'
import { useI18n } from '~/lib/i18n'
import {
  emptyDefinition,
  newSheetName,
  parsePlace,
  pivotLabels,
  pivotNameProblem,
  preselected,
  sourceChoices,
  suggestName,
} from '~/lib/pivots'
import type { Session } from '~/lib/session'
import { cellLabel } from '~/lib/cells'

const { t } = useI18n()
const props = defineProps<{ session: Session; sheetName: string; cursor: { row: number; col: number } }>()
const emit = defineEmits<{ close: []; created: [name: string, sheet: string] }>()

const state = props.session.state
const choices = computed(() => sourceChoices(state.names, state.pivots))
const taken = computed(() => [...state.names.map((n) => n.name), ...state.pivots.map((p) => p.name)])
const first = preselected(choices.value, state.activeSheet, props.cursor.row, props.cursor.col)
const source = ref(first?.name ?? '')
const insideTable = first !== null && first.region?.sheet === state.activeSheet && props.cursor.row >= first.region.row0 && props.cursor.row <= first.region.row1 && props.cursor.col >= first.region.col0 && props.cursor.col <= first.region.col1
const name = ref(suggestName(first?.name ?? '', taken.value))
const where = ref<'sheet' | 'cell'>('sheet')
const cell = ref(`${props.sheetName}!${cellLabel(props.cursor.row, props.cursor.col)}`)
const busy = ref(false)
const field = ref<HTMLInputElement | null>(null)

onMounted(() => field.value?.select())

const chosen = computed(() => choices.value.find((n) => n.name === source.value) ?? null)
const nameProblem = computed(() => pivotNameProblem(name.value.trim(), taken.value))
const place = computed(() => (where.value === 'cell' ? parsePlace(cell.value, props.sheetName) : null))
const placeProblem = computed(() => (where.value === 'cell' && place.value === null ? t('Write a cell of this sheet, like {example}.', { example: `${props.sheetName}!H11` }) : null))
const ready = computed(() => !busy.value && chosen.value !== null && nameProblem.value === null && placeProblem.value === null)

const describe = (n: { a1: string | null; rows: number; columns: unknown[] }) =>
  t('{range} · {rows} · {fields}', {
    range: n.a1 ?? '',
    rows: n.rows === 1 ? t('{count} row', { count: n.rows }) : t('{count} rows', { count: n.rows }),
    fields: n.columns.length === 1 ? t('{count} field', { count: n.columns.length }) : t('{count} fields', { count: n.columns.length }),
  })

async function create() {
  if (!ready.value || !chosen.value) return
  busy.value = true
  const text = name.value.trim()
  const done = await props.session.definePivot(
    text,
    emptyDefinition(chosen.value.name),
    pivotLabels(),
    where.value === 'sheet'
      ? { newSheet: newSheetName(t('Pivot'), [...state.tabs.map((s) => s.name), ...taken.value, text]) }
      : { sheet: state.activeSheet, row: place.value!.row, col: place.value!.col },
  )
  busy.value = false
  if (done !== null) {
    emit('created', text, done)
    emit('close')
  }
}
</script>

<template>
  <Modal :title="t('New pivot table')" :width="640" @close="emit('close')">
    <form class="create" data-testid="pivot-create" @submit.prevent="create">
      <p v-if="!choices.length" class="empty" role="status">
        {{ t('There is no table to analyse yet. Select cells with a header row, type a word in the box left of the formula bar and press Enter — then it can be a pivot table’s source.') }}
      </p>
      <template v-else>
        <label class="field">
          <span>{{ t('Name') }}</span>
          <span class="row">
            <input ref="field" v-model="name" class="mono" autocomplete="off" spellcheck="false" :aria-invalid="nameProblem !== null" :aria-describedby="nameProblem ? 'pivot-name-problem' : undefined" >
            <span class="note">{{ t('The result is a name too.') }}</span>
          </span>
          <span v-if="nameProblem" id="pivot-name-problem" class="problem" role="alert">{{ nameProblem }}</span>
        </label>
        <label class="field">
          <span>{{ t('Table or range to analyse') }}</span>
          <select v-model="source" aria-describedby="pivot-source-help">
            <option v-for="n in choices" :key="n.name" :value="n.name">{{ n.name }} — {{ describe(n) }}</option>
          </select>
          <span id="pivot-source-help" class="note">
            {{ insideTable ? t('The cursor is inside the table {name}, so it is preselected.', { name: source }) : '' }}
            {{ t('Tables, named ranges and query results are offered; the pivot follows them when rows are added.') }}
          </span>
        </label>
        <fieldset class="place">
          <legend>{{ t('Place it') }}</legend>
          <label class="check"><input v-model="where" type="radio" value="sheet" name="pivot-place" > {{ t('On a new sheet') }}</label>
          <label class="check">
            <input v-model="where" type="radio" value="cell" name="pivot-place" > {{ t('On this sheet at') }}
            <input v-model="cell" class="mono cell" :disabled="where !== 'cell'" :aria-label="t('first cell of the pivot table')" autocomplete="off" spellcheck="false" @focus="where = 'cell'" >
          </label>
          <span v-if="placeProblem" class="problem" role="alert">{{ placeProblem }}</span>
          <span v-else-if="where === 'cell'" class="note">{{ t('The result can’t land on cells that hold something.') }}</span>
        </fieldset>
      </template>
      <div class="buttons">
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
        <button class="btn primary" type="submit" :disabled="!ready">{{ t('Create') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.create {
  display: grid;
  gap: 16px;
  min-width: 0;
}
.field {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--muted);
}
.field input,
.field select {
  padding: 8px 10px;
  border: 1px solid var(--line-field);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: 14px;
  min-width: 0;
}
.row {
  display: flex;
  align-items: center;
  gap: 14px;
}
.row input {
  flex: 0 1 260px;
}
.mono {
  font-family: var(--font-mono, ui-monospace, monospace);
}
.note {
  font-size: 12px;
  color: var(--muted);
}
.problem {
  font-size: 12px;
  color: var(--danger-dark, var(--rose));
}
.empty {
  margin: 0;
  font-size: 13px;
  color: var(--muted);
}
.place {
  display: grid;
  gap: 8px;
  border: 0;
  padding: 0;
  margin: 0;
  font-size: 13px;
}
.place legend {
  padding: 0;
  margin-bottom: 6px;
  color: var(--muted);
}
.check {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text);
  font-size: 14px;
}
.cell {
  width: 150px;
  padding: 6px 8px;
  border: 1px solid var(--line-field);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  border-top: 1px solid var(--line);
  padding-top: 14px;
}
</style>
