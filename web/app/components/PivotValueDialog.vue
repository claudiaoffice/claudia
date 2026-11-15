<script setup lang="ts">
// Value field settings (E6.30, D624, mock 3): the name a value has in the pivot's header and how its values are put
// together — sum, count, average, min or max. (The number format of the mock and "show values as" come later: a pivot's
// values do not carry a format of their own yet, D626.)
import { computed, onMounted, ref } from 'vue'
import { useI18n } from '~/lib/i18n'
import { AGGREGATIONS, setValue, valueTitle, type Aggregation, type PivotInfo } from '~/lib/pivots'
import type { Session } from '~/lib/session'

const { t } = useI18n()
const props = defineProps<{ session: Session; pivot: PivotInfo; index: number }>()
const emit = defineEmits<{ close: [] }>()

const value = computed(() => props.pivot.definition.values[props.index] ?? null)
const aggregation = ref<Aggregation>(value.value?.aggregation ?? 'sum')
const name = ref(value.value?.name || (value.value ? valueTitle({ ...value.value, aggregation: aggregation.value, name: '' }, props.pivot.labels) : ''))
const edited = ref(false) // a name the person has written stays as it is when she picks another way to summarize
const busy = ref(false)
const field = ref<HTMLInputElement | null>(null)
const column = computed(() => props.session.state.names.find((n) => n.scope === null && n.name.toLowerCase() === props.pivot.definition.source.toLowerCase())?.columns.find((c) => c.name.toLowerCase() === value.value?.field.toLowerCase()))

onMounted(() => {
  edited.value = value.value?.name !== ''
  field.value?.select()
})

/** The title the header would have without a name of its own. */
const standard = (kind: Aggregation) => (value.value ? valueTitle({ ...value.value, aggregation: kind, name: '' }, props.pivot.labels) : '')

function pick(kind: Aggregation) {
  aggregation.value = kind
  if (!edited.value) name.value = standard(kind)
}

async function apply() {
  if (!value.value || busy.value) return
  busy.value = true
  const typed = name.value.trim()
  // the name the pivot would give anyway is no name of its own: the title then follows the labels
  const own = typed === '' || typed === standard(aggregation.value) ? '' : typed
  const done = await props.session.updatePivot(props.pivot.name, setValue(props.pivot.definition, props.index, { aggregation: aggregation.value, name: own }))
  busy.value = false
  if (done) emit('close')
}
</script>

<template>
  <Modal :title="t('Value field settings')" :width="560" @close="emit('close')">
    <form v-if="value" class="settings" data-testid="pivot-value" @submit.prevent="apply">
      <p class="source">
        <span class="muted">{{ t('Source field') }}</span><br>
        <strong class="mono">{{ value.field }}</strong>
        <span class="muted kind">{{ column?.type ?? '' }} · {{ t('in {source}', { source: pivot.definition.source }) }}</span>
      </p>
      <label class="field">
        <span>{{ t('Name in the pivot table') }}</span>
        <input ref="field" v-model="name" autocomplete="off" @input="edited = true" >
      </label>
      <fieldset>
        <legend>{{ t('Summarize values by') }}</legend>
        <label v-for="a in AGGREGATIONS" :key="a.value" class="choice">
          <input type="radio" name="pivot-aggregation" :value="a.value" :checked="aggregation === a.value" @change="pick(a.value)" >
          <strong>{{ a.label }}</strong>
          <span class="muted">{{ a.hint }}</span>
        </label>
      </fieldset>
      <div class="buttons">
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
        <button class="btn primary" type="submit" :disabled="busy">{{ t('Apply') }}</button>
      </div>
    </form>
    <p v-else class="muted">{{ t('This value is not in the pivot table (any more).') }}</p>
  </Modal>
</template>

<style scoped>
.settings {
  display: grid;
  gap: 16px;
}
.source {
  margin: 0;
  font-size: 13px;
}
.muted {
  color: var(--muted);
  font-size: 13px;
}
.kind {
  margin-left: 12px;
}
.mono {
  font-family: var(--font-mono, ui-monospace, monospace);
}
.field {
  display: grid;
  gap: 4px;
  font-size: 13px;
  color: var(--muted);
}
.field input {
  padding: 8px 10px;
  border: 1px solid var(--line-field);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  font-size: 14px;
}
fieldset {
  border: 0;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}
legend {
  padding: 0;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--muted);
}
.choice {
  display: grid;
  grid-template-columns: 22px 90px 1fr;
  align-items: center;
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  border-top: 1px solid var(--line);
  padding-top: 14px;
}
</style>
