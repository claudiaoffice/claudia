<script setup lang="ts">
import { ref } from 'vue'
import type { BaseSession } from '~/lib/base-session'

const props = defineProps<{ session: BaseSession }>()
const emit = defineEmits<{ close: [] }>()

const name = ref('')
const password = ref('')
const role = ref<'editor' | 'viewer'>('editor')
const added = ref<string[]>([])
const busy = ref(false)

async function add() {
  busy.value = true
  const who = name.value.trim()
  if (await props.session.addUser(who, password.value, role.value)) {
    added.value.push(`${who} (${role.value})`)
    name.value = ''
    password.value = ''
  }
  busy.value = false
}
</script>

<template>
  <Modal title="Share this document" @close="emit('close')">
    <p class="lead">
      Give a colleague a name and a password for <b>{{ session.state.doc }}</b>. They open the document with them, like you did. Tell them the
      password yourself: the server never shows it again.
    </p>
    <form class="form" @submit.prevent="add">
      <label class="field">Name<input v-model="name" autocomplete="off" /></label>
      <label class="field">Password (at least 8 characters)<input v-model="password" type="text" autocomplete="off" /></label>
      <label class="field">
        May<select v-model="role"><option value="editor">edit</option><option value="viewer">only look</option></select>
      </label>
      <div class="buttons">
        <button class="btn primary" type="submit" :disabled="busy || !name.trim() || password.length < 8">Add person</button>
        <button class="btn" type="button" @click="emit('close')">Done</button>
      </div>
    </form>
    <ul v-if="added.length" class="added" aria-label="people added just now">
      <li v-for="a in added" :key="a">✓ {{ a }}</li>
    </ul>
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
.added {
  margin: 0;
  padding: 0;
  list-style: none;
  color: var(--teal);
  font-weight: 500;
}
</style>
