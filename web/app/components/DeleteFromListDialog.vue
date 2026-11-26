<script setup lang="ts">
// Delete on the front page (D1608, UX-98): a document is deleted from the server from the list of documents, not from
// its own menus. Owners only, confirmed with the owner's name and own current password; the server checks both, and
// says why not to anybody else. There is no way back: no recycle bin, no undo.
import { ref } from 'vue'
import { useI18n } from '~/lib/i18n'

const { t } = useI18n()

const props = defineProps<{ id: string; user: string; busy: boolean; error: string }>()
const emit = defineEmits<{ close: []; delete: [values: { user: string; password: string }] }>()

const user = ref(props.user)
const password = ref('')

function submit() {
  if (props.busy || !password.value || !user.value.trim()) return
  emit('delete', { user: user.value.trim(), password: password.value })
}
</script>

<template>
  <Modal :title="t('Delete {id} from the server', { id })" @close="emit('close')">
    <form class="form" data-testid="delete-from-list" @submit.prevent="submit">
      <TransText tag="p" class="lead" :text="t('This removes {doc} from the server for good — its content, its history and its chat, and everybody\'s access to it. There is no way back: no recycle bin, no undo. Make sure everybody who needs something from it has it first (File ▸ Download).')">
        <template #doc><b>{{ id }}</b></template>
      </TransText>
      <div class="two">
        <label class="field">{{ t('Your name') }}<input v-model="user" name="delete-user" autocomplete="username" required ></label>
        <label class="field">{{ t('Your password, to confirm') }}<PasswordInput v-model="password" name="delete-password" autocomplete="current-password" required /></label>
      </div>
      <p class="hint">{{ t('Only an owner of the document can delete it.') }}</p>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="buttons">
        <button class="btn danger" type="submit" :disabled="busy || !password || !user.trim()">{{ t('Delete for good') }}</button>
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
.lead {
  margin: 0;
  color: var(--ink);
}
.two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.hint {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
.error {
  margin: 0;
  color: var(--rose);
}
.buttons {
  display: flex;
  gap: 10px;
}
.btn.danger {
  background: var(--rose);
  color: #fff;
  border-color: var(--rose);
}
</style>
