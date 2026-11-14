<script setup lang="ts">
// File ▸ Manage ▸ Change Password… (sheet 12, D448): a new password for this document, the person's own. Everybody in
// a document has their own name and password (D35), so the others keep theirs. The current password confirms it is
// really this person, not somebody at their desk. No "repeat the new password": the eye shows what was typed.
import { ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ session: BaseSession }>()
const emit = defineEmits<{ close: []; changed: [] }>()

const current = ref('')
const fresh = ref('')
const busy = ref(false)
const problem = ref('')

async function change() {
  busy.value = true
  problem.value = ''
  const answer = await props.session.changePassword(current.value, fresh.value)
  busy.value = false
  if (answer === true) emit('changed')
  else problem.value = answer
}
</script>

<template>
  <Modal :title="t('Change your password')" @close="emit('close')">
    <TransText tag="p" class="lead" :text="t('For {doc}, as {user}. Everybody else keeps their own password.')">
      <template #doc><b>{{ session.state.doc }}</b></template>
      <template #user><b>{{ session.state.me.user }}</b></template>
    </TransText>
    <form class="form" @submit.prevent="change">
      <label class="field">{{ t('Current password') }}<PasswordInput v-model="current" name="current-password" autocomplete="current-password" autofocus /></label>
      <label class="field">
        {{ t('New password') }}<PasswordInput v-model="fresh" name="new-password" autocomplete="new-password" aria-describedby="new-password-rule" />
        <span id="new-password-rule" class="rule">{{ t('At least 8 characters, with a capital letter, a small letter and a digit.') }}</span>
      </label>
      <p v-if="problem" class="error" role="alert">{{ problem }}</p>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="busy || !current || fresh.length < 8">{{ t('Change password') }}</button>
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
.rule {
  font-size: 12px;
  color: var(--muted);
}
.error {
  margin: 0;
  color: var(--rose);
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
