<script setup lang="ts">
// File ▸ Manage ▸ Leave document… (D141). Confirms it is really you, with your own current password, before
// removing you — not the password that opened this connection a moment ago, in case somebody is still at your desk.
import { ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ session: BaseSession }>()
const emit = defineEmits<{ close: []; left: [] }>()

const password = ref('')
const busy = ref(false)

async function leave() {
  busy.value = true
  if (await props.session.leave(password.value)) emit('left')
  busy.value = false
}
</script>

<template>
  <Modal :title="t('Leave this document')" @close="emit('close')">
    <TransText tag="p" class="lead" :text="t('You will no longer be able to open {doc}, unless somebody adds you again. Confirm it is you with your own current password.')">
      <template #doc><b>{{ session.state.doc }}</b></template>
    </TransText>
    <form class="form" @submit.prevent="leave">
      <label class="field">{{ t('Your password') }}<input v-model="password" type="password" autocomplete="current-password" ></label>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="busy || !password">{{ t('Leave document') }}</button>
        <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.lead {
  margin: 0;
  color: var(--muted);
}
.form {
  display: grid;
  gap: 12px;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
