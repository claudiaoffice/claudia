<script setup lang="ts">
// File ▸ Manage ▸ Accept ownership… (D141): the other half of Assign new owner…. Whoever was asked to take over a
// document comes here and confirms it is them with their own password; there is no notification yet (the decision
// log says so) — the two people tell each other, the same way they would hand over a key.
import { ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ session: BaseSession }>()
const emit = defineEmits<{ close: [] }>()

const password = ref('')
const busy = ref(false)
const accepted = ref(false)

async function accept() {
  busy.value = true
  if (await props.session.acceptOwner(password.value)) accepted.value = true
  busy.value = false
}
</script>

<template>
  <Modal :title="t('Accept ownership')" @close="emit('close')">
    <TransText v-if="accepted" tag="p" class="lead" :text="t('You are now the owner of {doc}.')"><template #doc><b>{{ session.state.doc }}</b></template></TransText>
    <template v-else>
      <TransText tag="p" class="lead" :text="t('If somebody asked you to take over {doc}, confirm it is you with your own current password.')"><template #doc><b>{{ session.state.doc }}</b></template></TransText>
      <form class="form" @submit.prevent="accept">
        <label class="field">{{ t('Your password') }}<input v-model="password" type="password" autocomplete="current-password" ></label>
        <div class="buttons">
          <button class="btn primary" type="submit" :disabled="busy || !password">{{ t('Accept') }}</button>
          <button class="btn" type="button" @click="emit('close')">{{ t('Cancel') }}</button>
        </div>
      </form>
    </template>
    <div v-if="accepted" class="buttons">
      <button class="btn primary" type="button" @click="emit('close')">{{ t('Done') }}</button>
    </div>
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
