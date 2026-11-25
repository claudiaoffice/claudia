<script setup lang="ts">
// A filter's members (E6.30, D624): which members of the field stay in the pivot. Listed from the source itself
// (`pivot_members`); "(blank)" is the empty one. A field with more different members than can be listed is not offered
// here yet, and the filter keeps them all.
import { computed, onMounted, ref } from 'vue'
import { useI18n } from '~/lib/i18n'
import { memberLabel, setKeep, type Member, type PivotInfo } from '~/lib/pivots'
import type { Session } from '~/lib/session'

const { t } = useI18n()
const props = defineProps<{ session: Session; pivot: PivotInfo; field: string; sheet: string; readonly: boolean }>()
const emit = defineEmits<{ close: [] }>()

const members = ref<Member[] | null>(null)
const more = ref(false)
const kept = ref<Set<Member>>(new Set())
const busy = ref(false)
const filter = computed(() => props.pivot.definition.filters.find((f) => f.field.toLowerCase() === props.field.toLowerCase()) ?? null)
const loading = computed(() => members.value === null)

onMounted(async () => {
  const found = await props.session.pivotMembers(props.pivot.definition.source, props.field, props.sheet)
  if (!found) {
    members.value = []
    return
  }
  members.value = found.members
  more.value = found.more
  kept.value = new Set(filter.value?.keep ?? found.members)
})

const all = computed(() => members.value !== null && members.value.every((m) => kept.value.has(m)))
function toggle(member: Member) {
  const next = new Set(kept.value)
  if (next.has(member)) next.delete(member)
  else next.add(member)
  kept.value = next
}
function setAll(on: boolean) {
  kept.value = new Set(on ? members.value : [])
}

async function apply() {
  if (busy.value || members.value === null || kept.value.size === 0) return
  busy.value = true
  const keep = all.value ? null : members.value.filter((m) => kept.value.has(m))
  const done = await props.session.updatePivot(props.pivot.name, setKeep(props.pivot.definition, props.field, keep))
  busy.value = false
  if (done) emit('close')
}
</script>

<template>
  <Modal :title="t('Members of {field}', { field })" :width="420" @close="emit('close')">
    <form class="members" data-testid="pivot-members" @submit.prevent="apply">
      <div role="status">
        <p v-if="loading" class="muted">{{ t('Looking…') }}</p>
      </div>
      <p v-if="!loading && more" class="muted" role="note">{{ t('{field} has more different members than can be listed here, so the filter keeps them all.', { field }) }}</p>
      <template v-else-if="!loading && members && members.length">
        <div class="all">
          <button type="button" class="link" @click="setAll(true)">{{ t('Select all') }}</button>
          <button type="button" class="link" @click="setAll(false)">{{ t('Select none') }}</button>
        </div>
        <ul role="group" :aria-label="t('Members of {field}', { field })">
          <li v-for="(m, i) in members" :key="i">
            <label><input type="checkbox" :checked="kept.has(m)" :disabled="readonly" @change="toggle(m)" > {{ memberLabel(m, pivot.labels) }}</label>
          </li>
        </ul>
        <p v-if="kept.size === 0" class="problem" role="alert">{{ t('Keep at least one member.') }}</p>
      </template>
      <p v-else-if="!loading" class="muted">{{ t('The field has no members.') }}</p>
      <div class="buttons">
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
        <button class="btn primary" type="submit" :disabled="readonly || busy || more || members === null || kept.size === 0">{{ t('Apply') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.members {
  display: grid;
  gap: 12px;
}
.muted,
.problem {
  margin: 0;
  font-size: 13px;
  color: var(--muted);
}
.problem {
  color: var(--danger-dark, var(--rose));
}
ul {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 280px;
  overflow-y: auto;
  display: grid;
  gap: 4px;
}
.all {
  display: flex;
  gap: 12px;
}
.link {
  border: 0;
  background: none;
  padding: 0;
  font-size: 13px;
  cursor: pointer;
  color: var(--app-text, var(--iris));
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
