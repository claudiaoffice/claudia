<script setup lang="ts">
// Delete Pivot Table… (E6.30, D624, mock 3): asks first. The cells it filled go empty, its name and definition are gone,
// and the source is untouched; one undo brings it back.
import { ref } from 'vue'
import { useI18n } from '~/lib/i18n'
import type { Session } from '~/lib/session'

const { t } = useI18n()
const props = defineProps<{ session: Session; name: string }>()
const emit = defineEmits<{ close: []; deleted: [] }>()
const busy = ref(false)

async function remove() {
  if (busy.value) return
  busy.value = true
  const done = await props.session.deletePivot(props.name)
  busy.value = false
  if (done) {
    emit('deleted')
    emit('close')
  }
}
</script>

<template>
  <Modal :title="t('Delete pivot table')" @close="emit('close')">
    <form class="ask" data-testid="pivot-delete" @submit.prevent="remove">
      <p>{{ t('Delete the pivot table {name}? Its cells go empty and the table it reads is not touched. You can undo it.', { name }) }}</p>
      <div class="buttons">
        <button class="btn" type="button" autofocus @click="emit('close')">{{ t('Cancel') }}</button>
        <button class="btn danger" type="submit" :disabled="busy">{{ t('Delete') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.ask {
  display: grid;
  gap: 16px;
}
.ask p {
  margin: 0;
  font-size: 14px;
}
.buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
