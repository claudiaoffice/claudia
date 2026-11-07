<script setup lang="ts">
// File ▸ Manage ▸ Leave document… (D135). Confirms it is really you, with your own current password, before
// removing you — not the password that opened this connection a moment ago, in case somebody is still at your desk.
import { ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'

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
  <Modal title="Leave this document" @close="emit('close')">
    <p class="lead">
      You will no longer be able to open <b>{{ session.state.doc }}</b>, unless somebody adds you again. Confirm it is you with your own current
      password.
    </p>
    <form class="form" @submit.prevent="leave">
      <label class="field">Your password<input v-model="password" type="password" autocomplete="current-password" /></label>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="busy || !password">Leave document</button>
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
.form {
  display: grid;
  gap: 12px;
}
.buttons {
  display: flex;
  gap: 10px;
}
</style>
