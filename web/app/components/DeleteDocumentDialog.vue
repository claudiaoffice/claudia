<script setup lang="ts">
// File ▸ Manage ▸ Delete from server… (D141). Owners only, confirmed with the owner's own current password. There
// is no way back from this: no recycle bin, no undo.
import { ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'

const props = defineProps<{ session: BaseSession }>()
const emit = defineEmits<{ close: []; deleted: [] }>()

const password = ref('')
const busy = ref(false)

async function remove() {
  busy.value = true
  if (await props.session.deleteDocument(password.value)) emit('deleted')
  busy.value = false
}
</script>

<template>
  <Modal title="Delete this document" @close="emit('close')">
    <p class="lead warning">
      This removes <b>{{ session.state.doc }}</b> from the server for good — its content, its history and its chat, and everybody's access to it. There is
      no way back: no recycle bin, no undo. Make sure everybody who needs something from it has it first (File ▸ Download).
    </p>
    <form class="form" @submit.prevent="remove">
      <label class="field">Your password, to confirm<input v-model="password" type="password" autocomplete="current-password" /></label>
      <div class="buttons">
        <button class="btn danger" type="submit" :disabled="busy || !password">Delete for good</button>
        <button class="btn" type="button" @click="emit('close')">Cancel</button>
      </div>
    </form>
  </Modal>
</template>

<style scoped>
.lead {
  margin: 0;
  color: var(--muted);
}
.lead.warning {
  color: var(--ink);
}
.form {
  display: grid;
  gap: 12px;
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
