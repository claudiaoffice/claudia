<script setup lang="ts">
// Tools ▸ Names… (E6.5, mock 3): every name of the workbook — named ranges, tables and the results of SQL() cells — to
// go to, rename or take away. Renaming rewrites the formulas that use the name (one change in the history, so one
// undo); taking one away leaves its cells, and the formulas that used it show #NAME?.
import { computed, ref } from 'vue'
import { nameProblem, purposeLabel, referLabel, type NameInfo } from '~/lib/names'
import type { Session } from '~/lib/session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ session: Session; readonly: boolean; scopeName: (scope: string | null) => string }>()
const emit = defineEmits<{ close: []; goto: [name: NameInfo]; editQuery: [name: NameInfo] }>()

const filter = ref('')
const rows = computed(() => {
  const wanted = filter.value.trim().toLowerCase()
  return props.session.state.names.filter((n) => !wanted || n.name.toLowerCase().includes(wanted) || (n.a1 ?? '').toLowerCase().includes(wanted))
})

const renaming = ref<{ name: NameInfo; text: string } | null>(null)
const renameProblem = computed(() => (renaming.value ? nameProblem(renaming.value.text.trim()) : null))
const confirming = ref<NameInfo | null>(null)
const busy = ref(false)

const same = (a: NameInfo, b: NameInfo) => a.name === b.name && a.scope === b.scope

function startRename(name: NameInfo) {
  confirming.value = null
  renaming.value = { name, text: name.name }
}
async function finishRename() {
  const r = renaming.value
  if (!r || renameProblem.value) return
  const next = r.text.trim()
  if (next === r.name.name) {
    renaming.value = null
    return
  }
  busy.value = true
  const done = await props.session.renameName(r.name.name, next, r.name.scope)
  busy.value = false
  if (done) renaming.value = null
}
async function remove(name: NameInfo) {
  busy.value = true
  const done = await props.session.removeName(name.name, name.scope)
  busy.value = false
  if (done) confirming.value = null
}
</script>

<template>
  <Modal :title="t('Names')" :width="780" @close="emit('close')">
    <div class="names" data-testid="names-dialog">
      <input v-model="filter" class="filter" type="search" :placeholder="t('Find a name or cells')" :aria-label="t('find a name')" autocomplete="off" >
      <p v-if="!session.state.names.length" class="empty">
        <TransText :text="t('No names yet. Select cells, type a word in the box left of the formula bar and press Enter — then {formula} and {query} work.')">
          <template #formula><span class="mono">=SUM(Sales[Amount])</span></template>
          <template #query><span class="mono">SELECT … FROM Sales</span></template>
        </TransText>
      </p>
      <p v-else-if="!rows.length" class="empty">{{ t('Nothing is called like that.') }}</p>
      <table v-else>
        <thead>
          <tr><th>{{ t('Name') }}</th><th>{{ t('Works on') }}</th><th>{{ t('Refers to') }}</th><th>{{ t('Rows') }}</th><th>{{ t('For') }}</th><th /></tr>
        </thead>
        <tbody>
          <tr v-for="n in rows" :key="`${n.scope}:${n.name}`" :data-name="n.name">
            <td class="mono strong">
              <form v-if="renaming && same(renaming.name, n)" class="inline" @submit.prevent="finishRename">
                <input v-model="renaming.text" class="mono" :aria-label="t('new name')" autofocus autocomplete="off" spellcheck="false" @keydown.esc.stop="renaming = null" >
                <span v-if="renameProblem" class="problem">{{ renameProblem }}</span>
              </form>
              <template v-else>{{ n.name }} <span v-if="n.kind === 'result'" class="badge">{{ t('SQL') }}</span></template>
            </td>
            <td>{{ scopeName(n.scope) }}</td>
            <td class="mono">{{ referLabel(n) }}</td>
            <td class="num">{{ n.header || n.kind === 'result' ? n.rows : '—' }}</td>
            <td>{{ purposeLabel(n.purpose) }}</td>
            <td class="actions">
              <template v-if="confirming && same(confirming, n)">
                <span class="ask">{{ t('Take {name} away?', { name: n.name }) }}</span>
                <button type="button" class="link danger" :disabled="busy" @click="remove(n)">{{ t('Take away') }}</button>
                <button type="button" class="link" @click="confirming = null">{{ t('Keep') }}</button>
              </template>
              <template v-else-if="renaming && same(renaming.name, n)">
                <button type="button" class="link" :disabled="busy || renameProblem !== null" @click="finishRename">{{ t('Rename') }}</button>
                <button type="button" class="link" @click="renaming = null">{{ t('Cancel') }}</button>
              </template>
              <template v-else>
                <button type="button" class="link" :disabled="n.region === null" @click="emit('goto', n); emit('close')">{{ t('Go to') }}</button>
                <button v-if="n.kind === 'result'" type="button" class="link" @click="emit('editQuery', n); emit('close')">{{ t('Edit query…') }}</button>
                <button type="button" class="link" :disabled="readonly" @click="startRename(n)">{{ t('Rename') }}</button>
                <button type="button" class="link danger" :disabled="readonly" @click="confirming = n">{{ t('Delete') }}</button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="buttons"><button class="btn" type="button" @click="emit('close')">{{ t('Close') }}</button></div>
    </div>
  </Modal>
</template>

<style scoped>
.names {
  display: grid;
  gap: 12px;
  min-width: 0;
}
.filter {
  width: 100%;
}
.empty {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th {
  text-align: left;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  padding: 4px 8px;
  border-bottom: 1px solid var(--line);
}
td {
  padding: 7px 8px;
  border-bottom: 1px solid var(--line);
  vertical-align: middle;
}
.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.strong {
  font-weight: 600;
}
.badge {
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--purpose-result);
  color: var(--text);
  font: 500 10px var(--font-ui);
}
.actions {
  text-align: right;
  white-space: nowrap;
}
.actions .ask {
  margin-right: 8px;
  color: var(--muted);
}
.link {
  border: 0;
  background: none;
  padding: 2px 6px;
  color: var(--app-text);
  font-size: 13px;
  cursor: pointer;
}
.link:hover:not(:disabled) {
  text-decoration: underline;
}
.link:disabled {
  color: var(--muted);
  cursor: default;
}
.link.danger {
  color: var(--danger-dark, var(--rose));
}
.inline {
  display: grid;
  gap: 2px;
}
.problem {
  color: var(--danger-dark, var(--rose));
  font-size: 11px;
  font-weight: 400;
}
.buttons {
  display: flex;
  justify-content: flex-end;
}
</style>
