<script setup lang="ts">
// Show Pivot Table as SQL… (E6.30, D624, mock 4): what the pivot asks of its source, read only, with Copy SQL and
// "Convert to SQL query…", which turns the pivot into a `SQL()` result of the same name in one undo step. A pivot is a
// special query, and this is where a person sees that (D620).
import { computed, onMounted, ref } from 'vue'
import { useI18n } from '~/lib/i18n'
import type { Session } from '~/lib/session'

const { t } = useI18n()
const props = defineProps<{ session: Session; name: string; readonly: boolean }>()
const emit = defineEmits<{ close: [] }>()

const sql = ref<string | null>(null)
const busy = ref(false)
const copied = ref(false)
const lines = computed(() => (sql.value ?? '').split('\n'))

onMounted(async () => {
  sql.value = await props.session.pivotSql(props.name)
  if (sql.value === null) emit('close') // the session has told the person why
})

async function copy() {
  if (sql.value === null) return
  try {
    await navigator.clipboard.writeText(sql.value)
    copied.value = true
  } catch {
    props.session.notice(t('The query could not be copied. Select it and copy it with the keyboard.'), 'warning')
  }
}

async function convert() {
  if (busy.value) return
  busy.value = true
  const done = await props.session.pivotToSql(props.name)
  busy.value = false
  if (done) emit('close')
}
</script>

<template>
  <Modal :title="t('Pivot table as SQL')" :width="940" @close="emit('close')">
    <div class="sql" data-testid="pivot-sql">
      <p class="who mono">{{ name }}</p>
      <div class="columns">
        <div class="code" role="group" :aria-label="t('The query, read only')" tabindex="0">
          <ol>
            <li v-for="(line, i) in lines" :key="i"><code>{{ line }}</code></li>
          </ol>
        </div>
        <aside class="notes">
          <div class="card">
            <h3>{{ t('This query') }}</h3>
            <ul>
              <li>{{ t('Made from the fields in the panel.') }}</li>
              <li>{{ t('A column for each member of the column field; a new member adds a column.') }}</li>
              <li>{{ t('Runs on the same read-only engine as SQL().') }}</li>
            </ul>
          </div>
          <div class="card">
            <h3>{{ t('Want to change it by hand?') }}</h3>
            <p>{{ t('Convert it to a SQL query. The pivot table becomes a SQL() result of the same name, with one header row. Undo brings the pivot table back.') }}</p>
          </div>
        </aside>
      </div>
      <p class="muted">{{ t('Read-only. It is what the pivot table asks {source}; change the fields and it changes.', { source: session.state.pivots.find((p) => p.name === name)?.definition.source ?? '' }) }}</p>
      <div class="buttons">
        <button class="btn" type="button" :disabled="sql === null" @click="copy">{{ copied ? t('Copied') : t('Copy SQL') }}</button>
        <span class="grow" />
        <button class="btn" type="button" :disabled="readonly || busy || sql === null" @click="convert">{{ t('Convert to SQL query…') }}</button>
        <button class="btn primary" type="button" @click="emit('close')">{{ t('Close') }}</button>
      </div>
      <span class="sr-only" role="status" aria-live="polite">{{ copied ? t('Copied') : '' }}</span>
    </div>
  </Modal>
</template>

<style scoped>
.sql {
  display: grid;
  gap: 12px;
  min-width: 0;
}
.who {
  margin: 0;
  color: var(--muted);
}
.mono,
code {
  font-family: var(--font-mono, ui-monospace, monospace);
}
.columns {
  display: grid;
  grid-template-columns: minmax(0, 1.9fr) minmax(0, 1fr);
  gap: 16px;
}
.code {
  max-height: 380px;
  overflow: auto;
  border: 1px solid var(--line-field);
  border-radius: 10px;
  background: color-mix(in srgb, var(--mist, #f4f1fa) 40%, var(--surface));
  padding: 10px 0;
  font-size: 12.5px;
}
.code ol {
  margin: 0;
  padding: 0;
  list-style: none;
  counter-reset: line;
}
.code li {
  counter-increment: line;
  display: flex;
  gap: 14px;
  padding: 0 12px;
  white-space: pre;
}
.code li::before {
  content: counter(line);
  flex: none;
  width: 22px;
  text-align: right;
  color: var(--muted);
}
.notes {
  display: grid;
  gap: 12px;
  align-content: start;
}
.card {
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 10px;
  font-size: 13px;
}
.card h3 {
  margin: 0 0 6px;
  font-size: 14px;
}
.card ul {
  margin: 0;
  padding-left: 18px;
}
.card p {
  margin: 0;
  color: var(--muted);
}
.muted {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
}
.buttons {
  display: flex;
  align-items: center;
  gap: 10px;
  border-top: 1px solid var(--line);
  padding-top: 14px;
}
.grow {
  flex: 1;
}
</style>
